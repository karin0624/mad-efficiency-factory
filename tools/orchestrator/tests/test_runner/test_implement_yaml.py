"""Tests for workflows/implement.yaml — validate structure and schema."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.orchestrator.runner.loader import load_workflow
from tools.orchestrator.runner.schema import Workflow

WORKFLOW_PATH = Path(__file__).resolve().parents[2] / "workflows" / "implement.yaml"


@pytest.fixture
def workflow() -> Workflow:
    return load_workflow(WORKFLOW_PATH)


class TestImplementYamlStructure:
    def test_loads_without_error(self, workflow: Workflow):
        assert workflow.name == "implement"

    def test_has_all_expected_steps(self, workflow: Workflow):
        ids = workflow.step_ids()
        expected = [
            "preflight",
            # Plan Phase
            "plan_resolve",
            "P0_input_check", "P0_clarify", "P0_merge_clarification",
            "P1_plan_gen", "P1e_plan_edit",
            "P2_plan_readiness", "P2_gate",
            "post_plan_creation",
            # Setup + Spec + Impl
            "setup",
            "spec_requirements", "detect_feature",
            "requirements_review",
            "spec_design", "design_review",
            "spec_tasks",
            "impl_code", "impl_validate",
            "steering",
            "scene_review_check", "scene_review",
            "commit",
            "push_pr", "cleanup",
        ]
        assert ids == expected

    def test_step_types(self, workflow: Workflow):
        type_map = {s.id: s.type for s in workflow.steps}
        assert type_map["preflight"] == "python"
        # Plan Phase
        assert type_map["plan_resolve"] == "python"
        assert type_map["P0_input_check"] == "python"
        assert type_map["P0_clarify"] == "review_gate"
        assert type_map["P0_merge_clarification"] == "python"
        assert type_map["P1_plan_gen"] == "claude"
        assert type_map["P1e_plan_edit"] == "claude"
        assert type_map["P2_plan_readiness"] == "claude"
        assert type_map["P2_gate"] == "review_gate"
        assert type_map["post_plan_creation"] == "python"
        # Setup + existing
        assert type_map["setup"] == "python"
        assert type_map["spec_requirements"] == "claude"
        assert type_map["requirements_review"] == "review_gate"
        assert type_map["spec_design"] == "claude"
        assert type_map["design_review"] == "review_gate"
        assert type_map["spec_tasks"] == "claude"
        assert type_map["impl_code"] == "claude"
        assert type_map["impl_validate"] == "claude"
        assert type_map["steering"] == "skill"
        assert type_map["commit"] == "claude"
        assert type_map["scene_review"] == "skill"
        assert type_map["push_pr"] == "claude"
        assert type_map["cleanup"] == "python"

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


class TestImplementYamlReviewGates:
    def test_requirements_review_has_feedback_loop(self, workflow: Workflow):
        gate = workflow.get_step("requirements_review")
        assert gate is not None
        assert gate.on_feedback is not None
        assert gate.on_feedback.rerun == "spec_requirements"
        assert gate.on_feedback.then == "requirements_review"

    def test_design_review_has_feedback_loop(self, workflow: Workflow):
        gate = workflow.get_step("design_review")
        assert gate is not None
        assert gate.on_feedback is not None
        assert gate.on_feedback.rerun == "spec_design"
        assert gate.on_feedback.then == "design_review"

    def test_review_gates_have_file_references(self, workflow: Workflow):
        req_review = workflow.get_step("requirements_review")
        assert req_review is not None
        assert "requirements-review.md" in req_review.file

        des_review = workflow.get_step("design_review")
        assert des_review is not None
        assert "design-review.md" in des_review.file


class TestImplementYamlMarkers:
    def test_spec_design_has_on_marker(self, workflow: Workflow):
        step = workflow.get_step("spec_design")
        assert step is not None
        assert "REVIEW_NEEDS_HUMAN" in step.on_marker
        assert "REJECT" in step.on_marker
        assert step.on_marker["REVIEW_NEEDS_HUMAN"].pause == "design_review"
        assert step.on_marker["REVIEW_NEEDS_HUMAN"].save_session is True

    def test_impl_validate_has_on_marker(self, workflow: Workflow):
        step = workflow.get_step("impl_validate")
        assert step is not None
        assert "VALIDATION_FAILED" in step.on_marker
        assert step.on_marker["VALIDATION_FAILED"].pause == "validation_triage"
        assert step.on_marker["VALIDATION_FAILED"].save_session is True
        assert step.on_marker["VALIDATION_FAILED"].question != ""
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
        assert "Retry" in on_resume
        assert on_resume["Retry"].goto == "impl_code"
        assert "Abort" in on_resume
        assert on_resume["Abort"].goto == "_abort"


class TestImplementYamlWhenConditions:
    def test_resume_conditions_use_run_sets(self, workflow: Workflow):
        for step_id in ["spec_requirements", "spec_design", "spec_tasks", "impl_code", "impl_validate"]:
            step = workflow.get_step(step_id)
            assert step is not None
            assert step.when, f"Step {step_id} should have a when condition"
            assert "resume_point in RUN_" in step.when

    def test_scene_review_has_condition(self, workflow: Workflow):
        step = workflow.get_step("scene_review")
        assert step is not None
        assert "has_l4_tasks" in step.when

    def test_preflight_sync_gates_removed(self, workflow: Workflow):
        for step_id in ["preflight_behind", "preflight_pull", "preflight_ahead", "preflight_push"]:
            assert workflow.get_step(step_id) is None

    def test_scene_review_runs_before_commit(self, workflow: Workflow):
        ids = workflow.step_ids()
        assert ids.index("scene_review_check") < ids.index("commit")
        assert ids.index("scene_review") < ids.index("commit")


class TestImplementYamlPlanPhase:
    def test_plan_resolve_is_python(self, workflow: Workflow):
        step = workflow.get_step("plan_resolve")
        assert step is not None
        assert step.type == "python"

    def test_plan_creation_steps_gated(self, workflow: Workflow):
        """P0_input_check, P1, P2, P2_gate, post_plan_creation are gated by needs_plan_creation."""
        gated_ids = ["P0_input_check", "P1_plan_gen", "P2_plan_readiness",
                     "P2_gate", "post_plan_creation"]
        for step_id in gated_ids:
            step = workflow.get_step(step_id)
            assert step is not None, f"Step {step_id} not found"
            assert "needs_plan_creation" in step.when, (
                f"Step {step_id} should be gated by needs_plan_creation"
            )

    def test_p0_clarify_gated(self, workflow: Workflow):
        step = workflow.get_step("P0_clarify")
        assert step is not None
        assert "p0_needs_clarification" in step.when

    def test_p1e_gated_by_user_feedback(self, workflow: Workflow):
        step = workflow.get_step("P1e_plan_edit")
        assert step is not None
        assert "USER_FEEDBACK" in step.when

    def test_p2_gate_has_feedback_loop(self, workflow: Workflow):
        gate = workflow.get_step("P2_gate")
        assert gate is not None
        assert gate.on_feedback is not None
        assert gate.on_feedback.rerun == "P1e_plan_edit"
        assert gate.on_feedback.then == "P2_gate"

    def test_setup_uses_worktree_only(self, workflow: Workflow):
        step = workflow.get_step("setup")
        assert step is not None
        assert "setup_worktree_only_step" in step.function


class TestImplementYamlModels:
    def test_opus_for_critical_steps(self, workflow: Workflow):
        for step_id in ["spec_requirements", "spec_design", "impl_validate", "P1_plan_gen", "P2_plan_readiness"]:
            step = workflow.get_step(step_id)
            assert step is not None
            assert step.model == "opus", f"Step {step_id} should use opus"

    def test_sonnet_for_execution_steps(self, workflow: Workflow):
        for step_id in ["spec_tasks", "impl_code", "commit", "push_pr", "P1e_plan_edit"]:
            step = workflow.get_step(step_id)
            assert step is not None
            assert step.model == "sonnet", f"Step {step_id} should use sonnet"


class TestImplementYamlParams:
    def test_spec_requirements_includes_user_feedback_param(self, workflow: Workflow):
        step = workflow.get_step("spec_requirements")
        assert step is not None
        assert step.params["USER_FEEDBACK"] == "{{ USER_FEEDBACK }}"

    def test_spec_design_includes_user_feedback_param(self, workflow: Workflow):
        step = workflow.get_step("spec_design")
        assert step is not None
        assert step.params["USER_FEEDBACK"] == "{{ USER_FEEDBACK }}"
