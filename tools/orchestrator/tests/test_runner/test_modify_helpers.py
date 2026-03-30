"""Tests for runner/modify_helpers.py — helper functions for modify workflow."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tools.orchestrator.runner.modify_helpers import (
    _build_prompt_with_params,
    _extract_adr_path,
    _extract_pr_url,
    _extract_propagation_entry,
    _get_pending_specs,
    _mark_spec_completed,
    _next_plan_id,
    _parse_execution_order,
    _parse_plan_params,
    _parse_target_specs,
    _read_adr_status,
    check_cascade_review,
    detect_mode_and_setup,
    modify_cleanup,
    plan_delivery_setup,
    plan_setup,
    post_b2_update,
    post_b_update,
    post_m3_update,
    process_m1_result,
    process_mp0_result,
    setup_modify_worktree,
    setup_output_dir,
    write_modify_index,
)
from tools.orchestrator.runner.executors import StepResult


# ── Fixtures ─────────────────────────────────────────────────────

@pytest.fixture
def mock_config(tmp_path: Path) -> MagicMock:
    config = MagicMock()
    config.project_root = tmp_path
    return config


@pytest.fixture
def base_variables() -> dict[str, Any]:
    return {
        "feature": "test-feature",
        "change": "Add logging to API endpoints",
        "modify_plan": "",
        "feature_name": "test-feature",
        "base_branch": "master",
    }


# ══════════════════════════════════════════════════════════════════
# Mode detection
# ══════════════════════════════════════════════════════════════════


class TestDetectModeAndSetup:
    def test_single_mode_with_valid_feature(self, mock_config: MagicMock, tmp_path: Path):
        spec_dir = tmp_path / ".kiro" / "specs" / "my-feature"
        spec_dir.mkdir(parents=True)
        (spec_dir / "spec.json").write_text(json.dumps({
            "feature_name": "my-feature", "phase": "requirements-generated",
        }))

        variables: dict[str, Any] = {"feature": "my-feature", "change": "test", "modify_plan": ""}
        result = detect_mode_and_setup(config=mock_config, variables=variables)

        assert isinstance(result, dict)
        assert result["mode"] == "single"
        assert result["mode_single"] == "true"
        assert result["mode_investigate"] == ""
        assert result["mode_plan"] == ""
        assert result["feature_name"] == "my-feature"

    def test_investigate_mode(self, mock_config: MagicMock):
        variables: dict[str, Any] = {"feature": "", "change": "Add dark mode", "modify_plan": ""}
        result = detect_mode_and_setup(config=mock_config, variables=variables)

        assert isinstance(result, dict)
        assert result["mode"] == "investigate"
        assert result["mode_investigate"] == "true"
        assert result["mode_single"] == ""

    def test_plan_mode(self, mock_config: MagicMock):
        variables: dict[str, Any] = {"feature": "", "change": "", "modify_plan": "m1"}
        result = detect_mode_and_setup(config=mock_config, variables=variables)

        assert isinstance(result, dict)
        assert result["mode"] == "plan"
        assert result["mode_plan"] == "true"
        assert result["mode_single_or_plan"] == "true"

    def test_missing_feature_returns_error(self, mock_config: MagicMock, tmp_path: Path):
        (tmp_path / ".kiro" / "specs").mkdir(parents=True)
        variables: dict[str, Any] = {"feature": "nonexistent", "change": "x", "modify_plan": ""}
        result = detect_mode_and_setup(config=mock_config, variables=variables)

        assert isinstance(result, StepResult)
        assert result.is_error
        assert "nonexistent" in result.error_message

    def test_no_params_returns_error(self, mock_config: MagicMock):
        variables: dict[str, Any] = {"feature": "", "change": "", "modify_plan": ""}
        result = detect_mode_and_setup(config=mock_config, variables=variables)

        assert isinstance(result, StepResult)
        assert result.is_error


# ══════════════════════════════════════════════════════════════════
# M1 processing
# ══════════════════════════════════════════════════════════════════


class TestProcessM1Result:
    def test_parses_full_m1_output(self, mock_config: MagicMock, tmp_path: Path):
        m1_output = (
            "ANALYSIS_DONE\n"
            "CLASSIFICATION: major\n"
            "CASCADE_DEPTH: requirements+design+tasks\n"
            "ADR_REQUIRED: no\n"
            "M1_CONFIDENCE: high\n"
            "DELTA_SUMMARY_START\nAdd logging middleware\nDELTA_SUMMARY_END\n"
        )
        variables: dict[str, Any] = {
            "m1_output": m1_output,
            "feature_name": "test-feature",
            "change": "Add logging",
        }
        result = process_m1_result(config=mock_config, variables=variables)

        assert isinstance(result, dict)
        assert result["cascade_depth"] == "requirements+design+tasks"
        assert result["classification"] == "major"
        assert result["m1_needs_review"] == ""
        assert result["run_M2"] == "true"
        assert result["run_M3"] == "true"
        assert result["run_B"] == "true"
        assert result["run_B2"] == "true"

    def test_requirements_only_skips_impl(self, mock_config: MagicMock, tmp_path: Path):
        m1_output = (
            "ANALYSIS_DONE\n"
            "CLASSIFICATION: doc-update\n"
            "CASCADE_DEPTH: requirements-only\n"
            "ADR_REQUIRED: no\n"
            "M1_CONFIDENCE: high\n"
        )
        variables: dict[str, Any] = {
            "m1_output": m1_output,
            "feature_name": "test-feature",
            "change": "Update docs",
        }
        result = process_m1_result(config=mock_config, variables=variables)

        assert isinstance(result, dict)
        assert result["run_M3"] == ""
        assert result["run_B"] == ""
        assert result["run_B2"] == ""
        assert result["run_steering"] == ""

    def test_low_confidence_sets_review_flag(self, mock_config: MagicMock, tmp_path: Path):
        m1_output = (
            "ANALYSIS_DONE\n"
            "CLASSIFICATION: refactor\n"
            "CASCADE_DEPTH: requirements+design\n"
            "ADR_REQUIRED: no\n"
            "M1_CONFIDENCE: low\n"
        )
        variables: dict[str, Any] = {
            "m1_output": m1_output,
            "feature_name": "test-feature",
            "change": "Refactor auth",
        }
        result = process_m1_result(config=mock_config, variables=variables)

        assert isinstance(result, dict)
        assert result["m1_needs_review"] == "true"

    def test_adr_required_flag(self, mock_config: MagicMock, tmp_path: Path):
        m1_output = (
            "ANALYSIS_DONE\n"
            "CLASSIFICATION: major\n"
            "CASCADE_DEPTH: requirements+design+tasks\n"
            "ADR_REQUIRED: yes\n"
            "ADR_CATEGORY: architecture\n"
            "ADR_REASON: Public API modification\n"
            "M1_CONFIDENCE: high\n"
        )
        variables: dict[str, Any] = {
            "m1_output": m1_output,
            "feature_name": "test-feature",
            "change": "Change API",
        }
        result = process_m1_result(config=mock_config, variables=variables)

        assert isinstance(result, dict)
        assert result["adr_required"] == "true"
        assert result["adr_category"] == "architecture"

    def test_empty_output_returns_error(self, mock_config: MagicMock):
        variables: dict[str, Any] = {"m1_output": "", "feature_name": "x", "change": "x"}
        result = process_m1_result(config=mock_config, variables=variables)

        assert isinstance(result, StepResult)
        assert result.is_error

    def test_caches_m1_result(self, mock_config: MagicMock, tmp_path: Path):
        m1_output = "ANALYSIS_DONE\nCLASSIFICATION: fix\nCASCADE_DEPTH: requirements+design+tasks\nADR_REQUIRED: no\nM1_CONFIDENCE: high\n"
        variables: dict[str, Any] = {
            "m1_output": m1_output,
            "feature_name": "my-feat",
            "change": "Fix bug",
        }
        process_m1_result(config=mock_config, variables=variables)

        cache_file = tmp_path / ".claude" / "orchestrator" / "modify-my-feat.json"
        assert cache_file.exists()
        data = json.loads(cache_file.read_text())
        assert data["feature_name"] == "my-feat"


# ══════════════════════════════════════════════════════════════════
# Cascade review check
# ══════════════════════════════════════════════════════════════════


class TestCheckCascadeReview:
    def test_requirements_only_skips_review(self, mock_config: MagicMock):
        variables: dict[str, Any] = {
            "cascade_depth": "requirements-only",
            "feature_name": "x",
            "worktree_path": "/tmp/wt",
        }
        result = check_cascade_review(config=mock_config, variables=variables)
        assert result["m2r_needs_review"] == ""

    def test_review_needed_with_documents(self, mock_config: MagicMock, tmp_path: Path):
        spec_dir = tmp_path / ".kiro" / "specs" / "my-feat"
        spec_dir.mkdir(parents=True)
        (spec_dir / "requirements-review.md").write_text("## Review\n\U0001F534 Critical issue")

        variables: dict[str, Any] = {
            "cascade_depth": "requirements+design+tasks",
            "feature_name": "my-feat",
            "worktree_path": str(tmp_path),
        }
        result = check_cascade_review(config=mock_config, variables=variables)
        assert result["m2r_needs_review"] == "true"
        assert "\U0001F534" in result["m2r_context"]


# ══════════════════════════════════════════════════════════════════
# MP0 processing
# ══════════════════════════════════════════════════════════════════


class TestProcessMp0Result:
    def test_parses_successful_mp0(self, mock_config: MagicMock):
        mp0_output = (
            "MP0_DONE\n"
            "TARGET_SPECS: auth-module (high), user-service (medium)\n"
            "EXECUTION_ORDER: auth-module, user-service\n"
        )
        variables: dict[str, Any] = {"mp0_output": mp0_output}
        result = process_mp0_result(config=mock_config, variables=variables)

        assert isinstance(result, dict)
        assert len(result["mp0_target_specs"]) == 2
        assert result["mp0_target_specs"][0]["name"] == "auth-module"
        assert result["mp0_target_specs"][0]["confidence"] == "high"

    def test_no_match_returns_pause(self, mock_config: MagicMock):
        mp0_output = "MP0_NO_MATCH\n"
        variables: dict[str, Any] = {"mp0_output": mp0_output}
        result = process_mp0_result(config=mock_config, variables=variables)

        assert isinstance(result, StepResult)
        assert result.is_pause


# ══════════════════════════════════════════════════════════════════
# Parallel execution helpers
# ══════════════════════════════════════════════════════════════════


class TestRunMp1Parallel:
    def test_parallel_execution(self, mock_config: MagicMock, tmp_path: Path):
        """Test that MP1 runs multiple specs in parallel."""
        from tools.orchestrator.runner.modify_helpers import run_mp1_parallel

        # Setup prompt file
        prompts_dir = tmp_path / "tools" / "orchestrator" / "prompts"
        prompts_dir.mkdir(parents=True)
        (prompts_dir / "modify-plan-gen.md").write_text("Generate plan for {{ FEATURE_NAME }}")

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        mock_result = MagicMock()
        mock_result.is_error = False
        mock_result.output_text = "MP1_SUMMARY_START\nSome summary\nMP1_SUMMARY_END\n"
        mock_result.parsed = MagicMock()
        mock_result.parsed.mp1_summary = "Some summary"
        mock_result.parsed.mp1_gaps = ""

        with patch(
            "tools.orchestrator.runner.claude_p.ClaudePRunner"
        ) as MockRunner:
            mock_runner_instance = MockRunner.return_value
            mock_runner_instance.run = AsyncMock(return_value=mock_result)

            variables: dict[str, Any] = {
                "mp0_target_specs": [
                    {"name": "spec-a", "confidence": "high"},
                    {"name": "spec-b", "confidence": "medium"},
                ],
                "change": "Add feature X",
                "mp0_propagation_map": "",
                "mp0_target_specs_str": "spec-a (high), spec-b (medium)",
                "mp_output_dir": str(output_dir),
            }

            result = asyncio.run(
                run_mp1_parallel(config=mock_config, variables=variables)
            )

            assert isinstance(result, dict)
            assert len(result["mp1_succeeded"]) == 2
            assert "spec-a" in result["mp1_succeeded"]
            assert "spec-b" in result["mp1_succeeded"]
            # Verify parallel execution (run called twice)
            assert mock_runner_instance.run.call_count == 2


class TestRunMp2Parallel:
    def test_parallel_review(self, mock_config: MagicMock, tmp_path: Path):
        """Test that MP2 reviews run in parallel."""
        from tools.orchestrator.runner.modify_helpers import run_mp2_parallel

        prompts_dir = tmp_path / "tools" / "orchestrator" / "prompts"
        prompts_dir.mkdir(parents=True)
        (prompts_dir / "modify-plan-review.md").write_text("Review plan for {{ FEATURE_NAME }}")

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        mock_result = MagicMock()
        mock_result.is_error = False
        mock_result.output_text = "MP2_STATUS: READY\n"
        mock_result.parsed = MagicMock()
        mock_result.parsed.mp2_status = "READY"
        mock_result.parsed.mp2_changes = ""

        with patch(
            "tools.orchestrator.runner.claude_p.ClaudePRunner"
        ) as MockRunner:
            mock_runner_instance = MockRunner.return_value
            mock_runner_instance.run = AsyncMock(return_value=mock_result)

            variables: dict[str, Any] = {
                "mp1_succeeded": ["spec-a", "spec-b"],
                "mp1_results": {
                    "spec-a": {"summary": "Summary A", "gaps": ""},
                    "spec-b": {"summary": "Summary B", "gaps": ""},
                },
                "change": "Add feature X",
                "mp0_propagation_map": "",
                "mp_output_dir": str(output_dir),
            }

            result = asyncio.run(
                run_mp2_parallel(config=mock_config, variables=variables)
            )

            assert isinstance(result, dict)
            assert "spec-a" in result["mp2_results"]
            assert "spec-b" in result["mp2_results"]
            assert mock_runner_instance.run.call_count == 2


# ══════════════════════════════════════════════════════════════════
# Plan-driven mode helpers
# ══════════════════════════════════════════════════════════════════


class TestPlanSetup:
    def test_valid_plan_setup(self, mock_config: MagicMock, tmp_path: Path):
        plan_dir = tmp_path / "docs" / "modify-plans" / "m1"
        plan_dir.mkdir(parents=True)
        (plan_dir / "_index.md").write_text(
            "# Modify Plan\n\n## 推奨実行順序\n1. spec-a\n2. spec-b\n"
        )

        with patch(
            "tools.orchestrator.runner.modify_helpers.create_or_reuse_worktree"
        ) as mock_wt:
            mock_wt.return_value = MagicMock(
                path=tmp_path / "worktree", branch="modify/m1", created=True
            )

            variables: dict[str, Any] = {"modify_plan": "m1", "base_branch": "master"}
            result = plan_setup(config=mock_config, variables=variables)

            assert isinstance(result, dict)
            assert result["plan_pending"] == ["spec-a", "spec-b"]
            assert "worktree_path" in result

    def test_missing_plan_dir_returns_error(self, mock_config: MagicMock):
        variables: dict[str, Any] = {"modify_plan": "nonexistent", "base_branch": "master"}
        result = plan_setup(config=mock_config, variables=variables)

        assert isinstance(result, StepResult)
        assert result.is_error


class TestPlanDeliverySetup:
    def test_sets_delivery_variables(self, mock_config: MagicMock):
        variables: dict[str, Any] = {
            "plan_pending": ["spec-a", "spec-b"],
            "plan_m1_results": {
                "spec-a": {
                    "feature_name": "feat-a",
                    "delta_summary": "Add A",
                    "change_description": "Change A",
                    "cascade_depth": "requirements+design+tasks",
                },
                "spec-b": {
                    "feature_name": "feat-b",
                    "delta_summary": "Add B",
                    "change_description": "Change B",
                    "cascade_depth": "requirements-only",
                },
            },
        }
        result = plan_delivery_setup(config=mock_config, variables=variables)

        assert isinstance(result, dict)
        assert result["feature_name"] == "feat-a"
        assert result["run_steering"] == "true"


# ══════════════════════════════════════════════════════════════════
# Static utility tests
# ══════════════════════════════════════════════════════════════════


class TestBuildPromptWithParams:
    def test_appends_params(self):
        template = "# Prompt\nDo something."
        params = {"FEATURE": "auth", "CHANGE": "fix bug"}
        result = _build_prompt_with_params(template, params)

        assert "## Parameters" in result
        assert "FEATURE: auth" in result
        assert "CHANGE: fix bug" in result

    def test_empty_params(self):
        template = "# Prompt"
        assert _build_prompt_with_params(template, {}) == "# Prompt"


class TestExtractPrUrl:
    def test_extracts_url(self):
        text = "Created PR: https://github.com/org/repo/pull/42 done"
        assert _extract_pr_url(text) == "https://github.com/org/repo/pull/42"

    def test_no_url(self):
        assert _extract_pr_url("no url here") == ""


class TestExtractAdrPath:
    def test_extracts_path(self):
        text = "ADR created at ADR_PATH=.kiro/decisions/api/001-change.md"
        assert _extract_adr_path(text) == ".kiro/decisions/api/001-change.md"

    def test_no_path(self):
        assert _extract_adr_path("no adr here") is None


class TestReadAdrStatus:
    def test_reads_accepted(self, tmp_path: Path):
        adr = tmp_path / "adr.md"
        adr.write_text("---\nstatus: accepted\n---\n# ADR")
        assert _read_adr_status(adr) == "accepted"

    def test_reads_proposed(self, tmp_path: Path):
        adr = tmp_path / "adr.md"
        adr.write_text("---\nstatus: proposed\n---\n# ADR")
        assert _read_adr_status(adr) == "proposed"

    def test_missing_file(self, tmp_path: Path):
        assert _read_adr_status(tmp_path / "missing.md") is None


class TestParseTargetSpecs:
    def test_parses_with_confidence(self):
        result = _parse_target_specs("auth (high), user-service (medium)")
        assert result == [("auth", "high"), ("user-service", "medium")]

    def test_parses_without_confidence(self):
        result = _parse_target_specs("auth, user-service")
        assert result == [("auth", "unknown"), ("user-service", "unknown")]


class TestExtractPropagationEntry:
    def test_extracts_section(self):
        prop_map = "## auth\nChanges to auth\nImpact: high\n\n## user\nChanges to user\n"
        result = _extract_propagation_entry(prop_map, "auth")
        assert "Changes to auth" in result
        assert "user" not in result

    def test_missing_section(self):
        assert _extract_propagation_entry("## other\n", "auth") == ""


class TestNextPlanId:
    def test_first_plan(self, tmp_path: Path):
        assert _next_plan_id(tmp_path) == "m1"

    def test_increments(self, tmp_path: Path):
        (tmp_path / "m1").mkdir()
        (tmp_path / "m3").mkdir()
        assert _next_plan_id(tmp_path) == "m4"


class TestParseExecutionOrder:
    def test_parses_numbered_list(self, tmp_path: Path):
        index = tmp_path / "_index.md"
        index.write_text(
            "# Plan\n\n## 推奨実行順序\n1. spec-a\n2. spec-b\n3. spec-c\n"
        )
        assert _parse_execution_order(index) == ["spec-a", "spec-b", "spec-c"]


class TestGetPendingSpecs:
    def test_all_pending(self, tmp_path: Path):
        assert _get_pending_specs(tmp_path, ["a", "b", "c"]) == ["a", "b", "c"]

    def test_some_completed(self, tmp_path: Path):
        (tmp_path / ".status.json").write_text(json.dumps({"completed": ["a"]}))
        assert _get_pending_specs(tmp_path, ["a", "b", "c"]) == ["b", "c"]


class TestMarkSpecCompleted:
    def test_marks_first(self, tmp_path: Path):
        _mark_spec_completed(tmp_path, "spec-a")
        data = json.loads((tmp_path / ".status.json").read_text())
        assert data["completed"] == ["spec-a"]

    def test_appends(self, tmp_path: Path):
        (tmp_path / ".status.json").write_text(json.dumps({"completed": ["spec-a"]}))
        _mark_spec_completed(tmp_path, "spec-b")
        data = json.loads((tmp_path / ".status.json").read_text())
        assert data["completed"] == ["spec-a", "spec-b"]


class TestParsePlanParams:
    def test_parses_yaml_block(self, tmp_path: Path):
        plan = tmp_path / "spec.md"
        plan.write_text(
            "# Plan\n\n## /modify 実行パラメータ\n\n```yaml\n"
            "feature_name: auth-module\n"
            "change_description: |\n  Add MFA support\n  to auth flow\n```\n"
        )
        feature, change = _parse_plan_params(plan)
        assert feature == "auth-module"
        assert "Add MFA support" in change

    def test_no_section(self, tmp_path: Path):
        plan = tmp_path / "spec.md"
        plan.write_text("# Plan\nNo params here")
        assert _parse_plan_params(plan) == ("", "")


class TestWriteModifyIndex:
    def test_writes_index(self, mock_config: MagicMock, tmp_path: Path):
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        variables: dict[str, Any] = {
            "mp_output_dir": str(output_dir),
            "mp_slug": "m1",
            "change": "Add dark mode",
            "mp0_target_specs": [
                {"name": "ui", "confidence": "high"},
                {"name": "theme", "confidence": "medium"},
            ],
            "mp0_propagation_map": "## ui\nTheme changes",
            "mp0_execution_order_str": "ui, theme",
            "mp2_results": {
                "ui": {"status": "READY"},
                "theme": {"status": "READY"},
            },
        }
        result = write_modify_index(config=mock_config, variables=variables)

        assert result["mp_status"] == "completed"
        index_path = output_dir / "_index.md"
        assert index_path.exists()
        content = index_path.read_text()
        assert "Modify Plan: m1" in content
        assert "Add dark mode" in content
        assert "| ui | high |" in content


class TestSetupOutputDir:
    def test_creates_directory(self, mock_config: MagicMock, tmp_path: Path):
        variables: dict[str, Any] = {"mp0_plan_slug": "my-plan"}
        result = setup_output_dir(config=mock_config, variables=variables)

        assert isinstance(result, dict)
        output_dir = Path(result["mp_output_dir"])
        assert output_dir.exists()
        assert result["mp_slug"] == "my-plan"

    def test_auto_increments_without_slug(self, mock_config: MagicMock, tmp_path: Path):
        (tmp_path / "docs" / "modify-plans" / "m1").mkdir(parents=True)
        variables: dict[str, Any] = {"mp0_plan_slug": ""}
        result = setup_output_dir(config=mock_config, variables=variables)

        assert result["mp_slug"] == "m2"
