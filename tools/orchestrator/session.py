"""Pipeline session management — create, load, save, list."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class PipelineSession:
    """Persistent state for an interruptible pipeline execution."""

    session_id: str
    pipeline: str  # "implement" | "modify" | "modify-plan"
    status: str = "running"  # "running" | "paused" | "completed" | "failed"
    params: dict[str, Any] = field(default_factory=dict)
    checkpoint: str = ""
    checkpoint_data: dict[str, Any] = field(default_factory=dict)
    completed_steps: list[dict[str, Any]] = field(default_factory=list)
    # Derived state
    worktree_path: str | None = None
    branch_name: str | None = None
    base_branch: str | None = None
    feature_name: str | None = None
    # modify-specific
    m1_results: dict[str, Any] | None = None
    adr_paths: dict[str, str | None] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PipelineSession:
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})


def create_session(
    pipeline: str, params: dict[str, Any], session_dir: Path
) -> PipelineSession:
    """Create a new session and persist it."""
    session = PipelineSession(
        session_id=uuid.uuid4().hex[:12],
        pipeline=pipeline,
        params=params,
    )
    save_session(session, session_dir)
    return session


def save_session(session: PipelineSession, session_dir: Path) -> None:
    """Persist session to disk."""
    session_dir.mkdir(parents=True, exist_ok=True)
    path = session_dir / f"{session.session_id}.json"
    path.write_text(json.dumps(session.to_dict(), ensure_ascii=False, indent=2))


def load_session(session_id: str, session_dir: Path) -> PipelineSession | None:
    """Load a session from disk. Returns None if not found."""
    path = session_dir / f"{session_id}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    return PipelineSession.from_dict(data)


def list_sessions(session_dir: Path) -> list[PipelineSession]:
    """List all active (running/paused) sessions."""
    if not session_dir.exists():
        return []
    sessions: list[PipelineSession] = []
    for path in session_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text())
            session = PipelineSession.from_dict(data)
            if session.status in ("running", "paused"):
                sessions.append(session)
        except (json.JSONDecodeError, KeyError):
            continue
    return sessions
