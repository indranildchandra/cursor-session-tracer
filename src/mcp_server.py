"""
MCP server for cursor-session-tracer.

Three tools: start_trace, append_trace, end_trace.
Served via FastMCP mounted onto a FastAPI app (streamable HTTP transport).

Cursor usage stats are captured automatically per session:
  - model: read from Cursor's local SQLite DB at session start
  - tool_call_count: incremented on every append_trace call
  - tokens_in / tokens_out: summed from Cursor's SQLite DB at end_trace
  - model per event: re-read at each append_trace; logged when it differs from session model
"""

from mcp.server.fastmcp import FastMCP

from src.cursor_db import get_active_composer, get_model_for_composer, get_token_counts
from src.file_utils import (
    build_trace_path,
    generate_session_id,
    generate_slug,
    get_date_dir,
    get_time_prefix,
    next_step_id,
    now_iso,
    read_trace,
    resolve_trace_path,
    write_trace,
)

mcp = FastMCP(
    name="cursor-session-tracer",
    instructions=(
        "Agentic session tracing tool. Call start_trace at the beginning of any "
        "multi-file task, append_trace before each significant decision, and end_trace "
        "when the task is complete. Pass the session_id returned by start_trace to every "
        "subsequent call. Pass the step_id from each append_trace as parent_step_id in "
        "the next call to build the reasoning chain."
    ),
    stateless_http=True,
)


@mcp.tool(
    description=(
        "Start a new agentic session trace. Call this at the beginning of any task "
        "touching more than 2 files or involving architectural changes. "
        "Store the returned session_id — you need it for every subsequent call. "
        "Model name and Cursor session ID are captured automatically from Cursor's local DB. "
        "If this work implements a decision recorded in an ADR (Architecture Decision "
        "Record produced by the review-council / adversarial review), pass its adr_id so "
        "the trace (what you did) links back to the ADR (what was planned)."
    )
)
def start_trace(task_description: str, files_in_scope: list[str], adr_id: str = "") -> dict:
    """
    Creates the trace file and writes the session header.
    Model and composer_id are auto-detected from Cursor's SQLite DB.

    Args:
        task_description: Full description of the task being performed.
        files_in_scope: List of files expected to be touched in this session.
        adr_id: Optional ID of the ADR this session implements (e.g. "ADR-0001").
                Links the implementation trace back to the planning artifact.

    Returns:
        {"session_id": str, "trace_file_path": str}
    """
    session_id = generate_session_id()
    slug = generate_slug(task_description)
    date_dir = get_date_dir()
    time_prefix = get_time_prefix()
    trace_path = build_trace_path(date_dir, session_id, slug, time_prefix)

    # Auto-detect model and Cursor composer session from local SQLite DB
    composer = get_active_composer()
    composer_id = composer["composer_id"] if composer else None
    model = composer["model"] if composer else None

    started_at = now_iso()

    data = {
        "session": {
            "session_id": session_id,
            "slug": slug,
            "task": task_description,
            "adr_id": adr_id or None,
            "started_at": started_at,
            "ended_at": None,
            "outcome": None,
            "repo_snapshot": files_in_scope,
            "cursor_stats": {
                "composer_id": composer_id,
                "model": model,
                "tool_call_count": 0,
                "tokens_in": None,
                "tokens_out": None,
            },
        },
        "events": [],
    }

    write_trace(trace_path, data)

    return {
        "session_id": session_id,
        "trace_file_path": str(trace_path),
    }


@mcp.tool(
    description=(
        "Append a decision or action event to the current session trace. "
        "Call this before each significant decision — reading a file to understand "
        "structure, choosing an implementation approach, modifying a file that other "
        "files depend on. The reason field must be specific, not generic. "
        "Pass the returned step_id as parent_step_id in your next call. "
        "Model is auto-detected per event; mid-session model switches are logged automatically."
    )
)
def append_trace(
    session_id: str,
    type: str,
    reason: str,
    files_read: list[str],
    files_modified: list[str],
    files_created: list[str],
    files_deleted: list[str],
    parent_step_id: str,
    notes: str = "",
) -> dict:
    """
    Appends one event to the session trace.

    Args:
        session_id: Returned by start_trace.
        type: One of decision, file_read, file_modify, file_create, file_delete,
              tool_call, checkpoint.
        reason: Why the agent made this decision. Must be specific.
        files_read: Files read during this step.
        files_modified: Files modified during this step.
        files_created: Files created during this step.
        files_deleted: Files deleted during this step.
        parent_step_id: step_id from the previous append_trace call (or "" for root).
        notes: Optional extra notes.

    Returns:
        {"step_id": str}
    """
    trace_path = resolve_trace_path(session_id)
    data = read_trace(trace_path)

    step_id = next_step_id(data["events"])

    # Auto-detect model for this event; flag if it differs from session-start model
    composer_id = data["session"]["cursor_stats"].get("composer_id")
    session_model = data["session"]["cursor_stats"].get("model")
    event_model = get_model_for_composer(composer_id) if composer_id else None

    event = {
        "step_id": step_id,
        "parent_step_id": parent_step_id or None,
        "type": type,
        "timestamp": now_iso(),
        "reason": reason,
        "files_read": files_read,
        "files_modified": files_modified,
        "files_created": files_created,
        "files_deleted": files_deleted,
        "notes": notes,
    }

    # Only add model to event when it differs from session model (mid-session switch)
    if event_model and event_model != session_model:
        event["model_override"] = event_model

    data["events"].append(event)

    # auto-increment tool_call_count in cursor_stats
    data["session"]["cursor_stats"]["tool_call_count"] = len(data["events"])

    write_trace(trace_path, data)

    return {"step_id": step_id}


@mcp.tool(
    description=(
        "End the session trace. Call this when the task is complete or you are stopping. "
        "Outcome must be one of: completed, partial, aborted. "
        "Token counts and model are captured automatically from Cursor's local DB — "
        "you do not need to pass them."
    )
)
def end_trace(
    session_id: str,
    outcome: str,
) -> dict:
    """
    Finalises the session trace. Token counts are auto-read from Cursor's SQLite DB.

    Args:
        session_id: Returned by start_trace.
        outcome: One of completed, partial, aborted.

    Returns:
        {"trace_file_path": str, "tokens_in": int, "tokens_out": int}
    """
    valid_outcomes = {"completed", "partial", "aborted"}
    if outcome not in valid_outcomes:
        raise ValueError(f"outcome must be one of {valid_outcomes}, got {outcome!r}")

    trace_path = resolve_trace_path(session_id)
    data = read_trace(trace_path)

    data["session"]["ended_at"] = now_iso()
    data["session"]["outcome"] = outcome

    # Auto-compute token counts from Cursor's DB for this session window
    stats = data["session"]["cursor_stats"]
    composer_id = stats.get("composer_id")
    started_at = data["session"]["started_at"]

    if composer_id:
        counts = get_token_counts(composer_id, started_at)
        stats["tokens_in"] = counts["tokens_in"]
        stats["tokens_out"] = counts["tokens_out"]

    write_trace(trace_path, data)

    return {
        "trace_file_path": str(trace_path),
        "tokens_in": stats.get("tokens_in"),
        "tokens_out": stats.get("tokens_out"),
    }
