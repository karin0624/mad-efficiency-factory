"""Implement pipeline: Plan -> cc-sdd full execution (checkpoint-based).

Steps: Preflight -> Plan resolve -> Worktree -> A1(WHAT) -> A2(HOW) -> A3(Tasks)
       -> B(Impl) -> B2(Validate) -> Steering -> C(Commit) -> L4 -> D(Push+PR)
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..agent_runner import AgentStep
from ..config import OrchestratorConfig
from ..output_parser import has_l4_human_review
from ..pipeline import InterruptiblePipeline
from ..plan_resolver import resolve_plan
from ..preflight import (
    PreflightError,
    pull_base,
    push_base,
    run_preflight,
)
from ..session import PipelineSession
from ..state import (
    ImplementResumePoint as RP,
    find_spec_in_worktree,
    detect_implement_resume,
)
from ..worktree import create_or_reuse_worktree, remove_worktree


# Resume points that should run each step.
_RUN_A1 = {RP.A1_WHAT, RP.A1_WHAT_PHASE2}
_RUN_A2 = _RUN_A1 | {RP.A2_HOW_FULL, RP.A2_HOW_REVIEW_ONLY}
_RUN_A3 = _RUN_A2 | {RP.A3_TASKS, RP.A3_TASKS_APPROVAL}
_RUN_B = _RUN_A3 | {RP.B_IMPL}
_RUN_B2 = _RUN_B | {RP.B2_VALIDATE}


class ImplementPipeline(InterruptiblePipeline):
    """Full implement pipeline: plan -> spec -> impl -> validate -> PR."""

    _SEGMENTS = [
        "preflight", "setup", "A1", "A2", "A3", "B", "B2",
        "steering", "C", "L4", "D",
    ]

    def __init__(
        self,
        config: OrchestratorConfig,
        session: PipelineSession,
        session_dir: Path,
    ) -> None:
        super().__init__(config, session, session_dir)

    async def run_until_checkpoint(self) -> dict[str, Any]:
        cp = self.session.checkpoint

        # Handle resume from interactive/error checkpoints
        if cp:
            result = self._handle_resume(cp)
            if result is not None:
                return result
            cp = self.session.checkpoint

        # Build segment list
        segments = self._build_segments()

        # Find starting segment
        start_from = cp if cp in [n for n, _ in segments] else ""

        result = await self._run_segments(segments, start_from)
        if result is not None:
            return result

        return self._complete_pipeline()

    # ── Resume handling ──────────────────────────────────────────

    def _handle_resume(self, cp: str) -> dict[str, Any] | None:
        """Handle resume input. Returns response or None to continue."""
        user_input = self.session.checkpoint_data.get("user_input", "")

        if cp == "preflight_behind":
            if "pull" in user_input.lower():
                pull_base(self.config.project_root, self.session.base_branch)
            # Re-check ahead
            try:
                preflight = run_preflight(self.config.project_root)
            except PreflightError:
                self.session.checkpoint = "setup"
                self._save()
                return None
            if preflight.ahead > 0:
                return self.make_interaction(
                    checkpoint="preflight_ahead",
                    question=f"ローカルに {preflight.ahead} 件の未pushコミットがあります。pushしますか？",
                    options=["push して続行", "そのまま続行"],
                )
            self.session.checkpoint = "setup"
            self._save()
            return None

        if cp == "preflight_ahead":
            if "push" in user_input.lower():
                push_base(self.config.project_root, self.session.base_branch)
            self.session.checkpoint = "setup"
            self._save()
            return None

        if cp.startswith("step_") and (cp.endswith("_failed") or cp.endswith("_rejected")):
            # Extract step name: "step_A2_failed" -> "A2", "step_A2_rejected" -> "A2"
            parts = cp[5:]  # remove "step_"
            step_name = parts.rsplit("_", 1)[0]
            return self._handle_step_error_resume(step_name)

        if cp.startswith("step_") and cp.endswith("_skip_confirm"):
            step_name = cp[5:-13]  # "step_A2_skip_confirm" -> "A2"
            return self._handle_skip_confirm_resume(step_name, self._build_segments())

        if cp == "scene_review_failed":
            if "続行" in user_input or "continue" in user_input.lower():
                self.session.checkpoint = "D"
                self._save()
                return None
            if "修正" in user_input or "retry" in user_input.lower():
                self.session.checkpoint = "L4"
                self._save()
                return None
            return self.make_failed(error_message="ユーザーがパイプラインを中止しました。")

        return None

    # ── Segment builders ─────────────────────────────────────────

    def _build_segments(self) -> list[tuple[str, Any]]:
        return [
            ("preflight", self._seg_preflight),
            ("setup", self._seg_setup),
            ("A1", self._seg_A1),
            ("A2", self._seg_A2),
            ("A3", self._seg_A3),
            ("B", self._seg_B),
            ("B2", self._seg_B2),
            ("steering", self._seg_steering),
            ("C", self._seg_C),
            ("L4", self._seg_L4),
            ("D", self._seg_D),
        ]

    # ── Segments ─────────────────────────────────────────────────

    async def _seg_preflight(self) -> dict[str, Any] | None:
        try:
            preflight = run_preflight(self.config.project_root)
        except PreflightError as e:
            return self.make_failed(error_message=str(e))

        self.session.base_branch = preflight.base_branch
        self._save()

        if preflight.behind > 0:
            return self.make_interaction(
                checkpoint="preflight_behind",
                question=f"リモートに {preflight.behind} 件の新コミットがあります。pullしますか？",
                options=["pull して続行", "そのまま続行"],
            )

        if preflight.ahead > 0:
            return self.make_interaction(
                checkpoint="preflight_ahead",
                question=f"ローカルに {preflight.ahead} 件の未pushコミットがあります。pushしますか？",
                options=["push して続行", "そのまま続行"],
            )

        return None

    async def _seg_setup(self) -> dict[str, Any] | None:
        """Plan resolution + worktree setup + resume detection."""
        plan_argument = self.session.params.get("plan", "")
        plan_path, plan_name = resolve_plan(self.config, plan_argument)

        self.session.checkpoint_data["plan_path"] = str(plan_path)
        self.session.checkpoint_data["plan_name"] = plan_name

        wt_info = create_or_reuse_worktree(
            self.config, "feat", plan_name, self.session.base_branch
        )
        self.session.worktree_path = str(wt_info.path)
        self.session.branch_name = wt_info.branch

        resume_point = RP.A1_WHAT
        if not wt_info.created:
            spec = find_spec_in_worktree(wt_info.path)
            if spec:
                resume_point = detect_implement_resume(spec)
                self.session.feature_name = spec.feature_name

        self.session.checkpoint_data["resume_point"] = resume_point.value
        self._save()
        return None

    async def _seg_A1(self) -> dict[str, Any] | None:
        rp = RP(self.session.checkpoint_data.get("resume_point", RP.A1_WHAT.value))
        wt_path = Path(self.session.worktree_path)
        plan_path = self.session.checkpoint_data.get("plan_path", "")

        if rp not in _RUN_A1:
            self.skip_step("A1: spec-what", "opus", "resume")
            return None

        result = await self.run_agent_step(
            AgentStep(
                "A1: spec-what",
                "tools/orchestrator/prompts/impl-spec-what.md",
                "opus",
                {"WORKTREE_PATH": str(wt_path), "PLAN_FILE_ABSOLUTE_PATH": plan_path},
            ),
            cwd=wt_path,
        )

        if result.is_error:
            return self.make_error(
                checkpoint="step_A1_failed",
                error=result.error_message,
                step_output=result.output_text[-2000:],
            )

        spec = find_spec_in_worktree(wt_path)
        if spec:
            self.session.feature_name = spec.feature_name
            self._save()

        if not self.session.feature_name:
            return self.make_failed(
                error_message="Feature name が取得できませんでした。spec.json を確認してください。"
            )

        return None

    async def _seg_A2(self) -> dict[str, Any] | None:
        rp = RP(self.session.checkpoint_data.get("resume_point", RP.A1_WHAT.value))
        wt_path = Path(self.session.worktree_path)

        if rp not in _RUN_A2:
            self.skip_step("A2: spec-how", "opus", "resume")
            return None

        resume_mode = "review-only" if rp == RP.A2_HOW_REVIEW_ONLY else "full"
        result = await self.run_agent_step(
            AgentStep(
                "A2: spec-how",
                "tools/orchestrator/prompts/impl-spec-how.md",
                "opus",
                {
                    "WORKTREE_PATH": str(wt_path),
                    "FEATURE_NAME": self.session.feature_name,
                    "RESUME_MODE": resume_mode,
                },
            ),
            cwd=wt_path,
        )

        if result.is_error:
            return self.make_error(
                checkpoint="step_A2_failed",
                error=result.error_message,
                step_output=result.output_text[-2000:],
            )

        if result.parsed.has_reject:
            return self.make_error(
                checkpoint="step_A2_rejected",
                error="Design review REJECT",
                step_output=result.output_text[-2000:],
                suggested_actions=["retry", "abort"],
            )

        return None

    async def _seg_A3(self) -> dict[str, Any] | None:
        rp = RP(self.session.checkpoint_data.get("resume_point", RP.A1_WHAT.value))
        wt_path = Path(self.session.worktree_path)

        if rp not in _RUN_A3:
            self.skip_step("A3: spec-tasks", "sonnet", "resume")
            return None

        result = await self.run_agent_step(
            AgentStep(
                "A3: spec-tasks",
                "tools/orchestrator/prompts/impl-spec-tasks.md",
                "sonnet",
                {
                    "WORKTREE_PATH": str(wt_path),
                    "FEATURE_NAME": self.session.feature_name,
                },
            ),
            cwd=wt_path,
        )

        if result.is_error:
            return self.make_error(
                checkpoint="step_A3_failed",
                error=result.error_message,
                step_output=result.output_text[-2000:],
            )

        return None

    async def _seg_B(self) -> dict[str, Any] | None:
        rp = RP(self.session.checkpoint_data.get("resume_point", RP.A1_WHAT.value))
        wt_path = Path(self.session.worktree_path)

        if rp not in _RUN_B:
            self.skip_step("B: impl", "sonnet", "resume")
            return None

        result = await self.run_agent_step(
            AgentStep(
                "B: impl",
                "tools/orchestrator/prompts/impl-code.md",
                "sonnet",
                {
                    "WORKTREE_PATH": str(wt_path),
                    "FEATURE_NAME": self.session.feature_name,
                },
            ),
            cwd=wt_path,
        )

        if result.is_error:
            return self.make_error(
                checkpoint="step_B_failed",
                error=result.error_message,
                step_output=result.output_text[-2000:],
            )

        return None

    async def _seg_B2(self) -> dict[str, Any] | None:
        rp = RP(self.session.checkpoint_data.get("resume_point", RP.A1_WHAT.value))
        wt_path = Path(self.session.worktree_path)

        if rp not in _RUN_B2:
            self.skip_step("B2: validate", "opus", "resume")
            return None

        result = await self.run_agent_step(
            AgentStep(
                "B2: validate",
                "tools/orchestrator/prompts/impl-validate.md",
                "opus",
                {
                    "WORKTREE_PATH": str(wt_path),
                    "FEATURE_NAME": self.session.feature_name,
                },
            ),
            cwd=wt_path,
        )

        if result.is_error:
            return self.make_error(
                checkpoint="step_B2_failed",
                error=result.error_message,
                step_output=result.output_text[-2000:],
            )

        if result.parsed.validation_failed:
            return self.make_error(
                checkpoint="step_B2_failed",
                error="Validation FAILED (NO-GO)",
                step_output=result.output_text[-2000:],
                suggested_actions=["retry", "abort"],
            )

        return None

    async def _seg_steering(self) -> dict[str, Any] | None:
        wt_path = Path(self.session.worktree_path)
        await self._run_steering_sync(wt_path)
        return None

    async def _seg_C(self) -> dict[str, Any] | None:
        wt_path = Path(self.session.worktree_path)

        result = await self.run_agent_step(
            AgentStep(
                "C: commit",
                "tools/orchestrator/prompts/impl-commit.md",
                "sonnet",
                {
                    "WORKTREE_PATH": str(wt_path),
                    "BRANCH_NAME": self.session.branch_name,
                    "FEATURE_NAME": self.session.feature_name,
                },
            ),
            cwd=wt_path,
        )

        if result.is_error:
            return self.make_error(
                checkpoint="step_C_failed",
                error=result.error_message,
                step_output=result.output_text[-2000:],
            )

        return None

    async def _seg_L4(self) -> dict[str, Any] | None:
        wt_path = Path(self.session.worktree_path)
        tasks_md = wt_path / ".kiro" / "specs" / self.session.feature_name / "tasks.md"
        has_l4 = tasks_md.exists() and has_l4_human_review(tasks_md.read_text())

        if not has_l4:
            self.skip_step("scene-review", "-", "L4 タスクなし")
            return None

        # Run scene-review as a single agent step
        prompt = (
            f"以下のSkillを実行してください:\n"
            f'Skill(skill="kiro:scene-review", args="{self.session.feature_name}")\n\n'
            f"結果を報告してください。不合格の項目があれば SCENE_REVIEW_FAILED と出力し、"
            f"全項目合格なら SCENE_REVIEW_PASSED と出力してください。"
        )
        full_text = await self._run_skill_step(
            "scene-review", prompt, wt_path, model="sonnet"
        )

        if "SCENE_REVIEW_PASSED" not in full_text:
            return self.make_interaction(
                checkpoint="scene_review_failed",
                question="Scene-review に不合格の項目があります。どうしますか？",
                options=["修正してリトライ", "続行 (不合格のまま)", "中止"],
                context=f"worktree={wt_path}",
            )

        return None

    async def _seg_D(self) -> dict[str, Any] | None:
        wt_path = Path(self.session.worktree_path)

        result = await self.run_agent_step(
            AgentStep(
                "D: push-pr",
                "tools/orchestrator/prompts/impl-push-pr.md",
                "sonnet",
                {
                    "WORKTREE_PATH": str(wt_path),
                    "BRANCH_NAME": self.session.branch_name,
                    "FEATURE_NAME": self.session.feature_name,
                    "BASE_BRANCH": self.session.base_branch,
                },
            ),
            cwd=wt_path,
        )

        if result.is_error:
            return self.make_error(
                checkpoint="step_D_failed",
                error=result.error_message,
                step_output=result.output_text[-2000:],
            )

        pr_url = self._extract_pr_url(result.output_text)
        self.session.checkpoint_data["pr_url"] = pr_url

        if pr_url:
            removed = remove_worktree(self.config, wt_path)
            self.session.checkpoint_data["worktree_removed"] = removed

        self._save()
        return None

    # ── Completion ───────────────────────────────────────────────

    def _complete_pipeline(self) -> dict[str, Any]:
        pr_url = self.session.checkpoint_data.get("pr_url", "")
        return self.make_completed({
            "status": "completed" if pr_url else "push-pr-incomplete",
            "branch": self.session.branch_name,
            "feature": self.session.feature_name,
            "pr_url": pr_url,
            "worktree": self.session.worktree_path,
        })

    # ── Helpers ──────────────────────────────────────────────────

    @staticmethod
    def _extract_pr_url(text: str) -> str:
        m = re.search(r"https://github\.com/\S+/pull/\d+", text)
        return m.group(0) if m else ""
