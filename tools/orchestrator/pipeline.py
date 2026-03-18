"""InterruptiblePipeline base class — checkpoint-based execution."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .agent_runner import AgentRunner, AgentStep, AgentResult
from .config import OrchestratorConfig
from .progress import StepTracker
from .response import (
    error_occurred,
    interaction_required,
    pipeline_completed,
    pipeline_failed,
)
from .session import PipelineSession, save_session


@dataclass
class SkillStepResult:
    """Result from _run_skill_step_with_session, including session_id for resume."""

    text: str
    session_id: str = ""


class PipelineError(Exception):
    """Raised when a pipeline step fails fatally (caught by server.py)."""

    def __init__(self, message: str, worktree_path: Path | None = None) -> None:
        super().__init__(message)
        self.worktree_path = worktree_path


class InterruptiblePipeline(ABC):
    """Base class for checkpoint-based interruptible pipelines."""

    def __init__(
        self,
        config: OrchestratorConfig,
        session: PipelineSession,
        session_dir: Path,
    ) -> None:
        self.config = config
        self.session = session
        self.session_dir = session_dir
        self.runner = AgentRunner(config)
        self.tracker = StepTracker()

    @abstractmethod
    async def run_until_checkpoint(self) -> dict[str, Any]:
        """Execute pipeline from current checkpoint until next checkpoint or completion."""
        ...

    # ── Response helpers ─────────────────────────────────────────

    def make_interaction(
        self,
        checkpoint: str,
        question: str,
        options: list[str] | None = None,
        context: str = "",
    ) -> dict[str, Any]:
        """Pause at checkpoint and return InteractionRequired response."""
        self.session.checkpoint = checkpoint
        self.session.status = "paused"
        self._save()
        return interaction_required(
            session_id=self.session.session_id,
            pipeline=self.session.pipeline,
            current_step=checkpoint,
            question=question,
            options=options,
            context=context,
            progress=self.tracker.to_progress_list(),
        )

    def make_error(
        self,
        checkpoint: str,
        error: str,
        step_output: str = "",
        recoverable: bool = True,
        suggested_actions: list[str] | None = None,
    ) -> dict[str, Any]:
        """Pause at error checkpoint and return ErrorOccurred response."""
        self.session.checkpoint = checkpoint
        self.session.status = "paused"
        self._save()
        return error_occurred(
            session_id=self.session.session_id,
            pipeline=self.session.pipeline,
            current_step=checkpoint,
            error_message=error,
            step_output=step_output,
            recoverable=recoverable,
            suggested_actions=suggested_actions,
            progress=self.tracker.to_progress_list(),
        )

    def make_completed(self, result: dict[str, Any]) -> dict[str, Any]:
        """Mark pipeline as completed and return response."""
        self.session.checkpoint = "done"
        self.session.status = "completed"
        self.session.completed_steps = self.tracker.to_progress_list()
        self._save()
        return pipeline_completed(
            session_id=self.session.session_id,
            pipeline=self.session.pipeline,
            current_step="done",
            result=result,
            progress=self.tracker.to_progress_list(),
        )

    def make_failed(self, error_message: str) -> dict[str, Any]:
        """Mark pipeline as failed and return response."""
        self.session.status = "failed"
        self._save()
        return pipeline_failed(
            session_id=self.session.session_id,
            pipeline=self.session.pipeline,
            current_step=self.session.checkpoint or "unknown",
            error_message=error_message,
            progress=self.tracker.to_progress_list(),
        )

    # ── Step execution ───────────────────────────────────────────

    async def run_agent_step(
        self,
        step: AgentStep,
        cwd: Path | None = None,
    ) -> AgentResult:
        """Execute an agent step with tracking."""
        record = self.tracker.add_step(step.name, step.model)
        self.tracker.start_step(record)

        result = await self.runner.run_step(
            step,
            progress=self.tracker,
            step_record=record,
            cwd=cwd,
        )

        if result.is_error:
            self.tracker.fail_step(record, result.error_message)
        else:
            self.tracker.complete_step(
                record, result.input_tokens, result.output_tokens
            )

        return result

    def skip_step(self, name: str, model: str, reason: str = "") -> None:
        """Register and skip a step."""
        record = self.tracker.add_step(name, model)
        self.tracker.skip_step(record, reason)

    def _save(self) -> None:
        """Persist session state to disk."""
        save_session(self.session, self.session_dir)

    # ── Segment runner ───────────────────────────────────────────

    async def _run_segments(
        self,
        segments: list[tuple[str, Any]],
        start_from: str = "",
    ) -> dict[str, Any] | None:
        """Run ordered segments from start_from. Returns checkpoint response or None."""
        start_idx = 0
        if start_from:
            for i, (name, _) in enumerate(segments):
                if name == start_from:
                    start_idx = i
                    break

        for i in range(start_idx, len(segments)):
            name, handler = segments[i]
            result = await handler()
            if result is not None:
                return result
            # Segment completed — update checkpoint to next
            if i + 1 < len(segments):
                self.session.checkpoint = segments[i + 1][0]
                self._save()

        return None  # All segments completed

    # ── Skill step runner ────────────────────────────────────────

    async def _run_skill_step(
        self,
        name: str,
        prompt: str,
        cwd: Path,
        model: str = "sonnet",
    ) -> str:
        """Run a skill as a single agent step via ClaudeSDKClient."""
        from claude_agent_sdk import (
            AssistantMessage,
            ClaudeAgentOptions,
            ClaudeSDKClient,
            ResultMessage,
            TextBlock,
        )

        record = self.tracker.add_step(name, model)
        self.tracker.start_step(record)

        options = ClaudeAgentOptions(
            model=self.config.resolve_model(model),
            cwd=str(cwd),
            setting_sources=["project"],
            permission_mode=self.config.permission_mode,
            allowed_tools=list(self.config.allowed_tools),
            max_turns=50,
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

        self.tracker.complete_step(record, 0, 0)
        return "\n".join(text_parts)

    async def _run_skill_step_with_session(
        self,
        name: str,
        prompt: str,
        cwd: Path,
        model: str = "sonnet",
        *,
        resume_session_id: str | None = None,
    ) -> SkillStepResult:
        """Run a skill step, returning both text output and session_id."""
        from claude_agent_sdk import (
            AssistantMessage,
            ClaudeAgentOptions,
            ClaudeSDKClient,
            ResultMessage,
            TextBlock,
        )

        record = self.tracker.add_step(name, model)
        self.tracker.start_step(record)

        options = ClaudeAgentOptions(
            model=self.config.resolve_model(model),
            cwd=str(cwd),
            setting_sources=["project"],
            permission_mode=self.config.permission_mode,
            allowed_tools=list(self.config.allowed_tools),
            max_turns=50,
            system_prompt={"type": "preset", "preset": "claude_code"},
            resume=resume_session_id,
        )

        text_parts: list[str] = []
        captured_session_id = ""
        async with ClaudeSDKClient(options) as client:
            await client.query(prompt)
            async for message in client.receive_messages():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            text_parts.append(block.text)
                elif isinstance(message, ResultMessage):
                    captured_session_id = message.session_id or ""
                    if message.result:
                        text_parts.append(message.result)
                    break

        self.tracker.complete_step(record, 0, 0)
        return SkillStepResult(
            text="\n".join(text_parts),
            session_id=captured_session_id,
        )

    async def _run_steering_sync(self, wt_path: Path) -> None:
        """/kiro:steering スキルを呼び出してsteering同期を実行する。"""
        await self._run_skill_step(
            "steering-sync",
            '以下のSkillを実行してください:\nSkill(skill="kiro:steering")',
            wt_path,
        )

    # ── Error resume helpers ─────────────────────────────────────

    def _handle_step_error_resume(
        self,
        step_name: str,
    ) -> dict[str, Any] | None:
        """Handle resume from step_X_failed / step_X_rejected checkpoint.

        Returns a response dict if another checkpoint is needed, or None to continue.
        Sets self.session.checkpoint to the segment to continue from.
        """
        action = self.session.checkpoint_data.get("action", "retry")

        if action == "abort":
            return self.make_failed(
                error_message=f"ユーザーがステップ '{step_name}' で中止しました。"
            )

        if action == "skip":
            return self.make_interaction(
                checkpoint=f"step_{step_name}_skip_confirm",
                question=(
                    f"ステップ '{step_name}' をスキップしますか？ "
                    f"スキップすると後続ステップに影響がある可能性があります。"
                ),
                options=["スキップして続行", "リトライ", "中止"],
            )

        # retry (default) — re-run the same segment
        self.session.checkpoint = step_name
        self._save()
        return None

    def _handle_skip_confirm_resume(
        self,
        step_name: str,
        segments: list[tuple[str, Any]],
    ) -> dict[str, Any] | None:
        """Handle resume from step_X_skip_confirm checkpoint."""
        user_input = self.session.checkpoint_data.get("user_input", "")

        if "スキップ" in user_input:
            # Advance to the next segment
            seg_names = [n for n, _ in segments]
            try:
                idx = seg_names.index(step_name)
                next_seg = seg_names[idx + 1] if idx + 1 < len(seg_names) else "done"
            except ValueError:
                next_seg = step_name
            self.session.checkpoint = next_seg
            self._save()
            return None

        if "リトライ" in user_input:
            self.session.checkpoint = step_name
            self._save()
            return None

        # 中止
        return self.make_failed(
            error_message="ユーザーがパイプラインを中止しました。"
        )
