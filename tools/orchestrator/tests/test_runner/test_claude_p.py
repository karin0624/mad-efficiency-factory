"""Tests for runner/claude_p.py — claude -p subprocess wrapper."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from tools.orchestrator.config import OrchestratorConfig
from tools.orchestrator.runner.claude_p import ClaudePRunner


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def config(tmp_path: Path) -> OrchestratorConfig:
    return OrchestratorConfig(project_root=tmp_path)


class TestBuildCommand:
    def test_basic_command(self, config: OrchestratorConfig):
        runner = ClaudePRunner(config)
        cmd = runner._build_command(
            model="opus",
            allowed_tools=None,
            permission_mode=None,
            max_turns=0,
            append_system_prompt="",
            resume_session_id="",
        )
        assert cmd[0] == "claude"
        assert "-p" in cmd
        assert "--model" in cmd
        assert "claude-opus-4-6" in cmd
        assert "--output-format" in cmd
        assert "json" in cmd
        assert "--permission-mode" in cmd
        assert "bypassPermissions" in cmd

    def test_with_allowed_tools(self, config: OrchestratorConfig):
        runner = ClaudePRunner(config)
        cmd = runner._build_command(
            model="sonnet",
            allowed_tools=["Bash", "Read"],
            permission_mode=None,
            max_turns=0,
            append_system_prompt="",
            resume_session_id="",
        )
        assert "--allowedTools" in cmd
        idx = cmd.index("--allowedTools")
        assert cmd[idx + 1] == "Bash,Read"

    def test_with_max_turns(self, config: OrchestratorConfig):
        runner = ClaudePRunner(config)
        cmd = runner._build_command(
            model="sonnet",
            allowed_tools=None,
            permission_mode=None,
            max_turns=50,
            append_system_prompt="",
            resume_session_id="",
        )
        assert "--max-turns" in cmd
        idx = cmd.index("--max-turns")
        assert cmd[idx + 1] == "50"

    def test_with_resume(self, config: OrchestratorConfig):
        runner = ClaudePRunner(config)
        cmd = runner._build_command(
            model="sonnet",
            allowed_tools=None,
            permission_mode=None,
            max_turns=0,
            append_system_prompt="",
            resume_session_id="abc123",
        )
        assert "--resume" in cmd
        idx = cmd.index("--resume")
        assert cmd[idx + 1] == "abc123"

    def test_with_system_prompt(self, config: OrchestratorConfig):
        runner = ClaudePRunner(config)
        cmd = runner._build_command(
            model="sonnet",
            allowed_tools=None,
            permission_mode=None,
            max_turns=0,
            append_system_prompt="Extra context",
            resume_session_id="",
        )
        assert "--append-system-prompt" in cmd
        idx = cmd.index("--append-system-prompt")
        assert cmd[idx + 1] == "Extra context"

    def test_no_resume_no_extra(self, config: OrchestratorConfig):
        runner = ClaudePRunner(config)
        cmd = runner._build_command(
            model="sonnet",
            allowed_tools=None,
            permission_mode=None,
            max_turns=0,
            append_system_prompt="",
            resume_session_id="",
        )
        assert "--resume" not in cmd
        assert "--max-turns" not in cmd
        assert "--append-system-prompt" not in cmd


class TestParseJsonOutput:
    def test_valid_json(self):
        data = {"result": "hello", "session_id": "abc"}
        assert ClaudePRunner._parse_json_output(json.dumps(data)) == data

    def test_json_with_extra_lines(self):
        lines = "some log\n" + json.dumps({"result": "ok"}) + "\n"
        parsed = ClaudePRunner._parse_json_output(lines)
        assert parsed["result"] == "ok"

    def test_fallback_to_raw(self):
        raw = "not json at all"
        parsed = ClaudePRunner._parse_json_output(raw)
        assert parsed["result"] == raw

    def test_multi_json_lines(self):
        lines = (
            json.dumps({"partial": True}) + "\n"
            + json.dumps({"result": "final", "session_id": "s1"})
        )
        parsed = ClaudePRunner._parse_json_output(lines)
        assert parsed["result"] == "final"


class TestRun:
    def test_successful_run(self, config: OrchestratorConfig):
        runner = ClaudePRunner(config)
        json_output = json.dumps({
            "result": "VALIDATION_PASSED\nAll tests pass.",
            "session_id": "sess-123",
            "cost_usd": 0.05,
            "duration_ms": 5000,
            "num_turns": 3,
            "is_error": False,
        })

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(json_output.encode(), b""))
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = _run(runner.run("test prompt", model="opus"))

        assert not result.is_error
        assert result.session_id == "sess-123"
        assert "VALIDATION_PASSED" in result.output_text
        assert result.parsed.validation_passed is True
        assert result.cost_usd == 0.05

    def test_error_return_code(self, config: OrchestratorConfig):
        runner = ClaudePRunner(config)

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"partial", b"something failed"))
        mock_proc.returncode = 1

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = _run(runner.run("test prompt"))

        assert result.is_error
        assert "something failed" in result.error_message

    def test_subprocess_exception(self, config: OrchestratorConfig):
        runner = ClaudePRunner(config)

        with patch("asyncio.create_subprocess_exec", side_effect=OSError("not found")):
            result = _run(runner.run("test prompt"))

        assert result.is_error
        assert "not found" in result.error_message
