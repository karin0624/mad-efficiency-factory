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

from tools.orchestrator.pipeline import SkillStepResult  # noqa: E402
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
            pipeline, "_run_skill_step_with_session",
            new=AsyncMock(return_value=SkillStepResult(
                text=f"ADR created.\nADR_PATH={adr_rel}", session_id="sess-1"
            )),
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
            pipeline, "_run_skill_step_with_session",
            new=AsyncMock(return_value=SkillStepResult(
                text=f"ADR_PATH={adr_rel}", session_id="sess-2"
            )),
        ):
            result = _run(pipeline._run_adr_gate(m1, tmp_path))

        assert isinstance(result, dict)
        assert result["type"] == "interaction_required"
        assert result["current_step"] == "adr_review"
        assert pipeline.session.checkpoint_data["adr_session_id"] == "sess-2"

    def test_adr_deprecated_returns_interaction(self, pipeline: ModifyPipeline, tmp_path: Path):
        """status=deprecated → interaction_required レスポンス。"""
        m1 = _make_m1()
        adr_rel = ".kiro/decisions/architecture/0001-test.md"
        adr_file = tmp_path / adr_rel
        adr_file.parent.mkdir(parents=True, exist_ok=True)
        adr_file.write_text(DEPRECATED_ADR)

        with patch.object(
            pipeline, "_run_skill_step_with_session",
            new=AsyncMock(return_value=SkillStepResult(
                text=f"ADR_PATH={adr_rel}", session_id="sess-3"
            )),
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
            pipeline, "_run_skill_step_with_session",
            new=AsyncMock(return_value=SkillStepResult(
                text="ADR created successfully.", session_id="sess-4"
            )),
        ), patch.object(
            ModifyPipeline, "_find_new_adr_file", return_value=adr_rel,
        ), patch("tools.orchestrator.pipelines.modify.find_spec_by_name", return_value=None):
            result = _run(pipeline._run_adr_gate(m1, tmp_path))

        assert result == adr_rel

    def test_no_marker_no_fallback_returns_error(self, pipeline: ModifyPipeline, tmp_path: Path):
        """ADR_PATH マーカーなし + glob フォールバック失敗 → error_occurred レスポンス。"""
        m1 = _make_m1()

        with patch.object(
            pipeline, "_run_skill_step_with_session",
            new=AsyncMock(return_value=SkillStepResult(
                text="Something happened.", session_id=""
            )),
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


# ── _is_adr_accept_only tests ────────────────────────────────────

class TestIsAdrAcceptOnly:
    def test_empty_string(self):
        assert ModifyPipeline._is_adr_accept_only("") is True

    def test_whitespace_only(self):
        assert ModifyPipeline._is_adr_accept_only("   ") is True

    def test_accept_phrases(self):
        for phrase in ["確認済み", "続行", "accept", "ok", "はい"]:
            assert ModifyPipeline._is_adr_accept_only(phrase) is True

    def test_case_insensitive(self):
        assert ModifyPipeline._is_adr_accept_only("OK") is True
        assert ModifyPipeline._is_adr_accept_only("Accept") is True

    def test_feedback_text(self):
        assert ModifyPipeline._is_adr_accept_only("理由をもっと詳しく書いてください") is False

    def test_partial_match_not_accepted(self):
        """'token' contains 'ok' but should NOT match (exact match only)."""
        assert ModifyPipeline._is_adr_accept_only("token") is False

    def test_broken_not_accepted(self):
        assert ModifyPipeline._is_adr_accept_only("broken") is False


# ── _handle_adr_review_resume tests ──────────────────────────────

class TestHandleAdrReviewResume:
    def test_accept_only_proceeds_to_m2(self, pipeline: ModifyPipeline):
        """確認のみ → M2 に進む。"""
        pipeline.session.checkpoint = "adr_review"
        pipeline.session.checkpoint_data = {
            "user_input": "確認済み",
            "adr_path": ".kiro/decisions/arch/0001.md",
            "adr_session_id": "sess-old",
        }
        result = _run(pipeline._handle_adr_review_resume())
        assert result is None
        assert pipeline.session.checkpoint == "M2"

    def test_empty_input_proceeds_to_m2(self, pipeline: ModifyPipeline):
        """空入力 → M2 に進む。"""
        pipeline.session.checkpoint = "adr_review"
        pipeline.session.checkpoint_data = {
            "user_input": "",
            "adr_path": ".kiro/decisions/arch/0001.md",
        }
        result = _run(pipeline._handle_adr_review_resume())
        assert result is None
        assert pipeline.session.checkpoint == "M2"

    def test_no_session_id_falls_back_to_m2(self, pipeline: ModifyPipeline):
        """session_id なし（レガシー）→ warning ログ出力し M2 にフォールバック。"""
        pipeline.session.checkpoint = "adr_review"
        pipeline.session.checkpoint_data = {
            "user_input": "理由を詳しく書いて",
            "adr_path": ".kiro/decisions/arch/0001.md",
        }
        result = _run(pipeline._handle_adr_review_resume())
        assert result is None
        assert pipeline.session.checkpoint == "M2"

    def test_feedback_resumes_session_and_accepted(self, pipeline: ModifyPipeline, tmp_path: Path):
        """フィードバック + session resume → accepted → M2。"""
        adr_rel = ".kiro/decisions/arch/0001.md"
        adr_file = tmp_path / adr_rel
        adr_file.parent.mkdir(parents=True, exist_ok=True)
        adr_file.write_text(ACCEPTED_ADR)

        pipeline.session.worktree_path = str(tmp_path)
        pipeline.session.checkpoint = "adr_review"
        pipeline.session.checkpoint_data = {
            "user_input": "理由をもっと詳しく書いてください",
            "adr_path": adr_rel,
            "adr_session_id": "sess-original",
        }

        with patch.object(
            pipeline, "_run_skill_step_with_session",
            new=AsyncMock(return_value=SkillStepResult(
                text="ADR revised.", session_id="sess-new"
            )),
        ) as mock_skill:
            result = _run(pipeline._handle_adr_review_resume())

        assert result is None
        assert pipeline.session.checkpoint == "M2"
        mock_skill.assert_called_once()
        call_kwargs = mock_skill.call_args
        assert call_kwargs.kwargs["resume_session_id"] == "sess-original"
        assert pipeline.session.checkpoint_data["adr_session_id"] == "sess-new"

    def test_feedback_still_proposed_returns_interaction(self, pipeline: ModifyPipeline, tmp_path: Path):
        """フィードバック後も proposed → 再度 interaction_required。"""
        adr_rel = ".kiro/decisions/arch/0001.md"
        adr_file = tmp_path / adr_rel
        adr_file.parent.mkdir(parents=True, exist_ok=True)
        adr_file.write_text(PROPOSED_ADR)

        pipeline.session.worktree_path = str(tmp_path)
        pipeline.session.checkpoint = "adr_review"
        pipeline.session.checkpoint_data = {
            "user_input": "修正してください",
            "adr_path": adr_rel,
            "adr_session_id": "sess-original",
        }

        with patch.object(
            pipeline, "_run_skill_step_with_session",
            new=AsyncMock(return_value=SkillStepResult(
                text="Revised.", session_id="sess-new"
            )),
        ):
            result = _run(pipeline._handle_adr_review_resume())

        assert isinstance(result, dict)
        assert result["type"] == "interaction_required"
        assert result["current_step"] == "adr_review"

    def test_resume_exception_falls_back_to_m2(self, pipeline: ModifyPipeline, tmp_path: Path):
        """resume 例外 → exception ログ出力し M2 にフォールバック。"""
        pipeline.session.worktree_path = str(tmp_path)
        pipeline.session.checkpoint = "adr_review"
        pipeline.session.checkpoint_data = {
            "user_input": "修正して",
            "adr_path": ".kiro/decisions/arch/0001.md",
            "adr_session_id": "sess-expired",
        }

        with patch.object(
            pipeline, "_run_skill_step_with_session",
            new=AsyncMock(side_effect=RuntimeError("session expired")),
        ):
            result = _run(pipeline._handle_adr_review_resume())

        assert result is None
        assert pipeline.session.checkpoint == "M2"
