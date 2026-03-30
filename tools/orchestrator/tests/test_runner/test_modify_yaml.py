"""Tests for workflows/modify.yaml — validate structure and schema."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.orchestrator.runner.loader import load_workflow
from tools.orchestrator.runner.schema import Workflow

WORKFLOW_PATH = Path(__file__).resolve().parents[2] / "workflows" / "modify.yaml"


@pytest.fixture
def workflow() -> Workflow:
    return load_workflow(WORKFLOW_PATH)


class TestModifyYamlStructure:
    def test_loads_without_error(self, workflow: Workflow):
        assert workflow.name == "modify"

    def test_has_all_expected_steps(self, workflow: Workflow):
        ids = workflow.step_ids()
        expected = [
            # Preflight
            "preflight",
            # Mode detection
            "mode_setup",
            # Investigate mode
            "MP0", "MP0_process", "MP0_confirm",
            "output_dir_setup", "MP1", "MP2", "MP_review", "write_index",
            # Single mode
            "M1", "M1_process", "M1_review",
            "worktree_setup",
            "ADR", "ADR_review",
            "M2", "M2R_check", "M2R",
            "M3", "M3_update",
            "B", "B_update",
            "B2", "B2_update",
            # Delivery (shared)
            "steering", "L4_check", "L4", "C", "D",
            # Single cleanup
            "cleanup",
            # Plan mode
            "plan_setup", "plan_M1_all", "plan_impl_all",
            "plan_delivery_setup", "plan_cleanup",
        ]
        assert ids == expected

    def test_step_types(self, workflow: Workflow):
        type_map = {s.id: s.type for s in workflow.steps}
        # Preflight
        assert type_map["preflight"] == "python"
        # Mode
        assert type_map["mode_setup"] == "python"
        # Investigate
        assert type_map["MP0"] == "claude"
        assert type_map["MP0_process"] == "python"
        assert type_map["MP0_confirm"] == "review_gate"
        assert type_map["MP1"] == "python"
        assert type_map["MP2"] == "python"
        assert type_map["MP_review"] == "review_gate"
        assert type_map["write_index"] == "python"
        # Single
        assert type_map["M1"] == "claude"
        assert type_map["M1_process"] == "python"
        assert type_map["M1_review"] == "review_gate"
        assert type_map["worktree_setup"] == "python"
        assert type_map["ADR"] == "python"
        assert type_map["ADR_review"] == "review_gate"
        assert type_map["M2"] == "claude"
        assert type_map["M2R_check"] == "python"
        assert type_map["M2R"] == "review_gate"
        assert type_map["M3"] == "claude"
        assert type_map["B"] == "claude"
        assert type_map["B2"] == "claude"
        # Delivery
        assert type_map["steering"] == "skill"
        assert type_map["C"] == "claude"
        assert type_map["L4"] == "skill"
        assert type_map["D"] == "claude"
        assert type_map["cleanup"] == "python"
        # Plan
        assert type_map["plan_setup"] == "python"
        assert type_map["plan_M1_all"] == "python"
        assert type_map["plan_impl_all"] == "python"

    def test_claude_steps_have_prompts(self, workflow: Workflow):
        for step in workflow.steps:
            if step.type == "claude":
                assert step.prompt, f"Step {step.id} missing prompt"

    def test_python_steps_have_functions(self, workflow: Workflow):
        for step in workflow.steps:
            if step.type == "python":
                assert step.function, f"Step {step.id} missing function"
                assert ":" in step.function, f"Step {step.id} function missing ':' separator"

    def test_skill_steps_have_skill_name(self, workflow: Workflow):
        for step in workflow.steps:
            if step.type == "skill":
                assert step.skill, f"Step {step.id} missing skill name"


class TestModifyYamlModeConditions:
    """Verify that steps are gated by correct mode conditions."""

    def test_investigate_steps_guarded(self, workflow: Workflow):
        investigate_ids = {"MP0", "MP0_process", "MP0_confirm",
                          "output_dir_setup", "MP1", "MP2", "MP_review", "write_index"}
        for step in workflow.steps:
            if step.id in investigate_ids:
                assert "mode_investigate" in step.when, (
                    f"Step {step.id} should be gated by mode_investigate"
                )

    def test_single_steps_guarded(self, workflow: Workflow):
        single_ids = {"M1", "M1_process", "worktree_setup"}
        for step in workflow.steps:
            if step.id in single_ids:
                assert "mode_single" in step.when, (
                    f"Step {step.id} should be gated by mode_single"
                )

    def test_plan_steps_guarded(self, workflow: Workflow):
        plan_ids = {"plan_setup", "plan_M1_all", "plan_impl_all",
                    "plan_delivery_setup", "plan_cleanup"}
        for step in workflow.steps:
            if step.id in plan_ids:
                assert "mode_plan" in step.when, (
                    f"Step {step.id} should be gated by mode_plan"
                )

    def test_delivery_shared_steps(self, workflow: Workflow):
        """C, L4_check, D are shared by single and plan modes."""
        shared_ids = {"C", "L4_check", "D"}
        for step in workflow.steps:
            if step.id in shared_ids:
                assert "mode_single_or_plan" in step.when, (
                    f"Step {step.id} should be gated by mode_single_or_plan"
                )

    def test_preflight_sync_gates_removed(self, workflow: Workflow):
        for step_id in ["preflight_behind", "preflight_pull", "preflight_ahead", "preflight_push"]:
            assert workflow.get_step(step_id) is None

    def test_l4_runs_before_commit(self, workflow: Workflow):
        ids = workflow.step_ids()
        assert ids.index("L4_check") < ids.index("C")
        assert ids.index("L4") < ids.index("C")


class TestModifyYamlReviewGates:
    def test_m1_review_has_feedback_loop(self, workflow: Workflow):
        m1r = workflow.get_step("M1_review")
        assert m1r is not None
        assert m1r.on_feedback is not None
        assert m1r.on_feedback.rerun == "M1"
        assert m1r.on_feedback.then == "M1_process"

    def test_m2r_has_feedback_loop(self, workflow: Workflow):
        m2r = workflow.get_step("M2R")
        assert m2r is not None
        assert m2r.on_feedback is not None
        assert m2r.on_feedback.rerun == "M2"
        assert m2r.on_feedback.then == "M2R_check"

    def test_adr_review_gate(self, workflow: Workflow):
        adr_r = workflow.get_step("ADR_review")
        assert adr_r is not None
        assert adr_r.type == "review_gate"
        assert "adr_needs_review" in adr_r.when

    def test_mp0_confirm_gate(self, workflow: Workflow):
        mp0c = workflow.get_step("MP0_confirm")
        assert mp0c is not None
        assert mp0c.type == "review_gate"
        assert len(mp0c.options) == 2


class TestModifyYamlMarkers:
    def test_m2_has_cascade_failed_marker(self, workflow: Workflow):
        m2 = workflow.get_step("M2")
        assert m2 is not None
        assert "CASCADE_FAILED" in m2.on_marker
        assert m2.on_marker["CASCADE_FAILED"].pause == "m2_cascade_review"
        assert m2.on_marker["CASCADE_FAILED"].save_session is True

    def test_b2_has_validation_failed_marker(self, workflow: Workflow):
        b2 = workflow.get_step("B2")
        assert b2 is not None
        assert "VALIDATION_FAILED" in b2.on_marker
        assert b2.on_marker["VALIDATION_FAILED"].pause == "validation_triage"
        assert b2.on_marker["VALIDATION_FAILED"].save_session is True
        assert len(b2.on_marker["VALIDATION_FAILED"].options) == 4

    def test_b2_conditional_go_option(self, workflow: Workflow):
        b2 = workflow.get_step("B2")
        assert b2 is not None
        options = b2.on_marker["VALIDATION_FAILED"].options
        assert any("Conditional GO" in o for o in options)

    def test_b2_on_resume_actions(self, workflow: Workflow):
        b2 = workflow.get_step("B2")
        assert b2 is not None
        on_resume = b2.on_marker["VALIDATION_FAILED"].on_resume
        assert "Conditional GO" in on_resume
        assert on_resume["Conditional GO"].resume_session is True
        assert on_resume["Conditional GO"].extra_prompt != ""
        assert "Retry" in on_resume
        assert on_resume["Retry"].goto == "B"
        assert "Abort" in on_resume
        assert on_resume["Abort"].goto == "_abort"


class TestModifyYamlCascadeConditions:
    """Verify cascade_depth-based when conditions for M2/M3/B/B2."""

    def test_m2_has_run_condition(self, workflow: Workflow):
        m2 = workflow.get_step("M2")
        assert m2 is not None
        assert "run_M2" in m2.when

    def test_m3_has_run_condition(self, workflow: Workflow):
        m3 = workflow.get_step("M3")
        assert m3 is not None
        assert "run_M3" in m3.when

    def test_b_has_run_condition(self, workflow: Workflow):
        b = workflow.get_step("B")
        assert b is not None
        assert "run_B" in b.when

    def test_b2_has_run_condition(self, workflow: Workflow):
        b2 = workflow.get_step("B2")
        assert b2 is not None
        assert "run_B2" in b2.when


class TestModifyYamlModels:
    def test_opus_for_analysis_steps(self, workflow: Workflow):
        for step_id in ["M1", "MP0", "M2", "B2"]:
            step = workflow.get_step(step_id)
            assert step is not None
            assert step.model == "opus", f"Step {step_id} should use opus"

    def test_sonnet_for_execution_steps(self, workflow: Workflow):
        for step_id in ["M3", "B", "C", "D"]:
            step = workflow.get_step(step_id)
            assert step is not None
            assert step.model == "sonnet", f"Step {step_id} should use sonnet"


class TestModifyYamlSessionSave:
    """Verify save_session is set for steps that need session resume."""

    def test_m1_saves_session(self, workflow: Workflow):
        m1 = workflow.get_step("M1")
        assert m1 is not None
        assert m1.save_session is True

    def test_m2_saves_session(self, workflow: Workflow):
        m2 = workflow.get_step("M2")
        assert m2 is not None
        assert m2.save_session is True

    def test_b2_saves_session(self, workflow: Workflow):
        b2 = workflow.get_step("B2")
        assert b2 is not None
        assert b2.save_session is True


class TestModifyYamlParams:
    def test_m2_includes_user_feedback_param(self, workflow: Workflow):
        m2 = workflow.get_step("M2")
        assert m2 is not None
        assert m2.params["USER_FEEDBACK"] == "{{ USER_FEEDBACK }}"
