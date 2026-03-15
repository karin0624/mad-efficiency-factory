"""Modify pipeline: existing spec → delta modification workflow.

Steps: Preflight → Feature resolve → M1(Analysis) → Worktree
       → M2(Cascade) → M3(Delta tasks) → B(Impl) → B2(Validate)
       → [L4 check] → C(Commit) → D(Push+PR)
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ..agent_runner import AgentStep
from ..config import OrchestratorConfig
from ..human_input import ask_sync_action, ask_text
from ..output_parser import has_l4_human_review
from ..pipeline import Pipeline, PipelineError
from ..preflight import (
    PreflightError,
    run_preflight,
    pull_base,
    push_base,
)
from ..progress import PipelineProgress
from ..state import (
    ModifyPhase,
    ModifyResumePoint as MRP,
    Phase,
    SpecState,
    find_spec_by_name,
    detect_modify_resume,
    load_spec,
)
from ..worktree import create_or_reuse_worktree, remove_worktree


class ModifyPipeline(Pipeline):
    """Modify pipeline: change analysis → cascade → delta tasks → impl → PR."""

    async def run(
        self,
        *,
        feature_name: str,
        change_description: str = "",
    ) -> dict[str, Any]:
        self.progress = PipelineProgress("Modify Pipeline")
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

        # ── Step 1: Feature + Change resolution ───────────────────
        self.progress.print_info("Step 1: Feature + Change resolution")

        spec_dir = self.config.project_root / ".kiro" / "specs" / feature_name
        if not spec_dir.is_dir():
            available = [
                d.name
                for d in (self.config.project_root / ".kiro" / "specs").iterdir()
                if d.is_dir()
            ]
            raise PipelineError(
                f"Feature '{feature_name}' が見つかりません。利用可能:\n"
                + "\n".join(f"  - {n}" for n in available)
            )

        main_spec = load_spec(spec_dir / "spec.json")
        if main_spec.phase == Phase.INITIALIZED:
            raise PipelineError(
                "要件生成が完了していません。先に /implement で要件を生成してください。"
            )

        if not change_description:
            change_description = ask_text("どのような変更を加えますか？")

        self.progress.print_info(f"Feature: {feature_name}")
        self.progress.print_info(f"Change: {change_description[:80]}")

        # ── Step 2: M1 — Change impact analysis ──────────────────
        # M1 runs in main repo (before worktree), per modify.md spec.
        result_m1 = await self._run_or_fail(
            "M1: analysis", "tools/orchestrator/prompts/modify-analyze.md", "opus",
            {
                "FEATURE_NAME": feature_name,
                "CHANGE_DESCRIPTION": change_description,
            },
            self.config.project_root,
        )

        if not result_m1.parsed.analysis_done:
            raise PipelineError("M1: 分析結果のマーカーが見つかりません。", None)

        m1_output = result_m1.output_text
        cascade_depth = result_m1.parsed.cascade_depth
        classification = result_m1.parsed.classification
        delta_summary = result_m1.parsed.delta_summary

        self.progress.print_info(
            f"Classification: {classification}, Cascade: {cascade_depth}"
        )

        # Persist M1 output for crash recovery
        m1_cache_dir = self.config.project_root / ".claude" / "orchestrator"
        m1_cache_dir.mkdir(parents=True, exist_ok=True)
        m1_cache_path = m1_cache_dir / f"modify-{feature_name}.json"
        m1_cache_path.write_text(json.dumps({
            "m1_output": m1_output,
            "cascade_depth": cascade_depth,
            "classification": classification,
            "change_description": change_description,
            "delta_summary": delta_summary,
        }, ensure_ascii=False, indent=2))

        # ── Step 3: Resume detection + Worktree ──────────────────
        self.progress.print_info("Step 3: Worktree setup")
        wt_info = create_or_reuse_worktree(
            self.config, "modify", feature_name, base_branch
        )
        wt_path = wt_info.path
        branch_name = wt_info.branch

        resume_point: MRP | None = None
        if not wt_info.created:
            wt_spec = find_spec_by_name(wt_path, feature_name)
            if wt_spec:
                wt_spec.ensure_modifications_field()
                resume_point = detect_modify_resume(wt_spec)
                if resume_point:
                    self.progress.print_info(f"Resume: {resume_point.value}")

        # ── Step 4: M2 — Spec cascade ────────────────────────────
        if resume_point is None or resume_point == MRP.M2_CASCADE:
            result_m2 = await self._run_or_fail(
                "M2: cascade", "tools/orchestrator/prompts/modify-cascade.md", "opus",
                {
                    "WORKTREE_PATH": str(wt_path),
                    "FEATURE_NAME": feature_name,
                    "CHANGE_IMPACT_REPORT": m1_output,
                    "CASCADE_DEPTH": cascade_depth,
                },
                wt_path,
            )
            if result_m2.parsed.cascade_failed:
                raise PipelineError(
                    "Cascade FAILED (design-review REJECT)。", wt_path
                )
        else:
            self.skip_step("M2: cascade", "opus", "resume")

        # ── Step 5: M3 — Delta tasks ─────────────────────────────
        skip_m3 = cascade_depth == "requirements-only"
        if skip_m3:
            self.skip_step("M3: delta-tasks", "sonnet", "CASCADE_DEPTH=requirements-only")
        elif resume_point is None or resume_point in (MRP.M2_CASCADE, MRP.M3_DELTA_TASKS):
            result_m3 = await self._run_or_fail(
                "M3: delta-tasks", "tools/orchestrator/prompts/modify-tasks.md", "sonnet",
                {
                    "WORKTREE_PATH": str(wt_path),
                    "FEATURE_NAME": feature_name,
                    "CHANGE_IMPACT_REPORT": m1_output,
                    "CASCADE_DEPTH": cascade_depth,
                },
                wt_path,
            )
            # Update modify_phase
            wt_spec = find_spec_by_name(wt_path, feature_name)
            if wt_spec:
                wt_spec.set_modify_phase(ModifyPhase.DELTA_TASKS_GENERATED)
        else:
            self.skip_step("M3: delta-tasks", "sonnet", "resume")

        # ── Step 6: B — Implementation ───────────────────────────
        skip_b = cascade_depth in ("requirements-only", "requirements+design")
        if skip_b:
            self.skip_step("B: impl", "sonnet", f"CASCADE_DEPTH={cascade_depth}")
        elif resume_point is None or resume_point in (
            MRP.M2_CASCADE, MRP.M3_DELTA_TASKS, MRP.B_IMPL,
        ):
            await self._run_or_fail(
                "B: impl", "tools/orchestrator/prompts/impl-code.md", "sonnet",
                {"WORKTREE_PATH": str(wt_path), "FEATURE_NAME": feature_name},
                wt_path,
            )
            wt_spec = find_spec_by_name(wt_path, feature_name)
            if wt_spec:
                wt_spec.set_modify_phase(ModifyPhase.IMPL_COMPLETED)
        else:
            self.skip_step("B: impl", "sonnet", "resume")

        # ── Step 7: B2 — Validate ────────────────────────────────
        skip_b2 = cascade_depth == "requirements-only"
        if skip_b2:
            self.skip_step("B2: validate", "opus", "CASCADE_DEPTH=requirements-only")
        elif resume_point is None or resume_point in (
            MRP.M2_CASCADE, MRP.M3_DELTA_TASKS, MRP.B_IMPL, MRP.B2_VALIDATE,
        ):
            r = await self._run_or_fail(
                "B2: validate", "tools/orchestrator/prompts/impl-validate.md", "opus",
                {"WORKTREE_PATH": str(wt_path), "FEATURE_NAME": feature_name},
                wt_path,
            )
            if r.parsed.validation_failed:
                raise PipelineError(
                    f"Validation FAILED (NO-GO)。Worktree: {wt_path}", wt_path
                )
            wt_spec = find_spec_by_name(wt_path, feature_name)
            if wt_spec:
                wt_spec.set_modify_phase(ModifyPhase.VALIDATED)
        else:
            self.skip_step("B2: validate", "opus", "resume")

        # ── Step 8: C — Commit ────────────────────────────────────
        await self._run_or_fail(
            "C: commit", "tools/orchestrator/prompts/impl-commit.md", "sonnet",
            {
                "WORKTREE_PATH": str(wt_path),
                "BRANCH_NAME": branch_name,
                "FEATURE_NAME": feature_name,
            },
            wt_path,
        )

        # ── Step 8.5: L4 Human Review check ──────────────────────
        tasks_md_path = wt_path / ".kiro" / "specs" / feature_name / "tasks.md"
        has_l4 = tasks_md_path.exists() and has_l4_human_review(tasks_md_path.read_text())

        # ── Step 9A: scene-review ─────────────────────────────────
        if has_l4:
            self.progress.print_info("L4 Human Review タスクを検出。")
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

        # ── Step 9B: D — Push + PR ────────────────────────────────
        change_summary = delta_summary.split("\n")[0] if delta_summary else change_description[:80]
        result_d = await self._run_or_fail(
            "D: push-pr", "tools/orchestrator/prompts/impl-push-pr.md", "sonnet",
            {
                "WORKTREE_PATH": str(wt_path),
                "BRANCH_NAME": branch_name,
                "FEATURE_NAME": feature_name,
                "BASE_BRANCH": base_branch,
                "MODIFY_MODE": "true",
                "CHANGE_SUMMARY": change_summary,
            },
            wt_path,
        )

        pr_url = self._extract_pr_url(result_d.output_text)

        # Update modify_phase and cleanup
        wt_spec = find_spec_by_name(wt_path, feature_name)
        if wt_spec:
            wt_spec.set_modify_phase(ModifyPhase.COMPLETED)

        if pr_url:
            removed = remove_worktree(self.config, wt_path)
            if removed:
                self.progress.print_info("Worktree を削除しました。")

        # Cleanup M1 cache
        if m1_cache_path.exists():
            m1_cache_path.unlink()

        self.progress.print_summary()

        if pr_url:
            self.progress.print_success(f"PR: {pr_url}")

        return {
            "status": "completed" if pr_url else "push-pr-incomplete",
            "branch": branch_name,
            "feature": feature_name,
            "classification": classification,
            "cascade_depth": cascade_depth,
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
        cwd: Path,
    ):
        """Run an agent step; raise PipelineError on failure."""
        result = await self.run_agent_step(
            AgentStep(name=name, instruction_path=instruction_path, model=model, params=params),
            cwd=cwd,
        )
        if result.is_error:
            raise PipelineError(f"{name} failed: {result.error_message}", cwd)
        return result

    async def _run_scene_review(self, wt_path: Path, feature_name: str) -> bool:
        """Run scene-review via a query() call that invokes the Skill."""
        from claude_agent_sdk import (
            AssistantMessage,
            ClaudeAgentOptions,
            ResultMessage,
            TextBlock,
            query,
        )

        prompt = (
            f"以下のSkillを実行してください:\n"
            f'Skill(skill="kiro:scene-review", args="{feature_name}")\n\n'
            f"結果を報告してください。不合格の項目があれば SCENE_REVIEW_FAILED と出力し、"
            f"全項目合格なら SCENE_REVIEW_PASSED と出力してください。"
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
        m = re.search(r"https://github\.com/\S+/pull/\d+", text)
        return m.group(0) if m else ""
