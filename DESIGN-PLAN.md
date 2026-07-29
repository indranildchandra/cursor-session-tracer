# Cursor Session Tracer — Design Plan

## Plan vs. Path: pairing an implementation trace with the decision that authorised it

**Talk + Build Design Document**
Indranil Chandra

> This is the **current** design document. It supersedes the first edition (v1,
> *"When the Agent Drives, Who Holds the Wheel?"*, Cursor Community Meetup Mumbai,
> May 2026), which shipped the tracer alone. v2 adds the other half of the story —
> the **plan** — and the check that ties plan to path.

[Talk Deck](https://docs.google.com/presentation/d/1OHTfj5cgA0UYj3bDyaxZVCk4pLTQC_4x/view)

---

## 0. What changed since v1 (read this first)

v1 answered *"what did the agent actually do?"* with a real-time reasoning **trace**.
It was a good answer to half a question. v2 adds the missing half:

| | v1 (May 2026) | v2 (current) |
|---|---|---|
| **Trace** — the *path* | ✅ three MCP tools, real-time reasoning graph | ✅ unchanged, plus a link back to the plan (`adr_id`) |
| **Cursor usage stats** | self-reported at `end_trace` | **auto-captured** from Cursor's local SQLite DB |
| **Plan** — the *ADR* | ✗ none | ✅ produced by an **adversarial review council** (`/design-review`) |
| **Plan-vs-path check** | ✗ none | ✅ `audit_trace.py` flags **LLD drift** |
| **Skill packaging** | n/a | Cursor-native (`.cursor/commands`, `.cursor/review-council`) |
| **Demo** | auth refactor (`APIKeyAuth → BearerTokenAuth`) | **resilient, idempotent checkout** — a decision worth reviewing |

The through-line: a record is only trustworthy if it is a **byproduct of the work**,
not a separate artifact someone must remember to update. The trace is a byproduct of
implementation; the ADR is a byproduct of planning. Neither drifts.

---

## 1. Audience & framing

### 1.1 Setting

Internal PubMatic brownbag. Bimodal audience:

- **Senior leaders** — care about ROI, review cost, onboarding cost, audit-readiness,
  and governance of agent-driven work at scale.
- **On-floor engineers** — care about whether this slows them down, how it works, and
  whether it is ceremony or a byproduct of work they already do.

The talk must land for both: name the business "so what" for leaders, and pre-empt the
"this is process tax" reflex for engineers (the ADR + trace are byproducts, not extra steps).

### 1.2 The two named problems

1. **Agentic amnesia.** When an agent reads 20 files and rewrites 40 in one session,
   it leaves the output and nothing else — no reasoning, no PR narrative, no Slack
   thread. By the time something breaks 48 hours later, there is no reasoning trail.
2. **Documentation drift.** On long-lived brownfield projects, `docs/` is written once
   and never kept honest. This is structural, not a discipline failure: docs and code
   are two artifacts with no feedback loop between them.

Both have the same cure: make the record a **byproduct** of the work at the moment the
work happens.

### 1.3 HLD has ADRs; LLD had nothing

ADRs capture the *why* behind high-level structural choices — but they stop at the
system boundary. What happens **inside** a module, why a function was refactored, what
the agent decided mid-session — the LLD layer has had no equivalent of an ADR. The
**trace is that missing LLD record**, and `adr_id` ties it back to the HLD decision.

---

## 2. Talk design

### 2.1 Title and thesis

**Title:** Your Code and its Story — Told by Adversarial Review & Cursor Session Tracer
**Tagline:** *Docs drift, traces don't.*

**Thesis:** Every change has two truths — what you *planned* and what you *did*. Capture
the plan as an **ADR forged in adversarial review**, capture the path as a **real-time
trace**, and check one against the other automatically. Together they replace the
drifting `docs/` folder with two artifacts that move with the code, and they make the
"PR of the future" — code + plan + path — reviewable by a human or an agent.

### 2.2 The core insight

- **Git blame** tells you *what* changed. **The trace** tells you *why* the agent
  decided to change it, in what order, given what it had read.
- **An ADR** tells you *what you meant to do and why*. **The audit** tells you whether
  the path stayed faithful to that plan, or drifted.

Plan vs. path, intent vs. execution — permanently recorded, not reconstructed from git
blame months later.

### 2.3 Business framing (for the leaders in the room)

This is the missing layer between "AI wrote this" and "an engineer owns this."
Accountability does not disappear when the agent writes the code; it just gets harder to
assign. Teams that instrument now get an audit-ready, review-friendly, onboardable
codebase. Teams that don't accumulate **agentic debt** — code that works but that no one
can explain — and pay it back at incident time.

### 2.4 Honest limitations (name them yourself)

Credibility comes from naming the cost: adversarial review adds compute + latency;
traces add storage + noise; ADRs need maintenance when the plan changes mid-flight; and
small changes don't warrant either. The tool is for decisions a reviewer would want to
understand in three weeks — not every one-line edit.

---

## 3. Talk structure

Delivered **demo-first** (show it working, then explain) — the speaker manages timing
live; the outline below is content, not a stopwatch.

1. **Cold open — the confession.** "I built a tool to fight documentation drift. Its own
   README had drifted from its code. That's not a discipline failure — that's how
   structural this problem is." Disarms the room; proves the thesis in 20 seconds.
2. **The demo (shown first).** The naive checkout with the double-charge bug →
   `/design-review` produces an ADR with a real blocker and a converged concern →
   implement with the tracer running → `audit_trace.py` shows plan vs. path. (See §11.)
3. **The gap.** HLD has ADRs; LLD has had nothing. The trace is the missing LLD record.
   The four questions: git history / step debugger / unit test / **agentic trace**.
4. **Two artifacts, one system.** ADR = plan (adversarial review), trace = path
   (implementation), audit = the check. Code, ADR, and trace move together.
5. **The PR of the future.** A PR ships as code + ADR + trace. An independent
   reviewer — increasingly an agent — reasons about faithfulness-to-plan and flags LLD
   drift, instead of reverse-engineering intent from the diff.
6. **The systems punchline.** The trace is a graph; today it's JSON, tomorrow a
   ClickHouse/Neo4j store answering cross-session questions. We have 30 years of runtime
   observability and almost none for agent reasoning. This is a start on the gap.

---

## 4. System architecture — the plan-vs-path loop

```
  /design-review                start_trace(adr_id=…)              audit_trace.py
 ┌────────────────┐   ADR      ┌────────────────────┐  trace     ┌──────────────────┐
 │ adversarial     │ ────────▶ │ implement with the  │ ─────────▶ │ plan vs. path:    │
 │ review council  │  (plan)    │ tracer running      │  (path)    │ flag LLD drift    │
 │ .cursor/commands│            │ src/mcp_server.py    │            │ audit_trace.py    │
 └────────────────┘            └────────────────────┘            └──────────────────┘
        │                               │                                  │
        ▼                               ▼                                  ▼
 docs/adr/ADR-NNNN.md          .cursor/traces/…/*.json            FAITHFUL | DRIFT (exit 1)
 docs/design-review.md         (adr_id links back to the ADR)     → PR comment / CI gate
```

| Component | Path | Role |
|---|---|---|
| `review-council` | `.cursor/commands/design-review.md` + `.cursor/review-council/` | Adversarial review → **ADR** |
| MCP tracer | `src/mcp_server.py`, `src/app.py`, `src/cursor_db.py` | Real-time **trace** |
| Renderer | `render_trace.py` | Trace → terminal tree / Mermaid |
| Auditor | `audit_trace.py` | ADR scope vs. trace touches → **drift** |

---

## 5. Trace file schema

### 5.1 Directory structure

```text
.cursor/traces/
  20260729/
    dde097e6/
      092435_implement_adr0001_resilient_idempotent_outbound.json
```

Committed sample (ships in-repo; `.gitignore` whitelists `20260729/`). Runtime traces
land under `<YYYYMMDD>/<session_id>/` the same way.

- **Date directory:** `YYYYMMDD`, created at `start_trace` time.
- **Session directory:** `uuid4()[:8]`, returned to the agent, passed on every call.
- **Filename:** `HHMMSS_<slug>.json` — slug = first 5 words of `task_description`,
  lowercased, underscored, punctuation stripped.
- **Multiple files under one session_id:** a restart artifact; kept by design.

### 5.2 Session header block

Written once by `start_trace`. `adr_id` links the trace to the plan it implements
(`null` if none). `composer_id` and `model` are auto-detected from Cursor's local SQLite
DB at `start_trace` (both `null` if no live Cursor session). `ended_at`, `outcome`,
`tokens_in`, `tokens_out` fill in at `end_trace`. `tool_call_count` increments on every
`append_trace`.

```json
{
  "session": {
    "session_id": "dde097e6",
    "slug": "implement_adr0001_resilient_idempotent_outbound",
    "task": "Implement ADR-0001: resilient, idempotent outbound calls for the checkout flow",
    "adr_id": "ADR-0001",
    "started_at": "2026-07-29T09:24:35Z",
    "ended_at": "2026-07-29T09:25:38Z",
    "outcome": "completed",
    "repo_snapshot": [
      "demo/resilience.py",
      "demo/clients/stripe.py",
      "demo/clients/github.py",
      "demo/main.py"
    ],
    "cursor_stats": {
      "composer_id": "febc6fdd-2637-4d27-afb3-21180f498c63",
      "model": "composer-2.5",
      "tool_call_count": 6,
      "tokens_in": 0,
      "tokens_out": 0
    }
  },
  "events": []
}
```

### 5.3 Event object

```json
{
  "step_id": "step_003",
  "parent_step_id": "step_002",
  "type": "decision",
  "timestamp": "2026-07-29T09:25:38Z",
  "reason": "Route StripeClient.charge through transport with charge:{order_id} idempotency key so retried charges dedupe instead of double-charging.",
  "files_read": ["demo/clients/stripe.py"],
  "files_modified": ["demo/clients/stripe.py"],
  "files_created": [],
  "files_deleted": [],
  "notes": ""
}
```

Event types: `decision` · `file_read` · `file_modify` · `file_create` · `file_delete` ·
`tool_call` · `checkpoint`. If Cursor's model changes mid-session, `append_trace` adds a
`model_override` field to that event.

### 5.4 The graph shape

`parent_step_id` makes this graph-shaped even as flat JSON: every event points to what
caused it. Each event → a node; each `parent_step_id` → a directed edge; each file
reference → an edge to a file node. This is what makes the future ClickHouse/Neo4j store
(§12) a schema migration rather than a redesign.

---

## 6. MCP tool specifications

> Three tools only. More than three raises the chance of the agent picking the wrong one
> mid-session.

### 6.1 start_trace

```text
start_trace(task_description: str, files_in_scope: list[str], adr_id: str = "") -> dict
# -> {"session_id": "dde097e6", "trace_file_path": ".cursor/traces/.../….json"}
```

- Generates `session_id` (`uuid4()[:8]`) and the slug; creates the date + session dirs.
- Auto-detects `composer_id` + `model` from Cursor's DB.
- Records `adr_id` (the plan this session implements) when supplied.
- Writes the session header with `events: []`.

### 6.2 append_trace

```text
append_trace(session_id, type, reason, files_read, files_modified,
             files_created, files_deleted, parent_step_id, notes="") -> dict
# -> {"step_id": "step_003"}
```

- Resolves the trace path from `session_id`; assigns the next `step_id`.
- Appends the event; increments `tool_call_count`; logs a `model_override` if the model
  changed. Pass the returned `step_id` as `parent_step_id` next call (`""` for the root).

### 6.3 end_trace

```text
end_trace(session_id: str, outcome: str) -> dict
# -> {"trace_file_path": "...", "tokens_in": 15000, "tokens_out": 4200}
```

- Writes `ended_at` + `outcome` (`completed` | `partial` | `aborted`; else `ValueError`).
- Auto-reads token counts from Cursor's DB for this `composer_id` (assistant turns at/after
  `started_at`). Model/tokens are **not** parameters — reading Cursor's ground truth makes
  agentic debt measurable rather than self-reported.

### 6.4 cursor_db.py — usage auto-capture

`src/cursor_db.py` reads Cursor's local SQLite DB (`state.vscdb`) read-only:
`get_active_composer()` (id + model), `get_model_for_composer()` (mid-session switch
detection), `get_token_counts()` (input/output sums). The DB path resolves per platform
(macOS / Linux / Windows, override via `CURSOR_DB_PATH`); all three degrade gracefully to
`None` / zero when Cursor isn't present, so the trace stays valid off-Cursor.

---

## 7. Adversarial review → ADR (the plan)

### 7.1 review-council

A Cursor command, `/design-review` (`.cursor/commands/design-review.md`), runs a council
of 3–6 **independent expert personas** (`.cursor/review-council/standard-personas/`) that
review a scope in isolation, debate, and converge on a verdict, with the human as an
active participant. Every council must include at least one of `staff-engineer`,
`cloud-cost-architect`, `appsec-architect`.

Phases: scope + human brief → domain fingerprint → persona selection → independent review
→ debate → human input → synthesis → **record transcript** (`docs/design-review.md`) →
**distil ADR** (`docs/adr/`).

### 7.2 The ADR is formulated *through* the review

The transcript in `docs/design-review.md` is the *argument*; the **ADR is the distilled
decision**. Phase 8 copies `docs/adr/TEMPLATE.md` → `docs/adr/ADR-NNNN-<slug>.md` and
fills: Context, Decision, **Scope (files)** (a machine contract — see §8), Alternatives,
Consequences (trade-offs + council-flagged risks), and the Verdict. Only written when the
verdict is `Proceed as-is` or `Proceed with modifications`.

### 7.3 The link

Implementation passes the ADR id to the tracer: `start_trace(..., adr_id="ADR-0001")`.
The trace declares which plan it executes; `render_trace.py` shows it; `/sessions` carries
it; `audit_trace.py` uses it.

---

## 8. audit_trace.py — the plan-vs-path check

The deterministic "independent reviewer." It parses the ADR's `## Scope (files)` list,
gathers the files the trace actually touched, and reports:

- **Implemented in scope** — planned ∩ changed
- **Planned but not touched** — planned − changed
- **LLD drift** — changed − planned (files changed the ADR never scoped ← the key signal)
- **Reads outside scope** — informational, not drift

```bash
python audit_trace.py --session 20260729/dde097e6                 # human-readable FAITHFUL | DRIFT
python audit_trace.py --session 20260729/dde097e6 --json | jq .   # PR comment / CI gate (exit 1 on drift)
```

Exit code: `0` faithful, `1` drift — so it drops straight into a CI gate. This supplies
the ground-truth planned-vs-actual diff; an agentic reviewer can layer *semantic*
faithfulness judgement on top (§12).

---

## 9. Cursor integration

- **`.cursor/mcp.json`** — committed; auto-registers the tracer (`/mcp` streamable HTTP,
  Cursor 0.43+; `/sse` fallback for older).
- **`.cursor/rules/session_trace.mdc`** — tells the agent when to trace (any multi-file or
  architectural task) and to pass `adr_id` when an ADR exists.
- **`.cursor/commands/design-review.md`** — the `/design-review` command; personas in
  `.cursor/review-council/`.

**Install into another repo:** copy the `.cursor/` folder (`mcp.json`, `rules/`,
`commands/`, `review-council/`) and `docs/adr/TEMPLATE.md`, then point that repo's
`.cursor/mcp.json` at your running tracer.

---

## 10. Server & renderers

- **FastAPI server** (`src/app.py`) mounts FastMCP. Routes `/health`, `/sessions` (both
  carry `adr_id`), `/docs`; MCP at `/mcp` and `/sse`. App routes register **before**
  `app.mount("/", …)` because Starlette evaluates in registration order and `Mount("/")`
  is a catch-all.
- **Terminal renderer** (`render_trace.py`) — reconstructs the parent-child tree, shows the
  `implements: ADR-…` link, handles orphans (`[ORPHAN]`, never crashes). Flags:
  `--verbose`, `--files-only`, `--mode mermaid`, `--max-nodes N`.
- **Mermaid renderer** (`--mode mermaid`) — `flowchart TD` to `diagram.mermaid`, per-type
  node shapes, merges restart files, escapes labels. Primary value: PR attachment.

---

## 11. The demo scenario

A naive **checkout service** (`demo/`) with a deliberate, dangerous flaw. `POST /checkout`
charges via Stripe then writes a receipt via GitHub, every call unguarded:

- **Not idempotent** — retry a timed-out checkout and the customer is **charged twice**.
- **No retry/backoff** — a transient 5xx surfaces as a hard failure.
- **No circuit breaker** — a Stripe outage cascades.

That's a decision worth reviewing, not just coding. The demo walks the full loop:

1. **Plan** — `/design-review` on the checkout flow (or `glow docs/design-review.md` for
   the pre-baked transcript). The council surfaces a **blocker** (retries before idempotency
   = automatic double-charge) and a **converged concern** (backoff without jitter + no
   breaker = retry storm). → `docs/adr/ADR-0001-resilient-idempotent-checkout.md`.
2. **Path** — implement with `start_trace(..., adr_id="ADR-0001")`; `watch` trace files in
   a second terminal (`watch -n 1 "find .cursor/traces -name '*.json' | sort"`).
3. **Check** — `audit_trace.py` confirms scope faithfulness; `--json | jq .` for CI-shaped
   output.
4. **Prove** — post `/checkout` dedupe test shows the double-charge bug is closed.

Presenter copy-paste commands, terminal layout, and screenshot references:
**[DEMO-RUNBOOK.md](DEMO-RUNBOOK.md)** (includes a Quick reference appendix).
**[demo_screenshots/](demo_screenshots/)** — captures from a live run (linked in README).

`tests/test_demo.py` is a **canary**: it asserts the naive starting state and fails loudly
if `demo/` is accidentally left in the post-implementation state before a talk. A committed
sample trace (`.cursor/traces/20260729/dde097e6/`) renders and audits **FAITHFUL** out of
the box against ADR-0001.

---

## 12. Roadmap / future scope

Framed for a newcomer: here is where the project is and where it goes next.

- **Pluggable graph/analytics trace store (the next logical step).** The schema is
  deliberately graph-shaped (§5.4). A `TraceStore` interface with a flat-file default and
  pluggable backends lets traces flow into **Neo4j** (reasoning-graph queries:
  `(Step)-[:CAUSED]->(Step)`, `(Step)-[:TOUCHED]->(File)`; "which decision patterns precede
  prod failures") or **ClickHouse** (columnar analytics across thousands of sessions:
  agentic-debt trends, drift rates per team). **This is the highest-value contribution
  area** — open an issue to coordinate.
- **Per-session cost capture.** Cursor's DB gives token counts but not dollar cost; deriving
  `cost_usd` needs a maintained `model → price` map. Dropped for now to avoid a stale price
  table — contributions welcome to add an opt-in pricing map.
- **CI integration.** Wire `audit_trace.py --json` into a PR check that comments the
  plan-vs-path report and gates on LLD drift.
- **Agentic reviewer.** `audit_trace.py` supplies the ground-truth file diff; layer an agent
  that judges *semantic* faithfulness — did the change honor the ADR's intent, not just its
  file list.
- **Agentic debt as a metric.** Once traces accumulate: sessions with orphaned decisions,
  skipped checkpoints, or out-of-scope touches are leading indicators of maintenance cost.

---

## 13. Setup & tooling

- **Python 3.12** (reference: `/Library/Frameworks/Python.framework/Versions/3.12/bin/python3`
  on macOS). Validated on 3.12.3.
- **Makefile:** `make setup` (venv + deps + demo CLI tools via Homebrew: `glow`, `watch`,
  `jq`), `make test`, `make server`, `make audit SESSION=…`, `make setup-tools` (CLI tools
  only). macOS override: `make setup PYTHON=/Library/Frameworks/Python.framework/Versions/3.12/bin/python3`.
- **Demo presentation:** `curl … | jq .` for JSON; `glow` for ADR / design-review markdown;
  `watch` for live trace panes during implementation.
- **Dependencies** pinned in `requirements.txt`; `make setup` builds an isolated `.venv`.
- **Tests** (`pytest`, Python 3.12) cover file utils, all three MCP tools (incl. `adr_id`),
  the cross-platform Cursor-DB reader, both renderers, the plan-vs-path audit, and the demo
  canary.
- **Docs map:** [README.md](README.md) (overview) · [DEMO-RUNBOOK.md](DEMO-RUNBOOK.md)
  (presenter commands) · [CONTRIBUTING.md](CONTRIBUTING.md) (PR guide) ·
  [docs/adr/README.md](docs/adr/README.md) (ADR model).
