"""Tests for ModifyPipeline._accept_adr method."""

import sys
from datetime import date
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

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


VALID_ADR = """\
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
- Driver 2

## Decision

We decided to do X.

## Consequences

### Positive

- Good thing

### Negative

- Bad thing
"""


@pytest.fixture
def pipeline() -> ModifyPipeline:
    p = object.__new__(ModifyPipeline)
    p.config = MagicMock()
    p.progress = MagicMock()
    return p


class TestAcceptProposedAdr:
    def test_accept_proposed_adr(self, pipeline: ModifyPipeline, tmp_path: Path):
        adr_file = tmp_path / "adr.md"
        adr_file.write_text(VALID_ADR)

        result = pipeline._accept_adr(tmp_path, "adr.md")

        assert result is True
        content = adr_file.read_text()
        assert "status: accepted" in content
        assert "status: proposed" not in content

    def test_accept_already_accepted(self, pipeline: ModifyPipeline, tmp_path: Path):
        adr_file = tmp_path / "adr.md"
        adr_file.write_text(VALID_ADR.replace("status: proposed", "status: accepted"))

        result = pipeline._accept_adr(tmp_path, "adr.md")

        assert result is True
        assert "status: accepted" in adr_file.read_text()


class TestAcceptAdrRejections:
    def test_reject_missing_file(self, pipeline: ModifyPipeline, tmp_path: Path):
        result = pipeline._accept_adr(tmp_path, "nonexistent.md")

        assert result is False
        pipeline.progress.print_warning.assert_called()

    def test_reject_no_frontmatter(self, pipeline: ModifyPipeline, tmp_path: Path):
        adr_file = tmp_path / "adr.md"
        adr_file.write_text("# No frontmatter\n\nJust content.")

        result = pipeline._accept_adr(tmp_path, "adr.md")

        assert result is False

    def test_reject_malformed_frontmatter(self, pipeline: ModifyPipeline, tmp_path: Path):
        adr_file = tmp_path / "adr.md"
        adr_file.write_text("---\ntitle: test\nstatus: proposed\n\nNo closing fence.")

        result = pipeline._accept_adr(tmp_path, "adr.md")

        assert result is False

    def test_reject_missing_sections(self, pipeline: ModifyPipeline, tmp_path: Path):
        adr_file = tmp_path / "adr.md"
        adr_file.write_text(
            "---\nstatus: proposed\ndate: \"2025-01-01\"\n---\n\n## Context\n\nSome context.\n"
        )

        result = pipeline._accept_adr(tmp_path, "adr.md")

        assert result is False
        warning_msg = pipeline.progress.print_warning.call_args[0][0]
        assert "ADR missing sections" in warning_msg


class TestAcceptAdrDateUpdate:
    def test_date_updated_on_accept(self, pipeline: ModifyPipeline, tmp_path: Path):
        adr_file = tmp_path / "adr.md"
        adr_file.write_text(VALID_ADR)

        pipeline._accept_adr(tmp_path, "adr.md")

        content = adr_file.read_text()
        today = date.today().isoformat()
        assert f'date: "{today}"' in content


class TestAcceptAdrRegression:
    def test_regression_accepted_trade_offs(self, pipeline: ModifyPipeline, tmp_path: Path):
        """Regression: 'accepted trade-offs' in body should NOT fool status check."""
        adr_content = VALID_ADR.replace("status: proposed", "status: deprecated")
        adr_content = adr_content.replace(
            "## Consequences",
            "## Consequences\n\nThis has accepted trade-offs that are well understood.",
        )
        adr_file = tmp_path / "adr.md"
        adr_file.write_text(adr_content)

        result = pipeline._accept_adr(tmp_path, "adr.md")

        assert result is False
