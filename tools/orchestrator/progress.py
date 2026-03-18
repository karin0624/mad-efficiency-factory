"""Step tracking — structured data collection for pipeline execution."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class StepRecord:
    """Record for a single pipeline step."""

    name: str
    model: str
    status: str = "pending"  # pending, running, completed, failed, skipped
    start_time: float = 0.0
    end_time: float = 0.0
    error: str = ""
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def elapsed_s(self) -> float:
        if self.start_time == 0:
            return 0.0
        end = self.end_time if self.end_time > 0 else time.time()
        return end - self.start_time

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "elapsed_s": round(self.elapsed_s, 1),
            "tokens": self.input_tokens + self.output_tokens,
        }


class StepTracker:
    """Collects structured step data without UI output."""

    def __init__(self) -> None:
        self.steps: list[StepRecord] = []

    def add_step(self, name: str, model: str) -> StepRecord:
        step = StepRecord(name=name, model=model)
        self.steps.append(step)
        return step

    def start_step(self, step: StepRecord) -> None:
        step.status = "running"
        step.start_time = time.time()

    def complete_step(
        self, step: StepRecord, input_tokens: int = 0, output_tokens: int = 0
    ) -> None:
        step.status = "completed"
        step.end_time = time.time()
        step.input_tokens = input_tokens
        step.output_tokens = output_tokens

    def fail_step(self, step: StepRecord, error: str = "") -> None:
        step.status = "failed"
        step.end_time = time.time()
        step.error = error

    def skip_step(self, step: StepRecord, reason: str = "") -> None:
        step.status = "skipped"

    def log_tool_call(
        self,
        step: StepRecord,
        tool_name: str,
        tool_input: dict[str, object] | None = None,
    ) -> None:
        """No-op — tool call logging not needed in MCP mode."""

    def log_tool_result(self, tool_name: str, result_block: Any) -> None:
        """No-op — tool result logging not needed in MCP mode."""

    def to_progress_list(self) -> list[dict[str, Any]]:
        """Convert completed steps to response progress format."""
        return [s.to_dict() for s in self.steps]


# Backward compatibility alias for agent_runner.py
PipelineProgress = StepTracker
