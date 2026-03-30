"""Step type executors — one function per step type."""

from __future__ import annotations

import asyncio
import importlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config import OrchestratorConfig
from ..output_parser import parse_agent_output
from ..progress import StepTracker
from .claude_p import ClaudePResult, ClaudePRunner
from .schema import Step
from .template import evaluate_condition, resolve, resolve_dict

logger = logging.getLogger(__name__)


@dataclass
class StepResult:
    """Unified result from any step executor."""

    output_text: str = ""
    session_id: str = ""
    is_error: bool = False
    error_message: str = ""
    is_pause: bool = False
    pause_data: dict[str, Any] | None = None
    extracted: dict[str, Any] | None = None
    markers: dict[str, bool] | None = None
    values: dict[str, str] | None = None
    raw_result: Any = None


async def execute_claude(
    step: Step,
    variables: dict[str, Any],
    config: OrchestratorConfig,
    runner: ClaudePRunner,
    tracker: StepTracker,
) -> StepResult:
    """Execute a claude -p step."""
    # Build prompt from template file + params
    prompt_path = config.project_root / resolve(step.prompt, variables)
    if not prompt_path.exists():
        return StepResult(
            is_error=True,
            error_message=f"Prompt file not found: {prompt_path}",
        )

    prompt_text = prompt_path.read_text(encoding="utf-8")
    resolved_params = resolve_dict(step.params, variables)

    # Append parameters section
    if resolved_params:
        parts = [prompt_text, "", "---", "## Parameters", ""]
        for key, value in resolved_params.items():
            parts.append(f"{key}: {value}")
        prompt_text = "\n".join(parts)

    cwd = resolve(step.cwd, variables) if step.cwd else str(config.project_root)

    record = tracker.add_step(step.id, step.model)
    tracker.start_step(record)

    result = await runner.run(
        prompt_text,
        model=step.model,
        cwd=Path(cwd),
        max_turns=step.max_turns,
        append_system_prompt=resolve(step.append_system_prompt, variables) if step.append_system_prompt else "",
        allowed_tools=step.allowed_tools or None,
        resume_session_id=variables.get(f"_session_{step.resume_from}", "") if step.resume_from else "",
    )

    if result.is_error:
        tracker.fail_step(record, result.error_message)
    else:
        tracker.complete_step(record)

    step_result = StepResult(
        output_text=result.output_text,
        session_id=result.session_id,
        is_error=result.is_error,
        error_message=result.error_message,
        markers=dict(result.parsed.markers),
        values=dict(result.parsed.values),
        raw_result=result,
    )

    # Handle extractions
    if step.extract:
        step_result.extracted = {}
        for var_name, expr in step.extract.items():
            step_result.extracted[var_name] = resolve(expr, {
                "result": result.parsed,
                "output": result.output_text,
                "session_id": result.session_id,
                **variables,
            })

    return step_result


async def execute_python(
    step: Step,
    variables: dict[str, Any],
    config: OrchestratorConfig,
    tracker: StepTracker,
) -> StepResult:
    """Execute a python function step.

    The function field should be "module.path:function_name".
    """
    record = tracker.add_step(step.id, "python")
    tracker.start_step(record)

    try:
        module_path, func_name = step.function.rsplit(":", 1)
        module = importlib.import_module(module_path)
        func = getattr(module, func_name)

        # Resolve args
        resolved_args = resolve_dict(step.args, variables)
        resolved_args["config"] = config
        resolved_args["variables"] = variables

        # Call function (support both sync and async)
        if asyncio.iscoroutinefunction(func):
            result = await func(**resolved_args)
        else:
            result = func(**resolved_args)

        # If function returns a StepResult directly, use it as-is
        if isinstance(result, StepResult):
            if result.is_error:
                tracker.fail_step(record, result.error_message)
            elif not result.is_pause:
                tracker.complete_step(record)
            return result

        tracker.complete_step(record)

        step_result = StepResult(raw_result=result)

        # Handle extractions
        if isinstance(result, dict):
            if step.extract:
                step_result.extracted = {}
                for var_name, expr in step.extract.items():
                    step_result.extracted[var_name] = resolve(expr, {
                        "result": result,
                        **variables,
                    })
            else:
                # Auto-merge all result keys into variables
                step_result.extracted = dict(result)

        return step_result

    except Exception as e:
        tracker.fail_step(record, str(e))
        return StepResult(is_error=True, error_message=str(e))


async def execute_skill(
    step: Step,
    variables: dict[str, Any],
    config: OrchestratorConfig,
    runner: ClaudePRunner,
    tracker: StepTracker,
) -> StepResult:
    """Execute a Claude Code skill via claude -p."""
    record = tracker.add_step(step.id, step.model)
    tracker.start_step(record)

    skill_name = resolve(step.skill, variables)
    skill_args = resolve(step.args.get("args", ""), variables) if step.args else ""

    # Build a prompt that invokes the skill
    prompt = f'以下のSkillを実行してください:\nSkill(skill="{skill_name}"'
    if skill_args:
        prompt += f', args="{skill_args}"'
    prompt += ")"

    cwd = resolve(step.cwd, variables) if step.cwd else str(config.project_root)

    result = await runner.run(
        prompt,
        model=step.model,
        cwd=Path(cwd),
        resume_session_id=variables.get(f"_session_{step.resume_from}", "") if step.resume_from else "",
    )

    if result.is_error:
        tracker.fail_step(record, result.error_message)
    else:
        tracker.complete_step(record)

    return StepResult(
        output_text=result.output_text,
        session_id=result.session_id,
        is_error=result.is_error,
        error_message=result.error_message,
        raw_result=result,
    )


async def execute_review_gate(
    step: Step,
    variables: dict[str, Any],
    config: OrchestratorConfig,
    tracker: StepTracker,
) -> StepResult:
    """Execute a review gate — always pauses for user input."""
    record = tracker.add_step(step.id, "gate")
    tracker.start_step(record)

    question = resolve(step.question, variables)
    options = [resolve(o, variables) for o in step.options] if step.options else []

    context = ""
    if step.file:
        file_path = Path(resolve(step.file, variables))
        if file_path.exists():
            content = file_path.read_text(encoding="utf-8")
            if step.focus:
                # Extract lines containing the focus marker
                focus_lines = [
                    line for line in content.splitlines()
                    if step.focus in line
                ]
                if focus_lines:
                    context = "\n".join(focus_lines)
        elif step.skip_if_file_missing:
            tracker.skip_step(record, f"File not found: {file_path}")
            return StepResult()  # Not a pause — skip this gate
        else:
            context = f"(File not found: {file_path})"

    tracker.complete_step(record)

    return StepResult(
        is_pause=True,
        pause_data={
            "question": question,
            "options": options,
            "context": context,
            "on_feedback": step.on_feedback.model_dump() if step.on_feedback else None,
        },
    )


async def execute_parallel(
    step: Step,
    variables: dict[str, Any],
    config: OrchestratorConfig,
    runner: ClaudePRunner,
    tracker: StepTracker,
) -> StepResult:
    """Execute parallel sub-steps via asyncio.gather()."""
    tasks = []
    for sub_step in step.steps:
        if not evaluate_condition(sub_step.when, variables):
            logger.info("Skipping parallel sub-step %s (condition false)", sub_step.id)
            continue

        if sub_step.type == "claude":
            tasks.append(execute_claude(sub_step, variables, config, runner, tracker))
        elif sub_step.type == "python":
            tasks.append(execute_python(sub_step, variables, config, tracker))
        elif sub_step.type == "skill":
            tasks.append(execute_skill(sub_step, variables, config, runner, tracker))
        else:
            logger.warning("Unsupported parallel sub-step type: %s", sub_step.type)

    if not tasks:
        return StepResult()

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Aggregate results
    errors = []
    extracted: dict[str, Any] = {}
    all_markers: dict[str, bool] = {}

    for i, r in enumerate(results):
        if isinstance(r, Exception):
            errors.append(f"Sub-step {step.steps[i].id}: {r}")
        elif isinstance(r, StepResult):
            if r.is_error:
                errors.append(f"Sub-step {step.steps[i].id}: {r.error_message}")
            if r.extracted:
                extracted.update(r.extracted)
            if r.markers:
                all_markers.update(r.markers)

    if errors:
        return StepResult(
            is_error=True,
            error_message="; ".join(errors),
            extracted=extracted or None,
            markers=all_markers or None,
        )

    return StepResult(
        extracted=extracted or None,
        markers=all_markers or None,
    )
