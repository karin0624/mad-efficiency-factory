"""Tests for session resume patterns across pipelines.

Tests the resume handlers for:
- F1: B2 Validation Triage (implement + modify)
- F2: A2 Design Review (implement)
- F3: L4 Scene Review (implement + modify)
- F4: M1 Impact Analysis (modify)
- F5: M2 Cascade Recovery (modify)
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Stub claude_agent_sdk before importing the pipeline module
_sdk_stub = ModuleType("claude_agent_sdk")
for attr in (
    "AssistantMessage", "ClaudeAgentOptions", "ClaudeSDKClient",
    "ResultMessage", "TextBlock", "ToolResultBlock", "ToolUseBlock",
    "UserMessage", "query",
):
    setattr(_sdk_stub, attr, MagicMock())
sys.modules.setdefault("claude_agent_sdk", _sdk_stub)

from tools.orchestrator.pipeline import SkillStepResult  # noqa: E402
from tools.orchestrator.session import PipelineSession  # noqa: E402


def _run(coro):
    """Helper to run async coroutine in sync test."""
    return asyncio.run(coro)


# ── Helpers ──────────────────────────────────────────────────────

def _make_implement_pipeline(**session_overrides):
    """Create an ImplementPipeline with mocked dependencies."""
    from tools.orchestrator.pipelines.implement import ImplementPipeline

    config = MagicMock()
    config.project_root = Path("/tmp/test-project")

    session_data = {
        "session_id": "test-impl-session",
        "pipeline": "implement",
        "checkpoint": "",
        "status": "paused",
        "checkpoint_data": {},
        "worktree_path": "/tmp/test-worktree",
        "branch_name": "feat/test",
        "feature_name": "test-feature",
    }
    session_data.update(session_overrides)
    session = PipelineSession(**session_data)

    pipeline = ImplementPipeline(config, session, Path("/tmp/sessions"))
    pipeline._save = MagicMock()
    return pipeline


def _make_modify_pipeline(**session_overrides):
    """Create a ModifyPipeline with mocked dependencies."""
    from tools.orchestrator.pipelines.modify import ModifyPipeline

    config = MagicMock()
    config.project_root = Path("/tmp/test-project")

    session_data = {
        "session_id": "test-mod-session",
        "pipeline": "modify",
        "checkpoint": "",
        "status": "paused",
        "checkpoint_data": {},
        "worktree_path": "/tmp/test-worktree",
        "branch_name": "modify/test",
        "feature_name": "test-feature",
        "params": {"feature": "test-feature", "change": "test change"},
        "m1_results": {"single": {
            "feature_name": "test-feature",
            "change_description": "test change",
            "m1_output": "test output",
            "cascade_depth": "requirements+design+tasks",
            "classification": "major",
            "delta_summary": "test summary",
            "adr_required": False,
            "adr_category": "",
            "adr_reason": "",
        }},
    }
    session_data.update(session_overrides)
    session = PipelineSession(**session_data)

    pipeline = ModifyPipeline(config, session, Path("/tmp/sessions"))
    pipeline._save = MagicMock()
    return pipeline


# ══════════════════════════════════════════════════════════════════
# F3: L4 Scene Review
# ══════════════════════════════════════════════════════════════════

class TestSceneReviewResumeImplement:
    """scene_review_failed resume in implement pipeline."""

    def test_continue_proceeds_to_D(self):
        p = _make_implement_pipeline(
            checkpoint="scene_review_failed",
            checkpoint_data={"user_input": "続行"},
        )
        result = _run(p._handle_scene_review_resume())
        assert result is None
        assert p.session.checkpoint == "D"

    def test_abort_fails_pipeline(self):
        p = _make_implement_pipeline(
            checkpoint="scene_review_failed",
            checkpoint_data={"user_input": "中止"},
        )
        result = _run(p._handle_scene_review_resume())
        assert result is not None
        assert result["type"] == "pipeline_failed"

    def test_feedback_with_session_id_resumes(self):
        p = _make_implement_pipeline(
            checkpoint="scene_review_failed",
            checkpoint_data={
                "user_input": "ヘッダーの色を修正してください",
                "scene_review_session_id": "sid-scene-123",
            },
        )
        p._run_skill_step_with_session = AsyncMock(
            return_value=SkillStepResult(text="fixed", session_id="sid-scene-456")
        )
        result = _run(p._handle_scene_review_resume())
        assert result is None
        assert p.session.checkpoint == "L4"
        p._run_skill_step_with_session.assert_called_once()

    def test_retry_without_session_id_falls_back(self):
        p = _make_implement_pipeline(
            checkpoint="scene_review_failed",
            checkpoint_data={"user_input": "修正してリトライ"},
        )
        result = _run(p._handle_scene_review_resume())
        assert result is None
        assert p.session.checkpoint == "L4"


class TestSceneReviewResumeModify:
    """scene_review_failed resume in modify pipeline."""

    def test_continue_sets_delivery_push(self):
        p = _make_modify_pipeline(
            checkpoint="scene_review_failed",
            checkpoint_data={"user_input": "続行"},
        )
        result = _run(p._handle_scene_review_resume())
        assert result is None
        assert p.session.checkpoint_data.get("scene_review_skip") is True

    def test_feedback_with_session_id_resumes(self):
        p = _make_modify_pipeline(
            checkpoint="scene_review_failed",
            checkpoint_data={
                "user_input": "ボタンの位置を調整",
                "scene_review_session_id": "sid-mod-scene",
            },
        )
        p._run_skill_step_with_session = AsyncMock(
            return_value=SkillStepResult(text="done", session_id="sid-mod-scene-2")
        )
        result = _run(p._handle_scene_review_resume())
        assert result is None
        assert p.session.checkpoint == "delivery"


# ══════════════════════════════════════════════════════════════════
# F5: M2 Cascade Recovery
# ══════════════════════════════════════════════════════════════════

class TestM2CascadeReviewResume:
    """m2_cascade_review resume in modify pipeline."""

    def test_abort_fails(self):
        p = _make_modify_pipeline(
            checkpoint="m2_cascade_review",
            checkpoint_data={"user_input": "中止"},
        )
        result = _run(p._handle_m2_cascade_review_resume())
        assert result["type"] == "pipeline_failed"

    def test_simple_retry_reruns_m2(self):
        p = _make_modify_pipeline(
            checkpoint="m2_cascade_review",
            checkpoint_data={"user_input": "リトライ"},
        )
        result = _run(p._handle_m2_cascade_review_resume())
        assert result is None
        assert p.session.checkpoint == "M2"

    def test_feedback_cascade_done_proceeds_to_m3(self):
        p = _make_modify_pipeline(
            checkpoint="m2_cascade_review",
            checkpoint_data={
                "user_input": "デザインのセクション3を修正して再試行",
                "m2_session_id": "sid-m2-123",
            },
        )
        p._run_skill_step_with_session = AsyncMock(
            return_value=SkillStepResult(
                text="修正完了\nCASCADE_DONE\n", session_id="sid-m2-456"
            )
        )
        result = _run(p._handle_m2_cascade_review_resume())
        assert result is None
        assert p.session.checkpoint == "M3"

    def test_feedback_cascade_re_failed_loops_back(self):
        p = _make_modify_pipeline(
            checkpoint="m2_cascade_review",
            checkpoint_data={
                "user_input": "別のアプローチで再試行",
                "m2_session_id": "sid-m2-123",
            },
        )
        p._run_skill_step_with_session = AsyncMock(
            return_value=SkillStepResult(
                text="CASCADE_FAILED\nまだ問題あり", session_id="sid-m2-789"
            )
        )
        result = _run(p._handle_m2_cascade_review_resume())
        assert result is not None
        assert result["type"] == "interaction_required"
        assert result["current_step"] == "m2_cascade_review"

    def test_no_session_id_fallback(self):
        p = _make_modify_pipeline(
            checkpoint="m2_cascade_review",
            checkpoint_data={"user_input": "何か修正してください"},
        )
        result = _run(p._handle_m2_cascade_review_resume())
        assert result is None
        assert p.session.checkpoint == "M2"


# ══════════════════════════════════════════════════════════════════
# F1: B2 Validation Triage
# ══════════════════════════════════════════════════════════════════

class TestValidationTriageResumeImplement:
    """validation_triage resume in implement pipeline."""

    def test_abort(self):
        p = _make_implement_pipeline(
            checkpoint="validation_triage",
            checkpoint_data={"user_input": "Abort"},
        )
        result = _run(p._handle_validation_triage_resume())
        assert result["type"] == "pipeline_failed"

    def test_retry_goes_to_B(self):
        p = _make_implement_pipeline(
            checkpoint="validation_triage",
            checkpoint_data={"user_input": "Retry (B から再実行)"},
        )
        result = _run(p._handle_validation_triage_resume())
        assert result is None
        assert p.session.checkpoint == "B"

    def test_go_proceeds_to_steering(self):
        p = _make_implement_pipeline(
            checkpoint="validation_triage",
            checkpoint_data={"user_input": "GO"},
        )
        result = _run(p._handle_validation_triage_resume())
        assert result is None
        assert p.session.checkpoint == "steering"

    def test_conditional_go_with_session(self):
        p = _make_implement_pipeline(
            checkpoint="validation_triage",
            checkpoint_data={
                "user_input": "Conditional GO: テスト環境の制約により一部テスト不通過を許容",
                "b2_session_id": "sid-b2-123",
            },
        )
        p._run_skill_step_with_session = AsyncMock(
            return_value=SkillStepResult(text="recorded", session_id="sid-b2-456")
        )
        result = _run(p._handle_validation_triage_resume())
        assert result is None
        assert p.session.checkpoint == "steering"
        p._run_skill_step_with_session.assert_called_once()

    def test_feedback_with_session_re_validates(self):
        p = _make_implement_pipeline(
            checkpoint="validation_triage",
            checkpoint_data={
                "user_input": "テストAのアサーションを修正してください",
                "b2_session_id": "sid-b2-123",
            },
        )
        p._run_skill_step_with_session = AsyncMock(
            return_value=SkillStepResult(text="fixed", session_id="sid-b2-456")
        )
        result = _run(p._handle_validation_triage_resume())
        assert result is None
        assert p.session.checkpoint == "B2"


class TestValidationTriageResumeModify:
    """validation_triage resume in modify pipeline."""

    def test_go_proceeds_to_delivery(self):
        p = _make_modify_pipeline(
            checkpoint="validation_triage",
            checkpoint_data={"user_input": "GO"},
        )
        result = _run(p._handle_validation_triage_resume())
        assert result is None
        assert p.session.checkpoint == "delivery"


# ══════════════════════════════════════════════════════════════════
# F4: M1 Impact Analysis
# ══════════════════════════════════════════════════════════════════

class TestM1ReviewResume:
    """m1_review resume in modify pipeline."""

    _PENDING_OUTPUT = (
        "ANALYSIS_DONE\n"
        "CLASSIFICATION: major\n"
        "CHANGE_TYPE: modifying\n"
        "CASCADE_DEPTH: requirements+design+tasks\n"
        "AFFECTED_REQUIREMENTS: 1, 2\n"
        "AFFECTED_DESIGN_SECTIONS: Components/Test\n"
        "AFFECTED_TASKS: 3.1\n"
        "M1_CONFIDENCE: low\n"
        "ADR_REQUIRED: no\n"
        "ADR_CATEGORY: spec\n"
        "ADR_REASON: none\n"
        "DELTA_SUMMARY_START\nTest change\nDELTA_SUMMARY_END\n"
    )

    def test_confirm_builds_m1_result(self):
        p = _make_modify_pipeline(
            checkpoint="m1_review",
            checkpoint_data={
                "user_input": "確認済み — 続行",
                "m1_pending_output": self._PENDING_OUTPUT,
            },
        )
        result = _run(p._handle_m1_review_resume())
        assert result is None
        assert p.session.checkpoint == "worktree"
        assert p.session.m1_results is not None
        m1 = p.session.m1_results["single"]
        assert m1["classification"] == "major"
        assert m1["cascade_depth"] == "requirements+design+tasks"

    def test_confirm_without_pending_reruns_m1(self):
        p = _make_modify_pipeline(
            checkpoint="m1_review",
            checkpoint_data={"user_input": "確認済み"},
        )
        result = _run(p._handle_m1_review_resume())
        assert result is None
        assert p.session.checkpoint == "M1"

    def test_feedback_with_session_revises(self):
        revised_output = (
            "ANALYSIS_DONE\n"
            "CLASSIFICATION: minor\n"
            "CHANGE_TYPE: additive\n"
            "CASCADE_DEPTH: requirements+design\n"
            "AFFECTED_REQUIREMENTS: 1\n"
            "AFFECTED_DESIGN_SECTIONS: Components/Test\n"
            "AFFECTED_TASKS: none\n"
            "M1_CONFIDENCE: high\n"
            "ADR_REQUIRED: no\n"
            "ADR_CATEGORY: spec\n"
            "ADR_REASON: none\n"
            "DELTA_SUMMARY_START\nRevised change\nDELTA_SUMMARY_END\n"
        )
        p = _make_modify_pipeline(
            checkpoint="m1_review",
            checkpoint_data={
                "user_input": "CLASSIFICATIONはminorで良いです",
                "m1_session_id": "sid-m1-123",
                "m1_pending_output": self._PENDING_OUTPUT,
            },
        )
        p._run_skill_step_with_session = AsyncMock(
            return_value=SkillStepResult(text=revised_output, session_id="sid-m1-456")
        )
        result = _run(p._handle_m1_review_resume())
        assert result is None
        assert p.session.checkpoint == "worktree"
        m1 = p.session.m1_results["single"]
        assert m1["classification"] == "minor"
        assert m1["cascade_depth"] == "requirements+design"

    def test_legacy_fallback_no_session_id(self):
        p = _make_modify_pipeline(
            checkpoint="m1_review",
            checkpoint_data={
                "user_input": "分析を修正してください",
            },
        )
        result = _run(p._handle_m1_review_resume())
        assert result is None
        assert p.session.checkpoint == "M1"


# ══════════════════════════════════════════════════════════════════
# F2: A2 Design Review
# ══════════════════════════════════════════════════════════════════

class TestDesignReviewResume:
    """design_review resume in implement pipeline."""

    def test_confirm_proceeds_to_A3(self):
        p = _make_implement_pipeline(
            checkpoint="design_review",
            checkpoint_data={"user_input": "確認済み — 続行"},
        )
        result = _run(p._handle_design_review_resume())
        assert result is None
        assert p.session.checkpoint == "A3"

    def test_empty_input_proceeds_to_A3(self):
        p = _make_implement_pipeline(
            checkpoint="design_review",
            checkpoint_data={"user_input": ""},
        )
        result = _run(p._handle_design_review_resume())
        assert result is None
        assert p.session.checkpoint == "A3"

    def test_feedback_with_session_applies_and_proceeds(self):
        p = _make_implement_pipeline(
            checkpoint="design_review",
            checkpoint_data={
                "user_input": "セクション3のAPIエンドポイントを変更してください",
                "a2_session_id": "sid-a2-123",
            },
        )
        p._run_skill_step_with_session = AsyncMock(
            return_value=SkillStepResult(text="APPROVE\n修正完了", session_id="sid-a2-456")
        )
        result = _run(p._handle_design_review_resume())
        assert result is None
        assert p.session.checkpoint == "A3"

    def test_feedback_with_reject_returns_error(self):
        p = _make_implement_pipeline(
            checkpoint="design_review",
            checkpoint_data={
                "user_input": "根本的に設計を変えてください",
                "a2_session_id": "sid-a2-123",
            },
        )
        p._run_skill_step_with_session = AsyncMock(
            return_value=SkillStepResult(text="REJECT\n設計に根本的な問題", session_id="sid-a2-456")
        )
        result = _run(p._handle_design_review_resume())
        assert result is not None
        assert result["type"] == "error_occurred"

    def test_legacy_fallback_no_session_id(self):
        p = _make_implement_pipeline(
            checkpoint="design_review",
            checkpoint_data={"user_input": "何か修正して"},
        )
        result = _run(p._handle_design_review_resume())
        assert result is None
        assert p.session.checkpoint == "A3"


# ══════════════════════════════════════════════════════════════════
# F6: A1R Requirements Review Gate
# ══════════════════════════════════════════════════════════════════

class TestRequirementsReviewResume:
    """requirements_review resume in implement pipeline."""

    def test_approve_proceeds_to_A2(self):
        p = _make_implement_pipeline(
            checkpoint="requirements_review",
            checkpoint_data={"user_input": "approve — 承認して続行"},
        )
        with patch("tools.orchestrator.pipelines.implement.find_spec_in_worktree", return_value=None):
            result = _run(p._handle_requirements_review_resume())
        assert result is None
        assert p.session.checkpoint == "A2"

    def test_empty_input_approves(self):
        p = _make_implement_pipeline(
            checkpoint="requirements_review",
            checkpoint_data={"user_input": ""},
        )
        with patch("tools.orchestrator.pipelines.implement.find_spec_in_worktree", return_value=None):
            result = _run(p._handle_requirements_review_resume())
        assert result is None
        assert p.session.checkpoint == "A2"

    def test_approve_marks_spec_review(self):
        mock_spec = MagicMock()
        mock_spec.raw = {}
        p = _make_implement_pipeline(
            checkpoint="requirements_review",
            checkpoint_data={"user_input": "承認"},
        )
        with patch("tools.orchestrator.pipelines.implement.find_spec_in_worktree", return_value=mock_spec):
            result = _run(p._handle_requirements_review_resume())
        assert result is None
        assert p.session.checkpoint == "A2"
        assert mock_spec.raw["review"]["requirements_approved"] is True
        mock_spec.save.assert_called_once()

    def test_feedback_reruns_A1(self):
        p = _make_implement_pipeline(
            checkpoint="requirements_review",
            checkpoint_data={
                "user_input": "要件3にセキュリティ要件を追加してください",
                "plan_path": "/tmp/plan.md",
            },
        )
        mock_result = MagicMock()
        mock_result.is_error = False
        p.run_agent_step = AsyncMock(return_value=mock_result)
        result = _run(p._handle_requirements_review_resume())
        assert result is None
        assert p.session.checkpoint == "A1R"
        p.run_agent_step.assert_called_once()

    def test_feedback_with_A1_error_returns_error(self):
        p = _make_implement_pipeline(
            checkpoint="requirements_review",
            checkpoint_data={
                "user_input": "要件を全部やり直して",
                "plan_path": "/tmp/plan.md",
            },
        )
        mock_result = MagicMock()
        mock_result.is_error = True
        mock_result.error_message = "Agent failed"
        mock_result.output_text = "error output"
        p.run_agent_step = AsyncMock(return_value=mock_result)
        result = _run(p._handle_requirements_review_resume())
        assert result is not None
        assert result["type"] == "error_occurred"


# ══════════════════════════════════════════════════════════════════
# F7: A2R Design Review Gate
# ══════════════════════════════════════════════════════════════════

class TestDesignReviewGateResume:
    """design_review_gate resume in implement pipeline."""

    def test_approve_proceeds_to_A3(self):
        p = _make_implement_pipeline(
            checkpoint="design_review_gate",
            checkpoint_data={"user_input": "approve — 承認して続行"},
        )
        with patch("tools.orchestrator.pipelines.implement.find_spec_in_worktree", return_value=None):
            result = _run(p._handle_design_review_gate_resume())
        assert result is None
        assert p.session.checkpoint == "A3"

    def test_empty_input_approves(self):
        p = _make_implement_pipeline(
            checkpoint="design_review_gate",
            checkpoint_data={"user_input": ""},
        )
        with patch("tools.orchestrator.pipelines.implement.find_spec_in_worktree", return_value=None):
            result = _run(p._handle_design_review_gate_resume())
        assert result is None
        assert p.session.checkpoint == "A3"

    def test_approve_marks_spec_review(self):
        mock_spec = MagicMock()
        mock_spec.raw = {}
        p = _make_implement_pipeline(
            checkpoint="design_review_gate",
            checkpoint_data={"user_input": "承認"},
        )
        with patch("tools.orchestrator.pipelines.implement.find_spec_in_worktree", return_value=mock_spec):
            result = _run(p._handle_design_review_gate_resume())
        assert result is None
        assert p.session.checkpoint == "A3"
        assert mock_spec.raw["review"]["design_approved"] is True
        mock_spec.save.assert_called_once()

    def test_feedback_reruns_A2(self):
        p = _make_implement_pipeline(
            checkpoint="design_review_gate",
            checkpoint_data={"user_input": "コンポーネント分割を見直してください"},
        )
        mock_result = MagicMock()
        mock_result.is_error = False
        p.run_agent_step = AsyncMock(return_value=mock_result)
        result = _run(p._handle_design_review_gate_resume())
        assert result is None
        assert p.session.checkpoint == "A2R"
        p.run_agent_step.assert_called_once()

    def test_feedback_with_A2_error_returns_error(self):
        p = _make_implement_pipeline(
            checkpoint="design_review_gate",
            checkpoint_data={"user_input": "設計を全部やり直して"},
        )
        mock_result = MagicMock()
        mock_result.is_error = True
        mock_result.error_message = "Agent failed"
        mock_result.output_text = "error output"
        p.run_agent_step = AsyncMock(return_value=mock_result)
        result = _run(p._handle_design_review_gate_resume())
        assert result is not None
        assert result["type"] == "error_occurred"


# ══════════════════════════════════════════════════════════════════
# F8: M2R Cascade Review Gate (modify)
# ══════════════════════════════════════════════════════════════════

class TestCascadeReviewGateResume:
    """cascade_review_gate resume in modify pipeline."""

    def test_approve_proceeds_to_M3(self):
        p = _make_modify_pipeline(
            checkpoint="cascade_review_gate",
            checkpoint_data={"user_input": "approve — 承認して続行"},
        )
        result = _run(p._handle_cascade_review_gate_resume())
        assert result is None
        assert p.session.checkpoint == "M3"

    def test_empty_input_approves(self):
        p = _make_modify_pipeline(
            checkpoint="cascade_review_gate",
            checkpoint_data={"user_input": ""},
        )
        result = _run(p._handle_cascade_review_gate_resume())
        assert result is None
        assert p.session.checkpoint == "M3"

    def test_feedback_reruns_M2(self):
        p = _make_modify_pipeline(
            checkpoint="cascade_review_gate",
            checkpoint_data={"user_input": "デザインの依存関係を見直してください"},
        )
        mock_result = MagicMock()
        mock_result.is_error = False
        p.run_agent_step = AsyncMock(return_value=mock_result)
        result = _run(p._handle_cascade_review_gate_resume())
        assert result is None
        assert p.session.checkpoint == "M2R"
        p.run_agent_step.assert_called_once()

    def test_feedback_with_M2_error_returns_error(self):
        p = _make_modify_pipeline(
            checkpoint="cascade_review_gate",
            checkpoint_data={"user_input": "カスケード更新をやり直して"},
        )
        mock_result = MagicMock()
        mock_result.is_error = True
        mock_result.error_message = "Cascade failed"
        mock_result.output_text = "error output"
        p.run_agent_step = AsyncMock(return_value=mock_result)
        result = _run(p._handle_cascade_review_gate_resume())
        assert result is not None
        assert result["type"] == "error_occurred"
