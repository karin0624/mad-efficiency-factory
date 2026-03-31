#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["langfuse>=4,<5"]
# ///
"""Langfuse trace collector for Claude Code hooks."""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
from typing import Any
import warnings

TRACE_NAME = "claude-code-session"
MAX_STRING_LENGTH = 500
MAX_LIST_ITEMS = 20
MAX_DICT_ITEMS = 50
MAX_TRACE_METADATA_LENGTH = 200


def main() -> None:
    if os.environ.get("TRACE_TO_LANGFUSE", "").lower() != "true":
        return

    raw = sys.stdin.read().strip()
    if not raw:
        return

    payload = json.loads(raw)
    event_name = str(payload.get("hook_event_name") or "")
    if event_name == "PostToolUse":
        _handle_post_tool_use(payload)
    elif event_name == "Stop":
        _handle_stop(payload)


def _handle_post_tool_use(payload: dict[str, Any]) -> None:
    from langfuse import Langfuse, propagate_attributes

    langfuse = Langfuse()
    session_id = _session_id(payload)
    tool_name = _ascii_text(payload.get("tool_name"), default="unknown-tool")

    with langfuse.start_as_current_observation(
        name=tool_name,
        as_type="tool",
        metadata=_tool_metadata(payload),
    ) as observation:
        with propagate_attributes(
            session_id=session_id,
            trace_name=TRACE_NAME,
            metadata=_trace_metadata(payload),
        ):
            observation.update(
                input=_summarize(payload.get("tool_input")),
                output=_summarize(payload.get("tool_response")),
            )

    langfuse.flush()


def _handle_stop(payload: dict[str, Any]) -> None:
    from langfuse import Langfuse, propagate_attributes

    langfuse = Langfuse()
    session_id = _session_id(payload)

    with langfuse.start_as_current_observation(
        name="session:stop",
        metadata=_stop_metadata(payload),
    ):
        with propagate_attributes(
            session_id=session_id,
            trace_name=TRACE_NAME,
            metadata=_trace_metadata(payload),
        ):
            langfuse.create_event(
                name="stop",
                input=_summarize(payload.get("last_assistant_message")),
                metadata={
                    "stop_hook_active": bool(payload.get("stop_hook_active", False)),
                },
            )

    langfuse.flush()


def _session_id(payload: dict[str, Any]) -> str:
    return _ascii_text(payload.get("session_id"), default="unknown-session")


def _tool_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "hook_event_name": payload.get("hook_event_name"),
        "tool_use_id": payload.get("tool_use_id"),
        "transcript_path": payload.get("transcript_path"),
        "cwd": payload.get("cwd"),
        "permission_mode": payload.get("permission_mode"),
    }


def _stop_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "hook_event_name": payload.get("hook_event_name"),
        "stop_hook_active": payload.get("stop_hook_active"),
        "transcript_path": payload.get("transcript_path"),
        "cwd": payload.get("cwd"),
        "permission_mode": payload.get("permission_mode"),
    }


def _trace_metadata(payload: dict[str, Any]) -> dict[str, str]:
    metadata = {
        "hook_event_name": payload.get("hook_event_name"),
        "permission_mode": payload.get("permission_mode"),
    }
    trace_metadata: dict[str, str] = {}
    for key, value in metadata.items():
        if value is None:
            continue
        trace_metadata[key] = _ascii_text(
            value,
            default="unknown",
            max_length=MAX_TRACE_METADATA_LENGTH,
        )
    return trace_metadata


def _ascii_text(value: Any, *, default: str, max_length: int = MAX_TRACE_METADATA_LENGTH) -> str:
    text = str(value) if value is not None else default
    ascii_text = text.encode("ascii", "backslashreplace").decode("ascii")
    if not ascii_text:
        return default
    return ascii_text[:max_length]


def _summarize(value: Any) -> Any:
    if isinstance(value, str):
        return _truncate(value)
    if isinstance(value, bytes):
        return _truncate(value.decode("utf-8", errors="replace"))
    if isinstance(value, dict):
        summarized: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= MAX_DICT_ITEMS:
                summarized["_truncated_keys"] = len(value) - MAX_DICT_ITEMS
                break
            summarized[str(key)] = _summarize(item)
        return summarized
    if isinstance(value, list):
        summarized_list = [_summarize(item) for item in value[:MAX_LIST_ITEMS]]
        if len(value) > MAX_LIST_ITEMS:
            summarized_list.append({"_truncated_items": len(value) - MAX_LIST_ITEMS})
        return summarized_list
    if isinstance(value, tuple):
        return _summarize(list(value))
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _truncate(repr(value))


def _truncate(text: str, max_length: int = MAX_STRING_LENGTH) -> str:
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


if __name__ == "__main__":
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            with contextlib.redirect_stderr(io.StringIO()):
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    main()
    except Exception:
        sys.exit(0)
