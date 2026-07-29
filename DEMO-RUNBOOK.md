# DEMO RUNBOOK

## cursor-session-tracer — live demo guide

**Talk:** Your Code and its Story — Told by Adversarial Review & Cursor Session Tracer
**Thesis:** Docs drift, traces don't. Plan (ADR) vs. path (trace), with a drift check between them.

The demo walks one loop on a deliberately broken app: **adversarial review → ADR → implement with tracing → audit plan vs. path.**

---

## 0. Pre-demo setup (do this before you present)

### Environment (Python 3.12)

```bash
git clone https://github.com/indranildchandra/cursor-session-tracer
cd cursor-session-tracer
make setup        # macOS: make setup PYTHON=/Library/Frameworks/Python.framework/Versions/3.12/bin/python3
make test         # expect all green
```

### Start the tracer server

```bash
make server       # http://127.0.0.1:8080  — leave this terminal running
# verify:
curl http://127.0.0.1:8080/health          # {"status":"ok","service":"cursor-session-tracer"}
```

### Point Cursor at the server

`.cursor/mcp.json` is already committed, so opening this repo in Cursor auto-registers the tracer. Confirm under **Cursor → Settings → MCP** that `cursor-session-tracer` shows **connected**. (If not, add `{"cursor-session-tracer": {"url": "http://127.0.0.1:8080/mcp"}}`.)

### Confirm the Cursor rule + command are installed

Both live in `.cursor/` and load automatically when the repo is open:

- **Rule:** `.cursor/rules/session_trace.mdc` → appears under **Cursor → Rules**.
- **Command:** `.cursor/commands/design-review.md` → type `/` in the agent chat and confirm **`design-review`** appears. Its personas are in `.cursor/review-council/`.

> Installing into another repo: copy the whole `.cursor/` folder (`mcp.json`, `rules/`, `commands/`, `review-council/`) and `docs/adr/TEMPLATE.md` into the target project, then point that repo's `.cursor/mcp.json` at your running tracer.

### Split the screen

- **Left:** Cursor agent chat.
- **Right:** a terminal watching traces appear:

```bash
watch -n 1 "find .cursor/traces -name '*.json' | sort"
```

---

## 1. Set the scene — the broken app (≈1 min)

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

## 2. Plan — run the adversarial review (≈3–5 min)

**Option A — run it live.** In the Cursor agent chat:

```
/design-review the checkout flow in demo/ — Stripe charge + GitHub receipt, currently unguarded
```

Narrate as the council forms: independent personas (staff-engineer, appsec-architect, cloud-cost-architect, …) review in isolation, then debate. Land on the two outcomes that matter:

> "Two things the council caught that a single reviewer might not. One — a **blocker**: you cannot add retries before idempotency, or you turn a manual double-charge into an automatic one. Two — a **converged concern**: backoff without jitter plus no circuit breaker is a retry storm during an outage. Both go into the ADR."

**Option B — if you're tight on time, show the pre-baked artefacts:**

```bash
sed -n '1,40p' docs/adr/ADR-0001-resilient-idempotent-checkout.md   # the decision
sed -n '1,30p' docs/design-review.md                                # the transcript it came from
```

> "The full debate is in `design-review.md`. The **ADR is the distilled decision** — context, the decision, the scope of files it touches, alternatives rejected, and the verdict. That `Scope (files)` list is a machine contract; you'll see why in a second."

---

## 3. Path — implement with the tracer running (≈4 min)

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
# grab the session path from the right pane, then:
python render_trace.py --session <YYYYMMDD>/<session_id>
```

> "Header says `implements: ADR-0001`. A reviewer gets this reasoning chain up front instead of reverse-engineering it from the diff."

---

## 4. Check — plan vs. path (≈2 min)

```bash
python audit_trace.py --session <YYYYMMDD>/<session_id>
# or: make audit SESSION=<YYYYMMDD>/<session_id>
```

> "This is the independent reviewer. It reads the ADR's declared scope and diffs it against what the trace actually touched. Everything in scope → **faithful**."

Now show the failure mode — a change that wandered outside the plan:

> "If the agent had also edited, say, `demo/auth.py` — a file the ADR never scoped — the audit flags it as **LLD drift**, exits non-zero, and that becomes a PR comment. `--json` makes it a CI gate."

```bash
python audit_trace.py --session <YYYYMMDD>/<session_id> --json   # exit 1 on drift
```

> "So a PR of the future ships as **code + ADR + trace**. The reviewer — human or agent — has the plan, the path, and an automatic check that they match."

---

## Fallback — if Cursor doesn't call the MCP tools automatically

Drive the tools directly to show the data model (this is current, tested code):

```bash
.venv/bin/python - <<'EOF'
import sys; sys.path.insert(0, ".")
from src.mcp_server import start_trace, append_trace, end_trace

r0 = start_trace(
    task_description="Implement resilient idempotent checkout",
    files_in_scope=["demo/resilience.py", "demo/clients/stripe.py",
                    "demo/clients/github.py", "demo/main.py"],
    adr_id="ADR-0001",
)
print("Started:", r0)

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
print("Ended:", end_trace(session_id=r0["session_id"], outcome="completed"))
print("Session:", r0["session_id"])
EOF

# then render + audit (find the date/session_id from the output above):
python render_trace.py --session $(date +%Y%m%d)/<SESSION_ID>
python audit_trace.py  --session $(date +%Y%m%d)/<SESSION_ID>
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

## Post-demo URLs

- `http://127.0.0.1:8080/health` — health
- `http://127.0.0.1:8080/sessions` — all sessions as JSON (includes `adr_id`)
- `http://127.0.0.1:8080/docs` — FastAPI Swagger UI
- `docs/adr/ADR-0001-resilient-idempotent-checkout.md` — the plan · `docs/design-review.md` — the transcript
