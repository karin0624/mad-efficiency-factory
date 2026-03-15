"""Preflight checks: gh auth, base branch detection, remote sync."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


class PreflightError(Exception):
    """Raised when preflight checks fail."""


@dataclass
class PreflightResult:
    base_branch: str
    behind: int
    ahead: int


def _run(cmd: list[str], cwd: Path, check: bool = True) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, check=check)
    return result.stdout.strip()


def _run_rc(cmd: list[str], cwd: Path) -> tuple[int, str, str]:
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def check_gh_auth(project_root: Path) -> None:
    """Verify GitHub CLI is available and authenticated."""
    rc, _, _ = _run_rc(["which", "gh"], cwd=project_root)
    if rc != 0:
        raise PreflightError("GitHub CLI (gh) が見つかりません。インストールしてください。")

    rc, _, stderr = _run_rc(["gh", "auth", "status"], cwd=project_root)
    if rc != 0:
        raise PreflightError(f"GitHub CLI が未認証です: {stderr}")


def detect_base_branch(project_root: Path) -> str:
    """Detect the default base branch (e.g. master/main)."""
    # Try symbolic-ref first
    rc, stdout, _ = _run_rc(
        ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
        cwd=project_root,
    )
    if rc == 0 and stdout:
        # "refs/remotes/origin/master" -> "master"
        return stdout.split("/")[-1]

    # Fallback: git remote show origin
    rc, stdout, _ = _run_rc(
        ["git", "remote", "show", "origin"],
        cwd=project_root,
    )
    if rc == 0:
        for line in stdout.splitlines():
            if "HEAD branch" in line:
                return line.split(":")[-1].strip()

    raise PreflightError(
        "ベースブランチを検出できませんでした。"
        "`git remote set-head origin --auto` を実行してください。"
    )


def check_current_branch(project_root: Path, base_branch: str) -> None:
    """Ensure we are on the base branch."""
    current = _run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=project_root,
    )
    if current != base_branch:
        raise PreflightError(
            f"現在のブランチ '{current}' はベースブランチ '{base_branch}' ではありません。"
            f"`git checkout {base_branch}` で切り替えてください。"
        )


def fetch_origin(project_root: Path) -> None:
    """Fetch from origin."""
    _run(["git", "fetch", "origin"], cwd=project_root)


def check_sync_status(project_root: Path, base_branch: str) -> tuple[int, int]:
    """Check behind/ahead counts relative to origin.

    Returns:
        (behind, ahead) tuple.
    """
    behind_str = _run(
        ["git", "rev-list", f"HEAD..origin/{base_branch}", "--count"],
        cwd=project_root,
    )
    ahead_str = _run(
        ["git", "rev-list", f"origin/{base_branch}..HEAD", "--count"],
        cwd=project_root,
    )
    return int(behind_str), int(ahead_str)


def pull_base(project_root: Path, base_branch: str) -> None:
    """Pull latest from origin base branch."""
    _run(["git", "pull", "origin", base_branch], cwd=project_root)


def push_base(project_root: Path, base_branch: str) -> None:
    """Push to origin base branch."""
    _run(["git", "push", "origin", base_branch], cwd=project_root)


def run_preflight(project_root: Path) -> PreflightResult:
    """Run all preflight checks.

    Returns PreflightResult on success.
    Raises PreflightError on failure.
    """
    check_gh_auth(project_root)
    base_branch = detect_base_branch(project_root)
    check_current_branch(project_root, base_branch)
    fetch_origin(project_root)
    behind, ahead = check_sync_status(project_root, base_branch)

    if behind > 0 and ahead > 0:
        raise PreflightError(
            f"ブランチが分岐しています (ahead={ahead}, behind={behind})。"
            "手動で解決してください。"
        )

    return PreflightResult(base_branch=base_branch, behind=behind, ahead=ahead)
