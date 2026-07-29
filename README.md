# cursor-session-tracer

**Agentic observability for Cursor.** When an agent restructures your codebase in a single session, git blame tells you *what* changed. This tells you **why** — a queryable, real-time reasoning trace of every decision, file touch, and reasoning chain, so you can debug a prod regression or review a PR by walking the trace instead of staring at the diff.

<p>
  <img alt="Python 3.12+" src="https://img.shields.io/badge/python-3.12+-blue.svg">
  <img alt="MCP" src="https://img.shields.io/badge/protocol-MCP-8A2BE2.svg">
  <img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-green.svg">
  <img alt="Tests: pytest" src="https://img.shields.io/badge/tests-pytest-0A9EDC.svg">
</p>

> **Docs drift. Traces don't.**
> A trace is a byproduct of the work, not a separate artefact someone has to remember to update. Pair it with an **ADR** — the decision-of-record produced by an [adversarial review](.cursor/commands/design-review.md) *before* implementation — and you get **plan vs. path**: what was decided and why, next to what actually happened, with [`audit_trace.py`](audit_trace.py) checking one stayed faithful to the other.

---

## Table of contents

- [Why](#why)
- [The two-artefact model: plan vs. path](#the-two-artefact-model-plan-vs-path)
- [Quickstart](#quickstart)
- [How the tracer works](#how-the-tracer-works)
- [Wire it into Cursor](#wire-it-into-cursor)
- [The live demo](#the-live-demo)
- [Rendering & auditing traces](#rendering--auditing-traces)
- [Testing](#testing)
- [Roadmap / future scope](#roadmap--future-scope)
- [Project structure](#project-structure)
- [Contributing](#contributing)
- [License](#license)

---

## Why

Agentic coding is a new execution model, and it broke an assumption: that the person who wrote the code can explain it. When an agent reads 20 files and rewrites 40 in one session, it leaves the output and nothing else — no PR description written along the way, no Slack thread, no reasoning. We call this **agentic amnesia**. Forty-eight hours later, when something breaks, git bisect points you at the agentic commit and the diff is a wall of noise.

The existing tools answer different questions:

| Tool | Answers |
| --- | --- |
| Git history | *What* changed, when, by whom |
| Step debugger | What is executing *right now* |
| Unit test failure | Which assertion broke, on which input |
| **Agentic session trace** | **Why** did the agent make *this* decision, given what it had read, at that point in the session |

The fourth question is new. This project is a working answer to it.

---

## The two-artefact model: plan vs. path

On long-lived brownfield projects the `docs/` folder is written once and never kept honest — the code moves on, the docs don't. The fix isn't more discipline; it's making the record a **byproduct of the work** at two moments:

| Artefact | Produced | By | Answers | Lives in |
| --- | --- | --- | --- | --- |
| **ADR** — the *plan* | *before* implementation | [`review-council`](.cursor/commands/design-review.md): an adversarial review by 3–6 expert personas | *What did we decide, and why?* | [`docs/adr/`](docs/adr/) |
| **Trace** — the *path* | *during* implementation | the three MCP tools below | *What did the agent actually do?* | `.cursor/traces/` |

HLD already has a home for its "why" — the ADR. The **LLD layer has had none**: what happened inside a module, why a function was refactored, what the agent decided mid-session. The trace is that missing LLD record, and `adr_id` ties it back to the plan. The loop:

```
  /design-review            start_trace(adr_id=…)          audit_trace.py
 ┌──────────────┐  ADR    ┌──────────────────┐  trace   ┌──────────────────┐
 │ adversarial   │ ─────▶ │ implement with    │ ───────▶ │ plan vs. path:    │
 │ review council│  plan   │ the tracer running │  path    │ flag LLD drift    │
 └──────────────┘         └──────────────────┘          └──────────────────┘
```

A PR then ships as **code + ADR + trace** — and the reviewer, human or agent, gets the full context instead of reverse-engineering intent from the diff. See [`docs/adr/README.md`](docs/adr/README.md) for the full model.

---

## Quickstart

Requires **Python 3.12**.

```bash
git clone https://github.com/indranildchandra/cursor-session-tracer
cd cursor-session-tracer

make setup          # creates .venv (Python 3.12) and installs deps
make test           # run the suite
make server         # start the MCP + FastAPI server on http://127.0.0.1:8080
```

On macOS, if `python3.12` isn't on your `PATH`, point `make` at the framework build:

```bash
make setup PYTHON=/Library/Frameworks/Python.framework/Versions/3.12/bin/python3
```

<details>
<summary>Prefer raw commands (no <code>make</code>)?</summary>

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest tests/ -q
uvicorn src.app:app --host 127.0.0.1 --port 8080 --reload
```
</details>

Health check: `curl http://127.0.0.1:8080/health` → `{"status":"ok","service":"cursor-session-tracer"}`

---

## How the tracer works

Three MCP tools integrate into Cursor's agentic loop, served by FastMCP mounted on FastAPI:

| Tool | The agent calls it… | What it does |
| --- | --- | --- |
| `start_trace(task, files_in_scope, adr_id="")` | at the start of a multi-file task | creates the trace file, returns a `session_id`; auto-detects model + Cursor session from the local DB; links the ADR if given |
| `append_trace(session_id, type, reason, files_*, parent_step_id)` | before each significant decision | appends an event; auto-increments `tool_call_count`; logs mid-session model switches |
| `end_trace(session_id, outcome)` | when the task completes or stops | writes `ended_at`, `outcome`, and token counts read from Cursor's DB |

Every event carries a `parent_step_id`. That's what makes the trace a **graph, not a log** — the reasoning chain is directional and queryable.

**Cursor usage stats are captured automatically** (no self-reporting): [`src/cursor_db.py`](src/cursor_db.py) reads Cursor's local SQLite DB (`state.vscdb`, resolved per-OS) to populate `composer_id`, `model`, per-event model switches, and `tokens_in` / `tokens_out`. If Cursor isn't installed or the DB is absent, these degrade gracefully to `null` and the trace stays valid.

<details>
<summary>Trace file schema</summary>

Stored at `.cursor/traces/<YYYYMMDD>/<session_id>/<HHMMSS>_<slug>.json`:

```json
{
  "session": {
    "session_id": "a1b2c3d4",
    "slug": "resilient_idempotent_checkout",
    "task": "Make the checkout flow resilient and idempotent",
    "adr_id": "ADR-0001",
    "started_at": "2026-05-09T14:32:01Z",
    "ended_at": "2026-05-09T15:14:32Z",
    "outcome": "completed",
    "repo_snapshot": ["demo/resilience.py", "demo/clients/stripe.py"],
    "cursor_stats": {
      "composer_id": "b7f3c1a0-…",
      "model": "claude-sonnet-4-5",
      "tool_call_count": 6,
      "tokens_in": 15000,
      "tokens_out": 4200
    }
  },
  "events": [
    {
      "step_id": "step_003",
      "parent_step_id": "step_002",
      "type": "decision",
      "timestamp": "2026-05-09T14:33:45Z",
      "reason": "charge() has no idempotency key; a retry double-charges. Route it through the transport.",
      "files_read": ["demo/clients/stripe.py"],
      "files_modified": ["demo/clients/stripe.py"],
      "files_created": [],
      "files_deleted": [],
      "notes": ""
    }
  ]
}
```

Event types: `decision` · `file_read` · `file_modify` · `file_create` · `file_delete` · `tool_call` · `checkpoint`.
</details>

---

## Wire it into Cursor

**1. MCP server.** `.cursor/mcp.json` is committed, so Cursor auto-registers the tracer when you open the project:

```json
{ "mcpServers": { "cursor-session-tracer": { "url": "http://127.0.0.1:8080/mcp" } } }
```
> Cursor 0.43+. Older versions: use `"url": "http://127.0.0.1:8080/sse"`.

**2. Tracing rule.** `.cursor/rules/session_trace.mdc` tells the agent when to call the tools (any multi-file or architectural task). It's active automatically.

**3. Adversarial review command.** `.cursor/commands/design-review.md` is the `/design-review` command; the expert personas live in `.cursor/review-council/`. Type `/design-review` in the agent chat to run the council and produce an ADR. See [`.cursor/review-council/README.md`](.cursor/review-council/README.md).

**Installing into another repo:** copy `.cursor/` (the `mcp.json`, `rules/`, `commands/`, and `review-council/` folders) and `docs/adr/TEMPLATE.md` into the target project, and point its `.cursor/mcp.json` at your running tracer.

---

## The live demo

The bundled `demo/` app is a **naive checkout service** with a deliberate, dangerous flaw: `POST /checkout` charges via Stripe then writes a receipt via GitHub, with every call unguarded. It is **not idempotent** — retry a timed-out checkout and the customer is **charged twice**. There's no retry/backoff and no circuit breaker.

That's a decision worth reviewing, not just coding. The demo walks the full loop:

1. **Plan** — run `/design-review` on the checkout flow. The council (staff-engineer, appsec-architect, cloud-cost-architect, …) debates and converges: retries are unsafe before idempotency (a **blocker**), and backoff without jitter + a breaker causes a retry storm (a **converged concern**). It distils [**ADR-0001**](docs/adr/ADR-0001-resilient-idempotent-checkout.md) — full transcript in [`docs/design-review.md`](docs/design-review.md).
2. **Path** — implement it in Cursor with the tracer running: `start_trace(..., adr_id="ADR-0001")`. Watch the trace populate in real time.
3. **Check** — `audit_trace.py` verifies the implementation stayed inside the ADR's declared scope.

Full step-by-step with the exact commands: **[DEMO-RUNBOOK.md](DEMO-RUNBOOK.md)**.

---

## Rendering & auditing traces

**Render a trace** as a terminal tree or a Mermaid diagram (PR-attachment ready):

```bash
python render_trace.py --session 20260509/a1b2c3d4                 # terminal tree
python render_trace.py --session 20260509/a1b2c3d4 --verbose       # full reason text
python render_trace.py --session 20260509/a1b2c3d4 --files-only    # file touches only
python render_trace.py --session 20260509/a1b2c3d4 --mode mermaid  # → diagram.mermaid
```

**Audit plan vs. path** — the deterministic "independent reviewer". It reads the ADR's `Scope (files)` and diffs it against what the trace actually touched, flagging **LLD drift** (files changed but never planned):

```bash
python audit_trace.py --session 20260509/a1b2c3d4          # resolves the ADR from the trace's adr_id
python audit_trace.py --session 20260509/a1b2c3d4 --json   # PR-comment / CI gate (exit 1 on drift)
# or: make audit SESSION=20260509/a1b2c3d4
```

```text
──────────────── Plan vs. Path — DRIFT DETECTED ────────────────
✓ Implemented in scope (1/4):  demo/resilience.py
○ Planned but not touched (3): demo/clients/github.py, demo/clients/stripe.py, demo/main.py
✗ LLD DRIFT — changed but not in the ADR (1):
    demo/auth.py  ← reviewer should ask why
```

---

## Testing

```bash
make test        # or: .venv/bin/python -m pytest tests/ -q
```

Validated on **Python 3.12**. Coverage spans the file utilities, all three MCP tools (incl. `adr_id` linking), the cross-platform Cursor-DB reader, both renderers, the plan-vs-path audit, and a canary suite over the demo's starting state (`tests/test_demo.py` fails loudly if `demo/` is accidentally left in the post-implementation state before a talk).

---

## Roadmap / future scope

**Where this is today:** a working, local, single-developer system. The trace, the ADR
pipeline (`/design-review`), and the plan-vs-path audit all run on your machine against a
flat-file trace store — no server infrastructure, no account, no external dependencies.
That's deliberate: it has to work in one repo on one laptop before it works at org scale.

**Where it goes next** is turning that single-developer loop into a team-scale one — a
shared trace store you can query across sessions, and a CI gate that enforces plan-vs-path
on every PR. Those are the items below, and they're where contributions go furthest:

- **Pluggable graph/analytics trace store (the next logical step).** The JSON schema is deliberately graph-shaped: every event is a node, `parent_step_id` is a directed edge, each file reference is an edge to a file node. The natural evolution is a **pluggable backend** so traces flow into:
  - **Neo4j** — reasoning-graph queries: `(Step)-[:CAUSED]->(Step)`, `(Step)-[:TOUCHED]->(File)`; "which decision patterns precede prod failures", "which files do agents touch most across sessions".
  - **ClickHouse** — columnar analytics across thousands of sessions: agentic-debt trends, token/latency distributions, drift rates per team.

  We'd love contributions here — a `TraceStore` interface with a flat-file default and Neo4j / ClickHouse implementations. Open an issue to coordinate.
- **Per-session cost capture.** Cursor's local DB gives token counts but not dollar cost; deriving `cost_usd` needs a maintained `model → price` map (and per-provider nuances). Dropped for now to avoid a stale price table — **contributions welcome** to add an opt-in pricing map so `cursor_stats` can carry cost.
- **CI integration.** Wire `audit_trace.py --json` into a PR check that comments the plan-vs-path report and gates on LLD drift.
- **Agentic reviewer.** The audit tool supplies the ground-truth planned-vs-actual diff; layer an agent on top to judge *semantic* faithfulness (did the change honour the ADR's intent, not just its file list).

---

## Project structure

```text
cursor-session-tracer/
├── src/
│   ├── file_utils.py            # slug gen, path resolver, JSON read/write
│   ├── cursor_db.py             # reads Cursor's SQLite (state.vscdb), cross-platform
│   ├── mcp_server.py            # FastMCP — start_trace, append_trace, end_trace
│   └── app.py                   # FastAPI app, mounts MCP, exposes /sessions
├── render_trace.py              # terminal tree + Mermaid renderer
├── audit_trace.py               # plan-vs-path: audit a trace against its ADR's scope
├── demo/                        # NAIVE checkout service — the live-demo target
│   ├── auth.py                  # BearerTokenAuth (auth is already solved)
│   ├── main.py                  # POST /checkout — not idempotent (double-charge bug)
│   └── clients/{stripe,github}.py  # unguarded outbound calls
├── docs/
│   ├── adr/                     # Architecture Decision Records — the PLAN half
│   │   ├── README.md            # the plan-vs-path model
│   │   ├── TEMPLATE.md          # ADR template (machine-readable Scope section)
│   │   └── ADR-0001-resilient-idempotent-checkout.md
│   └── design-review.md         # full adversarial-review transcript (ADR-0001's lineage)
├── .cursor/
│   ├── mcp.json                 # Cursor MCP registration (auto-loaded)
│   ├── rules/session_trace.mdc  # rule — tells the agent when to trace
│   ├── commands/design-review.md# the /design-review command
│   ├── review-council/          # adversarial-review personas + protocol
│   └── traces/                  # trace files, written at runtime
├── tests/                       # pytest suite (Python 3.12)
├── Makefile                     # setup / test / server / audit
├── DEMO-RUNBOOK.md              # step-by-step live-demo guide
└── requirements.txt
```

---

## Contributing

Issues and PRs welcome — see [Roadmap](#roadmap--future-scope) for where help goes furthest. Please run `make test` before opening a PR. If your change is architectural, dogfood the tool: run `/design-review` to produce an ADR, implement with the tracer running, and attach the trace + `audit_trace.py` output to your PR.

## License

[MIT](LICENSE) © Indranil Chandra
