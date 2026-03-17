"""Pipeline base class — shared run structure and error handling."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from .agent_runner import AgentRunner, AgentStep, AgentResult
from .config import OrchestratorConfig
from .progress import PipelineProgress, StepRecord


class PipelineError(Exception):
    """Raised when a pipeline step fails fatally."""

    def __init__(self, message: str, worktree_path: Path | None = None) -> None:
        super().__init__(message)
        self.worktree_path = worktree_path


class PipelineAborted(Exception):
    """Raised when the user cancels an interactive input."""
    pass


# ── ASK_USER marker helpers ──────────────────────────────────────

_ASK_USER_RE = re.compile(
    r"<<ASK_USER>>\s*\n(.*?)<</ASK_USER>>", re.DOTALL
)


def _parse_ask_user_marker(text: str) -> dict | None:
    """<<ASK_USER>> マーカーをパースして question と options を返す。

    question: の値が複数行にわたる場合（YAML ブロックスカラー ``|`` / ``>``
    や、単に改行で続く場合）も正しく収集する。``options:`` ヘッダまたは
    ``- `` リスト項目が現れるまでを question テキストとして扱う。
    """
    m = _ASK_USER_RE.search(text)
    if not m:
        return None

    body = m.group(1)
    question_lines: list[str] = []
    options: list[str] = []
    in_question = False

    for line in body.split("\n"):
        stripped = line.strip()
        if stripped.startswith("question:"):
            in_question = True
            # question: の後のテキストを取得（``|`` / ``>`` は除去）
            first = stripped[len("question:"):].strip()
            if first and first not in ("|", ">"):
                question_lines.append(first)
        elif stripped.startswith("options:"):
            in_question = False
        elif stripped.startswith("- "):
            in_question = False
            options.append(stripped[2:].strip())
        elif in_question and stripped:
            question_lines.append(stripped)

    question = "\n".join(question_lines)
    return {"question": question, "options": options} if question else None


def _collect_user_input(question: str, options: list[str]) -> str:
    """ターミナルでユーザー入力を収集する。

    Raises:
        PipelineAborted: ユーザーが Ctrl+C / EOF で入力を中断した場合。
    """
    from .human_input import ask_choice, ask_text

    try:
        if options:
            return ask_choice(question, options, allow_freetext=True)
        else:
            return ask_text(question)
    except (KeyboardInterrupt, EOFError):
        raise PipelineAborted("User cancelled interactive input")


class Pipeline(ABC):
    """Base class for orchestration pipelines."""

    def __init__(self, config: OrchestratorConfig) -> None:
        self.config = config
        self.runner = AgentRunner(config)
        self.progress: PipelineProgress | None = None

    @abstractmethod
    async def run(self, **kwargs: Any) -> dict[str, Any]:
        """Execute the pipeline. Returns a result summary dict."""
        ...

    async def run_agent_step(
        self,
        step: AgentStep,
        cwd: Path | None = None,
    ) -> AgentResult:
        """Execute an agent step with progress tracking.

        Creates a StepRecord, starts it, runs the step, and marks
        it as completed or failed.
        """
        record = None
        if self.progress:
            record = self.progress.add_step(step.name, step.model)
            self.progress.start_step(record)

        result = await self.runner.run_step(
            step,
            progress=self.progress,
            step_record=record,
            cwd=cwd,
        )

        if self.progress and record:
            if result.is_error:
                self.progress.fail_step(record, result.error_message)
            else:
                self.progress.complete_step(record, result.input_tokens, result.output_tokens)

        return result

    def skip_step(self, name: str, model: str, reason: str = "") -> None:
        """Register and immediately skip a step."""
        if self.progress:
            record = self.progress.add_step(name, model)
            self.progress.skip_step(record, reason)

    async def _run_interactive_skill(
        self,
        prompt: str,
        *,
        cwd: Path,
        extra_allowed_tools: list[str] | None = None,
        model: str = "sonnet",
        max_turns: int = 30,
    ) -> str:
        """ClaudeSDKClient でマルチターン対話可能なスキルを実行する。

        AskUserQuestion の代わりに <<ASK_USER>> マーカーを使用し、
        Python 側でユーザー入力を収集して同一セッションに注入する。
        """
        from claude_agent_sdk import (
            AssistantMessage,
            ClaudeAgentOptions,
            ClaudeSDKClient,
            ResultMessage,
            TextBlock,
        )

        # AskUserQuestion を除外（SDK サブプロセスでは動作しない）
        allowed = [t for t in self.config.allowed_tools if t != "AskUserQuestion"]
        if extra_allowed_tools:
            for tool in extra_allowed_tools:
                if tool not in allowed and tool != "AskUserQuestion":
                    allowed.append(tool)

        # ラッパープロンプト: AskUserQuestion → マーカー変換指示
        wrapped_prompt = (
            f"{prompt}\n\n"
            "---\n"
            "【環境制約】AskUserQuestion ツールはこの環境では利用できません。\n"
            "ユーザー入力が必要な場合は、以下のフォーマットで質問を出力してください:\n\n"
            "<<ASK_USER>>\n"
            "question: [質問文]\n"
            "options:\n"
            "- [選択肢1]\n"
            "- [選択肢2]\n"
            "<</ASK_USER>>\n\n"
            "マーカー出力後は応答を終了してください。\n"
            "次のメッセージでユーザーの回答が提供されます。\n"
        )

        options = ClaudeAgentOptions(
            model=self.config.resolve_model(model),
            cwd=str(cwd),
            setting_sources=["project"],
            permission_mode=self.config.permission_mode,
            allowed_tools=allowed,
            max_turns=max_turns,
            system_prompt={"type": "preset", "preset": "claude_code"},
        )

        text_parts: list[str] = []
        current_turn_text: list[str] = []

        async with ClaudeSDKClient(options) as client:
            await client.query(wrapped_prompt)

            # 単一の長寿命イテレータ — ResultMessage で閉じない
            async for message in client.receive_messages():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            text_parts.append(block.text)
                            current_turn_text.append(block.text)

                elif isinstance(message, ResultMessage):
                    turn_text = "\n".join(current_turn_text)
                    marker = _parse_ask_user_marker(turn_text)

                    if marker:
                        # ユーザー入力を収集
                        user_response = _collect_user_input(
                            marker["question"], marker["options"]
                        )
                        # 同一セッションに応答注入 → コンテキスト維持
                        await client.query(f"ユーザーの回答: {user_response}")
                        current_turn_text = []
                        # break しない — receive_messages() が次のターンを返す
                    else:
                        # マーカーなし → スキル完了
                        if message.result:
                            text_parts.append(message.result)
                        break

        return "\n".join(text_parts)

    async def _run_steering_sync(self, wt_path: Path) -> None:
        """/kiro:steering スキルを呼び出してsteering同期を実行する。"""
        from claude_agent_sdk import (
            ClaudeAgentOptions,
            ClaudeSDKClient,
            ResultMessage,
        )

        record = None
        if self.progress:
            record = self.progress.add_step("steering-sync", "sonnet")
            self.progress.start_step(record)

        options = ClaudeAgentOptions(
            model=self.config.resolve_model("sonnet"),
            cwd=str(wt_path),
            setting_sources=["project"],
            permission_mode=self.config.permission_mode,
            allowed_tools=list(self.config.allowed_tools),
            max_turns=50,
            system_prompt={"type": "preset", "preset": "claude_code"},
        )

        async with ClaudeSDKClient(options) as client:
            await client.query('以下のSkillを実行してください:\nSkill(skill="kiro:steering")')
            async for message in client.receive_messages():
                if isinstance(message, ResultMessage):
                    break

        if self.progress and record:
            self.progress.complete_step(record, 0, 0)
