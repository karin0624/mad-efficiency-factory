"""Tests for pipeline.py — _pause_with_session helper."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

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

from tools.orchestrator.pipeline import InterruptiblePipeline  # noqa: E402
from tools.orchestrator.session import PipelineSession  # noqa: E402


class ConcretePipeline(InterruptiblePipeline):
    """Minimal concrete pipeline for testing base class helpers."""

    async def run_until_checkpoint(self):
        return {}


def _make_pipeline() -> ConcretePipeline:
    config = MagicMock()
    session = PipelineSession(
        session_id="test-session",
        pipeline="test",
        checkpoint="start",
        status="running",
        checkpoint_data={},
    )
    session_dir = Path("/tmp/test-session")
    pipeline = ConcretePipeline(config, session, session_dir)
    pipeline._save = MagicMock()  # avoid disk writes
    return pipeline


class TestPauseWithSession:
    def test_saves_session_key(self):
        p = _make_pipeline()
        result = p._pause_with_session(
            checkpoint="test_cp",
            session_key="my_session_id",
            session_id="sid-123",
            question="Test question?",
        )
        assert p.session.checkpoint_data["my_session_id"] == "sid-123"
        assert result["type"] == "interaction_required"
        assert p.session.checkpoint == "test_cp"

    def test_saves_extra_data(self):
        p = _make_pipeline()
        p._pause_with_session(
            checkpoint="test_cp",
            session_key="sid_key",
            session_id="sid-456",
            question="Q?",
            extra_field="extra_value",
            another="data",
        )
        assert p.session.checkpoint_data["sid_key"] == "sid-456"
        assert p.session.checkpoint_data["extra_field"] == "extra_value"
        assert p.session.checkpoint_data["another"] == "data"

    def test_returns_interaction_format(self):
        p = _make_pipeline()
        result = p._pause_with_session(
            checkpoint="my_checkpoint",
            session_key="key",
            session_id="sid",
            question="Choose an option",
            options=["A", "B"],
            context="some context",
        )
        assert result["type"] == "interaction_required"
        assert result["current_step"] == "my_checkpoint"
        assert result["question"] == "Choose an option"
        assert result["options"] == ["A", "B"]
        assert result["context"] == "some context"

    def test_session_status_is_paused(self):
        p = _make_pipeline()
        p._pause_with_session(
            checkpoint="cp",
            session_key="k",
            session_id="s",
            question="Q",
        )
        assert p.session.status == "paused"
