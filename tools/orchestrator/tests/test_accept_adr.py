"""Tests for ModifyPipeline._read_adr_status and _run_adr_review methods."""

import asyncio
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

# Stub claude_agent_sdk before importing the pipeline module
_sdk_stub = ModuleType("claude_agent_sdk")
for attr in (
    "AssistantMessage", "ClaudeAgentOptions", "ResultMessage",
    "TextBlock", "ToolResultBlock", "ToolUseBlock", "UserMessage", "query",
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

        async def fake_query(**kwargs):
            return
            yield  # make it an async generator

        with patch.object(_sdk_stub, "query", fake_query):
            result = _run(pipeline._run_adr_review(tmp_path, "adr.md"))

        assert result is True

    def test_review_not_accepted(self, pipeline: ModifyPipeline, tmp_path: Path):
        """skill 実行後に status: proposed のままなら False を返す。"""
        adr = tmp_path / "adr.md"
        adr.write_text(PROPOSED_ADR)

        async def fake_query(**kwargs):
            return
            yield

        with patch.object(_sdk_stub, "query", fake_query):
            result = _run(pipeline._run_adr_review(tmp_path, "adr.md"))

        assert result is False

    def test_allowed_tools_includes_ask_user_question(
        self, pipeline: ModifyPipeline, tmp_path: Path
    ):
        """ClaudeAgentOptions の allowed_tools に AskUserQuestion が含まれる。"""
        adr = tmp_path / "adr.md"
        adr.write_text(PROPOSED_ADR)

        async def fake_query(**kwargs):
            return
            yield

        with patch.object(_sdk_stub, "query", fake_query), \
             patch.object(_sdk_stub, "ClaudeAgentOptions") as mock_opts:
            mock_opts.return_value = MagicMock()
            _run(pipeline._run_adr_review(tmp_path, "adr.md"))

            call_kwargs = mock_opts.call_args[1]
            assert "AskUserQuestion" in call_kwargs["allowed_tools"]
