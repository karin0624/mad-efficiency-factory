"""Orchestrator configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


MODEL_MAP: dict[str, str] = {
    "opus": "claude-opus-4-6",
    "sonnet": "claude-sonnet-4-6",
}

# Tools that every agent step should have auto-approved.
DEFAULT_ALLOWED_TOOLS: list[str] = [
    "Bash",
    "Read",
    "Write",
    "Edit",
    "Glob",
    "Grep",
    "Skill",
    "Agent",
    "TodoWrite",
]


@dataclass
class OrchestratorConfig:
    """Top-level configuration for a pipeline run."""

    project_root: Path
    model_map: dict[str, str] = field(default_factory=lambda: dict(MODEL_MAP))
    max_turns: int = 200
    permission_mode: str = "acceptEdits"
    allowed_tools: list[str] = field(
        default_factory=lambda: list(DEFAULT_ALLOWED_TOOLS)
    )
    worktree_base: str = ".claude/worktrees"
    plans_dir: str = "docs/plans"

    def resolve_model(self, alias: str) -> str:
        """Resolve a short model alias to a full model ID."""
        return self.model_map.get(alias, alias)

    @property
    def worktree_root(self) -> Path:
        return self.project_root / self.worktree_base
