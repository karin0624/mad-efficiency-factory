"""Tests for ADR gate, ASK_USER marker parsing, and interactive skill helpers."""

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

from tools.orchestrator.pipeline import (  # noqa: E402
    PipelineAborted,
    _collect_user_input,
    _parse_ask_user_marker,
    _print_pre_marker_text,
)
from tools.orchestrator.pipelines.modify import M1Result, ModifyPipeline  # noqa: E402


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
def pipeline() -> ModifyPipeline:
    p = object.__new__(ModifyPipeline)
    p.config = MagicMock()
    p.config.allowed_tools = ["Read", "Write", "Edit", "Bash"]
    p.config.resolve_model.return_value = "sonnet"
    p.config.permission_mode = "auto"
    p.progress = MagicMock()
    return p


def _run(coro):
    """Helper to run async coroutine in sync test."""
    return asyncio.get_event_loop().run_until_complete(coro)


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

    def test_adr_accepted(self, pipeline: ModifyPipeline, tmp_path: Path):
        """decision-create が ADR_PATH を返し、status=accepted → adr_path 返却。"""
        m1 = _make_m1()
        adr_rel = ".kiro/decisions/architecture/0001-test.md"
        adr_file = tmp_path / adr_rel
        adr_file.parent.mkdir(parents=True, exist_ok=True)
        adr_file.write_text(ACCEPTED_ADR)

        with patch.object(
            pipeline, "_run_interactive_skill",
            new=AsyncMock(return_value=f"ADR created.\nADR_PATH={adr_rel}"),
        ), patch("tools.orchestrator.pipelines.modify.find_spec_by_name", return_value=None):
            result = _run(pipeline._run_adr_gate(m1, tmp_path))

        assert result == adr_rel

    def test_adr_proposed_raises(self, pipeline: ModifyPipeline, tmp_path: Path):
        """status=proposed → PipelineError。"""
        from tools.orchestrator.pipeline import PipelineError

        m1 = _make_m1()
        adr_rel = ".kiro/decisions/architecture/0001-test.md"
        adr_file = tmp_path / adr_rel
        adr_file.parent.mkdir(parents=True, exist_ok=True)
        adr_file.write_text(PROPOSED_ADR)

        with patch.object(
            pipeline, "_run_interactive_skill",
            new=AsyncMock(return_value=f"ADR_PATH={adr_rel}"),
        ):
            with pytest.raises(PipelineError, match="ADR not accepted"):
                _run(pipeline._run_adr_gate(m1, tmp_path))

    def test_adr_deprecated_raises(self, pipeline: ModifyPipeline, tmp_path: Path):
        """status=deprecated → PipelineError。"""
        from tools.orchestrator.pipeline import PipelineError

        m1 = _make_m1()
        adr_rel = ".kiro/decisions/architecture/0001-test.md"
        adr_file = tmp_path / adr_rel
        adr_file.parent.mkdir(parents=True, exist_ok=True)
        adr_file.write_text(DEPRECATED_ADR)

        with patch.object(
            pipeline, "_run_interactive_skill",
            new=AsyncMock(return_value=f"ADR_PATH={adr_rel}"),
        ):
            with pytest.raises(PipelineError, match="ADR not accepted"):
                _run(pipeline._run_adr_gate(m1, tmp_path))

    def test_no_marker_glob_fallback(self, pipeline: ModifyPipeline, tmp_path: Path):
        """ADR_PATH マーカーなし + glob フォールバック成功 → adr_path 返却。"""
        m1 = _make_m1()
        adr_rel = ".kiro/decisions/architecture/0001-test.md"
        adr_file = tmp_path / adr_rel
        adr_file.parent.mkdir(parents=True, exist_ok=True)
        adr_file.write_text(ACCEPTED_ADR)

        with patch.object(
            pipeline, "_run_interactive_skill",
            new=AsyncMock(return_value="ADR created successfully."),
        ), patch.object(
            ModifyPipeline, "_find_new_adr_file", return_value=adr_rel,
        ), patch("tools.orchestrator.pipelines.modify.find_spec_by_name", return_value=None):
            result = _run(pipeline._run_adr_gate(m1, tmp_path))

        assert result == adr_rel

    def test_no_marker_no_fallback_raises(self, pipeline: ModifyPipeline, tmp_path: Path):
        """ADR_PATH マーカーなし + glob フォールバック失敗 → PipelineError。"""
        from tools.orchestrator.pipeline import PipelineError

        m1 = _make_m1()

        with patch.object(
            pipeline, "_run_interactive_skill",
            new=AsyncMock(return_value="Something happened."),
        ), patch.object(
            ModifyPipeline, "_find_new_adr_file", return_value=None,
        ):
            with pytest.raises(PipelineError, match="did not produce a file"):
                _run(pipeline._run_adr_gate(m1, tmp_path))


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


# ── _parse_ask_user_marker tests ─────────────────────────────────

class TestAskUserMarkerParsing:
    def test_normal_marker_with_options(self):
        text = (
            "Some text before.\n"
            "<<ASK_USER>>\n"
            "question: どの方針にしますか？\n"
            "options:\n"
            "- 方針A\n"
            "- 方針B\n"
            "<</ASK_USER>>\n"
            "Some text after."
        )
        result = _parse_ask_user_marker(text)
        assert result is not None
        assert result["question"] == "どの方針にしますか？"
        assert result["options"] == ["方針A", "方針B"]

    def test_marker_without_options(self):
        text = (
            "<<ASK_USER>>\n"
            "question: 何か補足はありますか？\n"
            "<</ASK_USER>>"
        )
        result = _parse_ask_user_marker(text)
        assert result is not None
        assert result["question"] == "何か補足はありますか？"
        assert result["options"] == []

    def test_no_marker(self):
        assert _parse_ask_user_marker("just normal text") is None

    def test_malformed_no_question(self):
        text = "<<ASK_USER>>\noptions:\n- A\n<</ASK_USER>>"
        assert _parse_ask_user_marker(text) is None

    def test_multiline_question_yaml_pipe(self):
        """YAML ブロックスカラー ``|`` で question が複数行になるケース。"""
        text = (
            "<<ASK_USER>>\n"
            "question: |\n"
            "  ドラフトを確認してください。\n"
            "  Decision DriversにXを含めましたが妥当ですか？\n"
            "  Option AをBより優先した根拠は性能です。\n"
            "options:\n"
            "- 承認（このまま accepted にする）\n"
            "- proposed のまま保留する\n"
            "- 修正指示をテキストで回答\n"
            "<</ASK_USER>>"
        )
        result = _parse_ask_user_marker(text)
        assert result is not None
        assert "ドラフトを確認してください。" in result["question"]
        assert "Option AをBより優先した根拠は性能です。" in result["question"]
        assert len(result["options"]) == 3

    def test_multiline_question_yaml_gt(self):
        """YAML 折りたたみスカラー ``>`` で question が複数行になるケース。"""
        text = (
            "<<ASK_USER>>\n"
            "question: >\n"
            "  整合性チェック結果を確認してください。\n"
            "  既存ADRとの矛盾はありません。\n"
            "options:\n"
            "- 承認（accepted）\n"
            "- 却下（deprecated）\n"
            "<</ASK_USER>>"
        )
        result = _parse_ask_user_marker(text)
        assert result is not None
        assert "整合性チェック結果を確認してください。" in result["question"]
        assert "既存ADRとの矛盾はありません。" in result["question"]
        assert len(result["options"]) == 2

    def test_multiline_question_no_yaml_indicator(self):
        """``|`` / ``>`` なしで question が複数行にわたるケース。"""
        text = (
            "<<ASK_USER>>\n"
            "question: 以下について確認してください:\n"
            "  1. フットプリントサイズの変更は妥当か\n"
            "  2. 受入基準の更新が必要か\n"
            "options:\n"
            "- はい\n"
            "- いいえ\n"
            "<</ASK_USER>>"
        )
        result = _parse_ask_user_marker(text)
        assert result is not None
        assert "以下について確認してください:" in result["question"]
        assert "フットプリントサイズの変更は妥当か" in result["question"]
        assert "受入基準の更新が必要か" in result["question"]

    def test_multiline_question_options_without_header(self):
        """``options:`` ヘッダなしで直接 ``- `` が来るケース。"""
        text = (
            "<<ASK_USER>>\n"
            "question: |\n"
            "  この変更を承認しますか？\n"
            "- 承認\n"
            "- 却下\n"
            "<</ASK_USER>>"
        )
        result = _parse_ask_user_marker(text)
        assert result is not None
        assert result["question"] == "この変更を承認しますか？"
        assert result["options"] == ["承認", "却下"]

    def test_single_line_question_unchanged(self):
        """既存の単一行 question が壊れていないことを確認。"""
        text = (
            "<<ASK_USER>>\n"
            "question: 承認しますか？\n"
            "options:\n"
            "- はい\n"
            "- いいえ\n"
            "<</ASK_USER>>"
        )
        result = _parse_ask_user_marker(text)
        assert result is not None
        assert result["question"] == "承認しますか？"
        assert result["options"] == ["はい", "いいえ"]


# ── _print_pre_marker_text tests ─────────────────────────────────

class TestPrintPreMarkerText:
    def test_prints_text_before_marker(self):
        """マーカー前のテキスト（ドラフト等）が console.print で表示される。"""
        turn_text = (
            "## ADR ドラフト\n"
            "Decision: フットプリントを1x1にする\n\n"
            "### 質問\n"
            "1. 受入基準7.1の変更は妥当ですか？\n"
            "2. 既存テストへの影響をどう評価しますか？\n\n"
            "<<ASK_USER>>\n"
            "question: 上記ドラフトを確認してください。\n"
            "options:\n"
            "- 承認\n"
            "- 却下\n"
            "<</ASK_USER>>"
        )
        with patch("tools.orchestrator.human_input.console") as mock_console:
            _print_pre_marker_text(turn_text)
        mock_console.print.assert_called_once()
        printed = mock_console.print.call_args[0][0]
        assert "ADR ドラフト" in printed
        assert "受入基準7.1の変更は妥当ですか？" in printed
        assert "既存テストへの影響" in printed

    def test_no_marker_does_nothing(self):
        """マーカーがないテキストでは何も表示しない。"""
        with patch("tools.orchestrator.human_input.console") as mock_console:
            _print_pre_marker_text("普通のテキスト")
        mock_console.print.assert_not_called()

    def test_no_pre_text_does_nothing(self):
        """マーカー前にテキストがない場合は何も表示しない。"""
        turn_text = (
            "<<ASK_USER>>\n"
            "question: 質問\n"
            "options:\n"
            "- A\n"
            "<</ASK_USER>>"
        )
        with patch("tools.orchestrator.human_input.console") as mock_console:
            _print_pre_marker_text(turn_text)
        mock_console.print.assert_not_called()


# ── _collect_user_input tests ────────────────────────────────────

class TestCollectUserInput:
    def test_with_options_calls_ask_choice(self):
        with patch("tools.orchestrator.human_input.ask_choice", return_value="方針A") as mock:
            result = _collect_user_input("質問", ["方針A", "方針B"])
        assert result == "方針A"
        mock.assert_called_once_with("質問", ["方針A", "方針B"], allow_freetext=True)

    def test_without_options_calls_ask_text(self):
        with patch("tools.orchestrator.human_input.ask_text", return_value="自由回答") as mock:
            result = _collect_user_input("質問", [])
        assert result == "自由回答"
        mock.assert_called_once_with("質問")

    def test_keyboard_interrupt_raises_aborted(self):
        with patch("tools.orchestrator.human_input.ask_text", side_effect=KeyboardInterrupt):
            with pytest.raises(PipelineAborted):
                _collect_user_input("質問", [])

    def test_eof_error_raises_aborted(self):
        with patch("tools.orchestrator.human_input.ask_text", side_effect=EOFError):
            with pytest.raises(PipelineAborted):
                _collect_user_input("質問", [])


# ── _run_interactive_skill multi-turn tests ──────────────────────

class TestRunInteractiveSkillMultiTurn:
    def test_multi_turn_flow(self, pipeline: ModifyPipeline):
        """マーカー検出→入力収集→応答注入→完了の全フロー。"""
        # SDK types as simple classes for isinstance checks
        class FakeTextBlock:
            def __init__(self, text):
                self.text = text

        class FakeAssistantMessage:
            def __init__(self, content):
                self.content = content

        class FakeResultMessage:
            def __init__(self, result=None):
                self.result = result

        # Patch isinstance checks in pipeline module
        with patch("tools.orchestrator.pipeline.AssistantMessage", FakeAssistantMessage, create=True), \
             patch("tools.orchestrator.pipeline.ResultMessage", FakeResultMessage, create=True), \
             patch("tools.orchestrator.pipeline.TextBlock", FakeTextBlock, create=True):

            # Build mock messages sequence
            turn1_assistant = FakeAssistantMessage([
                FakeTextBlock("ドラフト生成完了。\n<<ASK_USER>>\nquestion: 承認しますか？\noptions:\n- はい\n- いいえ\n<</ASK_USER>>")
            ])
            turn1_result = FakeResultMessage()
            turn2_assistant = FakeAssistantMessage([
                FakeTextBlock("承認されました。ADR_PATH=.kiro/decisions/arch/0001.md")
            ])
            turn2_result = FakeResultMessage(result="完了")

            messages = [turn1_assistant, turn1_result, turn2_assistant, turn2_result]

            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.query = AsyncMock()

            async def fake_receive():
                for msg in messages:
                    yield msg

            mock_client.receive_messages = fake_receive

            # Patch the SDK imports inside _run_interactive_skill
            with patch.dict(sys.modules, {"claude_agent_sdk": MagicMock(
                AssistantMessage=FakeAssistantMessage,
                ClaudeAgentOptions=MagicMock(return_value=MagicMock()),
                ClaudeSDKClient=MagicMock(return_value=mock_client),
                ResultMessage=FakeResultMessage,
                TextBlock=FakeTextBlock,
            )}), patch(
                "tools.orchestrator.pipeline._collect_user_input",
                return_value="はい",
            ) as mock_input, patch(
                "tools.orchestrator.pipeline._print_pre_marker_text",
            ) as mock_print_pre:
                result = _run(pipeline._run_interactive_skill(
                    "test prompt", cwd=Path("/tmp"),
                ))

            # マーカー前のテキストが表示された
            mock_print_pre.assert_called_once()
            pre_arg = mock_print_pre.call_args[0][0]
            assert "ドラフト生成完了" in pre_arg
            # ユーザー入力が収集された
            mock_input.assert_called_once_with("承認しますか？", ["はい", "いいえ"])
            # query が2回呼ばれた（初回 + 応答注入）
            assert mock_client.query.call_count == 2
            # 結果に両ターンのテキストが含まれる
            assert "ドラフト生成完了" in result
            assert "承認されました" in result
            assert "完了" in result

    def test_no_marker_completes_immediately(self, pipeline: ModifyPipeline):
        """マーカーなしの場合は即座に完了。"""
        class FakeTextBlock:
            def __init__(self, text):
                self.text = text

        class FakeAssistantMessage:
            def __init__(self, content):
                self.content = content

        class FakeResultMessage:
            def __init__(self, result=None):
                self.result = result

        assistant = FakeAssistantMessage([FakeTextBlock("処理完了")])
        result_msg = FakeResultMessage(result="done")

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.query = AsyncMock()

        async def fake_receive():
            yield assistant
            yield result_msg

        mock_client.receive_messages = fake_receive

        with patch.dict(sys.modules, {"claude_agent_sdk": MagicMock(
            AssistantMessage=FakeAssistantMessage,
            ClaudeAgentOptions=MagicMock(return_value=MagicMock()),
            ClaudeSDKClient=MagicMock(return_value=mock_client),
            ResultMessage=FakeResultMessage,
            TextBlock=FakeTextBlock,
        )}):
            result = _run(pipeline._run_interactive_skill(
                "test prompt", cwd=Path("/tmp"),
            ))

        assert "処理完了" in result
        assert "done" in result
        # query は初回のみ
        assert mock_client.query.call_count == 1

    def test_ask_user_excluded_from_allowed_tools(self, pipeline: ModifyPipeline):
        """AskUserQuestion が allowed_tools から除外されていることを確認。"""
        pipeline.config.allowed_tools = ["Read", "Write", "AskUserQuestion"]

        class FakeTextBlock:
            def __init__(self, text):
                self.text = text

        class FakeAssistantMessage:
            def __init__(self, content):
                self.content = content

        class FakeResultMessage:
            def __init__(self, result=None):
                self.result = result

        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.query = AsyncMock()

        async def fake_receive():
            yield FakeResultMessage(result="done")

        mock_client.receive_messages = fake_receive

        captured_opts = {}
        def capture_opts(**kwargs):
            captured_opts.update(kwargs)
            return MagicMock()

        with patch.dict(sys.modules, {"claude_agent_sdk": MagicMock(
            AssistantMessage=FakeAssistantMessage,
            ClaudeAgentOptions=capture_opts,
            ClaudeSDKClient=MagicMock(return_value=mock_client),
            ResultMessage=FakeResultMessage,
            TextBlock=FakeTextBlock,
        )}):
            _run(pipeline._run_interactive_skill("test", cwd=Path("/tmp")))

        assert "AskUserQuestion" not in captured_opts["allowed_tools"]


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
        with patch.object(
            pipeline, "_run_interactive_skill",
            new=AsyncMock(return_value=""),
        ):
            result = _run(pipeline._run_scene_review(tmp_path, "my-feature"))
        assert result is False

    def test_failed_marker_returns_false(self, pipeline: ModifyPipeline, tmp_path: Path):
        with patch.object(
            pipeline, "_run_interactive_skill",
            new=AsyncMock(return_value="不合格あり。SCENE_REVIEW_FAILED"),
        ):
            result = _run(pipeline._run_scene_review(tmp_path, "my-feature"))
        assert result is False
