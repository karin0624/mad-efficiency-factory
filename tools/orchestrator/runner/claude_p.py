"""claude -p subprocess wrapper — replaces ClaudeSDKClient."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..config import OrchestratorConfig
from ..output_parser import ParsedOutput, parse_agent_output

logger = logging.getLogger(__name__)


@dataclass
class ClaudePResult:
    """Result from a claude -p invocation."""

    output_text: str = ""
    parsed: ParsedOutput = field(default_factory=ParsedOutput)
    session_id: str = ""
    return_code: int = 0
    is_error: bool = False
    error_message: str = ""
    cost_usd: float = 0.0
    duration_ms: int = 0
    num_turns: int = 0


class ClaudePRunner:
    """Executes prompts via `claude -p` subprocess."""

    def __init__(self, config: OrchestratorConfig) -> None:
        self.config = config

    async def run(
        self,
        prompt: str,
        *,
        model: str = "sonnet",
        cwd: Path | str | None = None,
        allowed_tools: list[str] | None = None,
        permission_mode: str | None = None,
        max_turns: int = 0,
        append_system_prompt: str = "",
        resume_session_id: str = "",
    ) -> ClaudePResult:
        """Run a prompt through claude -p and return structured result.

        Args:
            prompt: The prompt text to send.
            model: Model alias ("opus", "sonnet") or full model ID.
            cwd: Working directory for the subprocess.
            allowed_tools: Override default allowed tools.
            permission_mode: Override default permission mode.
            max_turns: Max agentic turns (0 = use default).
            append_system_prompt: Additional system prompt text.
            resume_session_id: Session ID to resume from.

        Returns:
            ClaudePResult with output text, parsed markers, and metadata.
        """
        cmd = self._build_command(
            model=model,
            allowed_tools=allowed_tools,
            permission_mode=permission_mode,
            max_turns=max_turns,
            append_system_prompt=append_system_prompt,
            resume_session_id=resume_session_id,
        )

        work_dir = str(cwd) if cwd else str(self.config.project_root)
        logger.info("claude -p: model=%s cwd=%s resume=%s", model, work_dir, resume_session_id or "new")

        result = ClaudePResult()

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=work_dir,
            )
            stdout, stderr = await proc.communicate(input=prompt.encode("utf-8"))
            result.return_code = proc.returncode or 0

            if result.return_code != 0:
                result.is_error = True
                result.error_message = stderr.decode("utf-8", errors="replace").strip()
                # Still try to parse stdout for partial output
                result.output_text = stdout.decode("utf-8", errors="replace")
                result.parsed = parse_agent_output(result.output_text)
                return result

            # Parse JSON output
            raw_output = stdout.decode("utf-8", errors="replace")
            parsed_json = self._parse_json_output(raw_output)

            result.output_text = parsed_json.get("result", "")
            result.session_id = parsed_json.get("session_id", "")
            result.cost_usd = parsed_json.get("cost_usd", 0.0)
            result.duration_ms = parsed_json.get("duration_ms", 0)
            result.num_turns = parsed_json.get("num_turns", 0)
            result.is_error = parsed_json.get("is_error", False)
            result.parsed = parse_agent_output(result.output_text)

        except Exception as e:
            result.is_error = True
            result.error_message = f"Subprocess error: {e}"

        return result

    def _build_command(
        self,
        *,
        model: str,
        allowed_tools: list[str] | None,
        permission_mode: str | None,
        max_turns: int,
        append_system_prompt: str,
        resume_session_id: str,
    ) -> list[str]:
        """Build the claude CLI command arguments."""
        resolved_model = self.config.resolve_model(model)
        perm = permission_mode or self.config.permission_mode
        tools = allowed_tools or list(self.config.allowed_tools)

        cmd = [
            "claude",
            "-p",
            "--model", resolved_model,
            "--output-format", "json",
            "--permission-mode", perm,
        ]

        if tools:
            cmd.extend(["--allowedTools", ",".join(tools)])

        if max_turns > 0:
            cmd.extend(["--max-turns", str(max_turns)])

        if append_system_prompt:
            cmd.extend(["--append-system-prompt", append_system_prompt])

        if resume_session_id:
            cmd.extend(["--resume", resume_session_id])

        return cmd

    @staticmethod
    def _parse_json_output(raw: str) -> dict[str, Any]:
        """Parse the JSON output from claude -p --output-format json.

        The output may contain a single JSON object or multiple JSON lines.
        We take the last valid JSON object.
        """
        # Try parsing the entire output as JSON first
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # Fall back to parsing last line as JSON (streaming output)
        for line in reversed(raw.strip().splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    continue

        return {"result": raw}
