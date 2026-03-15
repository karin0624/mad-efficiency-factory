"""Plan file path resolution."""

from __future__ import annotations

import re
from pathlib import Path

from .config import OrchestratorConfig


class PlanResolutionError(Exception):
    """Raised when plan file cannot be resolved."""


def sanitize_branch_name(name: str) -> str:
    """Sanitize a name for use as a git branch component.

    Lowercase, replace spaces and special chars with hyphens, collapse runs.
    """
    name = name.lower()
    name = re.sub(r"[^a-z0-9\-]", "-", name)
    name = re.sub(r"-+", "-", name)
    return name.strip("-")


def resolve_plan(config: OrchestratorConfig, argument: str) -> tuple[Path, str]:
    """Resolve a plan argument to an absolute path and sanitized name.

    Args:
        config: Orchestrator config.
        argument: User-supplied plan argument (name, relative path, etc.).

    Returns:
        (absolute_path, sanitized_plan_name) tuple.

    Raises:
        PlanResolutionError: If the plan file cannot be found.
    """
    plans_dir = config.project_root / config.plans_dir

    # If argument looks like a path (contains / or ends with .md)
    if "/" in argument or argument.endswith(".md"):
        path = config.project_root / argument
        if path.is_file():
            stem = path.stem
            return path.resolve(), sanitize_branch_name(stem)
        raise PlanResolutionError(f"Plan ファイルが見つかりません: {path}")

    # Try exact match: docs/plans/<identifier>.md
    exact = plans_dir / f"{argument}.md"
    if exact.is_file():
        return exact.resolve(), sanitize_branch_name(argument)

    # Glob search
    candidates = sorted(plans_dir.glob(f"*{argument}*"))
    candidates = [c for c in candidates if c.is_file() and c.suffix == ".md"]

    if len(candidates) == 1:
        stem = candidates[0].stem
        return candidates[0].resolve(), sanitize_branch_name(stem)

    if len(candidates) == 0:
        available = sorted(p.name for p in plans_dir.glob("*.md"))
        raise PlanResolutionError(
            f"Plan '{argument}' が見つかりません。利用可能なplan:\n"
            + "\n".join(f"  - {n}" for n in available)
        )

    # Multiple candidates
    names = [c.name for c in candidates]
    raise PlanResolutionError(
        f"Plan '{argument}' に複数の候補があります:\n"
        + "\n".join(f"  - {n}" for n in names)
        + "\nより具体的な名前を指定してください。"
    )


def list_plans(config: OrchestratorConfig) -> list[Path]:
    """List all available plan files."""
    plans_dir = config.project_root / config.plans_dir
    if not plans_dir.is_dir():
        return []
    return sorted(plans_dir.glob("*.md"))
