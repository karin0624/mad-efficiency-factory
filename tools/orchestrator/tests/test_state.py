"""Tests for state.py — resume detection, spec.json read/write."""

import json
import pytest
from pathlib import Path

from tools.orchestrator.state import (
    Phase,
    ModifyPhase,
    ImplementResumePoint as IRP,
    ModifyResumePoint as MRP,
    SpecState,
    detect_implement_resume,
    detect_modify_resume,
    find_spec_in_worktree,
    find_spec_by_name,
    load_spec,
)


@pytest.fixture
def tmp_spec(tmp_path: Path):
    """Create a minimal spec.json and return its path."""
    def _make(data: dict) -> SpecState:
        spec_dir = tmp_path / ".kiro" / "specs" / data.get("feature_name", "test-feature")
        spec_dir.mkdir(parents=True, exist_ok=True)
        spec_json = spec_dir / "spec.json"
        spec_json.write_text(json.dumps(data, indent=2))
        return load_spec(spec_json)
    return _make


# ── Implement resume detection ────────────────────────────────────

class TestDetectImplementResume:
    """Test all 7+ resume point patterns from implement.md."""

    def test_validated_resumes_at_tests(self, tmp_spec):
        spec = tmp_spec({"feature_name": "f", "phase": "validated", "approvals": {}})
        assert detect_implement_resume(spec) == IRP.T_TESTS

    def test_impl_completed_resumes_at_validate(self, tmp_spec):
        spec = tmp_spec({"feature_name": "f", "phase": "impl-completed", "approvals": {}})
        assert detect_implement_resume(spec) == IRP.B2_VALIDATE

    def test_tasks_generated_approved_resumes_at_impl(self, tmp_spec):
        spec = tmp_spec({
            "feature_name": "f",
            "phase": "tasks-generated",
            "approvals": {"tasks": {"approved": True}},
        })
        assert detect_implement_resume(spec) == IRP.B_IMPL

    def test_tasks_generated_unapproved_resumes_at_tasks_approval(self, tmp_spec):
        spec = tmp_spec({
            "feature_name": "f",
            "phase": "tasks-generated",
            "approvals": {"tasks": {"approved": False}},
        })
        assert detect_implement_resume(spec) == IRP.A3_TASKS_APPROVAL

    def test_design_generated_codex_reviewed_resumes_at_tasks(self, tmp_spec):
        spec = tmp_spec({
            "feature_name": "f",
            "phase": "design-generated",
            "approvals": {"design": {"codex_reviewed": True}},
        })
        assert detect_implement_resume(spec) == IRP.A3_TASKS

    def test_design_generated_not_reviewed_resumes_at_review(self, tmp_spec):
        spec = tmp_spec({
            "feature_name": "f",
            "phase": "design-generated",
            "approvals": {"design": {"codex_reviewed": False}},
        })
        assert detect_implement_resume(spec) == IRP.A2_HOW_REVIEW_ONLY

    def test_requirements_generated_resumes_at_how(self, tmp_spec):
        spec = tmp_spec({"feature_name": "f", "phase": "requirements-generated", "approvals": {}})
        assert detect_implement_resume(spec) == IRP.A2_HOW_FULL

    def test_initialized_resumes_at_what_phase2(self, tmp_spec):
        spec = tmp_spec({"feature_name": "f", "phase": "initialized", "approvals": {}})
        assert detect_implement_resume(spec) == IRP.A1_WHAT_PHASE2


# ── Modify resume detection ───────────────────────────────────────

class TestDetectModifyResume:
    """Test all 5 modify resume patterns from modify.md."""

    def test_no_modifications_returns_none(self, tmp_spec):
        spec = tmp_spec({"feature_name": "f", "phase": "tasks-generated", "approvals": {}})
        assert detect_modify_resume(spec) is None

    def test_empty_modifications_returns_none(self, tmp_spec):
        spec = tmp_spec({
            "feature_name": "f", "phase": "tasks-generated",
            "approvals": {}, "modifications": [],
        })
        assert detect_modify_resume(spec) is None

    def test_analysis_completed_resumes_at_adr_gate(self, tmp_spec):
        spec = tmp_spec({
            "feature_name": "f", "phase": "tasks-generated", "approvals": {},
            "modifications": [{"modify_phase": "analysis-completed"}],
        })
        assert detect_modify_resume(spec) == MRP.ADR_GATE

    def test_spec_cascaded_resumes_at_delta_tasks(self, tmp_spec):
        spec = tmp_spec({
            "feature_name": "f", "phase": "tasks-generated", "approvals": {},
            "modifications": [{"modify_phase": "spec-cascaded"}],
        })
        assert detect_modify_resume(spec) == MRP.M3_DELTA_TASKS

    def test_delta_tasks_generated_resumes_at_impl(self, tmp_spec):
        spec = tmp_spec({
            "feature_name": "f", "phase": "tasks-generated", "approvals": {},
            "modifications": [{"modify_phase": "delta-tasks-generated"}],
        })
        assert detect_modify_resume(spec) == MRP.B_IMPL

    def test_impl_completed_resumes_at_validate(self, tmp_spec):
        spec = tmp_spec({
            "feature_name": "f", "phase": "tasks-generated", "approvals": {},
            "modifications": [{"modify_phase": "impl-completed"}],
        })
        assert detect_modify_resume(spec) == MRP.B2_VALIDATE

    def test_validated_resumes_at_tests(self, tmp_spec):
        spec = tmp_spec({
            "feature_name": "f", "phase": "tasks-generated", "approvals": {},
            "modifications": [{"modify_phase": "validated"}],
        })
        assert detect_modify_resume(spec) == MRP.T_TESTS

    def test_completed_returns_none(self, tmp_spec):
        """completed modify_phase means nothing to resume."""
        spec = tmp_spec({
            "feature_name": "f", "phase": "tasks-generated", "approvals": {},
            "modifications": [{"modify_phase": "completed"}],
        })
        assert detect_modify_resume(spec) is None

    def test_uses_last_modification(self, tmp_spec):
        """Should always check the LAST modification entry."""
        spec = tmp_spec({
            "feature_name": "f", "phase": "tasks-generated", "approvals": {},
            "modifications": [
                {"modify_phase": "completed"},
                {"modify_phase": "analysis-completed"},
            ],
        })
        assert detect_modify_resume(spec) == MRP.ADR_GATE


# ── Spec state operations ─────────────────────────────────────────

class TestSpecState:
    def test_save_and_reload(self, tmp_spec):
        spec = tmp_spec({"feature_name": "f", "phase": "initialized", "approvals": {}})
        spec.set_phase(Phase.REQUIREMENTS_GENERATED)
        reloaded = load_spec(spec.path)
        assert reloaded.phase == Phase.REQUIREMENTS_GENERATED

    def test_ensure_modifications_field(self, tmp_spec):
        spec = tmp_spec({"feature_name": "f", "phase": "initialized", "approvals": {}})
        assert "modifications" not in spec.raw
        spec.ensure_modifications_field()
        assert spec.raw["modifications"] == []
        # Verify persisted
        reloaded = load_spec(spec.path)
        assert reloaded.modifications == []

    def test_set_modify_phase(self, tmp_spec):
        spec = tmp_spec({
            "feature_name": "f", "phase": "tasks-generated", "approvals": {},
            "modifications": [{"modify_phase": "analysis-completed"}],
        })
        spec.set_modify_phase(ModifyPhase.SPEC_CASCADED)
        reloaded = load_spec(spec.path)
        assert reloaded.modifications[-1]["modify_phase"] == "spec-cascaded"


# ── Worktree spec finding ─────────────────────────────────────────

class TestFindSpec:
    def test_find_spec_in_worktree(self, tmp_spec):
        spec = tmp_spec({"feature_name": "my-feature", "phase": "initialized", "approvals": {}})
        # tmp_path is the worktree root (has .kiro/specs/my-feature/spec.json)
        worktree = spec.path.parent.parent.parent.parent
        found = find_spec_in_worktree(worktree)
        assert found is not None
        assert found.feature_name == "my-feature"

    def test_find_spec_by_name(self, tmp_spec):
        spec = tmp_spec({"feature_name": "my-feature", "phase": "initialized", "approvals": {}})
        worktree = spec.path.parent.parent.parent.parent
        found = find_spec_by_name(worktree, "my-feature")
        assert found is not None
        assert found.feature_name == "my-feature"

    def test_find_spec_by_name_missing(self, tmp_path):
        found = find_spec_by_name(tmp_path, "nonexistent")
        assert found is None
