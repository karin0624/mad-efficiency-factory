"""Modify pipeline: existing spec → delta modification workflow.

Steps: Preflight → Feature resolve → M1(Analysis) → Worktree
       → ADR Gate → M2(Cascade) → M3(Delta tasks) → B(Impl) → B2(Validate)
       → [L4 check] → C(Commit) → D(Push+PR)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
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


@dataclass
class M1Result:
    """Structured result from M1 change-impact analysis."""

    feature_name: str
    change_description: str
    m1_output: str
    cascade_depth: str
    classification: str
    delta_summary: str
    adr_required: bool
    adr_category: str
    adr_reason: str


class ModifyPipeline(Pipeline):
    """Modify pipeline: change analysis → ADR gate → cascade → delta tasks → impl → PR."""

    # ── Plan helpers (static) ─────────────────────────────────────

    @staticmethod
    def _parse_execution_order(index_path: Path) -> list[str]:
        """Parse execution order from _index.md."""
        content = index_path.read_text()
        order: list[str] = []

        in_section = False
        for line in content.split("\n"):
            if "推奨実行順序" in line:
                in_section = True
                continue
            if in_section:
                if line.startswith("##") or line.startswith("> "):
                    if order:
                        break
                    continue
                m = re.match(r"^\d+\.\s+(\S+)\s*$", line.strip())
                if m:
                    order.append(m.group(1))
                    continue
                m = re.match(r".*feature=(\S+)", line)
                if m:
                    order.append(m.group(1))

        return order

    @staticmethod
    def _find_next_pending_spec(plan_dir: Path, order: list[str]) -> str | None:
        """Find the first spec not yet completed in .status.json."""
        status_path = plan_dir / ".status.json"
        completed: list[str] = []
        if status_path.exists():
            try:
                data = json.loads(status_path.read_text())
                completed = data.get("completed", [])
            except (json.JSONDecodeError, KeyError):
                pass

        for spec in order:
            if spec not in completed:
                return spec
        return None

    @staticmethod
    def _get_pending_specs(plan_dir: Path, order: list[str]) -> list[str]:
        """Return all pending specs in execution order."""
        status_path = plan_dir / ".status.json"
        completed: list[str] = []
        if status_path.exists():
            try:
                data = json.loads(status_path.read_text())
                completed = data.get("completed", [])
            except (json.JSONDecodeError, KeyError):
                pass

        return [spec for spec in order if spec not in completed]

    @staticmethod
    def _mark_spec_completed(plan_dir: Path, spec_name: str) -> None:
        """Append completed spec to .status.json."""
        status_path = plan_dir / ".status.json"
        data: dict[str, Any] = {"completed": []}
        if status_path.exists():
            try:
                data = json.loads(status_path.read_text())
            except (json.JSONDecodeError, KeyError):
                pass

        if spec_name not in data.get("completed", []):
            data.setdefault("completed", []).append(spec_name)
        status_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    @staticmethod
    def _parse_plan_params(plan_file: Path) -> tuple[str, str]:
        """Extract feature_name and change_description from plan file YAML block."""
        content = plan_file.read_text()

        section_match = re.search(r"##\s*/modify\s*実行パラメータ", content)
        if not section_match:
            return "", ""

        section_text = content[section_match.end():]

        yaml_match = re.search(r"\s*```ya?ml\s*\n(.*?)\s*```", section_text, re.DOTALL)
        if not yaml_match:
            return "", ""

        yaml_text = yaml_match.group(1)

        fn_match = re.search(r"feature_name:\s*(\S+)", yaml_text)
        feature_name = fn_match.group(1) if fn_match else ""

        cd_match = re.search(r"change_description:\s*\|?\s*\n(.*?)(?:\n\S|\Z)", yaml_text, re.DOTALL)
        if cd_match:
            raw_lines = cd_match.group(1).split("\n")
            stripped = [line.strip() for line in raw_lines if line.strip()]
            change_description = "\n".join(stripped)
        else:
            cd_match = re.search(r"change_description:\s*(.+)", yaml_text)
            change_description = cd_match.group(1).strip() if cd_match else ""

        return feature_name, change_description

    # ── M1 analysis ───────────────────────────────────────────────

    async def _run_m1_analysis(
        self, feature_name: str, change_description: str
    ) -> M1Result:
        """M1分析をmain repoで実行し結果を返す。"""
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

        m1 = M1Result(
            feature_name=feature_name,
            change_description=change_description,
            m1_output=result_m1.output_text,
            cascade_depth=result_m1.parsed.cascade_depth,
            classification=result_m1.parsed.classification,
            delta_summary=result_m1.parsed.delta_summary,
            adr_required=result_m1.parsed.adr_required,
            adr_category=result_m1.parsed.adr_category,
            adr_reason=result_m1.parsed.adr_reason,
        )

        self.progress.print_info(
            f"Classification: {m1.classification}, Cascade: {m1.cascade_depth}"
        )

        # Persist M1 output for crash recovery
        m1_cache_dir = self.config.project_root / ".claude" / "orchestrator"
        m1_cache_dir.mkdir(parents=True, exist_ok=True)
        m1_cache_path = m1_cache_dir / f"modify-{feature_name}.json"
        m1_cache_path.write_text(json.dumps({
            "m1_output": m1.m1_output,
            "cascade_depth": m1.cascade_depth,
            "classification": m1.classification,
            "change_description": m1.change_description,
            "delta_summary": m1.delta_summary,
            "adr_required": m1.adr_required,
            "adr_category": m1.adr_category,
            "adr_reason": m1.adr_reason,
        }, ensure_ascii=False, indent=2))

        return m1

    # ── ADR Gate ──────────────────────────────────────────────────

    @staticmethod
    def _read_adr_status(adr_file: Path) -> str | None:
        """Read the status field from an ADR file's YAML frontmatter."""
        if not adr_file.exists():
            return None
        content = adr_file.read_text()
        if not content.startswith("---"):
            return None
        try:
            end_idx = content.index("---", 3)
        except ValueError:
            return None
        frontmatter = content[3:end_idx]
        m = re.search(r"^status:\s*(\S+)\s*$", frontmatter, re.MULTILINE)
        return m.group(1) if m else None

    async def _run_adr_review(self, wt_path: Path, adr_path: str) -> bool:
        """decision-create review スキルでヒューマンレビューを実施。accepted なら True。"""
        adr_file = wt_path / adr_path if not Path(adr_path).is_absolute() else Path(adr_path)
        rel_path = str(adr_file.relative_to(wt_path))

        prompt = (
            f"以下のSkillを実行してください:\n"
            f'Skill(skill="kiro:decision-create", args="review {rel_path}")\n\n'
            f"ADRのレビュー結果を報告してください。"
        )

        await self._run_interactive_skill(prompt, cwd=wt_path)

        # ファイルの実際の status で判定（テキスト出力に依存しない）
        status = self._read_adr_status(adr_file)
        return status == "accepted"

    async def _run_adr_gate(
        self,
        m1: M1Result,
        wt_path: Path,
        *,
        scope: str = "spec",
        plan_specs: list[str] | None = None,
        all_m1_outputs: str | None = None,
    ) -> str | None:
        """ADR生成+レビューゲート。accepted→ADRパス, 不要→None, rejected→PipelineError"""
        if not m1.adr_required:
            self.skip_step("ADR: gate", "sonnet", "ADR not required")
            return None

        self.progress.print_info(
            f"ADR required: {m1.adr_category} — {m1.adr_reason}"
        )

        feature_names = m1.feature_name
        m1_output = all_m1_outputs if all_m1_outputs else m1.m1_output

        result_adr = await self._run_or_fail(
            "ADR: auto-generate",
            "tools/orchestrator/prompts/modify-adr.md",
            "sonnet",
            {
                "FEATURE_NAMES": feature_names,
                "CHANGE_DESCRIPTION": m1.change_description,
                "ADR_CATEGORY": m1.adr_category,
                "ADR_REASON": m1.adr_reason,
                "DELTA_SUMMARY": m1.delta_summary,
                "M1_OUTPUT": m1_output,
                "SPEC_DIFF": "",
                "ADR_SCOPE": scope,
            },
            wt_path,
        )

        if not result_adr.parsed.markers.get("ADR_CREATED"):
            self.progress.print_warning("ADR generation failed — continuing without ADR")
            return None

        adr_path = result_adr.parsed.adr_path
        if not adr_path:
            self.progress.print_warning("ADR_PATH not found in output — continuing without ADR")
            return None

        # Run ADR review
        accepted = await self._run_adr_review(wt_path, adr_path)
        if not accepted:
            raise PipelineError("ADR rejected", wt_path)

        # Update modify_phase for spec-level ADR
        if scope == "spec":
            wt_spec = find_spec_by_name(wt_path, m1.feature_name)
            if wt_spec:
                wt_spec.set_modify_phase(ModifyPhase.ADR_ACCEPTED)

        return adr_path

    # ── Spec implementation (M2→B2) ───────────────────────────────

    async def _run_spec_impl(
        self,
        m1: M1Result,
        wt_path: Path,
        resume_point: MRP | None,
        *,
        adr_path: str | None = None,
    ) -> None:
        """M2 cascade → M3 delta tasks → B impl → B2 validate を worktree で実行。"""
        extra_params: dict[str, str] = {}
        if adr_path:
            extra_params["ADR_PATH"] = adr_path

        # ── M2 — Spec cascade ────────────────────────────────────
        if resume_point is None or resume_point in (MRP.ADR_GATE, MRP.M2_CASCADE):
            result_m2 = await self._run_or_fail(
                "M2: cascade", "tools/orchestrator/prompts/modify-cascade.md", "opus",
                {
                    "WORKTREE_PATH": str(wt_path),
                    "FEATURE_NAME": m1.feature_name,
                    "CHANGE_IMPACT_REPORT": m1.m1_output,
                    "CASCADE_DEPTH": m1.cascade_depth,
                    **extra_params,
                },
                wt_path,
            )
            if result_m2.parsed.cascade_failed:
                raise PipelineError(
                    "Cascade FAILED (design-review REJECT)。", wt_path
                )
        else:
            self.skip_step("M2: cascade", "opus", "resume")

        # ── M3 — Delta tasks ─────────────────────────────────────
        skip_m3 = m1.cascade_depth == "requirements-only"
        if skip_m3:
            self.skip_step("M3: delta-tasks", "sonnet", "CASCADE_DEPTH=requirements-only")
        elif resume_point is None or resume_point in (MRP.ADR_GATE, MRP.M2_CASCADE, MRP.M3_DELTA_TASKS):
            await self._run_or_fail(
                "M3: delta-tasks", "tools/orchestrator/prompts/modify-tasks.md", "sonnet",
                {
                    "WORKTREE_PATH": str(wt_path),
                    "FEATURE_NAME": m1.feature_name,
                    "CHANGE_IMPACT_REPORT": m1.m1_output,
                    "CASCADE_DEPTH": m1.cascade_depth,
                },
                wt_path,
            )
            wt_spec = find_spec_by_name(wt_path, m1.feature_name)
            if wt_spec:
                wt_spec.set_modify_phase(ModifyPhase.DELTA_TASKS_GENERATED)
        else:
            self.skip_step("M3: delta-tasks", "sonnet", "resume")

        # ── B — Implementation ───────────────────────────────────
        skip_b = m1.cascade_depth in ("requirements-only", "requirements+design")
        if skip_b:
            self.skip_step("B: impl", "sonnet", f"CASCADE_DEPTH={m1.cascade_depth}")
        elif resume_point is None or resume_point in (
            MRP.ADR_GATE, MRP.M2_CASCADE, MRP.M3_DELTA_TASKS, MRP.B_IMPL,
        ):
            await self._run_or_fail(
                "B: impl", "tools/orchestrator/prompts/impl-code.md", "sonnet",
                {
                    "WORKTREE_PATH": str(wt_path),
                    "FEATURE_NAME": m1.feature_name,
                    **extra_params,
                },
                wt_path,
            )
            wt_spec = find_spec_by_name(wt_path, m1.feature_name)
            if wt_spec:
                wt_spec.set_modify_phase(ModifyPhase.IMPL_COMPLETED)
        else:
            self.skip_step("B: impl", "sonnet", "resume")

        # ── B2 — Validate ────────────────────────────────────────
        skip_b2 = m1.cascade_depth == "requirements-only"
        if skip_b2:
            self.skip_step("B2: validate", "opus", "CASCADE_DEPTH=requirements-only")
        elif resume_point is None or resume_point in (
            MRP.ADR_GATE, MRP.M2_CASCADE, MRP.M3_DELTA_TASKS, MRP.B_IMPL, MRP.B2_VALIDATE,
        ):
            r = await self._run_or_fail(
                "B2: validate", "tools/orchestrator/prompts/impl-validate.md", "opus",
                {"WORKTREE_PATH": str(wt_path), "FEATURE_NAME": m1.feature_name},
                wt_path,
            )
            if r.parsed.validation_failed:
                raise PipelineError(
                    f"Validation FAILED (NO-GO)。Worktree: {wt_path}", wt_path
                )
            wt_spec = find_spec_by_name(wt_path, m1.feature_name)
            if wt_spec:
                wt_spec.set_modify_phase(ModifyPhase.VALIDATED)
        else:
            self.skip_step("B2: validate", "opus", "resume")

    # ── Delivery (Commit → L4 → scene-review → Push-PR → Cleanup) ─

    async def _run_delivery(
        self,
        wt_path: Path,
        branch_name: str,
        base_branch: str,
        feature_names: list[str],
        delta_summary: str,
        change_description: str,
        classification: str,
        cascade_depth: str,
    ) -> dict[str, Any]:
        """Commit → L4 check → scene-review → Push-PR → Cleanup。"""
        primary_feature = feature_names[0]

        # ── Steering sync ─────────────────────────────────────────
        if cascade_depth not in ("requirements-only",):
            await self._run_steering_sync(wt_path)
        else:
            self.skip_step("steering-sync", "sonnet", "CASCADE_DEPTH=requirements-only")

        # ── Commit ────────────────────────────────────────────────
        await self._run_or_fail(
            "C: commit", "tools/orchestrator/prompts/impl-commit.md", "sonnet",
            {
                "WORKTREE_PATH": str(wt_path),
                "BRANCH_NAME": branch_name,
                "FEATURE_NAME": primary_feature,
            },
            wt_path,
        )

        # ── L4 Human Review check ────────────────────────────────
        tasks_md_path = wt_path / ".kiro" / "specs" / primary_feature / "tasks.md"
        has_l4 = tasks_md_path.exists() and has_l4_human_review(tasks_md_path.read_text())

        # ── scene-review ──────────────────────────────────────────
        if has_l4:
            self.progress.print_info("L4 Human Review タスクを検出。")
            sr_passed = await self._run_scene_review(wt_path, primary_feature)
            if not sr_passed:
                self.progress.print_error(
                    f"Scene-review に不合格の項目があります。\nWorktree: {wt_path}"
                )
                self.progress.print_summary()
                return {
                    "status": "scene-review-failed",
                    "branch": branch_name,
                    "feature": primary_feature,
                    "worktree": str(wt_path),
                }
        else:
            self.skip_step("scene-review", "-", "L4 タスクなし")

        # ── Push + PR ─────────────────────────────────────────────
        change_summary = delta_summary.split("\n")[0] if delta_summary else change_description[:80]
        result_d = await self._run_or_fail(
            "D: push-pr", "tools/orchestrator/prompts/impl-push-pr.md", "sonnet",
            {
                "WORKTREE_PATH": str(wt_path),
                "BRANCH_NAME": branch_name,
                "FEATURE_NAME": primary_feature,
                "BASE_BRANCH": base_branch,
                "MODIFY_MODE": "true",
                "CHANGE_SUMMARY": change_summary,
            },
            wt_path,
        )

        pr_url = self._extract_pr_url(result_d.output_text)

        # Update modify_phase and cleanup
        for fname in feature_names:
            wt_spec = find_spec_by_name(wt_path, fname)
            if wt_spec:
                wt_spec.set_modify_phase(ModifyPhase.COMPLETED)

        if pr_url:
            removed = remove_worktree(self.config, wt_path)
            if removed:
                self.progress.print_info("Worktree を削除しました。")

        # Cleanup M1 caches
        m1_cache_dir = self.config.project_root / ".claude" / "orchestrator"
        for fname in feature_names:
            m1_cache_path = m1_cache_dir / f"modify-{fname}.json"
            if m1_cache_path.exists():
                m1_cache_path.unlink()

        self.progress.print_summary()

        if pr_url:
            self.progress.print_success(f"PR: {pr_url}")

        return {
            "status": "completed" if pr_url else "push-pr-incomplete",
            "branch": branch_name,
            "feature": primary_feature,
            "classification": classification,
            "cascade_depth": cascade_depth,
            "pr_url": pr_url,
            "worktree": str(wt_path),
        }

    # ── Find existing ADR (for resume) ────────────────────────────

    @staticmethod
    def _find_existing_adr(wt_path: Path, feature_name: str) -> str | None:
        """worktree内の accepted ADR を feature名で検索。"""
        decisions_dir = wt_path / ".kiro" / "decisions"
        if not decisions_dir.exists():
            return None

        re_status = re.compile(r"^status:\s*accepted\s*$", re.MULTILINE)
        re_spec = re.compile(r"^spec:\s*[\"']?" + re.escape(feature_name) + r"[\"']?\s*$", re.MULTILINE)
        re_specs = re.compile(r"^specs:\s*\[.*?" + re.escape(feature_name) + r".*?\]", re.MULTILINE)

        for category_dir in decisions_dir.iterdir():
            if not category_dir.is_dir():
                continue
            for adr_file in category_dir.glob("*.md"):
                try:
                    content = adr_file.read_text()
                    if not content.startswith("---"):
                        continue
                    end_idx = content.index("---", 3)
                    frontmatter = content[3:end_idx]
                    if not re_status.search(frontmatter):
                        continue
                    if re_spec.search(frontmatter) or re_specs.search(frontmatter):
                        return str(adr_file.relative_to(wt_path))
                except (ValueError, OSError):
                    continue

        return None

    # ── Single-spec run() ─────────────────────────────────────────

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
        m1 = await self._run_m1_analysis(feature_name, change_description)

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

        # ── Step 4: ADR Gate (NEW) ────────────────────────────────
        adr_path: str | None = None
        if resume_point is None or resume_point == MRP.ADR_GATE:
            adr_path = await self._run_adr_gate(m1, wt_path)
        elif resume_point and resume_point in (
            MRP.M2_CASCADE, MRP.M3_DELTA_TASKS, MRP.B_IMPL, MRP.B2_VALIDATE, MRP.C_COMMIT,
        ):
            adr_path = self._find_existing_adr(wt_path, feature_name)

        # ── Steps 5-8: Spec implementation ────────────────────────
        await self._run_spec_impl(m1, wt_path, resume_point, adr_path=adr_path)

        # ── Steps 9-12: Delivery ──────────────────────────────────
        return await self._run_delivery(
            wt_path, branch_name, base_branch,
            [feature_name], m1.delta_summary, m1.change_description,
            m1.classification, m1.cascade_depth,
        )

    # ── Plan-driven run ───────────────────────────────────────────

    async def run_from_plan(self, plan_name: str) -> dict[str, Any]:
        """Run modify pipeline for all pending specs in a plan (single PR)."""
        plan_dir = self.config.project_root / "docs" / "modify-plans" / plan_name
        if not plan_dir.is_dir():
            raise PipelineError(f"Plan directory not found: docs/modify-plans/{plan_name}")

        index_path = plan_dir / "_index.md"
        if not index_path.exists():
            raise PipelineError(f"_index.md not found in: docs/modify-plans/{plan_name}")

        order = self._parse_execution_order(index_path)
        if not order:
            raise PipelineError("推奨実行順序のパースに失敗しました。")

        pending = self._get_pending_specs(plan_dir, order)
        if not pending:
            self.progress = PipelineProgress("Modify Pipeline")
            self.progress.print_header()
            self.progress.print_success("全specの処理が完了しています。")
            self.progress.print_summary()
            return {"status": "all-completed", "plan": plan_name}

        self.progress = PipelineProgress("Modify Pipeline (Plan)")
        self.progress.print_header()
        self.progress.print_info(f"Plan: {plan_name}, Pending specs: {', '.join(pending)}")

        # ── Phase 0: Preflight + Worktree ─────────────────────────
        self.progress.print_info("Phase 0: Preflight + Worktree")
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

        wt_info = create_or_reuse_worktree(
            self.config, "modify", plan_name, base_branch
        )
        wt_path = wt_info.path
        branch_name = wt_info.branch

        # ── Phase 1: 全specのM1分析 ──────────────────────────────
        self.progress.print_info("Phase 1: M1 analysis for all specs")
        m1_results: dict[str, M1Result] = {}
        for spec_name in pending:
            plan_file = plan_dir / f"{spec_name}.md"
            if not plan_file.exists():
                raise PipelineError(f"Plan file not found: {plan_file}")

            feature_name, change_desc = self._parse_plan_params(plan_file)
            if not feature_name or not change_desc:
                raise PipelineError(
                    f"{spec_name}.md から実行パラメータを抽出できません。"
                )
            m1_results[spec_name] = await self._run_m1_analysis(feature_name, change_desc)

        # ── Phase 2: ADR Gate ─────────────────────────────────────
        self.progress.print_info("Phase 2: ADR Gate")
        adr_specs = {name: m1 for name, m1 in m1_results.items() if m1.adr_required}
        adr_paths: dict[str, str | None] = {name: None for name in pending}

        if adr_specs:
            categories = {m1.adr_category for m1 in adr_specs.values()}

            if len(adr_specs) >= 2 and len(categories) == 1:
                # Plan-level ADR: 同一カテゴリの複数spec → 1つのADRに集約
                representative_m1 = next(iter(adr_specs.values()))
                all_m1_outputs = "\n---\n".join(
                    f"## {name}\n{m1.m1_output}" for name, m1 in adr_specs.items()
                )
                all_delta = "\n".join(m1.delta_summary for m1 in adr_specs.values())
                combined_m1 = M1Result(
                    feature_name=", ".join(m1.feature_name for m1 in adr_specs.values()),
                    change_description="\n".join(m1.change_description for m1 in adr_specs.values()),
                    m1_output=all_m1_outputs,
                    cascade_depth=representative_m1.cascade_depth,
                    classification=representative_m1.classification,
                    delta_summary=all_delta,
                    adr_required=True,
                    adr_category=representative_m1.adr_category,
                    adr_reason=representative_m1.adr_reason,
                )
                plan_adr_path = await self._run_adr_gate(
                    combined_m1, wt_path,
                    scope="plan",
                    plan_specs=list(adr_specs.keys()),
                    all_m1_outputs=all_m1_outputs,
                )
                for name in adr_specs:
                    adr_paths[name] = plan_adr_path
            else:
                # Per-spec ADRs: 1specのみ or 異なるカテゴリ
                for name, m1 in adr_specs.items():
                    adr_paths[name] = await self._run_adr_gate(m1, wt_path)
        else:
            self.skip_step("ADR: gate", "sonnet", "No specs require ADR")

        # ── Phase 3: 全specの実装 ────────────────────────────────
        self.progress.print_info("Phase 3: Implementation for all specs")
        for spec_name in pending:
            m1 = m1_results[spec_name]
            self.progress.print_info(f"Implementing: {m1.feature_name}")
            await self._run_spec_impl(m1, wt_path, None, adr_path=adr_paths.get(spec_name))
            self._mark_spec_completed(plan_dir, spec_name)

        # ── Phase 4: Delivery (単一commit + 単一PR) ──────────────
        self.progress.print_info("Phase 4: Delivery")
        all_feature_names = [m1_results[s].feature_name for s in pending]
        first_m1 = m1_results[pending[0]]
        all_delta = "\n".join(m1_results[s].delta_summary for s in pending)
        all_change = "\n".join(m1_results[s].change_description for s in pending)

        return await self._run_delivery(
            wt_path, branch_name, base_branch,
            all_feature_names, all_delta, all_change,
            first_m1.classification, first_m1.cascade_depth,
        )

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

    async def _get_worktree_diff(self, wt_path: Path) -> str:
        """Get git diff from worktree to understand implementation changes."""
        import subprocess

        try:
            result = subprocess.run(
                ["git", "diff", "HEAD"],
                cwd=str(wt_path),
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result.stdout[:10000] if result.stdout else "(no diff)"
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            return "(diff unavailable)"

    async def _run_scene_review(self, wt_path: Path, feature_name: str) -> bool:
        """Run scene-review via ClaudeSDKClient to invoke the Skill."""
        prompt = (
            f"以下のSkillを実行してください:\n"
            f'Skill(skill="kiro:scene-review", args="{feature_name}")\n\n'
            f"結果を報告してください。不合格の項目があれば SCENE_REVIEW_FAILED と出力し、"
            f"全項目合格なら SCENE_REVIEW_PASSED と出力してください。"
        )

        full_text = await self._run_interactive_skill(prompt, cwd=wt_path)
        return "SCENE_REVIEW_PASSED" in full_text

    @staticmethod
    def _extract_pr_url(text: str) -> str:
        m = re.search(r"https://github\.com/\S+/pull/\d+", text)
        return m.group(0) if m else ""
