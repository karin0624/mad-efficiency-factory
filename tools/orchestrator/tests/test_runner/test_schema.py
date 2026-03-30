"""Tests for runner/schema.py — Pydantic YAML schema models."""

import pytest
from pydantic import ValidationError

from tools.orchestrator.runner.schema import (
    OnFeedback,
    OnMarkerAction,
    OnResumeAction,
    Step,
    VarDef,
    Workflow,
)


class TestVarDef:
    def test_defaults(self):
        v = VarDef()
        assert v.from_param == ""
        assert v.type == "string"
        assert v.default is None

    def test_from_param(self):
        v = VarDef(from_param="plan")
        assert v.from_param == "plan"

    def test_with_default(self):
        v = VarDef(type="string", default="a1-what")
        assert v.default == "a1-what"


class TestStep:
    def test_claude_step_valid(self):
        s = Step(id="A1", type="claude", prompt="prompts/a1.md", model="opus")
        assert s.id == "A1"
        assert s.type == "claude"
        assert s.model == "opus"

    def test_claude_step_missing_prompt(self):
        with pytest.raises(ValidationError, match="requires 'prompt'"):
            Step(id="A1", type="claude")

    def test_python_step_valid(self):
        s = Step(id="preflight", type="python", function="orchestrator.preflight:run_preflight")
        assert s.function == "orchestrator.preflight:run_preflight"

    def test_python_step_missing_function(self):
        with pytest.raises(ValidationError, match="requires 'function'"):
            Step(id="preflight", type="python")

    def test_skill_step_valid(self):
        s = Step(id="steering", type="skill", skill="kiro:steering")
        assert s.skill == "kiro:steering"

    def test_skill_step_missing_skill(self):
        with pytest.raises(ValidationError, match="requires 'skill'"):
            Step(id="steering", type="skill")

    def test_review_gate_valid(self):
        s = Step(
            id="A1R",
            type="review_gate",
            question="要件レビュー文書を確認してください。",
            options=["approve", "feedback"],
        )
        assert s.question == "要件レビュー文書を確認してください。"
        assert s.options == ["approve", "feedback"]

    def test_review_gate_missing_question(self):
        with pytest.raises(ValidationError, match="requires 'question'"):
            Step(id="A1R", type="review_gate")

    def test_parallel_step_valid(self):
        s = Step(
            id="parallel_1",
            type="parallel",
            steps=[
                Step(id="sub1", type="claude", prompt="p1.md"),
                Step(id="sub2", type="claude", prompt="p2.md"),
            ],
        )
        assert len(s.steps) == 2

    def test_parallel_step_missing_steps(self):
        with pytest.raises(ValidationError, match="requires 'steps'"):
            Step(id="parallel_1", type="parallel")

    def test_review_gate_with_on_feedback(self):
        s = Step(
            id="A1R",
            type="review_gate",
            question="Review?",
            on_feedback=OnFeedback(
                rerun="A1",
                extra_params={"USER_FEEDBACK": "{{ user_input }}"},
                then="A1R",
            ),
        )
        assert s.on_feedback is not None
        assert s.on_feedback.rerun == "A1"
        assert s.on_feedback.then == "A1R"

    def test_claude_step_with_on_marker(self):
        s = Step(
            id="B2",
            type="claude",
            prompt="validate.md",
            markers=["VALIDATION_PASSED", "VALIDATION_FAILED"],
            on_marker={
                "VALIDATION_FAILED": OnMarkerAction(
                    pause="validation_triage",
                    save_session=True,
                ),
            },
        )
        assert "VALIDATION_FAILED" in s.on_marker
        assert s.on_marker["VALIDATION_FAILED"].pause == "validation_triage"
        assert s.on_marker["VALIDATION_FAILED"].save_session is True

    def test_step_with_when_condition(self):
        s = Step(
            id="A1",
            type="claude",
            prompt="a1.md",
            when="{{ resume_point in RUN_A1 }}",
        )
        assert s.when == "{{ resume_point in RUN_A1 }}"

    def test_on_marker_with_on_resume(self):
        s = Step(
            id="B2",
            type="claude",
            prompt="validate.md",
            on_marker={
                "VALIDATION_FAILED": OnMarkerAction(
                    pause="validation_triage",
                    save_session=True,
                    options=["GO", "Conditional GO", "Retry", "Abort"],
                    on_resume={
                        "Conditional GO": OnResumeAction(
                            resume_session=True,
                            extra_prompt="Reason: {{ user_input }}",
                        ),
                        "Retry": OnResumeAction(goto="B"),
                        "Abort": OnResumeAction(goto="_abort"),
                    },
                ),
            },
        )
        marker = s.on_marker["VALIDATION_FAILED"]
        assert len(marker.on_resume) == 3
        assert marker.on_resume["Conditional GO"].resume_session is True
        assert marker.on_resume["Retry"].goto == "B"
        assert marker.on_resume["Abort"].goto == "_abort"


class TestOnResumeAction:
    def test_defaults(self):
        a = OnResumeAction()
        assert a.goto == ""
        assert a.resume_session is False
        assert a.extra_prompt == ""

    def test_goto_abort(self):
        a = OnResumeAction(goto="_abort")
        assert a.goto == "_abort"

    def test_resume_session(self):
        a = OnResumeAction(resume_session=True, extra_prompt="Record reason")
        assert a.resume_session is True
        assert a.extra_prompt == "Record reason"

    def test_goto_step(self):
        a = OnResumeAction(goto="B")
        assert a.goto == "B"


class TestWorkflow:
    def test_minimal_workflow(self):
        w = Workflow(name="test")
        assert w.name == "test"
        assert w.steps == []
        assert w.vars == {}

    def test_workflow_with_steps(self):
        w = Workflow(
            name="implement",
            description="Plan -> Spec -> Impl",
            steps=[
                Step(id="A1", type="claude", prompt="a1.md"),
                Step(id="A1R", type="review_gate", question="Review?"),
            ],
        )
        assert len(w.steps) == 2
        assert w.step_ids() == ["A1", "A1R"]

    def test_get_step(self):
        w = Workflow(
            name="test",
            steps=[
                Step(id="A1", type="claude", prompt="a1.md"),
                Step(id="A1R", type="review_gate", question="Review?"),
            ],
        )
        assert w.get_step("A1") is not None
        assert w.get_step("A1R") is not None
        assert w.get_step("nonexistent") is None

    def test_get_step_in_parallel(self):
        w = Workflow(
            name="test",
            steps=[
                Step(
                    id="par",
                    type="parallel",
                    steps=[
                        Step(id="sub1", type="claude", prompt="s1.md"),
                        Step(id="sub2", type="claude", prompt="s2.md"),
                    ],
                ),
            ],
        )
        assert w.get_step("sub1") is not None
        assert w.get_step("sub2") is not None

    def test_workflow_with_vars(self):
        w = Workflow(
            name="test",
            vars={
                "plan_argument": VarDef(from_param="plan"),
                "resume_point": VarDef(type="string", default="a1-what"),
            },
        )
        assert w.vars["plan_argument"].from_param == "plan"
        assert w.vars["resume_point"].default == "a1-what"

    def test_model_validate_from_dict(self):
        raw = {
            "name": "implement",
            "description": "Test workflow",
            "vars": {
                "plan": {"from_param": "plan"},
            },
            "steps": [
                {"id": "A1", "type": "claude", "prompt": "a1.md", "model": "opus"},
                {"id": "gate", "type": "review_gate", "question": "OK?"},
            ],
        }
        w = Workflow.model_validate(raw)
        assert w.name == "implement"
        assert len(w.steps) == 2
        assert w.steps[0].model == "opus"
