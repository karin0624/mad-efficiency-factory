"""Rich console progress display for pipeline execution."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.text import Text


@dataclass
class StepRecord:
    name: str
    model: str
    status: str = "pending"  # pending, running, completed, failed, skipped
    start_time: float = 0.0
    end_time: float = 0.0
    tool_calls: list[str] = field(default_factory=list)
    error: str = ""
    cost_usd: float = 0.0

    @property
    def elapsed_s(self) -> float:
        if self.start_time == 0:
            return 0.0
        end = self.end_time if self.end_time > 0 else time.time()
        return end - self.start_time


class PipelineProgress:
    """Tracks and displays pipeline execution progress."""

    def __init__(self, pipeline_name: str) -> None:
        self.pipeline_name = pipeline_name
        self.console = Console()
        self.steps: list[StepRecord] = []
        self._current: StepRecord | None = None

    def add_step(self, name: str, model: str) -> StepRecord:
        """Register a step (before it runs)."""
        step = StepRecord(name=name, model=model)
        self.steps.append(step)
        return step

    def start_step(self, step: StepRecord) -> None:
        """Mark a step as running."""
        step.status = "running"
        step.start_time = time.time()
        self._current = step
        self.console.print(
            f"  [bold cyan]▶[/] {step.name} [dim]({step.model})[/]"
        )

    def log_tool_call(self, step: StepRecord, tool_name: str) -> None:
        """Log a tool call during step execution."""
        step.tool_calls.append(tool_name)
        self.console.print(f"    [dim]↳ {tool_name}[/]")

    def complete_step(
        self, step: StepRecord, cost_usd: float = 0.0
    ) -> None:
        """Mark a step as completed."""
        step.status = "completed"
        step.end_time = time.time()
        step.cost_usd = cost_usd
        elapsed = step.elapsed_s
        cost_str = f" ${cost_usd:.3f}" if cost_usd else ""
        self.console.print(
            f"  [bold green]✓[/] {step.name} "
            f"[dim]({elapsed:.1f}s{cost_str})[/]"
        )
        self._current = None

    def fail_step(self, step: StepRecord, error: str = "") -> None:
        """Mark a step as failed."""
        step.status = "failed"
        step.end_time = time.time()
        step.error = error
        self.console.print(
            f"  [bold red]✗[/] {step.name} "
            f"[dim]({step.elapsed_s:.1f}s)[/]"
        )
        if error:
            self.console.print(f"    [red]{error}[/]")
        self._current = None

    def skip_step(self, step: StepRecord, reason: str = "") -> None:
        """Mark a step as skipped."""
        step.status = "skipped"
        msg = f"  [dim]⊘ {step.name} (skipped"
        if reason:
            msg += f": {reason}"
        msg += ")[/]"
        self.console.print(msg)

    def print_header(self) -> None:
        """Print pipeline header."""
        self.console.print()
        self.console.print(
            Panel(
                f"[bold]{self.pipeline_name}[/]",
                style="blue",
                width=60,
            )
        )
        self.console.print()

    def print_summary(self) -> None:
        """Print final summary table."""
        self.console.print()
        table = Table(title="Pipeline Summary", show_lines=True)
        table.add_column("Step", style="bold")
        table.add_column("Status")
        table.add_column("Time", justify="right")
        table.add_column("Cost", justify="right")

        total_cost = 0.0
        total_time = 0.0

        for step in self.steps:
            status_str = {
                "completed": "[green]✓[/]",
                "failed": "[red]✗[/]",
                "skipped": "[dim]⊘[/]",
                "running": "[yellow]…[/]",
                "pending": "[dim]·[/]",
            }.get(step.status, step.status)

            time_str = f"{step.elapsed_s:.1f}s" if step.elapsed_s > 0 else "-"
            cost_str = f"${step.cost_usd:.3f}" if step.cost_usd > 0 else "-"

            table.add_row(step.name, status_str, time_str, cost_str)
            total_cost += step.cost_usd
            total_time += step.elapsed_s

        table.add_row(
            "[bold]Total[/]",
            "",
            f"[bold]{total_time:.1f}s[/]",
            f"[bold]${total_cost:.3f}[/]",
        )

        self.console.print(table)
        self.console.print()

    def print_error(self, message: str) -> None:
        """Print an error message."""
        self.console.print(f"[bold red]Error:[/] {message}")

    def print_info(self, message: str) -> None:
        """Print an info message."""
        self.console.print(f"[bold blue]Info:[/] {message}")

    def print_success(self, message: str) -> None:
        """Print a success message."""
        self.console.print(f"[bold green]Success:[/] {message}")
