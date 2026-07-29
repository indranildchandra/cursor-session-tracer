# DEMO CURSOR CHAT

An illustrative agent transcript for the live demo — implementing **ADR-0001**
(resilient, idempotent checkout) with the tracer running. Yours will differ.

## User request

> Implement ADR-0001. Create `demo/resilience.py` with an idempotency key applied
> *before* a retry loop (exponential backoff + full jitter, transient failures only)
> behind a per-dependency circuit breaker, and route `StripeClient.charge` and
> `GitHubClient.create_receipt_issue` through it. Start a trace with `adr_id="ADR-0001"`.

## Cursor response (abridged)

I'll follow ADR-0001. First I'll open it to confirm scope and the ordering constraint
(idempotency must precede retries), then start a trace linked to it.

→ `start_trace(task_description="Implement resilient idempotent checkout",
files_in_scope=["demo/resilience.py","demo/clients/stripe.py","demo/clients/github.py","demo/main.py"],
adr_id="ADR-0001")` → session `dde097e6`.

Creating the transport. The order matters: apply the `order_id`-derived idempotency key,
short-circuit an already-succeeded key, then run the bounded retry loop with full jitter,
all behind a circuit breaker keyed per dependency base URL.

→ `append_trace(type="file_create", reason="resilience.py: idempotency -> retry(backoff+jitter,
transient-only) -> per-dependency circuit breaker. Idempotency first so a retry reuses the key.",
files_created=["demo/resilience.py"], parent_step_id="")` → `step_001`.

Now routing the money path. `StripeClient.charge` goes through the transport with `order_id`
as the idempotency key, so a retried charge dedupes instead of double-charging.

→ `append_trace(type="file_modify", reason="Route charge() through transport; order_id is the
idempotency key — closes the double-charge bug.", files_modified=["demo/clients/stripe.py"],
parent_step_id="step_001")` → `step_002`.

Routing the receipt call through the same transport for consistent backoff, then wiring
`main.py`'s checkout to the updated clients.

→ `append_trace(... files_modified=["demo/clients/github.py"], parent_step_id="step_002")` → `step_003`
→ `append_trace(... files_modified=["demo/main.py"], parent_step_id="step_003")` → `step_004`

Tests pass, including the deterministic backoff/dedupe/breaker cases. Closing the trace.

→ `end_trace(session_id="dde097e6", outcome="completed")` — model and token counts read from
Cursor's local DB automatically.

## After the session

```bash
python render_trace.py --session 20260729/dde097e6     # header shows: implements: ADR-0001
python audit_trace.py  --session 20260729/dde097e6     # Plan vs. Path — FAITHFUL (all touches in scope)
```
