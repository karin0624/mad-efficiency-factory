"""Modify pipeline: existing spec -> delta modification workflow (checkpoint-based).

Steps: Preflight -> Feature resolve -> M1(Analysis) -> Worktree
       -> ADR Gate -> M2(Cascade) -> M2R(Cascade Review) -> M3(Delta tasks)
       -> B(Impl) -> B2(Validate) -> [L4 check] -> C(Commit) -> D(Push+PR)
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

from ..agent_runner import AgentStep
from ..config import OrchestratorConfig
from ..output_parser import has_l4_human_review
from ..pipeline import InterruptiblePipeline
from ..preflight import (
    PreflightError,
    pull_base,
    push_base,
    run_preflight,
)
from ..session import PipelineSession
from ..state import (
    ModifyPhase,
    ModifyResumePoint as MRP,
    Phase,
    SpecState,
    detect_modify_resume,
    find_spec_by_name,
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_name": self.feature_name,
            "change_description": self.change_description,
            "m1_output": self.m1_output,
            "cascade_depth": self.cascade_depth,
            "classification": self.classification,
            "delta_summary": self.delta_summary,
            "adr_required": self.adr_required,
            "adr_category": self.adr_category,
            "adr_reason": self.adr_reason,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> M1Result:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class ModifyPipeline(InterruptiblePipeline):
    """Modify pipeline: change analysis -> ADR gate -> cascade -> delta tasks -> impl -> PR."""

    def __init__(
        self,
        config: OrchestratorConfig,
        session: PipelineSession,
        session_dir: Path,
    ) -> None:
        super().__init__(config, session, session_dir)

    async def run_until_checkpoint(self) -> dict[str, Any]:
        if self.session.params.get("modify_plan"):
            return await self._run_plan_mode()
        return await self._run_single_mode()

    # ══════════════════════════════════════════════════════════════
    # Single-spec mode
    # ══════════════════════════════════════════════════════════════

    async def _run_single_mode(self) -> dict[str, Any]:
        cp = self.session.checkpoint

        if cp:
            result = await self._handle_resume(cp)
            if result is not None:
                return result
            cp = self.session.checkpoint

        segments = [
            ("preflight", self._seg_preflight),
            ("resolve", self._seg_resolve),
            ("M1", self._seg_M1),
            ("worktree", self._seg_worktree),
            ("ADR", self._seg_ADR),
            ("M2", self._seg_M2),
            ("M2R", self._seg_M2R),
            ("M3", self._seg_M3),
            ("B", self._seg_B),
            ("B2", self._seg_B2),
            ("delivery", self._seg_delivery),
        ]

        start_from = cp if cp in [n for n, _ in segments] else ""
        result = await self._run_segments(segments, start_from)
        if result is not None:
            return result

        return self._complete_pipeline()

    # ── Resume handling ──────────────────────────────────────────

    async def _handle_resume(self, cp: str) -> dict[str, Any] | None:
        user_input = self.session.checkpoint_data.get("user_input", "")

        if cp == "preflight_behind":
            if "pull" in user_input.lower():
                pull_base(self.config.project_root, self.session.base_branch)
            try:
                preflight = run_preflight(self.config.project_root)
            except PreflightError:
                self.session.checkpoint = "resolve" if not self.session.params.get("modify_plan") else "worktree"
                self._save()
                return None
            if preflight.ahead > 0:
                return self.make_interaction(
                    checkpoint="preflight_ahead",
                    question=f"ローカルに {preflight.ahead} 件の未pushコミットがあります。pushしますか？",
                    options=["push して続行", "そのまま続行"],
                )
            self.session.checkpoint = "resolve" if not self.session.params.get("modify_plan") else "worktree"
            self._save()
            return None

        if cp == "preflight_ahead":
            if "push" in user_input.lower():
                push_base(self.config.project_root, self.session.base_branch)
            self.session.checkpoint = "resolve" if not self.session.params.get("modify_plan") else "worktree"
            self._save()
            return None

        if cp == "change_description_needed":
            if user_input:
                self.session.params["change"] = user_input
                self.session.checkpoint = "M1"
                self._save()
                return None
            return self.make_interaction(
                checkpoint="change_description_needed",
                question="どのような変更を加えますか？",
            )

        if cp == "adr_review":
            return await self._handle_adr_review_resume()

        if cp.startswith("step_") and (cp.endswith("_failed") or cp.endswith("_rejected")):
            step_name = cp[5:].rsplit("_", 1)[0]
            return self._handle_step_error_resume(step_name)

        if cp.startswith("step_") and cp.endswith("_skip_confirm"):
            step_name = cp[5:-13]
            segments = [
                ("preflight", None), ("resolve", None), ("M1", None),
                ("worktree", None), ("ADR", None), ("M2", None), ("M2R", None),
                ("M3", None), ("B", None), ("B2", None), ("delivery", None),
            ]
            return self._handle_skip_confirm_resume(step_name, segments)

        if cp == "scene_review_failed":
            return await self._handle_scene_review_resume()

        if cp == "m2_cascade_review":
            return await self._handle_m2_cascade_review_resume()

        if cp == "cascade_review_gate":
            return await self._handle_cascade_review_gate_resume()

        if cp == "validation_triage":
            return await self._handle_validation_triage_resume()

        if cp == "m1_review":
            return await self._handle_m1_review_resume()

        return None

    async def _handle_scene_review_resume(self) -> dict[str, Any] | None:
        """Handle resume from scene_review_failed checkpoint."""
        user_input = self.session.checkpoint_data.get("user_input", "")

        if "続行" in user_input or "continue" in user_input.lower():
            self.session.checkpoint_data["scene_review_skip"] = True
            self.session.checkpoint = "delivery_push"
            self._save()
            return None

        if "中止" in user_input or "abort" in user_input.lower():
            return self.make_failed(error_message="ユーザーがパイプラインを中止しました。")

        # 修正 / retry — check for feedback + session_id
        resume_sid = self.session.checkpoint_data.get("scene_review_session_id")
        feedback = user_input.strip()

        if feedback and resume_sid:
            wt_path = Path(self.session.worktree_path)
            feedback_prompt = (
                f"ユーザーからフィードバックがありました:\n\n{feedback}\n\n"
                f"フィードバックに基づいて修正を実行してください。"
            )
            await self._run_skill_step_with_session(
                "scene-review: fix", feedback_prompt, wt_path,
                model="sonnet", resume_session_id=resume_sid,
            )

        self.session.checkpoint = "delivery"
        self.session.checkpoint_data["delivery_stage"] = "scene_review"
        self._save()
        return None

    # ── ADR review resume ────────────────────────────────────────

    _ADR_ACCEPT_PHRASES = frozenset(["確認済み", "続行", "accept", "ok", "はい"])

    @staticmethod
    def _is_adr_accept_only(user_input: str) -> bool:
        stripped = user_input.strip().lower()
        if not stripped:
            return True
        return stripped in ModifyPipeline._ADR_ACCEPT_PHRASES

    async def _handle_adr_review_resume(self) -> dict[str, Any] | None:
        """Handle resume from adr_review checkpoint with optional feedback."""
        user_input = self.session.checkpoint_data.get("user_input", "")
        adr_path = self.session.checkpoint_data.get("adr_path")
        adr_session_id = self.session.checkpoint_data.get("adr_session_id")

        # Simple confirmation → proceed to M2
        if self._is_adr_accept_only(user_input):
            self.session.checkpoint = "M2"
            self._save()
            return None

        # No session_id (legacy session) → fallback
        if not adr_session_id:
            logger.warning(
                "adr_session_id not found in checkpoint_data "
                "(legacy session or expired). User feedback will not be applied. "
                "Falling back to M2."
            )
            self.session.checkpoint = "M2"
            self._save()
            return None

        # Resume session with user feedback to revise ADR
        wt_path = Path(self.session.worktree_path)
        feedback_prompt = (
            f"ユーザーからADRについてフィードバックがありました:\n\n"
            f"{user_input}\n\n"
            f"ADRファイル ({adr_path}) をフィードバックに基づいて修正してください。\n"
            f"修正完了後、ADR_PATH={adr_path} を出力してください。"
        )

        try:
            skill_result = await self._run_skill_step_with_session(
                "ADR: revise", feedback_prompt, wt_path,
                model="opus", resume_session_id=adr_session_id,
            )
        except Exception:
            logger.exception(
                "Failed to resume ADR session (session_id=%s). "
                "Falling back to M2 — user feedback was not applied.",
                adr_session_id,
            )
            self.session.checkpoint = "M2"
            self._save()
            return None

        # Update session_id for potential next resume
        if skill_result.session_id:
            self.session.checkpoint_data["adr_session_id"] = skill_result.session_id

        # Re-check ADR status after revision
        adr_file = wt_path / adr_path
        status = self._read_adr_status(adr_file)
        if status != "accepted":
            self._save()
            return self.make_interaction(
                checkpoint="adr_review",
                question=f"ADR修正後のステータスが '{status}' です。確認してください。",
                options=["確認済み — 続行", "フィードバックを入力"],
                context=f"adr_path={adr_path}",
            )

        # accepted → proceed to M2
        self.session.checkpoint = "M2"
        self._save()
        return None

    # ── M2 cascade review resume ─────────────────────────────────

    async def _handle_m2_cascade_review_resume(self) -> dict[str, Any] | None:
        """Handle resume from m2_cascade_review checkpoint."""
        user_input = self.session.checkpoint_data.get("user_input", "")
        lower = user_input.lower().strip()

        if "中止" in user_input or "abort" in lower:
            return self.make_failed(error_message="ユーザーがパイプラインを中止しました。")

        resume_sid = self.session.checkpoint_data.get("m2_session_id")

        # Simple retry without context
        if "リトライ" in user_input or (not user_input.strip()):
            self.session.checkpoint = "M2"
            self._save()
            return None

        # Feedback with session resume
        if resume_sid and user_input.strip():
            wt_path = Path(self.session.worktree_path)
            feedback_prompt = (
                f"ユーザーからフィードバックがありました:\n\n{user_input}\n\n"
                f"フィードバックに基づいてカスケード処理を修正・再試行してください。\n"
                f"完了したら CASCADE_DONE を、失敗したら CASCADE_FAILED を出力してください。"
            )
            try:
                from ..output_parser import parse_agent_output
                skill_result = await self._run_skill_step_with_session(
                    "M2: cascade-retry", feedback_prompt, wt_path,
                    model="opus", resume_session_id=resume_sid,
                )
                parsed = parse_agent_output(skill_result.text)
                if parsed.cascade_done:
                    self.session.checkpoint = "M3"
                    self._save()
                    return None
                # Re-failed → loop back
                return self._pause_with_session(
                    checkpoint="m2_cascade_review",
                    session_key="m2_session_id",
                    session_id=skill_result.session_id,
                    question="カスケード処理が再度失敗しました。",
                    options=["フィードバックを入力して再試行", "リトライ (コンテキストなし)", "中止"],
                    context=skill_result.text[-2000:],
                )
            except Exception:
                logger.exception("Failed to resume M2 session. Falling back to M2 re-run.")

        # Fallback
        self.session.checkpoint = "M2"
        self._save()
        return None

    # ── Validation triage resume ──────────────────────────────────

    async def _handle_validation_triage_resume(self) -> dict[str, Any] | None:
        """Handle resume from validation_triage checkpoint (modify pipeline)."""
        user_input = self.session.checkpoint_data.get("user_input", "")
        lower = user_input.lower().strip()

        if "abort" in lower or "中止" in lower:
            return self.make_failed(error_message="ユーザーがパイプラインを中止しました。")

        if "retry" in lower or "再実行" in lower:
            self.session.checkpoint = "B"
            self._save()
            return None

        if "conditional" in lower:
            resume_sid = self.session.checkpoint_data.get("b2_session_id")
            if resume_sid and user_input.strip():
                wt_path = Path(self.session.worktree_path)
                record_prompt = (
                    f"ユーザーが Conditional GO を選択しました。理由:\n\n{user_input}\n\n"
                    f"この理由を impl-journal.md に記録してください。"
                )
                await self._run_skill_step_with_session(
                    "B2: conditional-go", record_prompt, wt_path,
                    model="sonnet", resume_session_id=resume_sid,
                )
            self.session.checkpoint = "delivery"
            self._save()
            return None

        # GO or feedback
        resume_sid = self.session.checkpoint_data.get("b2_session_id")
        if "go" in lower or not user_input.strip():
            self.session.checkpoint = "delivery"
            self._save()
            return None

        # Feedback with session resume → re-validate
        if resume_sid and user_input.strip():
            wt_path = Path(self.session.worktree_path)
            feedback_prompt = (
                f"ユーザーからフィードバックがありました:\n\n{user_input}\n\n"
                f"フィードバックに基づいて修正を実行してください。"
            )
            await self._run_skill_step_with_session(
                "B2: feedback", feedback_prompt, wt_path,
                model="sonnet", resume_session_id=resume_sid,
            )
            self.session.checkpoint = "B2"
            self._save()
            return None

        self.session.checkpoint = "B2"
        self._save()
        return None

    # ── M1 review resume ─────────────────────────────────────────

    async def _handle_m1_review_resume(self) -> dict[str, Any] | None:
        """Handle resume from m1_review checkpoint."""
        user_input = self.session.checkpoint_data.get("user_input", "")
        resume_sid = self.session.checkpoint_data.get("m1_session_id")
        pending_output = self.session.checkpoint_data.get("m1_pending_output", "")

        # Simple confirmation → build M1Result from pending output
        if not user_input.strip() or "確認" in user_input or "続行" in user_input:
            if pending_output:
                from ..output_parser import parse_agent_output
                parsed = parse_agent_output(pending_output)
                feature_name = self.session.feature_name or self.session.params.get("feature", "")
                change = self.session.params.get("change", "")
                m1 = M1Result(
                    feature_name=feature_name,
                    change_description=change,
                    m1_output=pending_output,
                    cascade_depth=parsed.cascade_depth,
                    classification=parsed.classification,
                    delta_summary=parsed.delta_summary,
                    adr_required=parsed.adr_required,
                    adr_category=parsed.adr_category,
                    adr_reason=parsed.adr_reason,
                )
                self.session.m1_results = {"single": m1.to_dict()}
                self.session.checkpoint = "worktree"
                self._save()
                return None
            # No pending output — re-run M1
            self.session.checkpoint = "M1"
            self._save()
            return None

        # Feedback with session resume → revised analysis
        if resume_sid and user_input.strip():
            feedback_prompt = (
                f"ユーザーからM1分析についてフィードバックがありました:\n\n{user_input}\n\n"
                f"フィードバックに基づいて分析を修正してください。\n"
                f"修正後は M1_CONFIDENCE: high を出力し、通常の出力形式で結果を出力してください。"
            )
            try:
                from ..output_parser import parse_agent_output
                skill_result = await self._run_skill_step_with_session(
                    "M1: revise", feedback_prompt, self.config.project_root,
                    model="opus", resume_session_id=resume_sid,
                )
                parsed = parse_agent_output(skill_result.text)
                feature_name = self.session.feature_name or self.session.params.get("feature", "")
                change = self.session.params.get("change", "")
                m1 = M1Result(
                    feature_name=feature_name,
                    change_description=change,
                    m1_output=skill_result.text,
                    cascade_depth=parsed.cascade_depth,
                    classification=parsed.classification,
                    delta_summary=parsed.delta_summary,
                    adr_required=parsed.adr_required,
                    adr_category=parsed.adr_category,
                    adr_reason=parsed.adr_reason,
                )
                self.session.m1_results = {"single": m1.to_dict()}
                self.session.checkpoint = "worktree"
                self._save()
                return None
            except Exception:
                logger.exception("Failed to resume M1 session. Falling back to M1 re-run.")

        # Fallback
        self.session.checkpoint = "M1"
        self._save()
        return None

    # ── Single-spec segments ─────────────────────────────────────

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

    async def _seg_resolve(self) -> dict[str, Any] | None:
        """Feature + change resolution."""
        feature_name = self.session.params.get("feature", "")
        change = self.session.params.get("change", "")

        spec_dir = self.config.project_root / ".kiro" / "specs" / feature_name
        if not spec_dir.is_dir():
            available = [
                d.name
                for d in (self.config.project_root / ".kiro" / "specs").iterdir()
                if d.is_dir()
            ]
            return self.make_failed(
                error_message=(
                    f"Feature '{feature_name}' が見つかりません。利用可能:\n"
                    + "\n".join(f"  - {n}" for n in available)
                )
            )

        main_spec = load_spec(spec_dir / "spec.json")
        if main_spec.phase == Phase.INITIALIZED:
            return self.make_failed(
                error_message="要件生成が完了していません。先に implement で要件を生成してください。"
            )

        if not change:
            return self.make_interaction(
                checkpoint="change_description_needed",
                question="どのような変更を加えますか？",
            )

        self.session.feature_name = feature_name
        self._save()
        return None

    async def _seg_M1(self) -> dict[str, Any] | None:
        """M1 change-impact analysis."""
        feature_name = self.session.feature_name or self.session.params.get("feature", "")
        change = self.session.params.get("change", "")

        m1 = await self._run_m1_analysis(feature_name, change)
        if isinstance(m1, dict):
            return m1  # Error response

        self.session.m1_results = {"single": m1.to_dict()}
        self._save()
        return None

    async def _seg_worktree(self) -> dict[str, Any] | None:
        """Worktree setup + resume detection."""
        feature_name = self.session.feature_name or self.session.params.get("feature", "")
        wt_info = create_or_reuse_worktree(
            self.config, "modify", feature_name, self.session.base_branch
        )
        self.session.worktree_path = str(wt_info.path)
        self.session.branch_name = wt_info.branch

        resume_point: MRP | None = None
        if not wt_info.created:
            wt_spec = find_spec_by_name(wt_info.path, feature_name)
            if wt_spec:
                wt_spec.ensure_modifications_field()
                resume_point = detect_modify_resume(wt_spec)

        self.session.checkpoint_data["resume_point"] = resume_point.value if resume_point else ""
        self._save()
        return None

    async def _seg_ADR(self) -> dict[str, Any] | None:
        """ADR gate."""
        resume_point = self.session.checkpoint_data.get("resume_point", "")
        if resume_point and resume_point not in (MRP.ADR_GATE.value,):
            # Already past ADR gate — find existing ADR
            wt_path = Path(self.session.worktree_path)
            feature_name = self.session.feature_name
            adr_path = self._find_existing_adr(wt_path, feature_name)
            self.session.checkpoint_data["adr_path"] = adr_path
            self._save()
            return None

        m1_data = (self.session.m1_results or {}).get("single", {})
        m1 = M1Result.from_dict(m1_data)
        wt_path = Path(self.session.worktree_path)

        result = await self._run_adr_gate(m1, wt_path)
        if isinstance(result, dict):
            return result  # Checkpoint response

        self.session.checkpoint_data["adr_path"] = result
        self._save()
        return None

    async def _seg_M2(self) -> dict[str, Any] | None:
        """M2 cascade."""
        resume_point = self.session.checkpoint_data.get("resume_point", "")
        rp = MRP(resume_point) if resume_point else None
        m1_data = (self.session.m1_results or {}).get("single", {})
        m1 = M1Result.from_dict(m1_data)
        wt_path = Path(self.session.worktree_path)
        adr_path = self.session.checkpoint_data.get("adr_path")

        if rp is not None and rp not in (MRP.ADR_GATE, MRP.M2_CASCADE):
            self.skip_step("M2: cascade", "opus", "resume")
            return None

        extra_params: dict[str, str] = {}
        if adr_path:
            extra_params["ADR_PATH"] = adr_path

        result = await self.run_agent_step(
            AgentStep(
                "M2: cascade",
                "tools/orchestrator/prompts/modify-cascade.md",
                "opus",
                {
                    "WORKTREE_PATH": str(wt_path),
                    "FEATURE_NAME": m1.feature_name,
                    "CHANGE_IMPACT_REPORT": m1.m1_output,
                    "CASCADE_DEPTH": m1.cascade_depth,
                    **extra_params,
                },
            ),
            cwd=wt_path,
        )

        if result.is_error:
            return self.make_error(
                checkpoint="step_M2_failed",
                error=result.error_message,
                step_output=result.output_text[-2000:],
            )

        if result.parsed.cascade_failed:
            return self._pause_with_session(
                checkpoint="m2_cascade_review",
                session_key="m2_session_id",
                session_id=result.session_id,
                question="カスケード処理が失敗しました（design-review REJECT 等）。",
                options=["フィードバックを入力して再試行", "リトライ (コンテキストなし)", "中止"],
                context=result.output_text[-2000:],
            )

        return None

    async def _seg_M2R(self) -> dict[str, Any] | None:
        """M2R: Cascade Review Gate — review changes made by M2 cascade."""
        resume_point = self.session.checkpoint_data.get("resume_point", "")
        rp = MRP(resume_point) if resume_point else None
        wt_path = Path(self.session.worktree_path)
        feature_name = self.session.feature_name or self.session.params.get("feature", "")

        if rp is not None and rp not in (MRP.ADR_GATE, MRP.M2_CASCADE, MRP.M2R_REVIEW):
            self.skip_step("M2R: cascade-review-gate", "sonnet", "resume")
            return None

        m1_data = (self.session.m1_results or {}).get("single", {})
        cascade_depth = m1_data.get("cascade_depth", "")

        # Only show review gate when requirements or design were changed
        if cascade_depth == "requirements-only" or not cascade_depth:
            self.skip_step("M2R: cascade-review-gate", "sonnet", "レビュー不要")
            return None

        # Check for review documents (requirements-review.md / design-review.md)
        spec_dir = wt_path / ".kiro" / "specs" / feature_name
        req_review = spec_dir / "requirements-review.md"
        design_review = spec_dir / "design-review.md"

        review_docs: list[str] = []
        focus_items: list[str] = []

        for doc in (req_review, design_review):
            if doc.exists():
                review_docs.append(str(doc))
                text = doc.read_text()
                focus_items.extend(
                    line.strip() for line in text.splitlines() if "🔴" in line
                )

        if not review_docs:
            # Fallback: no review documents — skip gate
            self.skip_step("M2R: cascade-review-gate", "sonnet", "レビュー文書なし — スキップ")
            return None

        focus_summary = "\n".join(focus_items) if focus_items else "（重大な指摘なし）"
        context = (
            f"変更されたレビュー文書:\n"
            + "\n".join(f"  - {d}" for d in review_docs)
            + f"\n\nカスケード深度: {cascade_depth}"
            + f"\n\nフォーカスエリア（🔴項目）:\n{focus_summary}"
        )

        return self.make_interaction(
            checkpoint="cascade_review_gate",
            question="カスケード更新のレビュー文書が生成されました。変更内容を確認してください。",
            options=["approve — 承認して続行", "feedback — フィードバックを入力"],
            context=context,
        )

    async def _handle_cascade_review_gate_resume(self) -> dict[str, Any] | None:
        """Handle resume from cascade_review_gate checkpoint."""
        user_input = self.session.checkpoint_data.get("user_input", "")

        # Approve → proceed to M3
        if not user_input.strip() or "approve" in user_input.lower() or "承認" in user_input:
            self.session.checkpoint = "M3"
            self._save()
            return None

        # Feedback → re-run M2 with feedback
        wt_path = Path(self.session.worktree_path)
        feedback = user_input.strip()
        m1_data = (self.session.m1_results or {}).get("single", {})
        m1 = M1Result.from_dict(m1_data)
        adr_path = self.session.checkpoint_data.get("adr_path")

        extra_params: dict[str, str] = {}
        if adr_path:
            extra_params["ADR_PATH"] = adr_path

        result = await self.run_agent_step(
            AgentStep(
                "M2: cascade (feedback)",
                "tools/orchestrator/prompts/modify-cascade.md",
                "opus",
                {
                    "WORKTREE_PATH": str(wt_path),
                    "FEATURE_NAME": m1.feature_name,
                    "CHANGE_IMPACT_REPORT": m1.m1_output,
                    "CASCADE_DEPTH": m1.cascade_depth,
                    "USER_FEEDBACK": feedback,
                    **extra_params,
                },
            ),
            cwd=wt_path,
        )

        if result.is_error:
            return self.make_error(
                checkpoint="step_M2_failed",
                error=result.error_message,
                step_output=result.output_text[-2000:],
            )

        # Loop back to M2R to re-check review documents
        self.session.checkpoint = "M2R"
        self._save()
        return None

    async def _seg_M3(self) -> dict[str, Any] | None:
        """M3 delta tasks."""
        resume_point = self.session.checkpoint_data.get("resume_point", "")
        rp = MRP(resume_point) if resume_point else None
        m1_data = (self.session.m1_results or {}).get("single", {})
        m1 = M1Result.from_dict(m1_data)
        wt_path = Path(self.session.worktree_path)

        if m1.cascade_depth == "requirements-only":
            self.skip_step("M3: delta-tasks", "sonnet", "CASCADE_DEPTH=requirements-only")
            return None

        if rp is not None and rp not in (MRP.ADR_GATE, MRP.M2_CASCADE, MRP.M2R_REVIEW, MRP.M3_DELTA_TASKS):
            self.skip_step("M3: delta-tasks", "sonnet", "resume")
            return None

        result = await self.run_agent_step(
            AgentStep(
                "M3: delta-tasks",
                "tools/orchestrator/prompts/modify-tasks.md",
                "sonnet",
                {
                    "WORKTREE_PATH": str(wt_path),
                    "FEATURE_NAME": m1.feature_name,
                    "CHANGE_IMPACT_REPORT": m1.m1_output,
                    "CASCADE_DEPTH": m1.cascade_depth,
                },
            ),
            cwd=wt_path,
        )

        if result.is_error:
            return self.make_error(
                checkpoint="step_M3_failed",
                error=result.error_message,
                step_output=result.output_text[-2000:],
            )

        wt_spec = find_spec_by_name(wt_path, m1.feature_name)
        if wt_spec:
            wt_spec.set_modify_phase(ModifyPhase.DELTA_TASKS_GENERATED)

        return None

    async def _seg_B(self) -> dict[str, Any] | None:
        """B implementation."""
        resume_point = self.session.checkpoint_data.get("resume_point", "")
        rp = MRP(resume_point) if resume_point else None
        m1_data = (self.session.m1_results or {}).get("single", {})
        m1 = M1Result.from_dict(m1_data)
        wt_path = Path(self.session.worktree_path)
        adr_path = self.session.checkpoint_data.get("adr_path")

        if m1.cascade_depth in ("requirements-only", "requirements+design"):
            self.skip_step("B: impl", "sonnet", f"CASCADE_DEPTH={m1.cascade_depth}")
            return None

        if rp is not None and rp not in (MRP.ADR_GATE, MRP.M2_CASCADE, MRP.M3_DELTA_TASKS, MRP.B_IMPL):
            self.skip_step("B: impl", "sonnet", "resume")
            return None

        extra_params: dict[str, str] = {}
        if adr_path:
            extra_params["ADR_PATH"] = adr_path

        result = await self.run_agent_step(
            AgentStep(
                "B: impl",
                "tools/orchestrator/prompts/impl-code.md",
                "sonnet",
                {
                    "WORKTREE_PATH": str(wt_path),
                    "FEATURE_NAME": m1.feature_name,
                    **extra_params,
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

        wt_spec = find_spec_by_name(wt_path, m1.feature_name)
        if wt_spec:
            wt_spec.set_modify_phase(ModifyPhase.IMPL_COMPLETED)

        return None

    async def _seg_B2(self) -> dict[str, Any] | None:
        """B2 validation."""
        resume_point = self.session.checkpoint_data.get("resume_point", "")
        rp = MRP(resume_point) if resume_point else None
        m1_data = (self.session.m1_results or {}).get("single", {})
        m1 = M1Result.from_dict(m1_data)
        wt_path = Path(self.session.worktree_path)

        if m1.cascade_depth == "requirements-only":
            self.skip_step("B2: validate", "opus", "CASCADE_DEPTH=requirements-only")
            return None

        if rp is not None and rp not in (
            MRP.ADR_GATE, MRP.M2_CASCADE, MRP.M3_DELTA_TASKS, MRP.B_IMPL, MRP.B2_VALIDATE,
        ):
            self.skip_step("B2: validate", "opus", "resume")
            return None

        result = await self.run_agent_step(
            AgentStep(
                "B2: validate",
                "tools/orchestrator/prompts/impl-validate.md",
                "opus",
                {"WORKTREE_PATH": str(wt_path), "FEATURE_NAME": m1.feature_name},
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
            return self._pause_with_session(
                checkpoint="validation_triage",
                session_key="b2_session_id",
                session_id=result.session_id,
                question="バリデーションに失敗しました。",
                options=["GO (問題を受容して続行)", "Conditional GO (理由を記録して続行)",
                         "Retry (B から再実行)", "Abort"],
                context=result.output_text[-2000:],
            )

        wt_spec = find_spec_by_name(wt_path, m1.feature_name)
        if wt_spec:
            wt_spec.set_modify_phase(ModifyPhase.VALIDATED)

        return None

    async def _seg_delivery(self) -> dict[str, Any] | None:
        """Steering -> Commit -> L4 -> scene-review -> Push-PR -> Cleanup."""
        m1_data = (self.session.m1_results or {}).get("single", {})
        m1 = M1Result.from_dict(m1_data)
        wt_path = Path(self.session.worktree_path)
        feature_name = m1.feature_name

        # Steering sync
        if m1.cascade_depth not in ("requirements-only",):
            await self._run_steering_sync(wt_path)
        else:
            self.skip_step("steering-sync", "sonnet", "CASCADE_DEPTH=requirements-only")

        # Commit
        result = await self.run_agent_step(
            AgentStep(
                "C: commit",
                "tools/orchestrator/prompts/impl-commit.md",
                "sonnet",
                {
                    "WORKTREE_PATH": str(wt_path),
                    "BRANCH_NAME": self.session.branch_name,
                    "FEATURE_NAME": feature_name,
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

        # L4 check + scene-review
        tasks_md = wt_path / ".kiro" / "specs" / feature_name / "tasks.md"
        has_l4 = tasks_md.exists() and has_l4_human_review(tasks_md.read_text())

        if has_l4 and not self.session.checkpoint_data.get("scene_review_skip"):
            prompt = (
                f"以下のSkillを実行してください:\n"
                f'Skill(skill="kiro:scene-review", args="{feature_name}")\n\n'
                f"結果を報告してください。不合格の項目があれば SCENE_REVIEW_FAILED と出力し、"
                f"全項目合格なら SCENE_REVIEW_PASSED と出力してください。"
            )
            skill_result = await self._run_skill_step_with_session(
                "scene-review", prompt, wt_path, model="sonnet"
            )
            full_text = skill_result.text
            if "SCENE_REVIEW_PASSED" not in full_text:
                return self._pause_with_session(
                    checkpoint="scene_review_failed",
                    session_key="scene_review_session_id",
                    session_id=skill_result.session_id,
                    question="Scene-review に不合格の項目があります。どうしますか？",
                    options=["修正してリトライ (フィードバック可)", "続行 (不合格のまま)", "中止"],
                    context=f"worktree={wt_path}",
                )
        else:
            self.skip_step("scene-review", "-", "L4 タスクなし")

        # Push + PR
        change_summary = m1.delta_summary.split("\n")[0] if m1.delta_summary else m1.change_description[:80]
        result_d = await self.run_agent_step(
            AgentStep(
                "D: push-pr",
                "tools/orchestrator/prompts/impl-push-pr.md",
                "sonnet",
                {
                    "WORKTREE_PATH": str(wt_path),
                    "BRANCH_NAME": self.session.branch_name,
                    "FEATURE_NAME": feature_name,
                    "BASE_BRANCH": self.session.base_branch,
                    "MODIFY_MODE": "true",
                    "CHANGE_SUMMARY": change_summary,
                },
            ),
            cwd=wt_path,
        )

        if result_d.is_error:
            return self.make_error(
                checkpoint="step_D_failed",
                error=result_d.error_message,
                step_output=result_d.output_text[-2000:],
            )

        pr_url = self._extract_pr_url(result_d.output_text)
        self.session.checkpoint_data["pr_url"] = pr_url

        # Update phase and cleanup
        wt_spec = find_spec_by_name(wt_path, feature_name)
        if wt_spec:
            wt_spec.set_modify_phase(ModifyPhase.COMPLETED)

        if pr_url:
            remove_worktree(self.config, wt_path)

        # Cleanup M1 cache
        m1_cache = self.config.project_root / ".claude" / "orchestrator" / f"modify-{feature_name}.json"
        if m1_cache.exists():
            m1_cache.unlink()

        self._save()
        return None

    # ── Completion ───────────────────────────────────────────────

    def _complete_pipeline(self) -> dict[str, Any]:
        m1_data = (self.session.m1_results or {}).get("single", {})
        pr_url = self.session.checkpoint_data.get("pr_url", "")
        return self.make_completed({
            "status": "completed" if pr_url else "push-pr-incomplete",
            "branch": self.session.branch_name,
            "feature": self.session.feature_name,
            "classification": m1_data.get("classification", ""),
            "cascade_depth": m1_data.get("cascade_depth", ""),
            "pr_url": pr_url,
            "worktree": self.session.worktree_path,
        })

    # ══════════════════════════════════════════════════════════════
    # Plan-driven mode
    # ══════════════════════════════════════════════════════════════

    async def _run_plan_mode(self) -> dict[str, Any]:
        cp = self.session.checkpoint

        if cp:
            result = await self._handle_resume(cp)
            if result is not None:
                return result
            cp = self.session.checkpoint

        segments = [
            ("preflight", self._seg_preflight),
            ("plan_setup", self._seg_plan_setup),
            ("plan_M1_all", self._seg_plan_M1_all),
            ("plan_ADR", self._seg_plan_ADR),
            ("plan_impl_all", self._seg_plan_impl_all),
            ("plan_delivery", self._seg_plan_delivery),
        ]

        start_from = cp if cp in [n for n, _ in segments] else ""
        result = await self._run_segments(segments, start_from)
        if result is not None:
            return result

        return self._complete_plan_pipeline()

    async def _seg_plan_setup(self) -> dict[str, Any] | None:
        """Resolve plan directory, parse index, setup worktree."""
        plan_name = self.session.params.get("modify_plan", "")
        plan_dir = self.config.project_root / "docs" / "modify-plans" / plan_name

        if not plan_dir.is_dir():
            return self.make_failed(
                error_message=f"Plan directory not found: docs/modify-plans/{plan_name}"
            )

        index_path = plan_dir / "_index.md"
        if not index_path.exists():
            return self.make_failed(
                error_message=f"_index.md not found in: docs/modify-plans/{plan_name}"
            )

        order = self._parse_execution_order(index_path)
        if not order:
            return self.make_failed(error_message="推奨実行順序のパースに失敗しました。")

        pending = self._get_pending_specs(plan_dir, order)
        if not pending:
            return self.make_completed({
                "status": "all-completed",
                "plan": plan_name,
            })

        self.session.checkpoint_data["plan_dir"] = str(plan_dir)
        self.session.checkpoint_data["order"] = order
        self.session.checkpoint_data["pending"] = pending

        wt_info = create_or_reuse_worktree(
            self.config, "modify", plan_name, self.session.base_branch
        )
        self.session.worktree_path = str(wt_info.path)
        self.session.branch_name = wt_info.branch
        self._save()
        return None

    async def _seg_plan_M1_all(self) -> dict[str, Any] | None:
        """M1 analysis for all pending specs."""
        plan_dir = Path(self.session.checkpoint_data["plan_dir"])
        pending = self.session.checkpoint_data["pending"]

        m1_results: dict[str, dict] = {}
        for spec_name in pending:
            plan_file = plan_dir / f"{spec_name}.md"
            if not plan_file.exists():
                return self.make_failed(
                    error_message=f"Plan file not found: {plan_file}"
                )

            feature_name, change_desc = self._parse_plan_params(plan_file)
            if not feature_name or not change_desc:
                return self.make_failed(
                    error_message=f"{spec_name}.md から実行パラメータを抽出できません。"
                )

            m1 = await self._run_m1_analysis(feature_name, change_desc)
            if isinstance(m1, dict):
                return m1  # Error response
            m1_results[spec_name] = m1.to_dict()

        self.session.m1_results = m1_results
        self._save()
        return None

    async def _seg_plan_ADR(self) -> dict[str, Any] | None:
        """ADR gate for plan mode."""
        m1_results = self.session.m1_results or {}
        wt_path = Path(self.session.worktree_path)

        adr_specs = {
            name: M1Result.from_dict(data)
            for name, data in m1_results.items()
            if data.get("adr_required")
        }
        adr_paths: dict[str, str | None] = {name: None for name in m1_results}

        if not adr_specs:
            self.skip_step("ADR: gate", "sonnet", "No specs require ADR")
            self.session.adr_paths = adr_paths
            self._save()
            return None

        categories = {m1.adr_category for m1 in adr_specs.values()}

        if len(adr_specs) >= 2 and len(categories) == 1:
            # Plan-level ADR: same category -> single combined ADR
            representative = next(iter(adr_specs.values()))
            all_m1_outputs = "\n---\n".join(
                f"## {name}\n{m1.m1_output}" for name, m1 in adr_specs.items()
            )
            combined = M1Result(
                feature_name=", ".join(m1.feature_name for m1 in adr_specs.values()),
                change_description="\n".join(m1.change_description for m1 in adr_specs.values()),
                m1_output=all_m1_outputs,
                cascade_depth=representative.cascade_depth,
                classification=representative.classification,
                delta_summary="\n".join(m1.delta_summary for m1 in adr_specs.values()),
                adr_required=True,
                adr_category=representative.adr_category,
                adr_reason=representative.adr_reason,
            )
            result = await self._run_adr_gate(
                combined, wt_path,
                scope="plan",
                plan_specs=list(adr_specs.keys()),
                all_m1_outputs=all_m1_outputs,
            )
            if isinstance(result, dict):
                return result
            for name in adr_specs:
                adr_paths[name] = result
        else:
            # Per-spec ADRs
            for name, m1 in adr_specs.items():
                result = await self._run_adr_gate(m1, wt_path)
                if isinstance(result, dict):
                    return result
                adr_paths[name] = result

        self.session.adr_paths = adr_paths
        self._save()
        return None

    async def _seg_plan_impl_all(self) -> dict[str, Any] | None:
        """Implementation for all pending specs."""
        pending = self.session.checkpoint_data["pending"]
        plan_dir = Path(self.session.checkpoint_data["plan_dir"])
        m1_results = self.session.m1_results or {}
        wt_path = Path(self.session.worktree_path)
        adr_paths = self.session.adr_paths or {}

        for spec_name in pending:
            m1 = M1Result.from_dict(m1_results[spec_name])
            adr_path = adr_paths.get(spec_name)

            # Run M2, M3, B, B2 for this spec
            result = await self._run_spec_impl(m1, wt_path, adr_path)
            if result is not None:
                return result

            self._mark_spec_completed(plan_dir, spec_name)

        return None

    async def _seg_plan_delivery(self) -> dict[str, Any] | None:
        """Single commit + single PR for all specs."""
        pending = self.session.checkpoint_data["pending"]
        m1_results = self.session.m1_results or {}
        wt_path = Path(self.session.worktree_path)
        first_m1 = M1Result.from_dict(m1_results[pending[0]])
        all_features = [m1_results[s]["feature_name"] for s in pending]
        primary_feature = all_features[0]

        # Steering sync
        if first_m1.cascade_depth not in ("requirements-only",):
            await self._run_steering_sync(wt_path)
        else:
            self.skip_step("steering-sync", "sonnet", "CASCADE_DEPTH=requirements-only")

        # Commit
        result = await self.run_agent_step(
            AgentStep(
                "C: commit",
                "tools/orchestrator/prompts/impl-commit.md",
                "sonnet",
                {
                    "WORKTREE_PATH": str(wt_path),
                    "BRANCH_NAME": self.session.branch_name,
                    "FEATURE_NAME": primary_feature,
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

        # Push + PR
        all_delta = "\n".join(m1_results[s].get("delta_summary", "") for s in pending)
        all_change = "\n".join(m1_results[s].get("change_description", "") for s in pending)
        change_summary = all_delta.split("\n")[0] if all_delta else all_change[:80]

        result_d = await self.run_agent_step(
            AgentStep(
                "D: push-pr",
                "tools/orchestrator/prompts/impl-push-pr.md",
                "sonnet",
                {
                    "WORKTREE_PATH": str(wt_path),
                    "BRANCH_NAME": self.session.branch_name,
                    "FEATURE_NAME": primary_feature,
                    "BASE_BRANCH": self.session.base_branch,
                    "MODIFY_MODE": "true",
                    "CHANGE_SUMMARY": change_summary,
                },
            ),
            cwd=wt_path,
        )

        if result_d.is_error:
            return self.make_error(
                checkpoint="step_D_failed",
                error=result_d.error_message,
                step_output=result_d.output_text[-2000:],
            )

        pr_url = self._extract_pr_url(result_d.output_text)
        self.session.checkpoint_data["pr_url"] = pr_url

        # Update phases and cleanup
        for fname in all_features:
            wt_spec = find_spec_by_name(wt_path, fname)
            if wt_spec:
                wt_spec.set_modify_phase(ModifyPhase.COMPLETED)

        if pr_url:
            remove_worktree(self.config, wt_path)

        # Cleanup M1 caches
        m1_cache_dir = self.config.project_root / ".claude" / "orchestrator"
        for fname in all_features:
            m1_cache_path = m1_cache_dir / f"modify-{fname}.json"
            if m1_cache_path.exists():
                m1_cache_path.unlink()

        self._save()
        return None

    def _complete_plan_pipeline(self) -> dict[str, Any]:
        pr_url = self.session.checkpoint_data.get("pr_url", "")
        plan_name = self.session.params.get("modify_plan", "")
        return self.make_completed({
            "status": "completed" if pr_url else "push-pr-incomplete",
            "plan": plan_name,
            "branch": self.session.branch_name,
            "pr_url": pr_url,
            "worktree": self.session.worktree_path,
        })

    # ══════════════════════════════════════════════════════════════
    # Shared helpers
    # ══════════════════════════════════════════════════════════════

    async def _run_m1_analysis(
        self, feature_name: str, change_description: str
    ) -> M1Result | dict[str, Any]:
        """Run M1 analysis. Returns M1Result on success, response dict on error."""
        result = await self.run_agent_step(
            AgentStep(
                "M1: analysis",
                "tools/orchestrator/prompts/modify-analyze.md",
                "opus",
                {
                    "FEATURE_NAME": feature_name,
                    "CHANGE_DESCRIPTION": change_description,
                },
            ),
            cwd=self.config.project_root,
        )

        if result.is_error:
            return self.make_error(
                checkpoint="step_M1_failed",
                error=result.error_message,
                step_output=result.output_text[-2000:],
            )

        if not result.parsed.analysis_done:
            return self.make_failed(
                error_message="M1: 分析結果のマーカーが見つかりません。"
            )

        if result.parsed.m1_confidence == "low":
            return self._pause_with_session(
                checkpoint="m1_review",
                session_key="m1_session_id",
                session_id=result.session_id,
                question=(
                    f"M1分析の確信度が低い項目があります:\n"
                    f"CLASSIFICATION: {result.parsed.classification}\n"
                    f"CASCADE_DEPTH: {result.parsed.cascade_depth}"
                ),
                options=["確認済み — 続行", "フィードバックを入力"],
                context=result.output_text[-3000:],
                m1_pending_output=result.output_text,
            )

        m1 = M1Result(
            feature_name=feature_name,
            change_description=change_description,
            m1_output=result.output_text,
            cascade_depth=result.parsed.cascade_depth,
            classification=result.parsed.classification,
            delta_summary=result.parsed.delta_summary,
            adr_required=result.parsed.adr_required,
            adr_category=result.parsed.adr_category,
            adr_reason=result.parsed.adr_reason,
        )

        # Persist M1 for crash recovery
        m1_cache_dir = self.config.project_root / ".claude" / "orchestrator"
        m1_cache_dir.mkdir(parents=True, exist_ok=True)
        m1_cache_path = m1_cache_dir / f"modify-{feature_name}.json"
        m1_cache_path.write_text(json.dumps(m1.to_dict(), ensure_ascii=False, indent=2))

        return m1

    async def _run_adr_gate(
        self,
        m1: M1Result,
        wt_path: Path,
        *,
        scope: str = "spec",
        plan_specs: list[str] | None = None,
        all_m1_outputs: str | None = None,
    ) -> str | None | dict[str, Any]:
        """ADR gate. Returns adr_path (str|None) on success, response dict on checkpoint."""
        if not m1.adr_required:
            self.skip_step("ADR: gate", "sonnet", "ADR not required")
            return None

        m1_output = all_m1_outputs if all_m1_outputs else m1.m1_output
        context_parts = [
            f"category={m1.adr_category}",
            f"feature={m1.feature_name}",
            f"{m1.adr_reason}",
        ]
        if scope == "plan" and plan_specs:
            context_parts.append(f"scope=plan specs={','.join(plan_specs)}")

        context_arg = " ".join(context_parts)
        prompt = (
            f"以下のSkillを実行してください:\n"
            f'Skill(skill="kiro:decision-create", args="new {context_arg}")\n\n'
            f"変更の説明:\n{m1.change_description}\n\n"
            f"M1分析サマリー:\n{m1.delta_summary}\n\n"
            f"M1分析全文:\n{m1_output}\n\n"
            f"完了時に必ず ADR_PATH=<作成されたADRファイルの相対パス> を出力してください。"
        )

        skill_result = await self._run_skill_step_with_session(
            "ADR: decision-create", prompt, wt_path, model="opus"
        )
        result_text = skill_result.text

        adr_path = self._extract_adr_path_from_output(result_text)
        if not adr_path:
            adr_path = self._find_new_adr_file(wt_path)
        if not adr_path:
            return self.make_error(
                checkpoint="step_ADR_failed",
                error="ADR was required but decision-create did not produce a file",
            )

        adr_file = wt_path / adr_path
        status = self._read_adr_status(adr_file)

        if status != "accepted":
            self.session.checkpoint_data["adr_path"] = adr_path
            self.session.checkpoint_data["adr_session_id"] = skill_result.session_id
            self._save()
            return self.make_interaction(
                checkpoint="adr_review",
                question=f"ADRのステータスが '{status}' です。確認して修正してください。",
                options=["確認済み — 続行", "フィードバックを入力"],
                context=f"adr_path={adr_path}",
            )

        if scope == "spec":
            wt_spec = find_spec_by_name(wt_path, m1.feature_name)
            if wt_spec:
                wt_spec.set_modify_phase(ModifyPhase.ADR_ACCEPTED)

        return adr_path

    async def _run_spec_impl(
        self,
        m1: M1Result,
        wt_path: Path,
        adr_path: str | None,
    ) -> dict[str, Any] | None:
        """Run M2 -> M3 -> B -> B2 for a single spec. Returns None on success."""
        extra_params: dict[str, str] = {}
        if adr_path:
            extra_params["ADR_PATH"] = adr_path

        # M2 cascade
        result = await self.run_agent_step(
            AgentStep(
                "M2: cascade",
                "tools/orchestrator/prompts/modify-cascade.md",
                "opus",
                {
                    "WORKTREE_PATH": str(wt_path),
                    "FEATURE_NAME": m1.feature_name,
                    "CHANGE_IMPACT_REPORT": m1.m1_output,
                    "CASCADE_DEPTH": m1.cascade_depth,
                    **extra_params,
                },
            ),
            cwd=wt_path,
        )
        if result.is_error:
            return self.make_error(
                checkpoint="step_M2_failed",
                error=result.error_message,
                step_output=result.output_text[-2000:],
            )
        if result.parsed.cascade_failed:
            return self.make_error(
                checkpoint="step_M2_cascade_failed",
                error="Cascade FAILED (design-review REJECT)",
                step_output=result.output_text[-2000:],
            )

        # M3 delta tasks
        if m1.cascade_depth != "requirements-only":
            result = await self.run_agent_step(
                AgentStep(
                    "M3: delta-tasks",
                    "tools/orchestrator/prompts/modify-tasks.md",
                    "sonnet",
                    {
                        "WORKTREE_PATH": str(wt_path),
                        "FEATURE_NAME": m1.feature_name,
                        "CHANGE_IMPACT_REPORT": m1.m1_output,
                        "CASCADE_DEPTH": m1.cascade_depth,
                    },
                ),
                cwd=wt_path,
            )
            if result.is_error:
                return self.make_error(
                    checkpoint="step_M3_failed",
                    error=result.error_message,
                    step_output=result.output_text[-2000:],
                )
            wt_spec = find_spec_by_name(wt_path, m1.feature_name)
            if wt_spec:
                wt_spec.set_modify_phase(ModifyPhase.DELTA_TASKS_GENERATED)

        # B impl
        if m1.cascade_depth not in ("requirements-only", "requirements+design"):
            result = await self.run_agent_step(
                AgentStep(
                    "B: impl",
                    "tools/orchestrator/prompts/impl-code.md",
                    "sonnet",
                    {
                        "WORKTREE_PATH": str(wt_path),
                        "FEATURE_NAME": m1.feature_name,
                        **extra_params,
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
            wt_spec = find_spec_by_name(wt_path, m1.feature_name)
            if wt_spec:
                wt_spec.set_modify_phase(ModifyPhase.IMPL_COMPLETED)

        # B2 validate
        if m1.cascade_depth != "requirements-only":
            result = await self.run_agent_step(
                AgentStep(
                    "B2: validate",
                    "tools/orchestrator/prompts/impl-validate.md",
                    "opus",
                    {"WORKTREE_PATH": str(wt_path), "FEATURE_NAME": m1.feature_name},
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
                )
            wt_spec = find_spec_by_name(wt_path, m1.feature_name)
            if wt_spec:
                wt_spec.set_modify_phase(ModifyPhase.VALIDATED)

        return None

    # ── Static helpers ───────────────────────────────────────────

    @staticmethod
    def _parse_execution_order(index_path: Path) -> list[str]:
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
    def _get_pending_specs(plan_dir: Path, order: list[str]) -> list[str]:
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

    @staticmethod
    def _read_adr_status(adr_file: Path) -> str | None:
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

    @staticmethod
    def _extract_adr_path_from_output(text: str) -> str | None:
        m = re.search(r"ADR_PATH=(\S+)", text)
        return m.group(1) if m else None

    @staticmethod
    def _find_new_adr_file(wt_path: Path) -> str | None:
        import subprocess

        decisions_dir = wt_path / ".kiro" / "decisions"
        if not decisions_dir.exists():
            return None
        result = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=A", "HEAD"],
            cwd=str(wt_path),
            capture_output=True,
            text=True,
        )
        new_files = [
            f for f in result.stdout.strip().splitlines()
            if f.startswith(".kiro/decisions/") and f.endswith(".md")
        ]
        if not new_files:
            all_adrs = sorted(decisions_dir.rglob("*.md"), key=lambda p: p.stat().st_mtime)
            if all_adrs:
                return str(all_adrs[-1].relative_to(wt_path))
            return None
        new_files.sort()
        return new_files[-1]

    @staticmethod
    def _find_existing_adr(wt_path: Path, feature_name: str) -> str | None:
        decisions_dir = wt_path / ".kiro" / "decisions"
        if not decisions_dir.exists():
            return None
        re_status = re.compile(r"^status:\s*accepted\s*$", re.MULTILINE)
        re_spec = re.compile(
            r"^spec:\s*[\"']?" + re.escape(feature_name) + r"[\"']?\s*$", re.MULTILINE
        )
        re_specs = re.compile(
            r"^specs:\s*\[.*?" + re.escape(feature_name) + r".*?\]", re.MULTILINE
        )
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

    @staticmethod
    def _extract_pr_url(text: str) -> str:
        m = re.search(r"https://github\.com/\S+/pull/\d+", text)
        return m.group(0) if m else ""
