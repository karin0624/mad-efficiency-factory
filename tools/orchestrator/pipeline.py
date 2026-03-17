"""Pipeline base class — shared run structure and error handling."""

from __future__ import annotations

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
        """ClaudeSDKClient を使ってインタラクティブなスキルを実行する。

        query() と異なり stdin を維持するため AskUserQuestion が動作する。
        テキスト出力を収集して返す。
        """
        from claude_agent_sdk import (
            AssistantMessage,
            ClaudeAgentOptions,
            ClaudeSDKClient,
            ResultMessage,
            TextBlock,
        )

        allowed = list(self.config.allowed_tools)
        if "AskUserQuestion" not in allowed:
            allowed.append("AskUserQuestion")
        if extra_allowed_tools:
            for tool in extra_allowed_tools:
                if tool not in allowed:
                    allowed.append(tool)

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
        async with ClaudeSDKClient(options) as client:
            await client.query(prompt)
            async for message in client.receive_messages():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            text_parts.append(block.text)
                elif isinstance(message, ResultMessage):
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
