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
            "preflight", "preflight_behind", "preflight_pull",
            "preflight_ahead", "preflight_push",
            # Plan Phase
            "plan_resolve",
            "P0_input_check", "P0_clarify", "P0_merge_clarification",
            "P1_plan_gen", "P1e_plan_edit",
            "P2_plan_readiness", "P2_gate",
            "post_plan_creation",
            # Setup + Spec + Impl
            "setup",
            "A1", "A1_detect_feature",
            "A1R",
            "A2", "A2R",
            "A3",
            "B", "B2",
            "steering",
            "C",
            "L4_check", "L4",
            "D", "cleanup",
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
        assert type_map["A1"] == "claude"
        assert type_map["A1R"] == "review_gate"
        assert type_map["A2"] == "claude"
        assert type_map["A2R"] == "review_gate"
        assert type_map["A3"] == "claude"
        assert type_map["B"] == "claude"
        assert type_map["B2"] == "claude"
        assert type_map["steering"] == "skill"
        assert type_map["C"] == "claude"
        assert type_map["L4"] == "skill"
        assert type_map["D"] == "claude"
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
    def test_a1r_has_feedback_loop(self, workflow: Workflow):
        a1r = workflow.get_step("A1R")
        assert a1r is not None
        assert a1r.on_feedback is not None
        assert a1r.on_feedback.rerun == "A1"
        assert a1r.on_feedback.then == "A1R"

    def test_a2r_has_feedback_loop(self, workflow: Workflow):
        a2r = workflow.get_step("A2R")
        assert a2r is not None
        assert a2r.on_feedback is not None
        assert a2r.on_feedback.rerun == "A2"
        assert a2r.on_feedback.then == "A2R"

    def test_review_gates_have_file_references(self, workflow: Workflow):
        a1r = workflow.get_step("A1R")
        assert a1r is not None
        assert "requirements-review.md" in a1r.file

        a2r = workflow.get_step("A2R")
        assert a2r is not None
        assert "design-review.md" in a2r.file


class TestImplementYamlMarkers:
    def test_a2_has_on_marker(self, workflow: Workflow):
        a2 = workflow.get_step("A2")
        assert a2 is not None
        assert "REVIEW_NEEDS_HUMAN" in a2.on_marker
        assert "REJECT" in a2.on_marker
        assert a2.on_marker["REVIEW_NEEDS_HUMAN"].pause == "design_review"
        assert a2.on_marker["REVIEW_NEEDS_HUMAN"].save_session is True

    def test_b2_has_on_marker(self, workflow: Workflow):
        b2 = workflow.get_step("B2")
        assert b2 is not None
        assert "VALIDATION_FAILED" in b2.on_marker
        assert b2.on_marker["VALIDATION_FAILED"].pause == "validation_triage"
        assert b2.on_marker["VALIDATION_FAILED"].save_session is True
        assert b2.on_marker["VALIDATION_FAILED"].question != ""
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
        assert "Retry" in on_resume
        assert on_resume["Retry"].goto == "B"
        assert "Abort" in on_resume
        assert on_resume["Abort"].goto == "_abort"


class TestImplementYamlWhenConditions:
    def test_resume_conditions_use_run_sets(self, workflow: Workflow):
        for step_id in ["A1", "A2", "A3", "B", "B2"]:
            step = workflow.get_step(step_id)
            assert step is not None
            assert step.when, f"Step {step_id} should have a when condition"
            assert "resume_point in RUN_" in step.when

    def test_l4_has_condition(self, workflow: Workflow):
        l4 = workflow.get_step("L4")
        assert l4 is not None
        assert "has_l4_tasks" in l4.when

    def test_preflight_gates_have_conditions(self, workflow: Workflow):
        for step_id in ["preflight_behind", "preflight_pull",
                        "preflight_ahead", "preflight_push"]:
            step = workflow.get_step(step_id)
            assert step is not None
            assert step.when


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
        for step_id in ["A1", "A2", "B2", "P1_plan_gen", "P2_plan_readiness"]:
            step = workflow.get_step(step_id)
            assert step is not None
            assert step.model == "opus", f"Step {step_id} should use opus"

    def test_sonnet_for_execution_steps(self, workflow: Workflow):
        for step_id in ["A3", "B", "C", "D", "P1e_plan_edit"]:
            step = workflow.get_step(step_id)
            assert step is not None
            assert step.model == "sonnet", f"Step {step_id} should use sonnet"
