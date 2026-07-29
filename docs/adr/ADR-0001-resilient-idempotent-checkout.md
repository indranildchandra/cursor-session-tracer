# ADR-0001: Resilient, idempotent outbound calls for the checkout flow

- **Status:** Accepted
- **Date:** 2026-05-09
- **Deciders:** Indranil Chandra + review-council (5 personas)
- **Review record:** `docs/design-review.md` (2026-05-09 06:40:00)
- **Implemented by trace:** `pending` — link at `start_trace` via `adr_id="ADR-0001"`
- **Follow-up:** distributed circuit-breaker state → **ADR-0002** (see Consequences)

## Context

`POST /checkout` charges via Stripe, then writes a receipt via GitHub — each call direct
and unguarded. Three problems, entangled:

- **Not idempotent** → a retried charge **double-charges** the customer (money bug).
- **No retries** → a transient 5xx becomes a hard checkout failure.
- **No backpressure** → during a Stripe outage every request keeps hitting a dead dependency.

They can't be fixed independently: adding retries *before* idempotency turns the
double-charge from "on manual retry" into "automatic, every time." That coupling is why
this is one ADR, not three tweaks.

## Decision

Introduce one resilient transport, `demo/resilience.py`, and route both clients' mutating
calls through it. Applied **in this order** (the order is the safety property):

1. **Idempotency key** — derived from the logical operation (`order_id`); short-circuits a
   repeat of an already-succeeded key, so a retry can never double-charge.
2. **Retry** — bounded, exponential backoff + **full jitter**, transient (5xx/timeout) only.
3. **Circuit breaker** — per dependency; opens after repeated failures and fails fast for a
   cool-down window instead of piling on.

`demo/main.py` still orchestrates; the reliability policy lives in exactly one seam.

## Scope (files)

- `demo/resilience.py`
- `demo/clients/stripe.py`
- `demo/clients/github.py`
- `demo/main.py`

## Alternatives Considered

- **Per-client ad-hoc retry** — rejected: duplicates the policy and makes the
  idempotency/retry ordering easy to get wrong per client (the dangerous case).
- **A retry library (`tenacity`/`stamina`)** — reasonable in production, rejected here to
  stay dependency-light and keep the idempotency-before-retry ordering explicit (the teaching point).
- **Distributed breaker (Redis) now** — rejected for this change (see override below).

## Consequences

- **Positive:** the double-charge bug is closed at the seam; transient failures become
  invisible; an outage degrades instead of cascading. One auditable module owns the policy.
- **Trade-off:** breaker state is **in-memory / per-process** — a multi-instance fleet trips
  later than a single logical breaker would.
- **Risks flagged by council:** retry storm without jitter + breaker (converged: staff +
  cost); double-charge if retries ship before idempotency (blocker: appsec + staff).

## Council Verdict

**Proceed with modifications** — 5 personas (staff-engineer, appsec-architect,
cloud-cost-architect, senior-backend-engineer, lead-sdet).

- **Modification required:** full jitter + circuit breaker are in scope, not optional.
- **Blocker (resolved by design):** appsec + staff blocked "retries before idempotency";
  resolved by the ordered dependency above — retries live strictly behind the idempotency key.
- **Human override (recorded):** council wanted distributed breaker state; Indranil overrode
  — *"single-instance demo; a per-process breaker is honest for the scope and I don't want
  Redis on stage"* — and filed **ADR-0002** rather than silently dropping it.
