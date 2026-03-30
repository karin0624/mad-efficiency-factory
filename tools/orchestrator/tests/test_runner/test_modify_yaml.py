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
            "investigate_analyze", "investigate_process", "investigate_confirm",
            "output_dir_setup", "investigate_cascade", "investigate_plan", "investigate_review", "write_index",
            # Single mode
            "change_analyze", "change_analyze_process", "change_analyze_review",
            "worktree_setup",
            "ADR", "ADR_review",
            "cascade", "cascade_review_check", "cascade_review",
            "delta_tasks", "delta_tasks_update",
            "impl_code", "impl_code_update",
            "impl_validate", "impl_validate_update",
            # Plan mode
            "plan_setup", "plan_analyze_all", "plan_analyze_review", "plan_impl_all",
            "plan_delivery_setup",
            # Delivery (shared)
            "steering", "scene_review_check", "scene_review", "commit", "push_pr",
            # Cleanup
            "cleanup",
            "plan_cleanup",
        ]
        assert ids == expected

    def test_step_types(self, workflow: Workflow):
        type_map = {s.id: s.type for s in workflow.steps}
        # Preflight
        assert type_map["preflight"] == "python"
        # Mode
        assert type_map["mode_setup"] == "python"
        # Investigate
        assert type_map["investigate_analyze"] == "claude"
        assert type_map["investigate_process"] == "python"
        assert type_map["investigate_confirm"] == "review_gate"
        assert type_map["investigate_cascade"] == "python"
        assert type_map["investigate_plan"] == "python"
        assert type_map["investigate_review"] == "review_gate"
        assert type_map["write_index"] == "python"
        # Single
        assert type_map["change_analyze"] == "claude"
        assert type_map["change_analyze_process"] == "python"
        assert type_map["change_analyze_review"] == "review_gate"
        assert type_map["worktree_setup"] == "python"
        assert type_map["ADR"] == "python"
        assert type_map["ADR_review"] == "review_gate"
        assert type_map["cascade"] == "claude"
        assert type_map["cascade_review_check"] == "python"
        assert type_map["cascade_review"] == "review_gate"
        assert type_map["delta_tasks"] == "claude"
        assert type_map["impl_code"] == "claude"
        assert type_map["impl_validate"] == "claude"
        # Delivery
        assert type_map["steering"] == "skill"
        assert type_map["commit"] == "claude"
        assert type_map["scene_review"] == "skill"
        assert type_map["push_pr"] == "claude"
        assert type_map["cleanup"] == "python"
        # Plan
        assert type_map["plan_setup"] == "python"
        assert type_map["plan_analyze_all"] == "python"
        assert type_map["plan_analyze_review"] == "review_gate"
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
        investigate_ids = {"investigate_analyze", "investigate_process", "investigate_confirm",
                          "output_dir_setup", "investigate_cascade", "investigate_plan", "investigate_review", "write_index"}
        for step in workflow.steps:
            if step.id in investigate_ids:
                assert "mode_investigate" in step.when, (
                    f"Step {step.id} should be gated by mode_investigate"
                )

    def test_single_steps_guarded(self, workflow: Workflow):
        single_ids = {"change_analyze", "change_analyze_process", "worktree_setup"}
        for step in workflow.steps:
            if step.id in single_ids:
                assert "mode_single" in step.when, (
                    f"Step {step.id} should be gated by mode_single"
                )

    def test_plan_steps_guarded(self, workflow: Workflow):
        plan_ids = {"plan_setup", "plan_analyze_all", "plan_analyze_review", "plan_impl_all",
                    "plan_delivery_setup", "plan_cleanup"}
        for step in workflow.steps:
            if step.id in plan_ids:
                assert "mode_plan" in step.when, (
                    f"Step {step.id} should be gated by mode_plan"
                )

    def test_delivery_shared_steps(self, workflow: Workflow):
        """commit, scene_review_check, push_pr are shared by single and plan modes."""
        shared_ids = {"commit", "scene_review_check", "push_pr"}
        for step in workflow.steps:
            if step.id in shared_ids:
                assert "mode_single_or_plan" in step.when, (
                    f"Step {step.id} should be gated by mode_single_or_plan"
                )

    def test_preflight_sync_gates_removed(self, workflow: Workflow):
        for step_id in ["preflight_behind", "preflight_pull", "preflight_ahead", "preflight_push"]:
            assert workflow.get_step(step_id) is None

    def test_scene_review_runs_before_commit(self, workflow: Workflow):
        ids = workflow.step_ids()
        assert ids.index("scene_review_check") < ids.index("commit")
        assert ids.index("scene_review") < ids.index("commit")


class TestModifyYamlReviewGates:
    def test_change_analyze_review_has_feedback_loop(self, workflow: Workflow):
        gate = workflow.get_step("change_analyze_review")
        assert gate is not None
        assert gate.on_feedback is not None
        assert gate.on_feedback.rerun == "change_analyze"
        assert gate.on_feedback.then == "change_analyze_process"

    def test_cascade_review_has_feedback_loop(self, workflow: Workflow):
        gate = workflow.get_step("cascade_review")
        assert gate is not None
        assert gate.on_feedback is not None
        assert gate.on_feedback.rerun == "cascade"
        assert gate.on_feedback.then == "cascade_review_check"

    def test_adr_review_gate(self, workflow: Workflow):
        adr_r = workflow.get_step("ADR_review")
        assert adr_r is not None
        assert adr_r.type == "review_gate"
        assert "adr_needs_review" in adr_r.when

    def test_investigate_confirm_gate(self, workflow: Workflow):
        gate = workflow.get_step("investigate_confirm")
        assert gate is not None
        assert gate.type == "review_gate"
        assert len(gate.options) == 2

    def test_plan_analyze_review_gate(self, workflow: Workflow):
        gate = workflow.get_step("plan_analyze_review")
        assert gate is not None
        assert gate.type == "review_gate"
        assert len(gate.options) == 2


class TestModifyYamlMarkers:
    def test_cascade_has_cascade_failed_marker(self, workflow: Workflow):
        step = workflow.get_step("cascade")
        assert step is not None
        assert "CASCADE_FAILED" in step.on_marker
        assert step.on_marker["CASCADE_FAILED"].pause == "m2_cascade_review"
        assert step.on_marker["CASCADE_FAILED"].save_session is True

    def test_impl_validate_has_validation_failed_marker(self, workflow: Workflow):
        step = workflow.get_step("impl_validate")
        assert step is not None
        assert "VALIDATION_FAILED" in step.on_marker
        assert step.on_marker["VALIDATION_FAILED"].pause == "validation_triage"
        assert step.on_marker["VALIDATION_FAILED"].save_session is True
        assert len(step.on_marker["VALIDATION_FAILED"].options) == 4

    def test_impl_validate_conditional_go_option(self, workflow: Workflow):
        step = workflow.get_step("impl_validate")
        assert step is not None
        options = step.on_marker["VALIDATION_FAILED"].options
        assert any("Conditional GO" in o for o in options)

    def test_impl_validate_on_resume_actions(self, workflow: Workflow):
        step = workflow.get_step("impl_validate")
        assert step is not None
        on_resume = step.on_marker["VALIDATION_FAILED"].on_resume
        assert "Conditional GO" in on_resume
        assert on_resume["Conditional GO"].resume_session is True
        assert on_resume["Conditional GO"].extra_prompt != ""
        assert "Retry" in on_resume
        assert on_resume["Retry"].goto == "impl_code"
        assert "Abort" in on_resume
        assert on_resume["Abort"].goto == "_abort"


class TestModifyYamlCascadeConditions:
    """Verify cascade_depth-based when conditions for cascade/delta_tasks/impl_code/impl_validate."""

    def test_cascade_has_run_condition(self, workflow: Workflow):
        step = workflow.get_step("cascade")
        assert step is not None
        assert "run_M2" in step.when

    def test_delta_tasks_has_run_condition(self, workflow: Workflow):
        step = workflow.get_step("delta_tasks")
        assert step is not None
        assert "run_M3" in step.when

    def test_impl_code_has_run_condition(self, workflow: Workflow):
        step = workflow.get_step("impl_code")
        assert step is not None
        assert "run_B" in step.when

    def test_impl_validate_has_run_condition(self, workflow: Workflow):
        step = workflow.get_step("impl_validate")
        assert step is not None
        assert "run_B2" in step.when


class TestModifyYamlModels:
    def test_opus_for_analysis_steps(self, workflow: Workflow):
        for step_id in ["change_analyze", "investigate_analyze", "cascade", "impl_validate"]:
            step = workflow.get_step(step_id)
            assert step is not None
            assert step.model == "opus", f"Step {step_id} should use opus"

    def test_sonnet_for_execution_steps(self, workflow: Workflow):
        for step_id in ["delta_tasks", "impl_code", "commit", "push_pr"]:
            step = workflow.get_step(step_id)
            assert step is not None
            assert step.model == "sonnet", f"Step {step_id} should use sonnet"


class TestModifyYamlParams:
    def test_commit_uses_delivery_feature_name(self, workflow: Workflow):
        step = workflow.get_step("commit")
        assert step is not None
        assert step.params["FEATURE_NAME"] == "{{ delivery_feature_name }}"

    def test_push_pr_includes_affected_specs(self, workflow: Workflow):
        step = workflow.get_step("push_pr")
        assert step is not None
        assert step.params["FEATURE_NAME"] == "{{ delivery_feature_name }}"
        assert step.params["AFFECTED_SPECS"] == "{{ affected_specs }}"


class TestModifyYamlSessionSave:
    """Verify save_session is set for steps that need session resume."""

    def test_change_analyze_saves_session(self, workflow: Workflow):
        step = workflow.get_step("change_analyze")
        assert step is not None
        assert step.save_session is True

    def test_cascade_saves_session(self, workflow: Workflow):
        step = workflow.get_step("cascade")
        assert step is not None
        assert step.save_session is True

    def test_impl_validate_saves_session(self, workflow: Workflow):
        step = workflow.get_step("impl_validate")
        assert step is not None
        assert step.save_session is True


class TestModifyYamlParams:
    def test_cascade_includes_user_feedback_param(self, workflow: Workflow):
        step = workflow.get_step("cascade")
        assert step is not None
        assert step.params["USER_FEEDBACK"] == "{{ USER_FEEDBACK }}"
