"""Core agent execution engine — wraps Claude Agent SDK ClaudeSDKClient."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

from .config import OrchestratorConfig
from .output_parser import ParsedOutput, parse_agent_output
from .progress import PipelineProgress, StepRecord


@dataclass
class AgentStep:
    """Definition of a single agent execution step."""

    name: str
    instruction_path: str  # Relative to project root, e.g. "tools/orchestrator/prompts/impl-spec-what.md"
    model: str  # "opus" | "sonnet" or full model ID
    params: dict[str, str] = field(default_factory=dict)


@dataclass
class AgentResult:
    """Result of a single agent step execution."""

    output_text: str = ""
    parsed: ParsedOutput = field(default_factory=ParsedOutput)
    input_tokens: int = 0
    output_tokens: int = 0
    duration_ms: int = 0
    num_turns: int = 0
    session_id: str = ""
    is_error: bool = False
    error_message: str = ""


class AgentRunner:
    """Executes agent steps via Claude Agent SDK ClaudeSDKClient."""

    def __init__(self, config: OrchestratorConfig) -> None:
        self.config = config

    def _build_prompt(self, step: AgentStep) -> str:
        """Read instruction .md and substitute parameters to build prompt."""
        instruction_path = self.config.project_root / step.instruction_path
        instruction = instruction_path.read_text()

        # Build the prompt: instruction content + parameters
        parts = [instruction, "", "---", "## Parameters", ""]
        for key, value in step.params.items():
            parts.append(f"{key}: {value}")

        return "\n".join(parts)

    def _build_options(self, step: AgentStep, cwd: Path | None = None) -> ClaudeAgentOptions:
        """Build ClaudeAgentOptions for a step."""
        model = self.config.resolve_model(step.model)
        work_dir = cwd or self.config.project_root

        return ClaudeAgentOptions(
            model=model,
            cwd=str(work_dir),
            setting_sources=["project"],
            permission_mode=self.config.permission_mode,
            allowed_tools=list(self.config.allowed_tools),
            max_turns=self.config.max_turns,
            system_prompt={
                "type": "preset",
                "preset": "claude_code",
            },
        )

    async def run_step(
        self,
        step: AgentStep,
        progress: PipelineProgress | None = None,
        step_record: StepRecord | None = None,
        cwd: Path | None = None,
    ) -> AgentResult:
        """Execute a single agent step via ClaudeSDKClient.

        Args:
            step: The step definition.
            progress: Optional progress display.
            step_record: Optional progress step record.
            cwd: Working directory override (typically the worktree path).

        Returns:
            AgentResult with output text, parsed markers, and metadata.
        """
        prompt = self._build_prompt(step)
        options = self._build_options(step, cwd=cwd)
        result = AgentResult()

        text_parts: list[str] = []
        # Track tool_use_id → tool_name for matching results to calls
        tool_use_names: dict[str, str] = {}

        try:
            async with ClaudeSDKClient(options) as client:
                await client.query(prompt)
                async for message in client.receive_messages():
                    if isinstance(message, AssistantMessage):
                        for block in message.content:
                            if isinstance(block, TextBlock):
                                text_parts.append(block.text)
                            elif isinstance(block, ToolUseBlock):
                                tool_use_names[block.id] = block.name
                                if progress and step_record:
                                    progress.log_tool_call(step_record, block.name, block.input)
                            elif isinstance(block, ToolResultBlock):
                                if progress and step_record:
                                    name = tool_use_names.get(block.tool_use_id, "")
                                    progress.log_tool_result(name, block)

                    elif isinstance(message, UserMessage):
                        if isinstance(message.content, list):
                            for block in message.content:
                                if isinstance(block, ToolResultBlock):
                                    if progress and step_record:
                                        name = tool_use_names.get(block.tool_use_id, "")
                                        progress.log_tool_result(name, block)

                    elif isinstance(message, ResultMessage):
                        usage = message.usage or {}
                        result.input_tokens = usage.get("input_tokens", 0)
                        result.output_tokens = usage.get("output_tokens", 0)
                        result.duration_ms = message.duration_ms
                        result.num_turns = message.num_turns
                        result.session_id = message.session_id
                        result.is_error = message.is_error
                        if message.result:
                            text_parts.append(message.result)
                        break

        except Exception as e:
            result.is_error = True
            result.error_message = str(e)

        result.output_text = "\n".join(text_parts)
        result.parsed = parse_agent_output(result.output_text)
        return result
