"""Tests for ModifyPipeline._read_adr_status and _run_adr_review methods."""

import asyncio
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

from tools.orchestrator.pipelines.modify import ModifyPipeline  # noqa: E402


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


@pytest.fixture
def pipeline() -> ModifyPipeline:
    p = object.__new__(ModifyPipeline)
    p.config = MagicMock()
    p.config.allowed_tools = ["Read", "Write", "Edit", "Bash"]
    p.config.resolve_model.return_value = "sonnet"
    p.config.permission_mode = "auto"
    p.progress = MagicMock()
    return p


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


# ── _run_adr_review tests ────────────────────────────────────────

def _run(coro):
    """Helper to run async coroutine in sync test."""
    return asyncio.get_event_loop().run_until_complete(coro)


class TestRunAdrReview:
    def test_review_accepted(self, pipeline: ModifyPipeline, tmp_path: Path):
        """skill 実行後に status: accepted ならば True を返す。"""
        adr = tmp_path / "adr.md"
        adr.write_text(ACCEPTED_ADR)

        with patch.object(pipeline, "_run_interactive_skill", new=AsyncMock(return_value="")):
            result = _run(pipeline._run_adr_review(tmp_path, "adr.md"))

        assert result is True

    def test_review_not_accepted(self, pipeline: ModifyPipeline, tmp_path: Path):
        """skill 実行後に status: proposed のままなら False を返す。"""
        adr = tmp_path / "adr.md"
        adr.write_text(PROPOSED_ADR)

        with patch.object(pipeline, "_run_interactive_skill", new=AsyncMock(return_value="")):
            result = _run(pipeline._run_adr_review(tmp_path, "adr.md"))

        assert result is False

    def test_allowed_tools_includes_ask_user_question(
        self, pipeline: ModifyPipeline, tmp_path: Path
    ):
        """_run_interactive_skill は常に AskUserQuestion を allowed_tools に含める。"""
        adr = tmp_path / "adr.md"
        adr.write_text(PROPOSED_ADR)

        with patch.object(_sdk_stub, "ClaudeAgentOptions") as mock_opts, \
             patch.object(_sdk_stub, "ClaudeSDKClient") as mock_client_cls:
            # ClaudeSDKClient を非同期コンテキストマネージャとして設定
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.query = AsyncMock()

            async def empty_receive():
                return
                yield  # make it an async generator

            mock_client.receive_messages = empty_receive
            mock_client_cls.return_value = mock_client
            mock_opts.return_value = MagicMock()

            _run(pipeline._run_adr_review(tmp_path, "adr.md"))

            call_kwargs = mock_opts.call_args[1]
            assert "AskUserQuestion" in call_kwargs["allowed_tools"]


# ── _run_scene_review tests ──────────────────────────────────────

class TestRunSceneReview:
    def test_passed_marker_returns_true(self, pipeline: ModifyPipeline, tmp_path: Path):
        """SCENE_REVIEW_PASSED が含まれる出力なら True を返す。"""
        with patch.object(
            pipeline, "_run_interactive_skill",
            new=AsyncMock(return_value="全項目合格。SCENE_REVIEW_PASSED"),
        ):
            result = _run(pipeline._run_scene_review(tmp_path, "my-feature"))

        assert result is True

    def test_no_marker_returns_false(self, pipeline: ModifyPipeline, tmp_path: Path):
        """マーカーなし（空出力）は default-fail で False を返す。"""
        with patch.object(
            pipeline, "_run_interactive_skill",
            new=AsyncMock(return_value=""),
        ):
            result = _run(pipeline._run_scene_review(tmp_path, "my-feature"))

        assert result is False

    def test_failed_marker_returns_false(self, pipeline: ModifyPipeline, tmp_path: Path):
        """SCENE_REVIEW_FAILED が含まれ PASSED がなければ False を返す。"""
        with patch.object(
            pipeline, "_run_interactive_skill",
            new=AsyncMock(return_value="不合格あり。SCENE_REVIEW_FAILED"),
        ):
            result = _run(pipeline._run_scene_review(tmp_path, "my-feature"))

        assert result is False
