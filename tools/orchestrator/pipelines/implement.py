"""Implement pipeline: Plan → cc-sdd full execution.

Steps: Preflight → Plan resolve → Worktree → A1(WHAT) → A2(HOW) → A3(Tasks)
       → B(Impl) → B2(Validate) → T(Tests) → [L4 check] → C(Commit) → D(Push+PR)
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..agent_runner import AgentStep
from ..config import OrchestratorConfig
from ..human_input import ask_sync_action
from ..output_parser import has_l4_human_review
from ..pipeline import Pipeline, PipelineError
from ..plan_resolver import resolve_plan
from ..preflight import (
    PreflightError,
    run_preflight,
    pull_base,
    push_base,
)
from ..progress import PipelineProgress
from ..state import (
    ImplementResumePoint as RP,
    SpecState,
    find_spec_in_worktree,
    detect_implement_resume,
)
from ..worktree import create_or_reuse_worktree, remove_worktree


# Resume points that should run each step (step runs if resume_point is in the set).
_RUN_A1 = {RP.A1_WHAT, RP.A1_WHAT_PHASE2}
_RUN_A2 = _RUN_A1 | {RP.A2_HOW_FULL, RP.A2_HOW_REVIEW_ONLY}
_RUN_A3 = _RUN_A2 | {RP.A3_TASKS, RP.A3_TASKS_APPROVAL}
_RUN_B = _RUN_A3 | {RP.B_IMPL}
_RUN_B2 = _RUN_B | {RP.B2_VALIDATE}
_RUN_T = _RUN_B2 | {RP.T_TESTS}
# C (commit) always runs — it's idempotent (skips if no changes)


class ImplementPipeline(Pipeline):
    """Full implement pipeline: plan → spec → impl → validate → PR."""

    async def run(self, *, plan_argument: str) -> dict[str, Any]:
        self.progress = PipelineProgress("Implement Pipeline")
        self.progress.print_header()

        # ── Step 0: Preflight ──────────────────────────────────────
        self.progress.print_info("Step 0: Preflight checks")
        try:
            preflight = run_preflight(self.config.project_root)
        except PreflightError as e:
            self.progress.print_error(str(e))
            raise PipelineError(str(e))

        base_branch = preflight.base_branch

        if preflight.behind > 0:
            action = ask_sync_action("behind", preflight.behind, base_branch)
            if action == "pull":
                pull_base(self.config.project_root, base_branch)

        if preflight.ahead > 0:
            action = ask_sync_action("ahead", preflight.ahead, base_branch)
            if action == "push":
                push_base(self.config.project_root, base_branch)

        # ── Step 1: Plan resolution ───────────────────────────────
        self.progress.print_info("Step 1: Plan resolution")
        plan_path, plan_name = resolve_plan(self.config, plan_argument)
        self.progress.print_info(f"Plan: {plan_path.name} → feat/{plan_name}")

        # ── Step 2: Resume detection + Worktree ───────────────────
        self.progress.print_info("Step 2: Worktree setup")
        wt_info = create_or_reuse_worktree(
            self.config, "feat", plan_name, base_branch
        )
        wt_path = wt_info.path
        branch_name = wt_info.branch

        resume_point = RP.A1_WHAT
        feature_name = ""
        spec: SpecState | None = None

        if not wt_info.created:
            spec = find_spec_in_worktree(wt_path)
            if spec:
                resume_point = detect_implement_resume(spec)
                feature_name = spec.feature_name
                self.progress.print_info(
                    f"Resume: {feature_name} → {resume_point.value}"
                )

        # ── Step 3: A1 — WHAT ─────────────────────────────────────
        if resume_point in _RUN_A1:
            r = await self._run_or_fail(
                "A1: spec-what", "tools/orchestrator/prompts/impl-spec-what.md", "opus",
                {"WORKTREE_PATH": str(wt_path), "PLAN_FILE_ABSOLUTE_PATH": str(plan_path)},
                wt_path,
            )
            spec = find_spec_in_worktree(wt_path)
            if spec:
                feature_name = spec.feature_name
        else:
            self.skip_step("A1: spec-what", "opus", "resume")

        if not feature_name:
            raise PipelineError(
                "Feature name が取得できませんでした。spec.json を確認してください。",
                wt_path,
            )

        # ── Step 3.5: A2 — HOW ────────────────────────────────────
        if resume_point in _RUN_A2:
            resume_mode = "review-only" if resume_point == RP.A2_HOW_REVIEW_ONLY else "full"
            r = await self._run_or_fail(
                "A2: spec-how", "tools/orchestrator/prompts/impl-spec-how.md", "opus",
                {"WORKTREE_PATH": str(wt_path), "FEATURE_NAME": feature_name, "RESUME_MODE": resume_mode},
                wt_path,
            )
            if r.parsed.has_reject:
                raise PipelineError("Design review REJECT", wt_path)
        else:
            self.skip_step("A2: spec-how", "opus", "resume")

        # ── Step 3.75: A3 — Tasks ─────────────────────────────────
        if resume_point in _RUN_A3:
            await self._run_or_fail(
                "A3: spec-tasks", "tools/orchestrator/prompts/impl-spec-tasks.md", "sonnet",
                {"WORKTREE_PATH": str(wt_path), "FEATURE_NAME": feature_name},
                wt_path,
            )
        else:
            self.skip_step("A3: spec-tasks", "sonnet", "resume")

        # ── Step 4: B — Implementation ────────────────────────────
        if resume_point in _RUN_B:
            await self._run_or_fail(
                "B: impl", "tools/orchestrator/prompts/impl-code.md", "sonnet",
                {"WORKTREE_PATH": str(wt_path), "FEATURE_NAME": feature_name},
                wt_path,
            )
        else:
            self.skip_step("B: impl", "sonnet", "resume")

        # ── Step 4.5: B2 — Validate ──────────────────────────────
        if resume_point in _RUN_B2:
            r = await self._run_or_fail(
                "B2: validate", "tools/orchestrator/prompts/impl-validate.md", "opus",
                {"WORKTREE_PATH": str(wt_path), "FEATURE_NAME": feature_name},
                wt_path,
            )
            if r.parsed.validation_failed:
                raise PipelineError(
                    f"Validation FAILED (NO-GO)。Worktree: {wt_path}", wt_path
                )
        else:
            self.skip_step("B2: validate", "opus", "resume")

        # ── Step 4.6: T — Tests ──────────────────────────────────
        if resume_point in _RUN_T:
            await self.run_test_step(wt_path)
        else:
            self.skip_step("T: tests", "-", "resume")

        # ── Step 4.75: Steering sync ─────────────────────────────
        await self._run_steering_sync(wt_path)

        # ── Step 5: C — Commit ────────────────────────────────────
        await self._run_or_fail(
            "C: commit", "tools/orchestrator/prompts/impl-commit.md", "sonnet",
            {"WORKTREE_PATH": str(wt_path), "BRANCH_NAME": branch_name, "FEATURE_NAME": feature_name},
            wt_path,
        )

        # ── Step 5.5: L4 Human Review check ──────────────────────
        tasks_md_path = wt_path / ".kiro" / "specs" / feature_name / "tasks.md"
        has_l4 = tasks_md_path.exists() and has_l4_human_review(tasks_md_path.read_text())

        # ── Step 6A: scene-review (if L4 tasks exist) ─────────────
        if has_l4:
            self.progress.print_info("L4 Human Review タスクを検出。scene-review を実行します。")
            sr_passed = await self._run_scene_review(wt_path, feature_name)
            if not sr_passed:
                self.progress.print_error(
                    f"Scene-review に不合格の項目があります。\nWorktree: {wt_path}"
                )
                self.progress.print_summary()
                return {
                    "status": "scene-review-failed",
                    "branch": branch_name,
                    "feature": feature_name,
                    "worktree": str(wt_path),
                }
        else:
            self.skip_step("scene-review", "-", "L4 タスクなし")

        # ── Step 6B: D — Push + PR ────────────────────────────────
        result_d = await self._run_or_fail(
            "D: push-pr", "tools/orchestrator/prompts/impl-push-pr.md", "sonnet",
            {
                "WORKTREE_PATH": str(wt_path),
                "BRANCH_NAME": branch_name,
                "FEATURE_NAME": feature_name,
                "BASE_BRANCH": base_branch,
            },
            wt_path,
        )

        pr_url = self._extract_pr_url(result_d.output_text)

        # Cleanup worktree on success
        if pr_url:
            removed = remove_worktree(self.config, wt_path)
            if removed:
                self.progress.print_info("Worktree を削除しました。")
            else:
                self.progress.print_info(f"Worktree の削除に失敗: {wt_path}")

        self.progress.print_summary()

        if pr_url:
            self.progress.print_success(f"PR: {pr_url}")

        return {
            "status": "completed" if pr_url else "push-pr-incomplete",
            "branch": branch_name,
            "feature": feature_name,
            "pr_url": pr_url,
            "worktree": str(wt_path),
        }

    # ── Helpers ────────────────────────────────────────────────────

    async def _run_or_fail(
        self,
        name: str,
        instruction_path: str,
        model: str,
        params: dict[str, str],
        wt_path: Path,
    ):
        """Run an agent step; raise PipelineError on failure."""
        from ..agent_runner import AgentResult

        result = await self.run_agent_step(
            AgentStep(name=name, instruction_path=instruction_path, model=model, params=params),
            cwd=wt_path,
        )
        if result.is_error:
            raise PipelineError(f"{name} failed: {result.error_message}", wt_path)
        return result

    async def _run_scene_review(self, wt_path: Path, feature_name: str) -> bool:
        """Run scene-review via a query() call that invokes the Skill.

        Returns True if all items passed, False otherwise.
        """
        result = await self.runner.run_step(
            AgentStep(
                name="scene-review",
                instruction_path="tools/orchestrator/prompts/impl-commit.md",
                model="sonnet",
                params={},
            ),
            cwd=wt_path,
        )
        # Scene-review is interactive — send a prompt that calls the Skill
        prompt = (
            f"以下のSkillを実行してください:\n"
            f'Skill(skill="kiro:scene-review", args="{feature_name}")\n\n'
            f"結果を報告してください。不合格の項目があれば SCENE_REVIEW_FAILED と出力し、"
            f"全項目合格なら SCENE_REVIEW_PASSED と出力してください。"
        )
        from claude_agent_sdk import (
            AssistantMessage,
            ClaudeAgentOptions,
            ResultMessage,
            TextBlock,
            query,
        )

        options = ClaudeAgentOptions(
            model=self.config.resolve_model("sonnet"),
            cwd=str(wt_path),
            setting_sources=["project"],
            permission_mode=self.config.permission_mode,
            allowed_tools=list(self.config.allowed_tools),
            max_turns=30,
            system_prompt={"type": "preset", "preset": "claude_code"},
        )

        text_parts: list[str] = []
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        text_parts.append(block.text)
            elif isinstance(message, ResultMessage):
                if message.result:
                    text_parts.append(message.result)

        full_text = "\n".join(text_parts)
        return "SCENE_REVIEW_FAILED" not in full_text

    @staticmethod
    def _extract_pr_url(text: str) -> str:
        """Extract a GitHub PR URL from agent output text."""
        m = re.search(r"https://github\.com/\S+/pull/\d+", text)
        return m.group(0) if m else ""
