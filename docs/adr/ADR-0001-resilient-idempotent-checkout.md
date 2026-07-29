# ADR-0001: Resilient, Idempotent Checkout Outbound Calls

- **Status:** Accepted
- **Date:** 2026-07-29

## Context

The demo checkout service (`POST /checkout`) charges a customer via Stripe, then records a
receipt as a GitHub issue. Both outbound calls are made directly with no idempotency key,
retry policy, or circuit breaker. A client retry after timeout double-charges the customer
(two identical `POST /checkout` calls with the same `order_id` produce two distinct charges).

Auth is already handled (`BearerTokenAuth`) and is **not** in scope. The architectural gap
is resilience and idempotency on the two mutating outbound dependencies.

Human brief (Phase 0): primary worry is **double-charging on retry**; no hard constraints
on approach.

## Decision

Introduce a single resilient transport module (`demo/resilience.py`) and route both mutating
outbound calls through it:

1. **Idempotency first** — derive an idempotency key from the logical operation (`order_id`
   for charge and receipt). Short-circuit if the key already succeeded (return cached result).
2. **Retry with backoff + full jitter** — bounded retries (max 3), exponential base delay
   (100ms), full jitter, **transient failures only** (5xx / simulated transient errors).
3. **Per-dependency circuit breaker** — keyed by dependency base URL (Stripe vs GitHub) so
   an outage on one does not open the breaker on the other.

Apply policy in this order: **idempotency → retry → circuit breaker** (idempotency wraps the
retry loop so a retried attempt reuses the same key).

Wire `StripeClient.charge` and `GitHubClient.create_receipt_issue` through the transport.
Keep `demo/main.py` orchestration thin (charge, then receipt). Do **not** change auth.

Inject `sleep` / RNG in the transport for deterministic tests.

## Scope (files)

- `demo/resilience.py`
- `demo/clients/stripe.py`
- `demo/clients/github.py`
- `demo/main.py`

## Alternatives Considered

| Alternative | Why rejected |
| --- | --- |
| Per-client retry logic in `stripe.py` and `github.py` | Duplicates policy; easy to apply retries before idempotency on one client only |
| Retries without idempotency | **Blocked by council** — turns manual double-charge into automatic double-charge |
| Saga / compensating transaction for charge-then-receipt | Correct for production partial-failure, but out of scope for this demo; receipt dupes are annoying, not financial |
| Change auth or add inbound request idempotency middleware | Out of scope; auth is already solved; outbound mutating calls are the seam |

## Consequences

- Double-charge on client retry is closed for outbound calls keyed by `order_id`.
- Transient Stripe/GitHub failures get bounded retries instead of immediate hard failure.
- Circuit breaker limits retry pile-on during sustained outages.
- Partial failure (charge succeeds, receipt fails) can still occur; receipt is not financial
  risk but may duplicate on unkeyed client retries of the whole endpoint — mitigated by
  outbound idempotency on the receipt call.
- New module is the single place to evolve resilience policy.

### Risks flagged by council

- **Blocker (resolved in decision):** retries before idempotency on charge path
- **Converged:** retry storm without jitter + breaker during dependency outage
- **Open (accepted):** charge-then-receipt partial failure without saga — documented, not blocking demo

## Council Verdict

**Proceed with modifications** — adopt single transport; enforce idempotency-before-retry ordering; scope limited to four files above.

## Review record

See [design-review.md — 2026-07-29 checkout flow](../design-review.md#2026-07-29--checkout-flow-stripe--github-receipt).
