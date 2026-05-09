# DEMO RUNBOOK

## cursor-session-tracer — Live Demo Guide

**Talk:** When the Agent Drives, Who Holds the Wheel?
**Event:** Cursor Community Meetup Mumbai | May 2026
**Slot:** Minutes 8–16 (8 minutes live)

---

## Pre-Demo Setup (do this before the talk)

### 1. Start the MCP server

```bash
cd /path/to/cursor-session-tracer
bash run_server.sh
```

Server starts on `http://127.0.0.1:8080`. Leave this terminal open.

### 2. Verify the server is healthy

```bash
curl http://127.0.0.1:8080/health
# {"status":"ok","service":"cursor-session-tracer"}
```

### 3. Configure Cursor to use the MCP server

In Cursor → Settings → MCP Servers, add:

```json
{
  "cursor-session-tracer": {
    "url": "http://127.0.0.1:8080/mcp"
  }
}
```

### 4. Open the demo repo in Cursor

```bash
cursor /path/to/cursor-session-tracer/demo
```

### 5. Split the screen

- **Left pane:** Cursor agent chat
- **Right pane:** Terminal watching `.cursor/traces/` in real time

```bash
# Right pane — watch for new trace files
watch -n 1 "find .cursor/traces -name '*.json' | sort"
```

### 6. Confirm the Cursor rule is active

Open Cursor → Rules — you should see `session_trace.mdc` listed.

---

## Live Demo Script

### Step 1 — Set the scene

> "Here's the demo app — a small FastAPI service. It has GitHub and Stripe API clients
> both using an old `APIKeyAuth` pattern. I'm going to give the agent a real refactoring
> task and you'll watch the reasoning chain form in real time."

### Step 2 — Give the agent a task

Type in Cursor agent chat:

```text
Refactor all API clients in this codebase to use the new BearerTokenAuth
pattern from demo/auth.py instead of APIKeyAuth. Update demo/main.py,
demo/clients/github.py, and demo/clients/stripe.py. Make sure the
get_current_auth() function also returns the new auth type.
```

Point at the screen:
> "Watch the right pane — the agent is about to call `start_trace` before it touches
> anything. There's the session ID. There's the trace file appearing."

### Step 3 — Let the agent run

Let the agent work through 4–6 steps. While it runs, narrate what's happening:

- When `start_trace` fires:
  > "Session started. Session ID returned. Agent stores it — it'll pass it to every
  > subsequent tool call."

- When `append_trace` fires for the first decision:
  > "Before modifying `auth.py`, the agent logs why. Not what — why. That `reason`
  > field is the difference between a diff and a decision trail."

- When the parent chain starts forming:
  > "See `parent_step_id`? Step 003 points to step 002 which points to step 001.
  > That's a graph, not a list. The reasoning chain is directional."

### Step 4 — Render the trace

Open a new terminal tab (keep agent visible):

```bash
# Find your session date and ID from the trace file path
python render_trace.py --session 20260509/<SESSION_ID>
```

The tree prints to stdout. Walk through one decision:
> "Here's step 001 — the agent read `auth.py`, saw it was using `APIKeyAuth`, and
> decided the downstream clients all need updating because they import it directly.
> That's the reasoning chain. A reviewer gets this upfront instead of reverse-engineering
> it from the diff."

### Step 5 — End the session and show final trace

The agent will call `end_trace` when done. If not, prompt it:

```text
End the trace session with outcome "completed".
```

Then show the sessions endpoint:

```bash
curl http://127.0.0.1:8080/sessions | python3 -m json.tool
```

> "Every session is queryable. Outcome, event count, Cursor usage stats —
> model, token counts, cost — all in the trace."

### Step 6 — Optional: Mermaid output

```bash
python render_trace.py --session 20260509/<SESSION_ID> --mode mermaid
```

> "This goes straight into a PR as an attachment. The reviewer sees the decision flow
> before they open the diff."

---

## Fallback: If Cursor doesn't call the MCP tools automatically

Run the tools manually via the test script to show the data model:

```bash
# In the .venv shell
python3 - <<'EOF'
import sys; sys.path.insert(0, ".")
from src.mcp_server import start_trace, append_trace, end_trace

r0 = start_trace(
    task_description="Refactor API clients to use BearerTokenAuth",
    files_in_scope=["demo/auth.py", "demo/clients/github.py", "demo/clients/stripe.py"]
)
print("Started:", r0)

r1 = append_trace(
    session_id=r0["session_id"], type="decision",
    reason="demo/clients/github.py imports APIKeyAuth directly. Must update import and constructor call to use BearerTokenAuth.",
    files_read=["demo/clients/github.py"], files_modified=[], files_created=[], files_deleted=[],
    parent_step_id=""
)
print("Step 1:", r1)

r2 = append_trace(
    session_id=r0["session_id"], type="file_modify",
    reason="Replacing APIKeyAuth with BearerTokenAuth in GitHubClient.__init__. .headers property now returns Authorization: Bearer.",
    files_read=["demo/clients/github.py"], files_modified=["demo/clients/github.py"], files_created=[], files_deleted=[],
    parent_step_id=r1["step_id"]
)
print("Step 2:", r2)

r3 = end_trace(
    session_id=r0["session_id"], outcome="completed",
    model="claude-sonnet-4-5", tokens_in=8200, tokens_out=2100, cost_usd=0.0183
)
print("Ended:", r3)
EOF

# Then render it
python render_trace.py --session $(date +%Y%m%d)/<SESSION_ID_FROM_ABOVE>
```

---

## Key Lines to Say During the Demo

| Moment | What to say |
| --- | --- |
| `start_trace` fires | "Session open. Reasoning trail begins." |
| `append_trace` fires | "Decision logged. Not what — why." |
| Parent chain forms | "This is a graph, not a log. Directed. Queryable." |
| Tree renders | "This is what a senior engineer gets before opening the PR." |
| Cursor stats shown | "Model, tokens, cost — all in the trace. Agentic debt is now measurable." |
| End of demo | "JSON today. Neo4j at org scale. Same schema." |

---

## Troubleshooting

| Problem | Fix |
| --- | --- |
| Server not starting | `source .venv/bin/activate && uvicorn src.app:app --port 8080` |
| Cursor not calling tools | Check MCP server URL in Cursor settings. Verify `session_trace.mdc` rule is active. |
| Trace file not appearing | Check `.cursor/traces/` — date directory may differ from expected |
| `render_trace.py` not finding session | Run `find .cursor/traces -name "*.json"` and use the actual date/session_id |
| Port 8080 in use | Change port in `run_server.sh` and update Cursor MCP config accordingly |

---

## Post-Demo URLs to Show

- `http://127.0.0.1:8080/` — health
- `http://127.0.0.1:8080/sessions` — all sessions, JSON
- `http://127.0.0.1:8080/docs` — FastAPI auto-docs (Swagger UI)
- `.cursor/traces/<date>/<session_id>/*.json` — raw trace file
