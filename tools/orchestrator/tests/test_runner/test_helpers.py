"""Tests for runner/helpers.py — Python helper functions for YAML workflow steps."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from tools.orchestrator.config import OrchestratorConfig
from tools.orchestrator.runner.executors import StepResult
from tools.orchestrator.runner.helpers import (
    _extract_pr_url,
    check_l4_tasks,
    extract_pr_and_cleanup,
    merge_p0_clarification,
    p0_input_check_step,
    plan_resolve_or_create_step,
    post_a1_detect_feature,
    post_plan_creation_step,
    run_preflight_check,
    setup_worktree_only_step,
    setup_worktree_step,
)


@pytest.fixture
def config(tmp_path: Path) -> OrchestratorConfig:
    return OrchestratorConfig(project_root=tmp_path)


@pytest.fixture
def variables() -> dict:
    return {"project_root": "/tmp/test"}


# ── run_preflight_check ──────────────────────────────────────────


class TestRunPreflightCheck:
    @patch("tools.orchestrator.runner.helpers.run_preflight_simple")
    def test_success_returns_base_branch_and_empty_sync_flags(self, mock_preflight, config, variables):
        from tools.orchestrator.preflight import PreflightResultSimple
        mock_preflight.return_value = PreflightResultSimple(base_branch="master")
        result = run_preflight_check(config=config, variables=variables)
        assert isinstance(result, dict)
        assert result["base_branch"] == "master"
        assert result["preflight_behind"] == ""
        assert result["preflight_behind_count"] == "0"
        assert result["preflight_ahead"] == ""
        assert result["preflight_ahead_count"] == "0"

    @patch("tools.orchestrator.runner.helpers.run_preflight_simple")
    def test_error_returns_step_result(self, mock_preflight, config, variables):
        from tools.orchestrator.preflight import PreflightError
        mock_preflight.side_effect = PreflightError("diverged")
        result = run_preflight_check(config=config, variables=variables)
        assert isinstance(result, StepResult)
        assert result.is_error
        assert "diverged" in result.error_message


# ── setup_worktree_step ──────────────────────────────────────────


class TestSetupWorktreeStep:
    @patch("tools.orchestrator.runner.helpers.find_spec_in_worktree")
    @patch("tools.orchestrator.runner.helpers.create_or_reuse_worktree")
    @patch("tools.orchestrator.runner.helpers.resolve_plan")
    def test_new_worktree(self, mock_resolve, mock_create, mock_find, config):
        from tools.orchestrator.worktree import WorktreeInfo

        mock_resolve.return_value = (Path("/plans/test.md"), "test-plan")
        mock_create.return_value = WorktreeInfo(
            path=Path("/wt/feat/test-plan"), branch="feat/test-plan", created=True
        )
        mock_find.return_value = None

        variables = {"plan": "test.md", "base_branch": "master"}
        result = setup_worktree_step(config=config, variables=variables)

        assert isinstance(result, dict)
        assert result["worktree_path"] == "/wt/feat/test-plan"
        assert result["branch_name"] == "feat/test-plan"
        assert result["resume_point"] == "a1-what"
        assert "RUN_A1" in result
        assert result["resume_point"] in result["RUN_A1"]

    @patch("tools.orchestrator.runner.helpers.detect_implement_resume")
    @patch("tools.orchestrator.runner.helpers.find_spec_in_worktree")
    @patch("tools.orchestrator.runner.helpers.create_or_reuse_worktree")
    @patch("tools.orchestrator.runner.helpers.resolve_plan")
    def test_existing_worktree_with_spec(
        self, mock_resolve, mock_create, mock_find, mock_resume, config
    ):
        from unittest.mock import MagicMock
        from tools.orchestrator.state import ImplementResumePoint as RP
        from tools.orchestrator.worktree import WorktreeInfo

        mock_resolve.return_value = (Path("/plans/test.md"), "test-plan")
        mock_create.return_value = WorktreeInfo(
            path=Path("/wt/feat/test-plan"), branch="feat/test-plan", created=False
        )
        spec_mock = MagicMock()
        spec_mock.feature_name = "my-feature"
        mock_find.return_value = spec_mock
        mock_resume.return_value = RP.A3_TASKS

        variables = {"plan": "test.md", "base_branch": "master"}
        result = setup_worktree_step(config=config, variables=variables)

        assert result["feature_name"] == "my-feature"
        assert result["resume_point"] == "a3-tasks"
        assert result["resume_point"] in result["RUN_A3"]


# ── plan_resolve_or_create_step ──────────────────────────────────


class TestPlanResolveOrCreateStep:
    def test_existing_plan_resolved(self, config, tmp_path):
        # Create a plan file
        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)
        (plans_dir / "my-feature.md").write_text("# Plan")

        variables = {"plan": "my-feature"}
        result = plan_resolve_or_create_step(config=config, variables=variables)
        assert isinstance(result, dict)
        assert "plan_path" in result
        assert "my-feature" in result["plan_path"]
        assert result["plan_name"] == "my-feature"
        assert "needs_plan_creation" not in result

    def test_missing_plan_flags_creation(self, config, tmp_path):
        # No plan file exists
        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)

        variables = {"plan": "new feature with API endpoint"}
        result = plan_resolve_or_create_step(config=config, variables=variables)
        assert isinstance(result, dict)
        assert result["needs_plan_creation"] == "true"
        assert result["plan_file_path"].endswith(".md")
        assert result["user_description"] == "new feature with API endpoint"

    def test_empty_plan_argument(self, config, tmp_path):
        plans_dir = tmp_path / "docs" / "plans"
        plans_dir.mkdir(parents=True)

        variables = {"plan": ""}
        result = plan_resolve_or_create_step(config=config, variables=variables)
        assert result["needs_plan_creation"] == "true"
        assert "new-plan" in result["plan_name"]


# ── p0_input_check_step ─────────────────────────────────────────


class TestP0InputCheckStep:
    def test_empty_description_needs_clarification(self, config, variables):
        variables["user_description"] = ""
        result = p0_input_check_step(config=config, variables=variables)
        assert result["p0_needs_clarification"] == "true"

    def test_short_description_needs_clarification(self, config, variables):
        variables["user_description"] = "add button"
        result = p0_input_check_step(config=config, variables=variables)
        assert result["p0_needs_clarification"] == "true"

    def test_good_description_passes(self, config, variables):
        variables["user_description"] = (
            "Add a new API endpoint that should validate user input "
            "and return filtered results from the database"
        )
        result = p0_input_check_step(config=config, variables=variables)
        assert result["p0_needs_clarification"] == ""

    def test_scope_keyword_only(self, config, variables):
        variables["user_description"] = "Add a new component for the dashboard page that renders charts"
        result = p0_input_check_step(config=config, variables=variables)
        assert result["p0_needs_clarification"] == ""

    def test_usecase_keyword_only(self, config, variables):
        variables["user_description"] = "When user clicks submit, it should validate and display errors"
        result = p0_input_check_step(config=config, variables=variables)
        assert result["p0_needs_clarification"] == ""

    def test_no_keywords_needs_clarification(self, config, variables):
        variables["user_description"] = "make it better and fix the thing that is broken now"
        result = p0_input_check_step(config=config, variables=variables)
        assert result["p0_needs_clarification"] == "true"


# ── merge_p0_clarification ──────────────────────────────────────


class TestMergeP0Clarification:
    def test_merges_clarification(self, config, variables):
        variables["user_description"] = "original description"
        variables["_user_input"] = "The feature targets the auth module"
        result = merge_p0_clarification(config=config, variables=variables)
        assert "original description" in result["user_description"]
        assert "auth module" in result["user_description"]
        assert "補足情報" in result["user_description"]

    def test_no_clarification_noop(self, config, variables):
        variables["user_description"] = "original"
        variables["_user_input"] = ""
        result = merge_p0_clarification(config=config, variables=variables)
        assert result == {}


# ── post_plan_creation_step ─────────────────────────────────────


class TestPostPlanCreationStep:
    def test_sets_plan_path(self, config, tmp_path):
        plan_file = tmp_path / "plans" / "test.md"
        plan_file.parent.mkdir(parents=True)
        plan_file.write_text("# Plan")

        variables = {"plan_file_path": str(plan_file)}
        result = post_plan_creation_step(config=config, variables=variables)
        assert result["plan_path"] == str(plan_file)

    def test_fallback_when_file_missing(self, config, variables):
        variables["plan_file_path"] = "/nonexistent/plan.md"
        result = post_plan_creation_step(config=config, variables=variables)
        assert result["plan_path"] == "/nonexistent/plan.md"


# ── setup_worktree_only_step ────────────────────────────────────


class TestSetupWorktreeOnlyStep:
    def test_missing_plan_name_errors(self, config, variables):
        variables["plan_name"] = ""
        result = setup_worktree_only_step(config=config, variables=variables)
        assert isinstance(result, StepResult)
        assert result.is_error
        assert "plan_name" in result.error_message

    @patch("tools.orchestrator.runner.helpers.find_spec_in_worktree")
    @patch("tools.orchestrator.runner.helpers.create_or_reuse_worktree")
    def test_new_worktree(self, mock_create, mock_find, config):
        from tools.orchestrator.worktree import WorktreeInfo

        mock_create.return_value = WorktreeInfo(
            path=Path("/wt/feat/test-plan"), branch="feat/test-plan", created=True
        )
        mock_find.return_value = None

        variables = {"plan_name": "test-plan", "base_branch": "master"}
        result = setup_worktree_only_step(config=config, variables=variables)

        assert isinstance(result, dict)
        assert result["worktree_path"] == "/wt/feat/test-plan"
        assert result["branch_name"] == "feat/test-plan"
        assert result["resume_point"] == "a1-what"
        assert "RUN_A1" in result

    @patch("tools.orchestrator.runner.helpers.detect_implement_resume")
    @patch("tools.orchestrator.runner.helpers.find_spec_in_worktree")
    @patch("tools.orchestrator.runner.helpers.create_or_reuse_worktree")
    def test_existing_worktree_with_spec(self, mock_create, mock_find, mock_resume, config):
        from unittest.mock import MagicMock
        from tools.orchestrator.state import ImplementResumePoint as RP
        from tools.orchestrator.worktree import WorktreeInfo

        mock_create.return_value = WorktreeInfo(
            path=Path("/wt/feat/test-plan"), branch="feat/test-plan", created=False
        )
        spec_mock = MagicMock()
        spec_mock.feature_name = "my-feature"
        mock_find.return_value = spec_mock
        mock_resume.return_value = RP.B_IMPL

        variables = {"plan_name": "test-plan", "base_branch": "master"}
        result = setup_worktree_only_step(config=config, variables=variables)

        assert result["feature_name"] == "my-feature"
        assert result["resume_point"] == "b-impl"
        assert result["resume_point"] in result["RUN_B"]


# ── post_a1_detect_feature ───────────────────────────────────────


class TestPostA1DetectFeature:
    def test_finds_spec(self, config, tmp_path):
        # Create spec.json
        spec_dir = tmp_path / ".kiro" / "specs" / "my-feat"
        spec_dir.mkdir(parents=True)
        (spec_dir / "spec.json").write_text(
            '{"feature_name": "my-feat", "phase": "requirements-generated"}'
        )

        variables = {"worktree_path": str(tmp_path)}
        result = post_a1_detect_feature(config=config, variables=variables)
        assert result == {"feature_name": "my-feat"}

    def test_no_spec_returns_error(self, config, tmp_path):
        variables = {"worktree_path": str(tmp_path)}
        result = post_a1_detect_feature(config=config, variables=variables)
        assert isinstance(result, StepResult)
        assert result.is_error

    def test_keeps_existing_feature_name(self, config, tmp_path):
        variables = {"worktree_path": str(tmp_path), "feature_name": "existing"}
        result = post_a1_detect_feature(config=config, variables=variables)
        assert result == {}


# ── check_l4_tasks ───────────────────────────────────────────────


class TestCheckL4Tasks:
    def test_has_l4(self, config, tmp_path):
        spec_dir = tmp_path / ".kiro" / "specs" / "feat"
        spec_dir.mkdir(parents=True)
        (spec_dir / "tasks.md").write_text(
            "# Tasks\n- [ ] 3.1 Human review: Check the UI\n"
        )
        variables = {"worktree_path": str(tmp_path), "feature_name": "feat"}
        result = check_l4_tasks(config=config, variables=variables)
        assert result["has_l4_tasks"] == "true"

    def test_no_l4(self, config, tmp_path):
        spec_dir = tmp_path / ".kiro" / "specs" / "feat"
        spec_dir.mkdir(parents=True)
        (spec_dir / "tasks.md").write_text("# Tasks\n- [x] 1.1 Code stuff\n")
        variables = {"worktree_path": str(tmp_path), "feature_name": "feat"}
        result = check_l4_tasks(config=config, variables=variables)
        assert result["has_l4_tasks"] == ""

    def test_no_tasks_file(self, config, tmp_path):
        variables = {"worktree_path": str(tmp_path), "feature_name": "feat"}
        result = check_l4_tasks(config=config, variables=variables)
        assert result["has_l4_tasks"] == ""


# ── extract_pr_url ───────────────────────────────────────────────


class TestExtractPrUrl:
    def test_finds_url(self):
        text = "Created PR: https://github.com/owner/repo/pull/42 done"
        assert _extract_pr_url(text) == "https://github.com/owner/repo/pull/42"

    def test_no_url(self):
        assert _extract_pr_url("No PR here") == ""


class TestExtractPrAndCleanup:
    @patch("tools.orchestrator.runner.helpers.remove_worktree")
    def test_with_pr_url(self, mock_remove, config, tmp_path):
        mock_remove.return_value = True
        variables = {
            "worktree_path": str(tmp_path),
            "d_output": "Created https://github.com/org/repo/pull/99",
        }
        result = extract_pr_and_cleanup(config=config, variables=variables)
        assert result["pr_url"] == "https://github.com/org/repo/pull/99"
        assert result["worktree_removed"] == "true"
        mock_remove.assert_called_once()

    @patch("tools.orchestrator.runner.helpers.remove_worktree")
    def test_no_pr_url(self, mock_remove, config, tmp_path):
        variables = {"worktree_path": str(tmp_path), "d_output": "Push failed"}
        result = extract_pr_and_cleanup(config=config, variables=variables)
        assert result["pr_url"] == ""
        mock_remove.assert_not_called()
