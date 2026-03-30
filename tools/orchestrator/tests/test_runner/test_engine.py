"""Tests for runner/engine.py — WorkflowRunner execution engine."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from tools.orchestrator.config import OrchestratorConfig
from tools.orchestrator.output_parser import ParsedOutput
from tools.orchestrator.runner.claude_p import ClaudePResult
from tools.orchestrator.runner.engine import WorkflowRunner


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def config(tmp_path: Path) -> OrchestratorConfig:
    return OrchestratorConfig(project_root=tmp_path)


def _write_workflow(tmp_path: Path, yaml_content: str) -> Path:
    path = tmp_path / "test.yaml"
    path.write_text(yaml_content)
    return path


def _write_prompt(tmp_path: Path, rel_path: str, content: str = "prompt text") -> None:
    full = tmp_path / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content)


class TestWorkflowRunnerBasic:
    def test_empty_workflow_completes(self, config: OrchestratorConfig, tmp_path: Path):
        yaml = "name: empty\nsteps: []\n"
        path = _write_workflow(tmp_path, yaml)
        runner = WorkflowRunner(config, session_dir=tmp_path / "sessions")
        result = _run(runner.run(path))
        assert result["type"] == "pipeline_completed"

    def test_review_gate_pauses(self, config: OrchestratorConfig, tmp_path: Path):
        yaml = """
name: gate-test
steps:
  - id: gate1
    type: review_gate
    question: "Approve?"
    options: [approve, reject]
"""
        path = _write_workflow(tmp_path, yaml)
        runner = WorkflowRunner(config, session_dir=tmp_path / "sessions")
        result = _run(runner.run(path))
        assert result["type"] == "interaction_required"
        assert result["current_step"] == "gate1"
        assert "Approve?" in result["question"]

    def test_when_condition_skips_step(self, config: OrchestratorConfig, tmp_path: Path):
        _write_prompt(tmp_path, "p.md")
        yaml = """
name: when-test
steps:
  - id: skip_me
    type: claude
    prompt: p.md
    when: "{{ skip_flag }}"
"""
        path = _write_workflow(tmp_path, yaml)
        runner = WorkflowRunner(config, session_dir=tmp_path / "sessions")
        result = _run(runner.run(path, params={"skip_flag": False}))
        assert result["type"] == "pipeline_completed"

    def test_claude_step_executes(self, config: OrchestratorConfig, tmp_path: Path):
        _write_prompt(tmp_path, "p.md", "Do something")
        yaml = """
name: claude-test
steps:
  - id: step1
    type: claude
    prompt: p.md
    model: sonnet
"""
        path = _write_workflow(tmp_path, yaml)
        runner = WorkflowRunner(config, session_dir=tmp_path / "sessions")

        mock_result = ClaudePResult(
            output_text="Done VALIDATION_PASSED",
            parsed=ParsedOutput(
                raw_text="Done VALIDATION_PASSED",
                markers={"VALIDATION_PASSED": True},
            ),
            session_id="s1",
        )
        runner.runner.run = AsyncMock(return_value=mock_result)

        result = _run(runner.run(path))
        assert result["type"] == "pipeline_completed"
        runner.runner.run.assert_called_once()

    def test_claude_step_error(self, config: OrchestratorConfig, tmp_path: Path):
        _write_prompt(tmp_path, "p.md")
        yaml = """
name: error-test
steps:
  - id: fail_step
    type: claude
    prompt: p.md
"""
        path = _write_workflow(tmp_path, yaml)
        runner = WorkflowRunner(config, session_dir=tmp_path / "sessions")

        mock_result = ClaudePResult(
            is_error=True,
            error_message="model error",
        )
        runner.runner.run = AsyncMock(return_value=mock_result)

        result = _run(runner.run(path))
        assert result["type"] == "error_occurred"
        assert "model error" in result["error_message"]


class TestWorkflowRunnerResume:
    def test_resume_after_gate(self, config: OrchestratorConfig, tmp_path: Path):
        _write_prompt(tmp_path, "p.md")
        yaml = """
name: resume-test
steps:
  - id: gate1
    type: review_gate
    question: "Approve?"
    options: [approve, reject]
  - id: step2
    type: claude
    prompt: p.md
"""
        path = _write_workflow(tmp_path, yaml)
        runner = WorkflowRunner(config, session_dir=tmp_path / "sessions")

        # First run — pauses at gate
        result = _run(runner.run(path))
        assert result["type"] == "interaction_required"

        # Mock claude step for resume
        mock_result = ClaudePResult(
            output_text="OK",
            parsed=ParsedOutput(raw_text="OK"),
            session_id="s2",
        )
        runner.runner.run = AsyncMock(return_value=mock_result)

        # Resume — continues past gate
        result = _run(runner.resume(path, user_input="approve"))
        assert result["type"] == "pipeline_completed"

    def test_resume_abort(self, config: OrchestratorConfig, tmp_path: Path):
        _write_prompt(tmp_path, "p.md")
        yaml = """
name: abort-test
steps:
  - id: step1
    type: claude
    prompt: p.md
"""
        path = _write_workflow(tmp_path, yaml)
        runner = WorkflowRunner(config, session_dir=tmp_path / "sessions")

        # Simulate error state
        mock_result = ClaudePResult(is_error=True, error_message="fail")
        runner.runner.run = AsyncMock(return_value=mock_result)
        result = _run(runner.run(path))
        assert result["type"] == "error_occurred"

        # Resume with abort
        result = _run(runner.resume(path, action="abort"))
        assert result["type"] == "pipeline_failed"
        assert "aborted" in result["error_message"].lower()


class TestWorkflowRunnerFeedback:
    def test_review_gate_feedback_reruns(self, config: OrchestratorConfig, tmp_path: Path):
        _write_prompt(tmp_path, "p.md", "Original prompt")
        yaml = """
name: feedback-test
steps:
  - id: A1
    type: claude
    prompt: p.md
    model: opus
  - id: A1R
    type: review_gate
    question: "Review requirements?"
    options: [approve, feedback]
    on_feedback:
      rerun: A1
      extra_params:
        USER_FEEDBACK: "{{ user_input }}"
      then: A1R
"""
        path = _write_workflow(tmp_path, yaml)
        runner = WorkflowRunner(config, session_dir=tmp_path / "sessions")

        # Mock claude step
        call_count = 0
        async def mock_run(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return ClaudePResult(
                output_text="OK",
                parsed=ParsedOutput(raw_text="OK"),
                session_id=f"s{call_count}",
            )

        runner.runner.run = AsyncMock(side_effect=mock_run)

        # Run — A1 completes, pauses at A1R
        result = _run(runner.run(path))
        assert result["type"] == "interaction_required"
        assert result["current_step"] == "A1R"

        # Resume with feedback — reruns A1, then back to A1R
        result = _run(runner.resume(path, user_input="Fix section 3"))
        # Should pause again at A1R (rerun A1 -> A1R again)
        assert result["type"] == "interaction_required"
        assert result["current_step"] == "A1R"
        assert call_count == 2  # A1 was called twice


class TestWorkflowRunnerOnMarker:
    def test_on_marker_pause(self, config: OrchestratorConfig, tmp_path: Path):
        _write_prompt(tmp_path, "validate.md")
        yaml = """
name: marker-test
steps:
  - id: B2
    type: claude
    prompt: validate.md
    model: opus
    markers: [VALIDATION_PASSED, VALIDATION_FAILED]
    on_marker:
      VALIDATION_FAILED:
        pause: validation_triage
        save_session: true
"""
        path = _write_workflow(tmp_path, yaml)
        runner = WorkflowRunner(config, session_dir=tmp_path / "sessions")

        mock_result = ClaudePResult(
            output_text="VALIDATION_FAILED\nTests broken",
            parsed=ParsedOutput(
                raw_text="VALIDATION_FAILED\nTests broken",
                markers={"VALIDATION_FAILED": True},
            ),
            session_id="sess-b2",
        )
        runner.runner.run = AsyncMock(return_value=mock_result)

        result = _run(runner.run(path))
        assert result["type"] == "interaction_required"
        assert result["current_step"] == "validation_triage"

    def test_no_marker_continues(self, config: OrchestratorConfig, tmp_path: Path):
        _write_prompt(tmp_path, "validate.md")
        yaml = """
name: marker-pass-test
steps:
  - id: B2
    type: claude
    prompt: validate.md
    model: opus
    markers: [VALIDATION_PASSED, VALIDATION_FAILED]
    on_marker:
      VALIDATION_FAILED:
        pause: validation_triage
"""
        path = _write_workflow(tmp_path, yaml)
        runner = WorkflowRunner(config, session_dir=tmp_path / "sessions")

        mock_result = ClaudePResult(
            output_text="VALIDATION_PASSED\nAll good",
            parsed=ParsedOutput(
                raw_text="VALIDATION_PASSED\nAll good",
                markers={"VALIDATION_PASSED": True},
            ),
            session_id="sess-b2",
        )
        runner.runner.run = AsyncMock(return_value=mock_result)

        result = _run(runner.run(path))
        assert result["type"] == "pipeline_completed"


class TestWorkflowRunnerMarkerResume:
    def test_marker_resume_abort(self, config: OrchestratorConfig, tmp_path: Path):
        _write_prompt(tmp_path, "validate.md")
        yaml = """
name: marker-resume-abort
steps:
  - id: B2
    type: claude
    prompt: validate.md
    model: opus
    markers: [VALIDATION_FAILED]
    on_marker:
      VALIDATION_FAILED:
        pause: validation_triage
        save_session: true
        question: "Validation failed."
        options: ["GO", "Conditional GO", "Retry", "Abort"]
        on_resume:
          "Abort":
            goto: _abort
          "Retry":
            goto: B2
"""
        path = _write_workflow(tmp_path, yaml)
        runner = WorkflowRunner(config, session_dir=tmp_path / "sessions")

        mock_result = ClaudePResult(
            output_text="VALIDATION_FAILED",
            parsed=ParsedOutput(
                raw_text="VALIDATION_FAILED",
                markers={"VALIDATION_FAILED": True},
            ),
            session_id="sess-b2",
        )
        runner.runner.run = AsyncMock(return_value=mock_result)

        result = _run(runner.run(path))
        assert result["type"] == "interaction_required"

        # Resume with Abort
        result = _run(runner.resume(path, user_input="Abort"))
        assert result["type"] == "pipeline_failed"
        assert "aborted" in result["error_message"].lower()

    def test_marker_resume_goto(self, config: OrchestratorConfig, tmp_path: Path):
        _write_prompt(tmp_path, "validate.md")
        _write_prompt(tmp_path, "impl.md")
        yaml = """
name: marker-resume-goto
steps:
  - id: B
    type: claude
    prompt: impl.md
  - id: B2
    type: claude
    prompt: validate.md
    model: opus
    markers: [VALIDATION_FAILED]
    on_marker:
      VALIDATION_FAILED:
        pause: validation_triage
        save_session: true
        question: "Validation failed."
        options: ["GO", "Retry"]
        on_resume:
          "Retry":
            goto: B
"""
        path = _write_workflow(tmp_path, yaml)
        runner = WorkflowRunner(config, session_dir=tmp_path / "sessions")

        call_count = 0
        async def mock_run(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                # First B + B2 with failure
                if call_count == 2:
                    return ClaudePResult(
                        output_text="VALIDATION_FAILED",
                        parsed=ParsedOutput(
                            raw_text="VALIDATION_FAILED",
                            markers={"VALIDATION_FAILED": True},
                        ),
                        session_id="sess-b2",
                    )
            # Subsequent calls succeed
            return ClaudePResult(
                output_text="OK",
                parsed=ParsedOutput(raw_text="OK"),
                session_id=f"s{call_count}",
            )

        runner.runner.run = AsyncMock(side_effect=mock_run)

        # Run: B -> B2 (fails) -> pause
        result = _run(runner.run(path))
        assert result["type"] == "interaction_required"

        # Resume with Retry -> goto B -> B2 (now passes) -> complete
        result = _run(runner.resume(path, user_input="Retry (B から再実行)"))
        assert result["type"] == "pipeline_completed"
        assert call_count == 4  # B, B2(fail), B(retry), B2(pass)

    def test_marker_resume_go_default(self, config: OrchestratorConfig, tmp_path: Path):
        """GO (no on_resume match) should continue to next step."""
        _write_prompt(tmp_path, "validate.md")
        yaml = """
name: marker-resume-go
steps:
  - id: B2
    type: claude
    prompt: validate.md
    markers: [VALIDATION_FAILED]
    on_marker:
      VALIDATION_FAILED:
        pause: validation_triage
        save_session: true
        question: "Validation failed."
        options: ["GO", "Abort"]
        on_resume:
          "Abort":
            goto: _abort
"""
        path = _write_workflow(tmp_path, yaml)
        runner = WorkflowRunner(config, session_dir=tmp_path / "sessions")

        mock_result = ClaudePResult(
            output_text="VALIDATION_FAILED",
            parsed=ParsedOutput(
                raw_text="VALIDATION_FAILED",
                markers={"VALIDATION_FAILED": True},
            ),
            session_id="sess-b2",
        )
        runner.runner.run = AsyncMock(return_value=mock_result)

        result = _run(runner.run(path))
        assert result["type"] == "interaction_required"

        # Resume with GO (no match in on_resume -> default: continue)
        result = _run(runner.resume(path, user_input="GO (問題を受容して続行)"))
        assert result["type"] == "pipeline_completed"

    def test_marker_resume_conditional_go(self, config: OrchestratorConfig, tmp_path: Path):
        """Conditional GO should resume session and continue."""
        _write_prompt(tmp_path, "validate.md")
        yaml = """
name: marker-resume-conditional
steps:
  - id: B2
    type: claude
    prompt: validate.md
    model: opus
    markers: [VALIDATION_FAILED]
    on_marker:
      VALIDATION_FAILED:
        pause: validation_triage
        save_session: true
        question: "Validation failed."
        options: ["GO", "Conditional GO", "Abort"]
        on_resume:
          "Conditional GO":
            resume_session: true
            extra_prompt: "Record reason: {{ user_input }}"
          "Abort":
            goto: _abort
"""
        path = _write_workflow(tmp_path, yaml)
        runner = WorkflowRunner(config, session_dir=tmp_path / "sessions")

        mock_result = ClaudePResult(
            output_text="VALIDATION_FAILED",
            parsed=ParsedOutput(
                raw_text="VALIDATION_FAILED",
                markers={"VALIDATION_FAILED": True},
            ),
            session_id="sess-b2",
        )
        runner.runner.run = AsyncMock(return_value=mock_result)

        result = _run(runner.run(path))
        assert result["type"] == "interaction_required"

        # Resume with Conditional GO — should call runner.run with resume_session_id
        resume_mock = ClaudePResult(
            output_text="Recorded",
            parsed=ParsedOutput(raw_text="Recorded"),
            session_id="sess-b2-resumed",
        )
        runner.runner.run = AsyncMock(return_value=resume_mock)

        result = _run(runner.resume(
            path, user_input="Conditional GO テスト理由"
        ))
        assert result["type"] == "pipeline_completed"
        # Verify run was called with resume_session_id
        call_kwargs = runner.runner.run.call_args
        assert call_kwargs.kwargs.get("resume_session_id") == "sess-b2"


class TestWorkflowRunnerVars:
    def test_vars_initialized_from_params(self, config: OrchestratorConfig, tmp_path: Path):
        _write_prompt(tmp_path, "p.md")
        yaml = """
name: vars-test
vars:
  plan_arg:
    from_param: plan
  default_val:
    type: string
    default: "hello"
steps:
  - id: step1
    type: claude
    prompt: p.md
    params:
      PLAN: "{{ plan_arg }}"
      DEFAULT: "{{ default_val }}"
"""
        path = _write_workflow(tmp_path, yaml)
        runner = WorkflowRunner(config, session_dir=tmp_path / "sessions")

        captured_prompt = None
        async def mock_run(prompt, **kwargs):
            nonlocal captured_prompt
            captured_prompt = prompt
            return ClaudePResult(
                output_text="OK",
                parsed=ParsedOutput(raw_text="OK"),
            )

        runner.runner.run = AsyncMock(side_effect=mock_run)
        _run(runner.run(path, params={"plan": "my-plan"}))

        assert "my-plan" in captured_prompt
        assert "hello" in captured_prompt
