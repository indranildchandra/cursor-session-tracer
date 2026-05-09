"""
FastAPI application that mounts the MCP server.

Endpoints:
  GET  /         - health check
  GET  /health   - health check (alias)
  GET  /sessions - list all recorded trace sessions
  *    /mcp      - MCP streamable HTTP transport (Cursor 0.43+, recommended)
  GET  /sse      - MCP SSE transport (fallback for older Cursor)
  POST /messages - MCP SSE message handler

Cursor MCP config (.cursor/mcp.json):
  { "mcpServers": { "cursor-session-tracer": { "url": "http://127.0.0.1:8080/mcp" } } }

IMPORTANT: Routes must be registered BEFORE app.mount("/", ...) because
Starlette evaluates routes in registration order and Mount("/") is a catch-all.
"""

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from src.mcp_server import mcp

app = FastAPI(
    title="Cursor Session Tracer",
    description="Agentic observability layer for Cursor — traces agent reasoning chains.",
    version="1.0.0",
)


# ---------------------------------------------------------------------------
# Application routes — registered FIRST so Mount("/") doesn't shadow them
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
@app.get("/health")
async def health():
    return {"status": "ok", "service": "cursor-session-tracer"}


@app.get("/sessions")
async def list_sessions():
    """List all recorded trace sessions."""
    traces_root = Path(".cursor/traces")
    sessions = []

    for json_file in sorted(traces_root.glob("*/*/*.json"), reverse=True):
        try:
            with open(json_file, "r") as f:
                data = json.load(f)
            sess = data.get("session", {})
            sessions.append(
                {
                    "session_id": sess.get("session_id"),
                    "slug": sess.get("slug"),
                    "task": sess.get("task"),
                    "started_at": sess.get("started_at"),
                    "ended_at": sess.get("ended_at"),
                    "outcome": sess.get("outcome"),
                    "event_count": len(data.get("events", [])),
                    "cursor_stats": sess.get("cursor_stats"),
                    "file": str(json_file),
                }
            )
        except Exception:
            continue

    return JSONResponse({"sessions": sessions, "total": len(sessions)})


# ---------------------------------------------------------------------------
# MCP transports — mounted LAST so the routes above take priority
# /mcp  streamable HTTP  (Cursor 0.43+, recommended)
# /     SSE transport    (fallback; exposes /sse and /messages/)
# ---------------------------------------------------------------------------

app.mount("/mcp", mcp.streamable_http_app())
app.mount("/", mcp.sse_app())
