# DEMO RUNBOOK

## cursor-session-tracer — live demo guide

**Talk:** Your Code and its Story — Told by Adversarial Review & Cursor Session Tracer
**Thesis:** Docs drift, traces don't. Plan (ADR) vs. path (trace), with a drift check between them.

The demo walks one loop on a deliberately broken app: **adversarial review → ADR → implement with tracing → audit plan vs. path.**

**Terminal layout:** you need three terminals — (1) `make server`, (2) `watch …` during implementation, (3) everything else (curl, glow, render, audit, python).

---

## 0. Pre-demo setup (do this before you present)

### Environment (Python 3.12)

```bash
git clone https://github.com/indranildchandra/cursor-session-tracer
cd cursor-session-tracer
make setup        # macOS: make setup PYTHON=/Library/Frameworks/Python.framework/Versions/3.12/bin/python3
                  # also installs demo CLI tools via Homebrew: glow, watch, jq
make test         # expect all green
source .venv/bin/activate   # optional — or use .venv/bin/python throughout
```

### Start the tracer server

```bash
make server       # http://127.0.0.1:8080  — leave this terminal running
# verify:
curl http://127.0.0.1:8080/health | jq .
curl http://127.0.0.1:8080/sessions | jq .
```

### Point Cursor at the server

`.cursor/mcp.json` is already committed, so opening this repo in Cursor auto-registers the tracer. Confirm under **Cursor → Settings → MCP** that `cursor-session-tracer` shows **connected**. (If not, add `{"cursor-session-tracer": {"url": "http://127.0.0.1:8080/mcp"}}`.)

### Confirm the Cursor rule + command are installed

Both live in `.cursor/` and load automatically when the repo is open:

- **Rule:** `.cursor/rules/session_trace.mdc` → appears under **Cursor → Rules**.
- **Command (Cursor 1.6+):** `.cursor/commands/design-review.md` → type `/` in the agent chat and confirm **`design-review`** appears (Cursor auto-discovers any `.md` in `.cursor/commands/`). Its personas are in `.cursor/review-council/`. If `/design-review` doesn't appear, check **Cursor → Settings** that you're on 1.6+.

> Installing into another repo: copy the whole `.cursor/` folder (`mcp.json`, `rules/`, `commands/`, `review-council/`) and `docs/adr/TEMPLATE.md` into the target project, then point that repo's `.cursor/mcp.json` at your running tracer.

### Split the screen

- **Left:** Cursor agent chat.
- **Right:** a terminal watching traces appear:

```bash
watch -n 1 "find .cursor/traces -name '*.json' | sort"
```

---

## 1. Set the premise — the broken app

> "This is a checkout service. `POST /checkout` charges the customer, then writes a receipt. Every call is made directly — no idempotency, no retries, no circuit breaker."

Show the bug is real, not hypothetical:

```bash
.venv/bin/python - <<'EOF'
from demo.clients.stripe import StripeClient
sc = StripeClient()
sc.charge("cus_1", 5000)          # first attempt
sc.charge("cus_1", 5000)          # a retry of the same order
print("charges recorded:", len(sc.charges), "→ the customer was charged twice")
EOF
```

> "A timed-out checkout that the client retries double-charges the customer. That's not a lint nit — that's money. This is a decision worth reviewing, not just coding."

---

## 2. Plan — run the adversarial review

**Option A — run it live.** In the Cursor agent chat:

```
/design-review the checkout flow in demo/ — Stripe charge + GitHub receipt, currently unguarded
```

Narrate as the council forms: independent personas (staff-engineer, appsec-architect, cloud-cost-architect, …) review in isolation, then debate. Land on the two outcomes that matter:

> "Two things the council caught that a single reviewer might not. One — a **blocker**: you cannot add retries before idempotency, or you turn a manual double-charge into an automatic one. Two — a **converged concern**: backoff without jitter plus no circuit breaker is a retry storm during an outage. Both go into the ADR."

**Option B — if you're tight on time / with no internet connectivity, show the pre-baked artifacts:**

```bash
glow docs/adr/ADR-0001-resilient-idempotent-checkout.md   # the decision
glow docs/design-review.md                                # the transcript it came from
```

> "The full debate is in `design-review.md`. The **ADR is the distilled decision** — context, the decision, the scope of files it touches, alternatives rejected, and the verdict. That `Scope (files)` list is a machine contract; you'll see why in a second."

---

## 3. Path — implement with the tracer running

Give the agent the task, telling it which ADR it implements:

```
Implement ADR-0001. Create demo/resilience.py with an idempotency key applied before a
retry loop (exponential backoff + full jitter, transient failures only) behind a
per-dependency circuit breaker, and route StripeClient.charge and
GitHubClient.create_receipt_issue through it. Start a trace with adr_id="ADR-0001".
```

Point at the right pane:

> "Before it touches a file, it calls `start_trace` — and notice it passes `adr_id=ADR-0001`. The trace now *declares which plan it's executing*. Watch the events land: each one logs **why**, not just what, and each points at its parent. That's a reasoning graph, not a log."

When it finishes, it calls `end_trace`. Then render the reasoning chain:

```bash
# grab the session path from the watch pane, then:
python render_trace.py --session <YYYYMMDD>/<session_id>
python render_trace.py --session <YYYYMMDD>/<session_id> --verbose      # full reason text
python render_trace.py --session <YYYYMMDD>/<session_id> --files-only   # file touches only
python render_trace.py --session <YYYYMMDD>/<session_id> --mode mermaid # → creates a diagram.mermaid file
```

> Use `20260729/dde097e6` only for an offline rehearsal with the committed sample trace.

> "Header says `implements: ADR-0001`. A reviewer gets this reasoning chain up front instead of reverse-engineering it from the diff."

---

## 4. Check — plan vs. path

```bash
python audit_trace.py --session <YYYYMMDD>/<session_id>
# or: make audit SESSION=<YYYYMMDD>/<session_id>
```

> "This is the independent reviewer. It reads the ADR's declared scope and diffs it against what the trace actually touched. Everything in scope → **faithful**."

Now show the failure mode — a change that wandered outside the plan:

> "If the agent had also edited, say, `demo/auth.py` — a file the ADR never scoped — the audit flags it as **LLD drift**, exits non-zero, and that becomes a PR comment. `--json` makes it a CI gate."

```bash
python audit_trace.py --session <YYYYMMDD>/<session_id> --json | jq .   # exit 1 on drift; CI/PR gate
```

> "Same verdict, machine-readable — wire this into a PR check. `faithful: true`, four files implemented, zero drift."

> "So a PR of the future ships as **code + ADR + trace**. The reviewer — human or agent — has the plan, the path, and an automatic check that they match."

---

## 5. Prove the fix — idempotent checkout

After implementation, show the double-charge bug is closed:

```bash
.venv/bin/python - <<'EOF'
from fastapi.testclient import TestClient
from demo.main import app
c = TestClient(app)
payload = {"customer_id": "cus_1", "amount_cents": 5000, "order_id": "o-1"}
a = c.post("/checkout", json=payload).json()
b = c.post("/checkout", json=payload).json()
print(a["charge"]["id"], b["charge"]["id"], "→ deduped:", a["charge"]["id"] == b["charge"]["id"])
EOF
```

> "Same `order_id`, same charge id — the retry dedupes instead of double-charging."

---

## Fallback — if Cursor doesn't call the MCP tools automatically

Drive the tools directly to show the data model (this is current, tested code):

```bash
.venv/bin/python - <<'EOF'
import json, sys; sys.path.insert(0, ".")
from src.mcp_server import start_trace, append_trace, end_trace

r0 = start_trace(
    task_description="Implement resilient idempotent checkout",
    files_in_scope=["demo/resilience.py", "demo/clients/stripe.py",
                    "demo/clients/github.py", "demo/main.py"],
    adr_id="ADR-0001",
)
print(json.dumps({"started": r0}, indent=2))

r1 = append_trace(
    session_id=r0["session_id"], type="file_create",
    reason="Create demo/resilience.py: idempotency key -> retry(backoff+jitter) -> circuit breaker.",
    files_read=["demo/main.py"], files_modified=[], files_created=["demo/resilience.py"],
    files_deleted=[], parent_step_id="",
)
r2 = append_trace(
    session_id=r0["session_id"], type="file_modify",
    reason="Route StripeClient.charge through the transport with order_id as the idempotency key.",
    files_read=["demo/clients/stripe.py"], files_modified=["demo/clients/stripe.py"],
    files_created=[], files_deleted=[], parent_step_id=r1["step_id"],
)
# model / tokens are auto-read from Cursor's local DB; nothing to pass here.
ended = end_trace(session_id=r0["session_id"], outcome="completed")
print(json.dumps({"ended": ended, "session_id": r0["session_id"]}, indent=2))
EOF

# then render + audit (find the date/session_id from the output above):
python render_trace.py --session $(date +%Y%m%d)/<SESSION_ID>
python audit_trace.py  --session $(date +%Y%m%d)/<SESSION_ID>
python audit_trace.py  --session $(date +%Y%m%d)/<SESSION_ID> --json | jq .
```

---

## Key lines to say

| Moment | Line |
| --- | --- |
| The double-charge | "That's not a lint nit — that's money." |
| `/design-review` blocker | "The council blocked retries-before-idempotency. That's the ADR earning its keep." |
| `start_trace(adr_id=…)` | "The trace declares which plan it's executing." |
| `append_trace` | "It logs *why*, not what. That's the difference between a diff and a decision trail." |
| Parent chain | "A reasoning graph, not a log. Directed. Queryable." |
| `audit_trace` faithful | "Plan and path agree." |
| `audit_trace` drift | "Changed a file the ADR never scoped. That's LLD drift — surfaced automatically." |
| Close | "PR of the future: code + ADR + trace. Docs drift; these move with the code." |

---

## Troubleshooting

| Problem | Fix |
| --- | --- |
| Server won't start | `source .venv/bin/activate && uvicorn src.app:app --port 8080` |
| Cursor not calling tools | Check MCP URL in Cursor settings; confirm `session_trace.mdc` is active |
| `/design-review` not listed | Confirm `.cursor/commands/design-review.md` exists and the repo is open in Cursor |
| Trace file not appearing | `find .cursor/traces -name '*.json'` — the date dir may differ from what you expect |
| `render`/`audit` can't find session | use the actual `<date>/<session_id>` from `find .cursor/traces -name '*.json'` |
| Tokens/model show null | Auto-capture needs a live Cursor session on the machine (macOS/Linux/Windows path). Expected when run outside Cursor. |
| Port 8080 in use | change the port in `make server` / `.cursor/mcp.json` to match |
| `glow` / `jq` / `watch` not found | run `make setup-tools` or `brew install glow watch jq` |

---

## Quick reference — all commands (copy-paste)

Use three terminals: **T1** = server · **T2** = watch (during step 3) · **T3** = everything below.

### Setup (once, T3)

```bash
make setup PYTHON=/Library/Frameworks/Python.framework/Versions/3.12/bin/python3
make test
source .venv/bin/activate   # optional
```

### Server (T1 — leave running)

```bash
make server
curl http://127.0.0.1:8080/health | jq .
curl http://127.0.0.1:8080/sessions | jq .
```

### The bug (T3)

```bash
.venv/bin/python -c "from demo.clients.stripe import StripeClient as S; c=S(); c.charge('cus',5000); c.charge('cus',5000); print('charges:', len(c.charges))"
```

### Cursor prompts

**Plan** — live review (Option A) or skip to `glow` below (Option B):

```
/design-review the checkout flow in demo/ — Stripe charge + GitHub receipt, currently unguarded
```

**Pre-baked plan artifacts (T3, Option B or after live review):**

```bash
glow docs/design-review.md
glow docs/adr/ADR-0001-resilient-idempotent-checkout.md
```

**Watch traces (T2 — start before implement):**

```bash
watch -n 1 "find .cursor/traces -name '*.json' | sort"
```

**Path — implement (Cursor chat):**

```
Implement ADR-0001. Create demo/resilience.py with an idempotency key applied before a
retry loop (exponential backoff + full jitter, transient failures only) behind a
per-dependency circuit breaker, and route StripeClient.charge and
GitHubClient.create_receipt_issue through it. Start a trace with adr_id="ADR-0001".
```

### Render, audit, and verify (T3)

Replace `<YYYYMMDD>/<session_id>` with the session from T2, **or** use the committed sample for rehearsal:

```bash
SESSION=20260729/dde097e6   # sample trace — swap for your live session after implement

python render_trace.py --session $SESSION
python render_trace.py --session $SESSION --verbose
python render_trace.py --session $SESSION --files-only
python render_trace.py --session $SESSION --mode mermaid
python audit_trace.py  --session $SESSION
python audit_trace.py  --session $SESSION --json | jq .
jq . .cursor/traces/20260729/dde097e6/092435_implement_adr0001_resilient_idempotent_outbound.json

.venv/bin/python - <<'EOF'
from fastapi.testclient import TestClient
from demo.main import app
c = TestClient(app)
payload = {"customer_id": "cus_1", "amount_cents": 5000, "order_id": "o-1"}
a = c.post("/checkout", json=payload).json()
b = c.post("/checkout", json=payload).json()
print(a["charge"]["id"], b["charge"]["id"], "→ deduped:", a["charge"]["id"] == b["charge"]["id"])
EOF
```

### Post-demo links

```bash
curl http://127.0.0.1:8080/health | jq .
curl http://127.0.0.1:8080/sessions | jq .
glow docs/adr/ADR-0001-resilient-idempotent-checkout.md
glow docs/design-review.md
```

- `http://127.0.0.1:8080/docs` — FastAPI Swagger UI
- `.cursor/traces/20260729/dde097e6/` — committed sample trace (`render_trace.py` / `audit_trace.py` work offline against it)
- `demo_screenshots/` — screenshots from the same run (see [README.md](README.md#screenshots))
