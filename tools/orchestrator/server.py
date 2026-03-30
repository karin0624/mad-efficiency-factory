"""FastMCP server — exposes sdd_start, sdd_resume, sdd_status tools."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from .config import OrchestratorConfig
from .response import pipeline_failed
from .runner import WorkflowRunner
from .session import (
    PipelineSession,
    create_session,
    list_sessions,
    load_session,
    save_session,
)

mcp = FastMCP("sdd")

# Pipeline name → YAML workflow file (relative to tools/orchestrator/workflows/)
_WORKFLOW_FILES: dict[str, str] = {
    "implement": "implement.yaml",
    "modify": "modify.yaml",
    "modify-plan": "modify.yaml",  # modify-plan is investigate mode of modify
}


def _get_config() -> OrchestratorConfig:
    """Build config from CWD (MCP server context)."""
    return OrchestratorConfig(project_root=Path.cwd().resolve())


def _session_dir(config: OrchestratorConfig) -> Path:
    return config.project_root / config.session_dir


def _workflow_path(pipeline: str) -> Path:
    """Resolve the YAML workflow path for a pipeline name."""
    filename = _WORKFLOW_FILES.get(pipeline)
    if not filename:
        msg = f"Unknown pipeline: {pipeline}"
        raise ValueError(msg)
    return Path(__file__).parent / "workflows" / filename


@mcp.tool()
async def sdd_start(
    pipeline: str,
    plan: str = "",
    feature: str = "",
    change: str = "",
    modify_plan: str = "",
) -> dict[str, Any]:
    """Start a new SDD pipeline. Runs until the first checkpoint or completion.

    Args:
        pipeline: "implement" | "modify" | "modify-plan"
        plan: Plan file name (for implement)
        feature: Feature/spec name (for modify)
        change: Change description (for modify, modify-plan)
        modify_plan: Plan directory name (for modify --plan)
    """
    config = _get_config()
    sd = _session_dir(config)

    params: dict[str, Any] = {
        "plan": plan,
        "feature": feature,
        "change": change,
        "modify_plan": modify_plan,
    }

    # For modify-plan, set the mode flag so modify.yaml runs in investigate mode
    if pipeline == "modify-plan":
        params["mode"] = "investigate"

    session = create_session(pipeline, params, sd)

    try:
        wf_path = _workflow_path(pipeline)
        runner = WorkflowRunner(config, session=session, session_dir=sd)
        return await runner.run(wf_path, params)
    except Exception as e:
        session.status = "failed"
        save_session(session, sd)
        return pipeline_failed(
            session_id=session.session_id,
            pipeline=pipeline,
            current_step=session.checkpoint or "unknown",
            error_message=str(e),
            progress=session.completed_steps,
        )


@mcp.tool()
async def sdd_resume(
    session_id: str,
    user_input: str = "",
    action: str = "",
) -> dict[str, Any]:
    """Resume a paused pipeline session.

    Args:
        session_id: Session ID to resume
        user_input: Answer to an interaction_required question
        action: "retry" | "skip" | "abort" (for error_occurred)
    """
    config = _get_config()
    sd = _session_dir(config)

    session = load_session(session_id, sd)
    if not session:
        return pipeline_failed(
            session_id=session_id,
            pipeline="unknown",
            current_step="resume",
            error_message=f"Session not found: {session_id}",
        )

    if session.status != "paused":
        return pipeline_failed(
            session_id=session_id,
            pipeline=session.pipeline,
            current_step=session.checkpoint,
            error_message=f"Session is not paused (status={session.status})",
        )

    try:
        wf_path = _workflow_path(session.pipeline)
        runner = WorkflowRunner(config, session=session, session_dir=sd)
        return await runner.resume(wf_path, user_input=user_input, action=action)
    except Exception as e:
        session.status = "failed"
        save_session(session, sd)
        return pipeline_failed(
            session_id=session.session_id,
            pipeline=session.pipeline,
            current_step=session.checkpoint or "unknown",
            error_message=str(e),
            progress=session.completed_steps,
        )


@mcp.tool()
async def sdd_status(session_id: str = "") -> dict[str, Any]:
    """Check pipeline session status.

    Args:
        session_id: Specific session ID (omit for all active sessions)
    """
    config = _get_config()
    sd = _session_dir(config)

    if session_id:
        session = load_session(session_id, sd)
        if not session:
            return {"error": f"Session not found: {session_id}"}
        return session.to_dict()

    sessions = list_sessions(sd)
    return {"active_sessions": [s.to_dict() for s in sessions]}
