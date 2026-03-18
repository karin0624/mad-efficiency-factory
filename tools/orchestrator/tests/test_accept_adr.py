"""Tests for ADR gate and helper methods (updated for checkpoint-based API)."""

import asyncio
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Stub claude_agent_sdk before importing the pipeline module
_sdk_stub = ModuleType("claude_agent_sdk")
for attr in (
    "AssistantMessage", "ClaudeAgentOptions", "ClaudeSDKClient",
    "ResultMessage", "TextBlock", "ToolResultBlock", "ToolUseBlock",
    "UserMessage", "query",
):
    setattr(_sdk_stub, attr, MagicMock())
sys.modules.setdefault("claude_agent_sdk", _sdk_stub)

from tools.orchestrator.pipelines.modify import M1Result, ModifyPipeline  # noqa: E402
from tools.orchestrator.session import PipelineSession  # noqa: E402


# ── Fixtures ──────────────────────────────────────────────────────

PROPOSED_ADR = """\
---
title: "Test ADR"
status: proposed
date: "2025-01-01"
category: architecture
spec: test-feature
---

## Context

Some context here.

## Decision Drivers

- Driver 1

## Decision

We decided to do X.

## Consequences

- Good thing
"""

ACCEPTED_ADR = PROPOSED_ADR.replace("status: proposed", "status: accepted")
DEPRECATED_ADR = PROPOSED_ADR.replace("status: proposed", "status: deprecated")


def _make_m1(*, adr_required: bool = True) -> M1Result:
    return M1Result(
        feature_name="test-feature",
        change_description="テスト変更",
        m1_output="M1 output text",
        cascade_depth="full",
        classification="enhancement",
        delta_summary="delta summary",
        adr_required=adr_required,
        adr_category="architecture",
        adr_reason="テスト理由",
    )


@pytest.fixture
def pipeline(tmp_path: Path) -> ModifyPipeline:
    config = MagicMock()
    config.allowed_tools = ["Read", "Write", "Edit", "Bash"]
    config.resolve_model.return_value = "sonnet"
    config.permission_mode = "auto"

    session = PipelineSession(
        session_id="test123",
        pipeline="modify",
        params={"feature": "test-feature", "change": "test change"},
    )
    session_dir = tmp_path / "sessions"
    session_dir.mkdir()

    p = object.__new__(ModifyPipeline)
    p.config = config
    p.session = session
    p.session_dir = session_dir
    p.tracker = MagicMock()
    p.runner = MagicMock()
    return p


def _run(coro):
    """Helper to run async coroutine in sync test."""
    return asyncio.run(coro)


# ── _read_adr_status tests ───────────────────────────────────────

class TestReadAdrStatus:
    def test_read_status_proposed(self, tmp_path: Path):
        adr = tmp_path / "adr.md"
        adr.write_text(PROPOSED_ADR)
        assert ModifyPipeline._read_adr_status(adr) == "proposed"

    def test_read_status_accepted(self, tmp_path: Path):
        adr = tmp_path / "adr.md"
        adr.write_text(ACCEPTED_ADR)
        assert ModifyPipeline._read_adr_status(adr) == "accepted"

    def test_read_status_missing_file(self, tmp_path: Path):
        adr = tmp_path / "nonexistent.md"
        assert ModifyPipeline._read_adr_status(adr) is None

    def test_read_status_no_frontmatter(self, tmp_path: Path):
        adr = tmp_path / "adr.md"
        adr.write_text("# No frontmatter\n\nJust content.")
        assert ModifyPipeline._read_adr_status(adr) is None

    def test_read_status_malformed_frontmatter(self, tmp_path: Path):
        adr = tmp_path / "adr.md"
        adr.write_text("---\ntitle: test\nstatus: proposed\n\nNo closing fence.")
        assert ModifyPipeline._read_adr_status(adr) is None

    def test_regression_accepted_in_body(self, tmp_path: Path):
        """Body に 'accepted' があっても frontmatter の status を返す。"""
        content = PROPOSED_ADR.replace("status: proposed", "status: deprecated")
        content += "\nThis has accepted trade-offs.\n"
        adr = tmp_path / "adr.md"
        adr.write_text(content)
        assert ModifyPipeline._read_adr_status(adr) == "deprecated"


# ── _run_adr_gate tests ──────────────────────────────────────────

class TestRunAdrGate:
    def test_adr_not_required_returns_none(self, pipeline: ModifyPipeline, tmp_path: Path):
        """ADR 不要 → None 返却。"""
        m1 = _make_m1(adr_required=False)
        result = _run(pipeline._run_adr_gate(m1, tmp_path))
        assert result is None

    def test_adr_accepted_returns_path(self, pipeline: ModifyPipeline, tmp_path: Path):
        """status=accepted → adr_path 返却。"""
        m1 = _make_m1()
        adr_rel = ".kiro/decisions/architecture/0001-test.md"
        adr_file = tmp_path / adr_rel
        adr_file.parent.mkdir(parents=True, exist_ok=True)
        adr_file.write_text(ACCEPTED_ADR)

        with patch.object(
            pipeline, "_run_skill_step",
            new=AsyncMock(return_value=f"ADR created.\nADR_PATH={adr_rel}"),
        ), patch("tools.orchestrator.pipelines.modify.find_spec_by_name", return_value=None):
            result = _run(pipeline._run_adr_gate(m1, tmp_path))

        assert result == adr_rel

    def test_adr_proposed_returns_interaction(self, pipeline: ModifyPipeline, tmp_path: Path):
        """status=proposed → interaction_required レスポンス。"""
        m1 = _make_m1()
        adr_rel = ".kiro/decisions/architecture/0001-test.md"
        adr_file = tmp_path / adr_rel
        adr_file.parent.mkdir(parents=True, exist_ok=True)
        adr_file.write_text(PROPOSED_ADR)

        with patch.object(
            pipeline, "_run_skill_step",
            new=AsyncMock(return_value=f"ADR_PATH={adr_rel}"),
        ):
            result = _run(pipeline._run_adr_gate(m1, tmp_path))

        assert isinstance(result, dict)
        assert result["type"] == "interaction_required"
        assert result["current_step"] == "adr_review"

    def test_adr_deprecated_returns_interaction(self, pipeline: ModifyPipeline, tmp_path: Path):
        """status=deprecated → interaction_required レスポンス。"""
        m1 = _make_m1()
        adr_rel = ".kiro/decisions/architecture/0001-test.md"
        adr_file = tmp_path / adr_rel
        adr_file.parent.mkdir(parents=True, exist_ok=True)
        adr_file.write_text(DEPRECATED_ADR)

        with patch.object(
            pipeline, "_run_skill_step",
            new=AsyncMock(return_value=f"ADR_PATH={adr_rel}"),
        ):
            result = _run(pipeline._run_adr_gate(m1, tmp_path))

        assert isinstance(result, dict)
        assert result["type"] == "interaction_required"

    def test_no_marker_glob_fallback(self, pipeline: ModifyPipeline, tmp_path: Path):
        """ADR_PATH マーカーなし + glob フォールバック成功 → adr_path 返却。"""
        m1 = _make_m1()
        adr_rel = ".kiro/decisions/architecture/0001-test.md"
        adr_file = tmp_path / adr_rel
        adr_file.parent.mkdir(parents=True, exist_ok=True)
        adr_file.write_text(ACCEPTED_ADR)

        with patch.object(
            pipeline, "_run_skill_step",
            new=AsyncMock(return_value="ADR created successfully."),
        ), patch.object(
            ModifyPipeline, "_find_new_adr_file", return_value=adr_rel,
        ), patch("tools.orchestrator.pipelines.modify.find_spec_by_name", return_value=None):
            result = _run(pipeline._run_adr_gate(m1, tmp_path))

        assert result == adr_rel

    def test_no_marker_no_fallback_returns_error(self, pipeline: ModifyPipeline, tmp_path: Path):
        """ADR_PATH マーカーなし + glob フォールバック失敗 → error_occurred レスポンス。"""
        m1 = _make_m1()

        with patch.object(
            pipeline, "_run_skill_step",
            new=AsyncMock(return_value="Something happened."),
        ), patch.object(
            ModifyPipeline, "_find_new_adr_file", return_value=None,
        ):
            result = _run(pipeline._run_adr_gate(m1, tmp_path))

        assert isinstance(result, dict)
        assert result["type"] == "error_occurred"
        assert "did not produce a file" in result["error_message"]


# ── _extract_adr_path_from_output tests ──────────────────────────

class TestExtractAdrPath:
    def test_extracts_path(self):
        text = "Done.\nADR_PATH=.kiro/decisions/spec/0001-foo.md\nEnd."
        assert ModifyPipeline._extract_adr_path_from_output(text) == ".kiro/decisions/spec/0001-foo.md"

    def test_no_marker(self):
        assert ModifyPipeline._extract_adr_path_from_output("no marker here") is None


# ── _find_new_adr_file tests ─────────────────────────────────────

class TestFindNewAdrFile:
    def test_no_decisions_dir(self, tmp_path: Path):
        assert ModifyPipeline._find_new_adr_file(tmp_path) is None

    def test_git_diff_finds_new_file(self, tmp_path: Path):
        decisions_dir = tmp_path / ".kiro" / "decisions" / "arch"
        decisions_dir.mkdir(parents=True)
        (decisions_dir / "0001-test.md").write_text("content")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0,
                stdout=".kiro/decisions/arch/0001-test.md\n",
            )
            result = ModifyPipeline._find_new_adr_file(tmp_path)

        assert result == ".kiro/decisions/arch/0001-test.md"

    def test_no_new_files_falls_back_to_rglob(self, tmp_path: Path):
        decisions_dir = tmp_path / ".kiro" / "decisions" / "arch"
        decisions_dir.mkdir(parents=True)
        adr = decisions_dir / "0001-test.md"
        adr.write_text("content")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="",
            )
            result = ModifyPipeline._find_new_adr_file(tmp_path)

        assert result is not None
        assert result.endswith("0001-test.md")
