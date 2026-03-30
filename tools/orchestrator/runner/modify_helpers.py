"""Python helper functions for the modify YAML workflow.

Each function is called by execute_python with:
    config: OrchestratorConfig
    variables: dict[str, Any]  (mutable — shared across the workflow)
    **kwargs: resolved step args

Functions return either:
    dict  — keys are auto-merged into variables
    StepResult — used as-is (for pause/error control flow)
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import date
from pathlib import Path
from typing import Any

from ..config import OrchestratorConfig
from ..output_parser import parse_agent_output
from ..state import (
    ModifyPhase,
    ModifyResumePoint as MRP,
    Phase,
    detect_modify_resume,
    find_spec_by_name,
    load_spec,
)
from ..worktree import create_or_reuse_worktree, remove_worktree
from .executors import StepResult

logger = logging.getLogger(__name__)


# ── Resume point sets ────────────────────────────────────────────
# Steps that should run based on the modify resume point.

_RUN_M2 = {MRP.ADR_GATE.value, MRP.M2_CASCADE.value}
_RUN_M2R = _RUN_M2 | {MRP.M2R_REVIEW.value}
_RUN_M3 = _RUN_M2R | {MRP.M3_DELTA_TASKS.value}
_RUN_B = _RUN_M3 | {MRP.B_IMPL.value}
_RUN_B2 = _RUN_B | {MRP.B2_VALIDATE.value}


# ══════════════════════════════════════════════════════════════════
# Mode detection + setup
# ══════════════════════════════════════════════════════════════════


def detect_mode_and_setup(
    *, config: OrchestratorConfig, variables: dict[str, Any], **_: Any
) -> dict[str, Any] | StepResult:
    """Detect pipeline mode and validate initial parameters.

    Modes:
      - investigate: modify-plan investigation (MP0 → MP1 → MP2)
      - single: single-spec modification (M1 → M2 → M3 → B → B2 → D)
      - plan: plan-driven multi-spec modification
    """
    modify_plan = variables.get("modify_plan", "")
    feature = variables.get("feature", "")
    change = variables.get("change", "")

    if modify_plan:
        return {
            "mode": "plan",
            "mode_investigate": "",
            "mode_single": "",
            "mode_plan": "true",
            "mode_single_or_plan": "true",
        }

    if feature:
        # Single-spec mode: validate feature exists
        spec_dir = config.project_root / ".kiro" / "specs" / feature
        if not spec_dir.is_dir():
            available = [
                d.name
                for d in (config.project_root / ".kiro" / "specs").iterdir()
                if d.is_dir()
            ]
            return StepResult(
                is_error=True,
                error_message=(
                    f"Feature '{feature}' が見つかりません。利用可能:\n"
                    + "\n".join(f"  - {n}" for n in available)
                ),
            )

        main_spec = load_spec(spec_dir / "spec.json")
        if main_spec.phase == Phase.INITIALIZED:
            return StepResult(
                is_error=True,
                error_message="要件生成が完了していません。先に implement で要件を生成してください。",
            )

        return {
            "mode": "single",
            "mode_investigate": "",
            "mode_single": "true",
            "mode_plan": "",
            "mode_single_or_plan": "true",
            "feature_name": feature,
        }

    if change:
        return {
            "mode": "investigate",
            "mode_investigate": "true",
            "mode_single": "",
            "mode_plan": "",
            "mode_single_or_plan": "",
        }

    return StepResult(
        is_error=True,
        error_message="feature, change, または modify_plan のいずれかを指定してください。",
    )


# ══════════════════════════════════════════════════════════════════
# Single-spec mode helpers
# ══════════════════════════════════════════════════════════════════


def process_m1_result(
    *, config: OrchestratorConfig, variables: dict[str, Any], **_: Any
) -> dict[str, Any] | StepResult:
    """Parse M1 output and set variables for downstream when-conditions."""
    m1_output = variables.get("m1_output", "")
    if not m1_output:
        return StepResult(is_error=True, error_message="M1 出力が空です。")

    parsed = parse_agent_output(m1_output)

    if not parsed.analysis_done:
        return StepResult(
            is_error=True,
            error_message="M1: 分析結果のマーカーが見つかりません。",
        )

    feature_name = variables.get("feature_name", "")
    change = variables.get("change", "")

    # Cache M1 result for crash recovery
    m1_cache_dir = config.project_root / ".claude" / "orchestrator"
    m1_cache_dir.mkdir(parents=True, exist_ok=True)
    m1_cache_path = m1_cache_dir / f"modify-{feature_name}.json"
    m1_cache_path.write_text(
        json.dumps(
            {
                "feature_name": feature_name,
                "change_description": change,
                "m1_output": m1_output,
                "cascade_depth": parsed.cascade_depth,
                "classification": parsed.classification,
                "delta_summary": parsed.delta_summary,
                "adr_required": parsed.adr_required,
                "adr_category": parsed.adr_category,
                "adr_reason": parsed.adr_reason,
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    # Set when-condition flags for downstream steps
    cd = parsed.cascade_depth
    return {
        "cascade_depth": cd,
        "classification": parsed.classification,
        "delta_summary": parsed.delta_summary,
        "adr_required": "true" if parsed.adr_required else "",
        "adr_category": parsed.adr_category,
        "adr_reason": parsed.adr_reason,
        "m1_confidence": parsed.m1_confidence,
        "m1_needs_review": "true" if parsed.m1_confidence == "low" else "",
        # cascade_depth-based run flags
        "run_M2": "true",  # M2 always runs (cascade step)
        "run_M2R": "true" if cd not in ("requirements-only", "") else "",
        "run_M3": "true" if cd != "requirements-only" else "",
        "run_B": "true" if cd not in ("requirements-only", "requirements+design") else "",
        "run_B2": "true" if cd != "requirements-only" else "",
        "run_steering": "true" if cd != "requirements-only" else "",
        "change_summary": (
            parsed.delta_summary.split("\n")[0]
            if parsed.delta_summary
            else change[:80]
        ),
    }


def setup_modify_worktree(
    *, config: OrchestratorConfig, variables: dict[str, Any], **_: Any
) -> dict[str, Any] | StepResult:
    """Create or reuse worktree for modify and detect resume point."""
    feature_name = variables.get("feature_name", "")
    base_branch = variables.get("base_branch", "master")

    wt_info = create_or_reuse_worktree(config, "modify", feature_name, base_branch)

    resume_point = ""
    if not wt_info.created:
        wt_spec = find_spec_by_name(wt_info.path, feature_name)
        if wt_spec:
            wt_spec.ensure_modifications_field()
            rp = detect_modify_resume(wt_spec)
            if rp:
                resume_point = rp.value

    # Adjust run flags based on resume point
    result: dict[str, Any] = {
        "worktree_path": str(wt_info.path),
        "branch_name": wt_info.branch,
        "modify_resume_point": resume_point,
    }

    if resume_point:
        cd = variables.get("cascade_depth", "")
        rp_set = {resume_point}
        result["run_M2"] = "true" if rp_set & _RUN_M2 else (variables.get("run_M2", ""))
        result["run_M2R"] = (
            "true"
            if (rp_set & _RUN_M2R) and cd not in ("requirements-only", "")
            else ""
        )
        result["run_M3"] = (
            "true"
            if (rp_set & _RUN_M3) and cd != "requirements-only"
            else ""
        )
        result["run_B"] = (
            "true"
            if (rp_set & _RUN_B) and cd not in ("requirements-only", "requirements+design")
            else ""
        )
        result["run_B2"] = (
            "true"
            if (rp_set & _RUN_B2) and cd != "requirements-only"
            else ""
        )

    return result


async def run_adr_gate_step_async(
    *, config: OrchestratorConfig, variables: dict[str, Any], **_: Any
) -> dict[str, Any] | StepResult:
    """Async version of run_adr_gate_step."""
    from .claude_p import ClaudePRunner

    adr_required = variables.get("adr_required", "")
    if not adr_required:
        return {"adr_path": "", "adr_needs_review": ""}

    feature_name = variables.get("feature_name", "")
    change = variables.get("change", "")
    m1_output = variables.get("m1_output", "")
    delta_summary = variables.get("delta_summary", "")
    adr_category = variables.get("adr_category", "")
    adr_reason = variables.get("adr_reason", "")
    wt_path = Path(variables["worktree_path"])

    context_arg = f"category={adr_category} feature={feature_name} {adr_reason}"
    prompt = (
        f"以下のSkillを実行してください:\n"
        f'Skill(skill="kiro:decision-create", args="new {context_arg}")\n\n'
        f"変更の説明:\n{change}\n\n"
        f"M1分析サマリー:\n{delta_summary}\n\n"
        f"M1分析全文:\n{m1_output}\n\n"
        f"完了時に必ず ADR_PATH=<作成されたADRファイルの相対パス> を出力してください。"
    )

    runner = ClaudePRunner(config)
    result = await runner.run(prompt, model="opus", cwd=wt_path)

    if result.is_error:
        return StepResult(
            is_error=True,
            error_message=f"ADR decision-create failed: {result.error_message}",
        )

    adr_path = _extract_adr_path(result.output_text)
    if not adr_path:
        adr_path = _find_new_adr_file(wt_path)
    if not adr_path:
        return StepResult(
            is_error=True,
            error_message="ADR was required but decision-create did not produce a file",
        )

    adr_file = wt_path / adr_path
    status = _read_adr_status(adr_file)
    needs_review = status != "accepted"

    if not needs_review:
        wt_spec = find_spec_by_name(wt_path, feature_name)
        if wt_spec:
            wt_spec.set_modify_phase(ModifyPhase.ADR_ACCEPTED)

    return {
        "adr_path": adr_path or "",
        "adr_needs_review": "true" if needs_review else "",
        "adr_status": status or "",
        "_session_ADR": result.session_id,
    }


def check_cascade_review(
    *, config: OrchestratorConfig, variables: dict[str, Any], **_: Any
) -> dict[str, Any]:
    """Check if M2R cascade review gate should be shown."""
    cascade_depth = variables.get("cascade_depth", "")
    feature_name = variables.get("feature_name", "")
    wt_path = Path(variables["worktree_path"])

    if cascade_depth in ("requirements-only", ""):
        return {"m2r_needs_review": ""}

    spec_dir = wt_path / ".kiro" / "specs" / feature_name
    review_docs: list[str] = []
    focus_items: list[str] = []

    for doc_name in ("requirements-review.md", "design-review.md"):
        doc = spec_dir / doc_name
        if doc.exists():
            review_docs.append(str(doc))
            text = doc.read_text()
            focus_items.extend(
                line.strip() for line in text.splitlines() if "\U0001F534" in line
            )

    if not review_docs:
        return {"m2r_needs_review": ""}

    focus_summary = "\n".join(focus_items) if focus_items else "（重大な指摘なし）"
    context = (
        f"変更されたレビュー文書:\n"
        + "\n".join(f"  - {d}" for d in review_docs)
        + f"\n\nカスケード深度: {cascade_depth}"
        + f"\n\nフォーカスエリア（🔴項目）:\n{focus_summary}"
    )

    return {
        "m2r_needs_review": "true",
        "m2r_context": context,
    }


def post_m3_update(
    *, config: OrchestratorConfig, variables: dict[str, Any], **_: Any
) -> dict[str, Any]:
    """Update spec phase after M3 delta tasks."""
    wt_path = Path(variables["worktree_path"])
    feature_name = variables.get("feature_name", "")
    wt_spec = find_spec_by_name(wt_path, feature_name)
    if wt_spec:
        wt_spec.set_modify_phase(ModifyPhase.DELTA_TASKS_GENERATED)
    return {}


def post_b_update(
    *, config: OrchestratorConfig, variables: dict[str, Any], **_: Any
) -> dict[str, Any]:
    """Update spec phase after B implementation."""
    wt_path = Path(variables["worktree_path"])
    feature_name = variables.get("feature_name", "")
    wt_spec = find_spec_by_name(wt_path, feature_name)
    if wt_spec:
        wt_spec.set_modify_phase(ModifyPhase.IMPL_COMPLETED)
    return {}


def post_b2_update(
    *, config: OrchestratorConfig, variables: dict[str, Any], **_: Any
) -> dict[str, Any]:
    """Update spec phase after B2 validation."""
    wt_path = Path(variables["worktree_path"])
    feature_name = variables.get("feature_name", "")
    wt_spec = find_spec_by_name(wt_path, feature_name)
    if wt_spec:
        wt_spec.set_modify_phase(ModifyPhase.VALIDATED)
    return {}


def modify_cleanup(
    *, config: OrchestratorConfig, variables: dict[str, Any], **_: Any
) -> dict[str, Any]:
    """Extract PR URL, clean up worktree and M1 cache."""
    d_output = variables.get("d_output", "")
    pr_url = _extract_pr_url(d_output)
    feature_name = variables.get("feature_name", "")
    wt_path = Path(variables["worktree_path"])

    result: dict[str, Any] = {"pr_url": pr_url}

    # Update spec phase
    wt_spec = find_spec_by_name(wt_path, feature_name)
    if wt_spec:
        wt_spec.set_modify_phase(ModifyPhase.COMPLETED)

    # Remove worktree
    if pr_url:
        removed = remove_worktree(config, wt_path)
        result["worktree_removed"] = "true" if removed else ""

    # Clean M1 cache
    m1_cache = config.project_root / ".claude" / "orchestrator" / f"modify-{feature_name}.json"
    if m1_cache.exists():
        m1_cache.unlink()

    return result


# ══════════════════════════════════════════════════════════════════
# Investigate mode (modify-plan) helpers
# ══════════════════════════════════════════════════════════════════


def process_mp0_result(
    *, config: OrchestratorConfig, variables: dict[str, Any], **_: Any
) -> dict[str, Any] | StepResult:
    """Parse MP0 investigation output and extract target specs."""
    mp0_output = variables.get("mp0_output", "")
    if not mp0_output:
        return StepResult(is_error=True, error_message="MP0 出力が空です。")

    parsed = parse_agent_output(mp0_output)

    if parsed.mp0_no_match:
        return StepResult(
            is_pause=True,
            pause_data={
                "question": "対象specが見つかりませんでした。`/plan` で新規featureとして作成してください。",
                "options": [],
            },
        )

    if parsed.mp0_new_spec_recommended:
        return StepResult(
            is_pause=True,
            pause_data={
                "question": "この変更は新規featureとして実装することを推奨します。",
                "options": [],
            },
        )

    if not parsed.mp0_done:
        return StepResult(
            is_error=True,
            error_message="MP0: 調査結果のマーカーが見つかりません。",
        )

    target_specs_str = parsed.target_specs
    target_specs = _parse_target_specs(target_specs_str)
    if not target_specs:
        return StepResult(
            is_error=True,
            error_message="MP0: 対象specリストの解析に失敗しました。",
        )

    spec_list = "\n".join(f"  - {name} ({conf})" for name, conf in target_specs)

    return {
        "mp0_target_specs_str": target_specs_str,
        "mp0_target_specs": [{"name": n, "confidence": c} for n, c in target_specs],
        "mp0_execution_order_str": parsed.execution_order,
        "mp0_propagation_map": parsed.propagation_map,
        "mp0_plan_slug": parsed.plan_slug or "",
        "mp0_spec_list": spec_list,
    }


def setup_output_dir(
    *, config: OrchestratorConfig, variables: dict[str, Any], **_: Any
) -> dict[str, Any]:
    """Create output directory for modify-plan results."""
    plans_base = config.project_root / "docs" / "modify-plans"
    slug = variables.get("mp0_plan_slug") or _next_plan_id(plans_base)
    output_dir = plans_base / slug
    output_dir.mkdir(parents=True, exist_ok=True)

    return {
        "mp_slug": slug,
        "mp_output_dir": str(output_dir),
    }


async def run_mp1_parallel(
    *, config: OrchestratorConfig, variables: dict[str, Any], **_: Any
) -> dict[str, Any] | StepResult:
    """Run MP1 plan-gen in parallel for all target specs."""
    from .claude_p import ClaudePRunner

    target_specs = variables.get("mp0_target_specs", [])
    spec_names = [s["name"] for s in target_specs]
    change = variables.get("change", "")
    propagation_map = variables.get("mp0_propagation_map", "")
    target_specs_str = variables.get("mp0_target_specs_str", "")
    output_dir = Path(variables["mp_output_dir"])

    runner = ClaudePRunner(config)
    prompt_path = config.project_root / "tools" / "orchestrator" / "prompts" / "modify-plan-gen.md"
    prompt_template = prompt_path.read_text(encoding="utf-8")

    async def run_single(name: str) -> tuple[str, Any]:
        plan_path = output_dir / f"{name}.md"
        entry = _extract_propagation_entry(propagation_map, name)
        params = {
            "FEATURE_NAME": name,
            "CHANGE_DESCRIPTION": change,
            "PROPAGATION_ENTRY": entry,
            "OUTPUT_PATH": str(plan_path),
            "ALL_TARGET_SPECS": target_specs_str,
        }
        prompt = _build_prompt_with_params(prompt_template, params)
        try:
            result = await runner.run(prompt, model="sonnet", cwd=config.project_root)
            return name, result
        except Exception as e:
            return name, e

    tasks = [run_single(name) for name in spec_names]
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    successes: list[tuple[str, Any]] = []
    failures: list[tuple[str, str]] = []

    for item in raw_results:
        if isinstance(item, Exception):
            failures.append(("unknown", str(item)))
            continue
        name, result = item
        if isinstance(result, Exception):
            failures.append((name, str(result)))
        elif hasattr(result, "is_error") and result.is_error:
            failures.append((name, result.error_message))
        else:
            successes.append((name, result))

    if not successes and failures:
        return StepResult(
            is_error=True,
            error_message=(
                "MP1: 全てのplan生成が失敗しました。\n"
                + "\n".join(f"  - {name}: {err}" for name, err in failures)
            ),
        )

    mp1_data: dict[str, dict] = {}
    for name, result in successes:
        parsed = result.parsed if hasattr(result, "parsed") else parse_agent_output(result.output_text)
        mp1_data[name] = {
            "summary": parsed.mp1_summary if hasattr(parsed, "mp1_summary") else "",
            "gaps": parsed.mp1_gaps if hasattr(parsed, "mp1_gaps") else "",
        }

    return {
        "mp1_results": mp1_data,
        "mp1_succeeded": [n for n, _ in successes],
        "mp1_failures": [{"name": n, "error": e} for n, e in failures],
    }


async def run_mp2_parallel(
    *, config: OrchestratorConfig, variables: dict[str, Any], **_: Any
) -> dict[str, Any] | StepResult:
    """Run MP2 plan-review in parallel for all succeeded specs."""
    from .claude_p import ClaudePRunner

    mp1_succeeded = variables.get("mp1_succeeded", [])
    mp1_data = variables.get("mp1_results", {})
    change = variables.get("change", "")
    propagation_map = variables.get("mp0_propagation_map", "")
    output_dir = Path(variables["mp_output_dir"])

    all_summaries = "\n\n".join(
        f"## {name}\n{data.get('summary', '')}\nGaps: {data.get('gaps', '')}"
        for name, data in mp1_data.items()
    )

    runner = ClaudePRunner(config)
    prompt_path = config.project_root / "tools" / "orchestrator" / "prompts" / "modify-plan-review.md"
    prompt_template = prompt_path.read_text(encoding="utf-8")

    async def run_single(name: str) -> tuple[str, Any]:
        plan_path = str(output_dir / f"{name}.md")
        params = {
            "FEATURE_NAME": name,
            "PLAN_PATH": plan_path,
            "CHANGE_DESCRIPTION": change,
            "PROPAGATION_MAP": propagation_map,
            "ALL_PLANS_SUMMARY": all_summaries,
        }
        prompt = _build_prompt_with_params(prompt_template, params)
        try:
            result = await runner.run(prompt, model="opus", cwd=config.project_root)
            return name, result
        except Exception as e:
            return name, e

    tasks = [run_single(name) for name in mp1_succeeded]
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    mp2_data: dict[str, dict] = {}
    for item in raw_results:
        if isinstance(item, Exception):
            continue
        name, result = item
        if isinstance(result, Exception):
            continue
        parsed = result.parsed if hasattr(result, "parsed") else parse_agent_output(result.output_text)
        mp2_data[name] = {
            "status": parsed.mp2_status if hasattr(parsed, "mp2_status") else "unknown",
            "changes": parsed.mp2_changes if hasattr(parsed, "mp2_changes") else "",
        }

    # Build review summary
    results_summary = "\n".join(
        f"  - {name}: {data.get('status', 'unknown')}" for name, data in mp2_data.items()
    )

    return {
        "mp2_results": mp2_data,
        "mp2_summary": results_summary,
    }


def write_modify_index(
    *, config: OrchestratorConfig, variables: dict[str, Any], **_: Any
) -> dict[str, Any]:
    """Write _index.md for modify-plan results."""
    output_dir = Path(variables["mp_output_dir"])
    slug = variables["mp_slug"]
    change = variables.get("change", "")
    target_specs = variables.get("mp0_target_specs", [])
    propagation_map = variables.get("mp0_propagation_map", "")
    execution_order_str = variables.get("mp0_execution_order_str", "")
    mp2_data = variables.get("mp2_results", {})

    today = date.today().isoformat()

    spec_rows: list[str] = []
    for spec in target_specs:
        name = spec["name"]
        confidence = spec["confidence"]
        status = mp2_data.get(name, {}).get("status", "READY")
        spec_rows.append(
            f"| {name} | {confidence} | [{name}.md](./{name}.md) | {status} |"
        )
    spec_table = "\n".join(spec_rows)

    exec_order = [s.strip() for s in execution_order_str.split(",")]
    exec_list = "\n".join(f"{i}. {name}" for i, name in enumerate(exec_order, 1))

    content = f"""# Modify Plan: {slug}
**Generated**: {today}
**Change**: {change}

## 対象Spec
| Spec | 信頼度 | Plan | Status |
|------|--------|------|--------|
{spec_table}

## 伝播マップ
{propagation_map}

## 推奨実行順序
```bash
make modify plan={slug}
```
上記コマンドを実行すると、以下の順序で全specを一括処理し、1つのPRを作成します。

{exec_list}
"""
    index_path = output_dir / "_index.md"
    index_path.write_text(content)

    return {
        "mp_index_path": str(index_path),
        "mp_status": "completed",
    }


# ══════════════════════════════════════════════════════════════════
# Plan-driven mode helpers
# ══════════════════════════════════════════════════════════════════


def plan_setup(
    *, config: OrchestratorConfig, variables: dict[str, Any], **_: Any
) -> dict[str, Any] | StepResult:
    """Setup for plan-driven modify: parse index, resolve order, create worktree."""
    plan_name = variables.get("modify_plan", "")
    plan_dir = config.project_root / "docs" / "modify-plans" / plan_name
    base_branch = variables.get("base_branch", "master")

    if not plan_dir.is_dir():
        return StepResult(
            is_error=True,
            error_message=f"Plan directory not found: docs/modify-plans/{plan_name}",
        )

    index_path = plan_dir / "_index.md"
    if not index_path.exists():
        return StepResult(
            is_error=True,
            error_message=f"_index.md not found in: docs/modify-plans/{plan_name}",
        )

    order = _parse_execution_order(index_path)
    if not order:
        return StepResult(
            is_error=True,
            error_message="推奨実行順序のパースに失敗しました。",
        )

    pending = _get_pending_specs(plan_dir, order)
    if not pending:
        return StepResult(
            is_pause=True,
            pause_data={
                "question": f"Plan '{plan_name}' の全specは既に完了しています。",
                "options": [],
            },
        )

    wt_info = create_or_reuse_worktree(config, "modify", plan_name, base_branch)

    return {
        "plan_dir": str(plan_dir),
        "plan_order": order,
        "plan_pending": pending,
        "worktree_path": str(wt_info.path),
        "branch_name": wt_info.branch,
        "feature_name": pending[0],  # Primary feature for commit/PR
    }


async def plan_m1_all(
    *, config: OrchestratorConfig, variables: dict[str, Any], **_: Any
) -> dict[str, Any] | StepResult:
    """Run M1 analysis for all pending specs in plan."""
    from .claude_p import ClaudePRunner

    plan_dir = Path(variables["plan_dir"])
    pending = variables.get("plan_pending", [])

    runner = ClaudePRunner(config)
    prompt_path = config.project_root / "tools" / "orchestrator" / "prompts" / "modify-analyze.md"
    prompt_template = prompt_path.read_text(encoding="utf-8")

    m1_results: dict[str, dict] = {}
    for spec_name in pending:
        plan_file = plan_dir / f"{spec_name}.md"
        if not plan_file.exists():
            return StepResult(
                is_error=True,
                error_message=f"Plan file not found: {plan_file}",
            )

        feature_name, change_desc = _parse_plan_params(plan_file)
        if not feature_name or not change_desc:
            return StepResult(
                is_error=True,
                error_message=f"{spec_name}.md から実行パラメータを抽出できません。",
            )

        params = {
            "FEATURE_NAME": feature_name,
            "CHANGE_DESCRIPTION": change_desc,
        }
        prompt = _build_prompt_with_params(prompt_template, params)
        result = await runner.run(prompt, model="opus", cwd=config.project_root)

        if result.is_error:
            return StepResult(
                is_error=True,
                error_message=f"M1 analysis failed for {spec_name}: {result.error_message}",
            )

        parsed = result.parsed
        if not parsed.analysis_done:
            return StepResult(
                is_error=True,
                error_message=f"M1: {spec_name} の分析結果マーカーが見つかりません。",
            )

        m1_results[spec_name] = {
            "feature_name": feature_name,
            "change_description": change_desc,
            "m1_output": result.output_text,
            "cascade_depth": parsed.cascade_depth,
            "classification": parsed.classification,
            "delta_summary": parsed.delta_summary,
            "adr_required": parsed.adr_required,
            "adr_category": parsed.adr_category,
            "adr_reason": parsed.adr_reason,
        }

    return {"plan_m1_results": m1_results}


async def plan_impl_all(
    *, config: OrchestratorConfig, variables: dict[str, Any], **_: Any
) -> dict[str, Any] | StepResult:
    """Run M2 → M3 → B → B2 for each pending spec in plan."""
    from .claude_p import ClaudePRunner

    pending = variables.get("plan_pending", [])
    plan_dir = Path(variables["plan_dir"])
    m1_results = variables.get("plan_m1_results", {})
    wt_path = Path(variables["worktree_path"])
    adr_paths = variables.get("plan_adr_paths", {})

    runner = ClaudePRunner(config)

    for spec_name in pending:
        m1_data = m1_results.get(spec_name, {})
        feature_name = m1_data.get("feature_name", "")
        cascade_depth = m1_data.get("cascade_depth", "")
        m1_output = m1_data.get("m1_output", "")
        adr_path = adr_paths.get(spec_name)

        extra_params: dict[str, str] = {}
        if adr_path:
            extra_params["ADR_PATH"] = adr_path

        # M2 cascade
        prompt_path = config.project_root / "tools" / "orchestrator" / "prompts" / "modify-cascade.md"
        prompt = _build_prompt_with_params(
            prompt_path.read_text(encoding="utf-8"),
            {
                "WORKTREE_PATH": str(wt_path),
                "FEATURE_NAME": feature_name,
                "CHANGE_IMPACT_REPORT": m1_output,
                "CASCADE_DEPTH": cascade_depth,
                **extra_params,
            },
        )
        result = await runner.run(prompt, model="opus", cwd=wt_path)
        if result.is_error:
            return StepResult(
                is_error=True,
                error_message=f"M2 cascade failed for {spec_name}: {result.error_message}",
            )
        if result.parsed.cascade_failed:
            return StepResult(
                is_error=True,
                error_message=f"M2 cascade FAILED for {spec_name} (design-review REJECT)",
            )

        # M3 delta tasks
        if cascade_depth != "requirements-only":
            prompt_path = config.project_root / "tools" / "orchestrator" / "prompts" / "modify-tasks.md"
            prompt = _build_prompt_with_params(
                prompt_path.read_text(encoding="utf-8"),
                {
                    "WORKTREE_PATH": str(wt_path),
                    "FEATURE_NAME": feature_name,
                    "CHANGE_IMPACT_REPORT": m1_output,
                    "CASCADE_DEPTH": cascade_depth,
                },
            )
            result = await runner.run(prompt, model="sonnet", cwd=wt_path)
            if result.is_error:
                return StepResult(
                    is_error=True,
                    error_message=f"M3 delta-tasks failed for {spec_name}: {result.error_message}",
                )
            wt_spec = find_spec_by_name(wt_path, feature_name)
            if wt_spec:
                wt_spec.set_modify_phase(ModifyPhase.DELTA_TASKS_GENERATED)

        # B impl
        if cascade_depth not in ("requirements-only", "requirements+design"):
            prompt_path = config.project_root / "tools" / "orchestrator" / "prompts" / "impl-code.md"
            prompt = _build_prompt_with_params(
                prompt_path.read_text(encoding="utf-8"),
                {
                    "WORKTREE_PATH": str(wt_path),
                    "FEATURE_NAME": feature_name,
                    **extra_params,
                },
            )
            result = await runner.run(prompt, model="sonnet", cwd=wt_path)
            if result.is_error:
                return StepResult(
                    is_error=True,
                    error_message=f"B impl failed for {spec_name}: {result.error_message}",
                )
            wt_spec = find_spec_by_name(wt_path, feature_name)
            if wt_spec:
                wt_spec.set_modify_phase(ModifyPhase.IMPL_COMPLETED)

        # B2 validate
        if cascade_depth != "requirements-only":
            prompt_path = config.project_root / "tools" / "orchestrator" / "prompts" / "impl-validate.md"
            prompt = _build_prompt_with_params(
                prompt_path.read_text(encoding="utf-8"),
                {"WORKTREE_PATH": str(wt_path), "FEATURE_NAME": feature_name},
            )
            result = await runner.run(prompt, model="opus", cwd=wt_path)
            if result.is_error:
                return StepResult(
                    is_error=True,
                    error_message=f"B2 validate failed for {spec_name}: {result.error_message}",
                )
            if result.parsed.validation_failed:
                return StepResult(
                    is_error=True,
                    error_message=f"Validation FAILED for {spec_name} (NO-GO)",
                )
            wt_spec = find_spec_by_name(wt_path, feature_name)
            if wt_spec:
                wt_spec.set_modify_phase(ModifyPhase.VALIDATED)

        _mark_spec_completed(plan_dir, spec_name)

    return {}


def plan_delivery_setup(
    *, config: OrchestratorConfig, variables: dict[str, Any], **_: Any
) -> dict[str, Any]:
    """Prepare variables for plan-mode delivery (commit + PR)."""
    pending = variables.get("plan_pending", [])
    m1_results = variables.get("plan_m1_results", {})

    all_features = [m1_results[s]["feature_name"] for s in pending if s in m1_results]
    feature_name = all_features[0] if all_features else ""

    all_delta = "\n".join(m1_results.get(s, {}).get("delta_summary", "") for s in pending)
    all_change = "\n".join(m1_results.get(s, {}).get("change_description", "") for s in pending)
    change_summary = all_delta.split("\n")[0] if all_delta else all_change[:80]

    # Check if steering should run
    cascade_depths = [m1_results.get(s, {}).get("cascade_depth", "") for s in pending]
    run_steering = any(cd != "requirements-only" for cd in cascade_depths)

    return {
        "feature_name": feature_name,
        "change_summary": change_summary,
        "run_steering": "true" if run_steering else "",
    }


def plan_cleanup(
    *, config: OrchestratorConfig, variables: dict[str, Any], **_: Any
) -> dict[str, Any]:
    """Cleanup for plan-driven mode: PR URL, worktree, phases, caches."""
    d_output = variables.get("d_output", "")
    pr_url = _extract_pr_url(d_output)
    pending = variables.get("plan_pending", [])
    m1_results = variables.get("plan_m1_results", {})
    wt_path = Path(variables["worktree_path"])

    all_features = [m1_results[s]["feature_name"] for s in pending if s in m1_results]

    # Update phases
    for fname in all_features:
        wt_spec = find_spec_by_name(wt_path, fname)
        if wt_spec:
            wt_spec.set_modify_phase(ModifyPhase.COMPLETED)

    # Remove worktree
    if pr_url:
        remove_worktree(config, wt_path)

    # Cleanup M1 caches
    m1_cache_dir = config.project_root / ".claude" / "orchestrator"
    for fname in all_features:
        m1_cache = m1_cache_dir / f"modify-{fname}.json"
        if m1_cache.exists():
            m1_cache.unlink()

    return {"pr_url": pr_url}


# ══════════════════════════════════════════════════════════════════
# Shared utilities
# ══════════════════════════════════════════════════════════════════


def _build_prompt_with_params(template: str, params: dict[str, str]) -> str:
    """Append parameters section to a prompt template."""
    if not params:
        return template
    parts = [template, "", "---", "## Parameters", ""]
    for key, value in params.items():
        parts.append(f"{key}: {value}")
    return "\n".join(parts)


def _extract_pr_url(text: str) -> str:
    m = re.search(r"https://github\.com/\S+/pull/\d+", text)
    return m.group(0) if m else ""


def _extract_adr_path(text: str) -> str | None:
    m = re.search(r"ADR_PATH=(\S+)", text)
    return m.group(1) if m else None


def _read_adr_status(adr_file: Path) -> str | None:
    if not adr_file.exists():
        return None
    content = adr_file.read_text()
    if not content.startswith("---"):
        return None
    try:
        end_idx = content.index("---", 3)
    except ValueError:
        return None
    frontmatter = content[3:end_idx]
    m = re.search(r"^status:\s*(\S+)\s*$", frontmatter, re.MULTILINE)
    return m.group(1) if m else None


def _find_new_adr_file(wt_path: Path) -> str | None:
    import subprocess

    decisions_dir = wt_path / ".kiro" / "decisions"
    if not decisions_dir.exists():
        return None
    result = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=A", "HEAD"],
        cwd=str(wt_path),
        capture_output=True,
        text=True,
    )
    new_files = [
        f
        for f in result.stdout.strip().splitlines()
        if f.startswith(".kiro/decisions/") and f.endswith(".md")
    ]
    if not new_files:
        all_adrs = sorted(decisions_dir.rglob("*.md"), key=lambda p: p.stat().st_mtime)
        if all_adrs:
            return str(all_adrs[-1].relative_to(wt_path))
        return None
    new_files.sort()
    return new_files[-1]


def _parse_target_specs(specs_str: str) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    for item in specs_str.split(","):
        item = item.strip()
        m = re.match(r"(\S+)\s*\((\w+)\)", item)
        if m:
            result.append((m.group(1), m.group(2)))
        elif item:
            result.append((item, "unknown"))
    return result


def _extract_propagation_entry(propagation_map: str, spec_name: str) -> str:
    lines = propagation_map.split("\n")
    entry_lines: list[str] = []
    capturing = False
    for line in lines:
        if line.startswith(f"## {spec_name}"):
            capturing = True
            entry_lines.append(line)
        elif capturing and line.startswith("## "):
            break
        elif capturing:
            entry_lines.append(line)
    return "\n".join(entry_lines).strip() if entry_lines else ""


def _next_plan_id(plans_base: Path) -> str:
    existing = []
    if plans_base.is_dir():
        for d in plans_base.iterdir():
            if d.is_dir() and (m := re.match(r"^m(\d+)$", d.name)):
                existing.append(int(m.group(1)))
    return f"m{max(existing, default=0) + 1}"


def _parse_execution_order(index_path: Path) -> list[str]:
    content = index_path.read_text()
    order: list[str] = []
    in_section = False
    for line in content.split("\n"):
        if "推奨実行順序" in line:
            in_section = True
            continue
        if in_section:
            if line.startswith("##") or line.startswith("> "):
                if order:
                    break
                continue
            m = re.match(r"^\d+\.\s+(\S+)\s*$", line.strip())
            if m:
                order.append(m.group(1))
                continue
            m = re.match(r".*feature=(\S+)", line)
            if m:
                order.append(m.group(1))
    return order


def _get_pending_specs(plan_dir: Path, order: list[str]) -> list[str]:
    status_path = plan_dir / ".status.json"
    completed: list[str] = []
    if status_path.exists():
        try:
            data = json.loads(status_path.read_text())
            completed = data.get("completed", [])
        except (json.JSONDecodeError, KeyError):
            pass
    return [spec for spec in order if spec not in completed]


def _mark_spec_completed(plan_dir: Path, spec_name: str) -> None:
    status_path = plan_dir / ".status.json"
    data: dict[str, Any] = {"completed": []}
    if status_path.exists():
        try:
            data = json.loads(status_path.read_text())
        except (json.JSONDecodeError, KeyError):
            pass
    if spec_name not in data.get("completed", []):
        data.setdefault("completed", []).append(spec_name)
    status_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def _parse_plan_params(plan_file: Path) -> tuple[str, str]:
    content = plan_file.read_text()
    section_match = re.search(r"##\s*/modify\s*実行パラメータ", content)
    if not section_match:
        return "", ""
    section_text = content[section_match.end() :]
    yaml_match = re.search(r"\s*```ya?ml\s*\n(.*?)\s*```", section_text, re.DOTALL)
    if not yaml_match:
        return "", ""
    yaml_text = yaml_match.group(1)

    fn_match = re.search(r"feature_name:\s*(\S+)", yaml_text)
    feature_name = fn_match.group(1) if fn_match else ""

    cd_match = re.search(
        r"change_description:\s*\|?\s*\n(.*?)(?:\n\S|\Z)", yaml_text, re.DOTALL
    )
    if cd_match:
        raw_lines = cd_match.group(1).split("\n")
        stripped = [line.strip() for line in raw_lines if line.strip()]
        change_description = "\n".join(stripped)
    else:
        cd_match = re.search(r"change_description:\s*(.+)", yaml_text)
        change_description = cd_match.group(1).strip() if cd_match else ""

    return feature_name, change_description
