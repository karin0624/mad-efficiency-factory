"""Tests for runner/loader.py — YAML loading and validation."""

import tempfile
from pathlib import Path

import pytest

from tools.orchestrator.runner.loader import load_workflow


class TestLoadWorkflow:
    def test_load_valid_yaml(self, tmp_path: Path):
        yaml_content = """
name: test-workflow
description: A test workflow
vars:
  plan:
    from_param: plan
steps:
  - id: A1
    type: claude
    prompt: prompts/a1.md
    model: opus
  - id: gate
    type: review_gate
    question: "Approve?"
    options: [approve, reject]
"""
        path = tmp_path / "test.yaml"
        path.write_text(yaml_content)

        workflow = load_workflow(path)
        assert workflow.name == "test-workflow"
        assert len(workflow.steps) == 2
        assert workflow.steps[0].id == "A1"
        assert workflow.steps[0].type == "claude"
        assert workflow.steps[1].type == "review_gate"

    def test_load_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_workflow("/nonexistent/path.yaml")

    def test_load_invalid_yaml(self, tmp_path: Path):
        path = tmp_path / "bad.yaml"
        path.write_text("not: valid: yaml: [[[")
        with pytest.raises(Exception):
            load_workflow(path)

    def test_load_non_mapping_yaml(self, tmp_path: Path):
        path = tmp_path / "list.yaml"
        path.write_text("- item1\n- item2")
        with pytest.raises(ValueError, match="must be a YAML mapping"):
            load_workflow(path)

    def test_load_validation_error(self, tmp_path: Path):
        yaml_content = """
name: test
steps:
  - id: bad
    type: claude
    # missing prompt
"""
        path = tmp_path / "bad_step.yaml"
        path.write_text(yaml_content)
        with pytest.raises(Exception):
            load_workflow(path)

    def test_load_complex_workflow(self, tmp_path: Path):
        yaml_content = """
name: implement
description: "Plan -> Spec -> Impl -> Validate -> PR"
vars:
  plan_argument:
    from_param: plan
  worktree_path:
    type: path
  resume_point:
    type: string
    default: a1-what
steps:
  - id: preflight
    type: python
    function: orchestrator.preflight:run_preflight
    args:
      project_root: "{{ project_root }}"
    extract:
      base_branch: "{{ result.base_branch }}"

  - id: A1
    type: claude
    prompt: tools/orchestrator/prompts/impl-spec-what.md
    model: opus
    params:
      WORKTREE_PATH: "{{ worktree_path }}"
    when: "{{ resume_point in RUN_A1 }}"

  - id: A1R
    type: review_gate
    question: "要件レビュー文書を確認してください。"
    options: [approve, feedback]
    on_feedback:
      rerun: A1
      extra_params:
        USER_FEEDBACK: "{{ user_input }}"
      then: A1R

  - id: parallel_test
    type: parallel
    steps:
      - id: sub1
        type: claude
        prompt: p1.md
      - id: sub2
        type: claude
        prompt: p2.md

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
        path = tmp_path / "implement.yaml"
        path.write_text(yaml_content)

        workflow = load_workflow(path)
        assert workflow.name == "implement"
        assert len(workflow.steps) == 5
        assert workflow.vars["resume_point"].default == "a1-what"
        assert workflow.steps[2].on_feedback is not None
        assert workflow.steps[2].on_feedback.rerun == "A1"
        assert workflow.steps[3].type == "parallel"
        assert len(workflow.steps[3].steps) == 2
        assert workflow.steps[4].on_marker["VALIDATION_FAILED"].save_session is True
