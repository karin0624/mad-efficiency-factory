"""Response types for the SDD MCP tool API."""

from __future__ import annotations

from typing import Any


def _make_response(
    *,
    session_id: str,
    type: str,
    pipeline: str,
    current_step: str,
    progress: list[dict[str, Any]] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Build a standardized response dict."""
    resp: dict[str, Any] = {
        "session_id": session_id,
        "type": type,
        "pipeline": pipeline,
        "current_step": current_step,
        "progress": progress or [],
    }
    resp.update(extra)
    return resp


def interaction_required(
    *,
    session_id: str,
    pipeline: str,
    current_step: str,
    question: str,
    options: list[str] | None = None,
    context: str = "",
    progress: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """User input is needed — LLM should ask and resume."""
    return _make_response(
        session_id=session_id,
        type="interaction_required",
        pipeline=pipeline,
        current_step=current_step,
        progress=progress,
        question=question,
        options=options or [],
        context=context,
    )


def error_occurred(
    *,
    session_id: str,
    pipeline: str,
    current_step: str,
    error_message: str,
    step_output: str = "",
    recoverable: bool = True,
    suggested_actions: list[str] | None = None,
    progress: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Step failed — LLM should analyze and retry/skip/abort."""
    return _make_response(
        session_id=session_id,
        type="error_occurred",
        pipeline=pipeline,
        current_step=current_step,
        progress=progress,
        error_message=error_message,
        step_output=step_output,
        recoverable=recoverable,
        suggested_actions=suggested_actions or ["retry", "abort"],
    )


def pipeline_completed(
    *,
    session_id: str,
    pipeline: str,
    current_step: str,
    result: dict[str, Any],
    progress: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Pipeline finished successfully."""
    return _make_response(
        session_id=session_id,
        type="pipeline_completed",
        pipeline=pipeline,
        current_step=current_step,
        progress=progress,
        result=result,
    )


def pipeline_failed(
    *,
    session_id: str,
    pipeline: str,
    current_step: str,
    error_message: str,
    progress: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Pipeline failed irrecoverably."""
    return _make_response(
        session_id=session_id,
        type="pipeline_failed",
        pipeline=pipeline,
        current_step=current_step,
        progress=progress,
        error_message=error_message,
    )
