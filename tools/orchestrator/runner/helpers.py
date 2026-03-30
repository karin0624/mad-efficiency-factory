"""Python helper functions for YAML workflow steps.

Each function is called by execute_python with:
    config: OrchestratorConfig
    variables: dict[str, Any]  (mutable — shared across the workflow)
    **kwargs: resolved step args

Functions return either:
    dict  — keys are auto-merged into variables
    StepResult — used as-is (for pause/error control flow)
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..config import OrchestratorConfig
from ..output_parser import has_l4_human_review
from ..plan_resolver import PlanResolutionError, resolve_plan
from ..preflight import (
    PreflightError,
    pull_base,
    push_base,
    run_preflight,
)
from ..state import (
    ImplementResumePoint as RP,
    detect_implement_resume,
    find_spec_in_worktree,
)
from ..worktree import create_or_reuse_worktree, remove_worktree
from .executors import StepResult


# ── Resume point sets ─────────────────────────────────────────────
# Mirrors the sets in pipelines/implement.py for when-condition evaluation.

_RUN_A1 = {RP.A1_WHAT.value, RP.A1_WHAT_PHASE2.value}
_RUN_A1R = _RUN_A1 | {RP.A1R_REVIEW.value}
_RUN_A2 = _RUN_A1R | {RP.A2_HOW_FULL.value, RP.A2_HOW_REVIEW_ONLY.value}
_RUN_A2R = _RUN_A2 | {RP.A2R_REVIEW.value}
_RUN_A3 = _RUN_A2R | {RP.A3_TASKS.value, RP.A3_TASKS_APPROVAL.value}
_RUN_B = _RUN_A3 | {RP.B_IMPL.value}
_RUN_B2 = _RUN_B | {RP.B2_VALIDATE.value}


# ── Preflight ─────────────────────────────────────────────────────


def run_preflight_check(*, config: OrchestratorConfig, variables: dict[str, Any], **_: Any) -> dict[str, Any] | StepResult:
    """Run preflight checks. Sets base_branch and behind/ahead flags."""
    try:
        preflight = run_preflight(config.project_root)
    except PreflightError as e:
        return StepResult(is_error=True, error_message=str(e))

    return {
        "base_branch": preflight.base_branch,
        "preflight_behind": str(preflight.behind) if preflight.behind > 0 else "",
        "preflight_behind_count": str(preflight.behind),
        "preflight_ahead": str(preflight.ahead) if preflight.ahead > 0 else "",
        "preflight_ahead_count": str(preflight.ahead),
    }


def preflight_pull_action(*, config: OrchestratorConfig, variables: dict[str, Any], **_: Any) -> dict[str, Any]:
    """Pull from remote if user chose to."""
    user_input = variables.get("_user_input", "")
    if "pull" in user_input.lower():
        pull_base(config.project_root, variables["base_branch"])
    return {}


def preflight_push_action(*, config: OrchestratorConfig, variables: dict[str, Any], **_: Any) -> dict[str, Any]:
    """Push to remote if user chose to."""
    user_input = variables.get("_user_input", "")
    if "push" in user_input.lower():
        push_base(config.project_root, variables["base_branch"])
    return {}


# ── Setup ─────────────────────────────────────────────────────────


def setup_worktree_step(*, config: OrchestratorConfig, variables: dict[str, Any], **_: Any) -> dict[str, Any] | StepResult:
    """Plan resolution + worktree creation + resume point detection.

    Sets worktree_path, branch_name, feature_name, resume_point, and
    all RUN_* sets needed for step when-conditions.
    """
    plan_argument = variables.get("plan", variables.get("plan_argument", ""))
    plan_path, plan_name = resolve_plan(config, plan_argument)

    base_branch = variables.get("base_branch", "master")
    wt_info = create_or_reuse_worktree(config, "feat", plan_name, base_branch)

    resume_point = RP.A1_WHAT
    feature_name = ""
    if not wt_info.created:
        spec = find_spec_in_worktree(wt_info.path)
        if spec:
            resume_point = detect_implement_resume(spec)
            feature_name = spec.feature_name

    resume_mode = "full"
    if resume_point == RP.A2_HOW_REVIEW_ONLY:
        resume_mode = "review-only"

    return {
        "worktree_path": str(wt_info.path),
        "branch_name": wt_info.branch,
        "feature_name": feature_name,
        "plan_path": str(plan_path),
        "plan_name": plan_name,
        "resume_point": resume_point.value,
        "resume_mode": resume_mode,
        # Resume point sets for when-conditions
        "RUN_A1": _RUN_A1,
        "RUN_A1R": _RUN_A1R,
        "RUN_A2": _RUN_A2,
        "RUN_A2R": _RUN_A2R,
        "RUN_A3": _RUN_A3,
        "RUN_B": _RUN_B,
        "RUN_B2": _RUN_B2,
    }


# ── Plan Phase helpers ───────────────────────────────────────────

# Keywords that suggest a well-scoped user description
_SCOPE_KEYWORDS = re.compile(
    r"(spec|feature|module|component|endpoint|page|screen|api|cli|command|pipeline|workflow)",
    re.IGNORECASE,
)
_USECASE_KEYWORDS = re.compile(
    r"(when|should|must|can|allow|enable|support|provide|display|return|accept|reject|validate)",
    re.IGNORECASE,
)

_MIN_DESCRIPTION_LENGTH = 30


def plan_resolve_or_create_step(*, config: OrchestratorConfig, variables: dict[str, Any], **_: Any) -> dict[str, Any] | StepResult:
    """Try to resolve an existing plan file. If not found, flag for plan creation.

    On success: sets plan_path, plan_name.
    On PlanResolutionError: sets needs_plan_creation=true and plan_file_path
    for the P1 agent to write to.
    """
    plan_argument = variables.get("plan", variables.get("plan_argument", ""))

    try:
        plan_path, plan_name = resolve_plan(config, plan_argument)
        return {
            "plan_path": str(plan_path),
            "plan_name": plan_name,
        }
    except PlanResolutionError:
        # Plan not found — need to create one
        plans_dir = config.project_root / config.plans_dir
        plans_dir.mkdir(parents=True, exist_ok=True)
        from ..plan_resolver import sanitize_branch_name
        sanitized = sanitize_branch_name(plan_argument) if plan_argument else "new-plan"
        plan_file_path = plans_dir / f"{sanitized}.md"
        return {
            "needs_plan_creation": "true",
            "plan_file_path": str(plan_file_path),
            "plan_name": sanitized,
            "user_description": plan_argument,
        }


def p0_input_check_step(*, config: OrchestratorConfig, variables: dict[str, Any], **_: Any) -> dict[str, Any]:
    """Simple heuristic check on user_description sufficiency.

    Checks length, presence of use-case keywords, and scope keywords.
    Sets p0_needs_clarification if the description seems insufficient.
    """
    desc = variables.get("user_description", "")

    if not desc or len(desc.strip()) < _MIN_DESCRIPTION_LENGTH:
        return {"p0_needs_clarification": "true"}

    has_scope = bool(_SCOPE_KEYWORDS.search(desc))
    has_usecase = bool(_USECASE_KEYWORDS.search(desc))

    if not has_scope and not has_usecase:
        return {"p0_needs_clarification": "true"}

    return {"p0_needs_clarification": ""}


def merge_p0_clarification(*, config: OrchestratorConfig, variables: dict[str, Any], **_: Any) -> dict[str, Any]:
    """Merge P0_clarify user answers into user_description."""
    original = variables.get("user_description", "")
    clarification = variables.get("_user_input", "")
    if clarification:
        merged = f"{original}\n\n## 補足情報\n{clarification}"
        return {"user_description": merged}
    return {}


def post_plan_creation_step(*, config: OrchestratorConfig, variables: dict[str, Any], **_: Any) -> dict[str, Any]:
    """After P1/P2 plan creation, set plan_path from plan_file_path."""
    plan_file_path = variables.get("plan_file_path", "")
    if plan_file_path and Path(plan_file_path).exists():
        return {"plan_path": plan_file_path}
    # Fallback: if the file wasn't created at the expected path, return what we have
    return {"plan_path": plan_file_path}


def setup_worktree_only_step(*, config: OrchestratorConfig, variables: dict[str, Any], **_: Any) -> dict[str, Any] | StepResult:
    """Worktree creation + resume detection (without plan resolution).

    Unlike setup_worktree_step, this assumes plan_path/plan_name are
    already set by earlier Plan Phase steps.
    """
    plan_name = variables.get("plan_name", "")
    if not plan_name:
        return StepResult(
            is_error=True,
            error_message="plan_name が未設定です。Plan Phase を確認してください。",
        )

    base_branch = variables.get("base_branch", "master")
    wt_info = create_or_reuse_worktree(config, "feat", plan_name, base_branch)

    resume_point = RP.A1_WHAT
    feature_name = ""
    if not wt_info.created:
        spec = find_spec_in_worktree(wt_info.path)
        if spec:
            resume_point = detect_implement_resume(spec)
            feature_name = spec.feature_name

    resume_mode = "full"
    if resume_point == RP.A2_HOW_REVIEW_ONLY:
        resume_mode = "review-only"

    return {
        "worktree_path": str(wt_info.path),
        "branch_name": wt_info.branch,
        "feature_name": feature_name,
        "resume_point": resume_point.value,
        "resume_mode": resume_mode,
        # Resume point sets for when-conditions
        "RUN_A1": _RUN_A1,
        "RUN_A1R": _RUN_A1R,
        "RUN_A2": _RUN_A2,
        "RUN_A2R": _RUN_A2R,
        "RUN_A3": _RUN_A3,
        "RUN_B": _RUN_B,
        "RUN_B2": _RUN_B2,
    }


# ── Post-A1: detect feature name ─────────────────────────────────


def post_a1_detect_feature(*, config: OrchestratorConfig, variables: dict[str, Any], **_: Any) -> dict[str, Any] | StepResult:
    """Find spec.json after A1 step and extract feature_name."""
    wt_path = Path(variables["worktree_path"])
    spec = find_spec_in_worktree(wt_path)
    if spec:
        return {"feature_name": spec.feature_name}
    # If feature_name was already set by setup, keep it
    if variables.get("feature_name"):
        return {}
    return StepResult(
        is_error=True,
        error_message="Feature name が取得できませんでした。spec.json を確認してください。",
    )


# ── L4: check for human review tasks ─────────────────────────────


def check_l4_tasks(*, config: OrchestratorConfig, variables: dict[str, Any], **_: Any) -> dict[str, Any]:
    """Check if tasks.md contains L4 human review tasks."""
    wt_path = Path(variables["worktree_path"])
    feature_name = variables.get("feature_name", "")
    tasks_md = wt_path / ".kiro" / "specs" / feature_name / "tasks.md"

    has_l4 = False
    if tasks_md.exists():
        has_l4 = has_l4_human_review(tasks_md.read_text())

    return {"has_l4_tasks": "true" if has_l4 else ""}


# ── Post-D: extract PR URL and clean up worktree ─────────────────


def extract_pr_and_cleanup(*, config: OrchestratorConfig, variables: dict[str, Any], **_: Any) -> dict[str, Any]:
    """Extract PR URL from D step output and clean up worktree if successful."""
    # The PR URL is in the D step's output, stored by the engine
    d_output = variables.get("d_output", "")
    pr_url = _extract_pr_url(d_output)

    result: dict[str, Any] = {"pr_url": pr_url}

    if pr_url:
        wt_path = Path(variables["worktree_path"])
        removed = remove_worktree(config, wt_path)
        result["worktree_removed"] = "true" if removed else ""

    return result


def _extract_pr_url(text: str) -> str:
    """Extract GitHub PR URL from text."""
    m = re.search(r"https://github\.com/\S+/pull/\d+", text)
    return m.group(0) if m else ""
