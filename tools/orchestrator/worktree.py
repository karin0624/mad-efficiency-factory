"""Git worktree management."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config import OrchestratorConfig


@dataclass
class WorktreeInfo:
    path: Path
    branch: str
    created: bool  # True if newly created this run


def _run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> str:
    result = subprocess.run(
        cmd, capture_output=True, text=True, cwd=cwd, check=check
    )
    return result.stdout.strip()


def _run_rc(cmd: list[str], cwd: Path | None = None) -> tuple[int, str]:
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return result.returncode, result.stdout.strip()


def worktree_exists(config: OrchestratorConfig, rel_path: str) -> bool:
    """Check if a worktree directory exists."""
    return (config.project_root / config.worktree_base / rel_path).is_dir()


def get_worktree_path(config: OrchestratorConfig, rel_path: str) -> Path:
    """Get the absolute path for a worktree."""
    return (config.project_root / config.worktree_base / rel_path).resolve()


def branch_exists(config: OrchestratorConfig, branch: str) -> bool:
    """Check if a git branch exists locally."""
    rc, _ = _run_rc(
        ["git", "rev-parse", "--verify", branch],
        cwd=config.project_root,
    )
    return rc == 0


def create_or_reuse_worktree(
    config: OrchestratorConfig,
    prefix: str,
    name: str,
    base_branch: str,
) -> WorktreeInfo:
    """Create or reuse a git worktree.

    Args:
        config: Orchestrator configuration.
        prefix: Worktree prefix (e.g. "feat" or "modify").
        name: Sanitized name for the branch/worktree directory.
        base_branch: Base branch to create from (e.g. "master").

    Returns:
        WorktreeInfo with path, branch name, and whether it was newly created.
    """
    rel_path = f"{prefix}/{name}"
    branch = f"{prefix}/{name}"
    wt_path = get_worktree_path(config, rel_path)

    # Case 1: Worktree already exists — reuse
    if wt_path.is_dir():
        return WorktreeInfo(path=wt_path, branch=branch, created=False)

    # Ensure parent directory exists
    wt_path.parent.mkdir(parents=True, exist_ok=True)

    # Case 2: Branch exists but no worktree — create worktree for existing branch
    if branch_exists(config, branch):
        _run(
            ["git", "worktree", "add", str(wt_path), branch],
            cwd=config.project_root,
        )
        return WorktreeInfo(path=wt_path, branch=branch, created=False)

    # Case 3: Neither exists — create new branch + worktree
    _run(
        [
            "git",
            "worktree",
            "add",
            "-b",
            branch,
            str(wt_path),
            f"origin/{base_branch}",
        ],
        cwd=config.project_root,
    )
    return WorktreeInfo(path=wt_path, branch=branch, created=True)


def remove_worktree(config: OrchestratorConfig, wt_path: Path) -> bool:
    """Remove a worktree. Returns True if successful."""
    rc, _ = _run_rc(
        ["git", "worktree", "remove", str(wt_path)],
        cwd=config.project_root,
    )
    if rc != 0:
        return False

    # Try to clean up empty parent directory
    parent = wt_path.parent
    try:
        parent.rmdir()
    except OSError:
        pass
    return True
