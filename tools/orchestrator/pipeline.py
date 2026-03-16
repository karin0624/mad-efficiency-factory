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
