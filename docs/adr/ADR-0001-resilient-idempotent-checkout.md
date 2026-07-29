# ADR-0001: Resilient, idempotent outbound calls for the checkout flow

- **Status:** Accepted
- **Date:** 2026-05-09
- **Deciders:** Indranil Chandra + review-council (5 personas)
- **Review record:** `docs/design-review.md` (2026-05-09 06:40:00 entry)
- **Implemented by trace:** `pending` (linked at `start_trace` time via `adr_id="ADR-0001"`)
- **Supersedes / follow-ups:** distributed circuit-breaker coordination deferred to **ADR-0002** (see Consequences)

## Context

The checkout flow (`demo/main.py → StripeClient.charge → GitHubClient.create_receipt_issue`)
makes each outbound call directly, with no shared reliability policy:

- **Not idempotent.** `StripeClient.charge` has no idempotency key, so a client that
  retries a timed-out `POST /checkout` charges the customer **twice**. This is a
  money-losing correctness bug, not a latency nit.
- **No retries.** A transient `503` from Stripe surfaces to the user as a hard
  checkout failure even though a retry would have succeeded.
- **No backpressure.** During a Stripe outage every in-flight request keeps hitting
  a dead dependency, turning a partial outage into a full one.

These three concerns are entangled: you cannot safely add retries (which fixes the
transient-failure problem) *without first* adding idempotency, or you amplify the
double-charge bug from "on manual retry" to "automatically, every time." That
coupling is what makes this worth an ADR rather than three independent tweaks.

## Decision

We will introduce a single resilient outbound transport, `demo/resilience.py`, and
route both clients' **mutating** calls through it. The transport provides, in this
order of dependency:

1. **Idempotency keys** — a deterministic key per logical operation (`order_id` for
   a charge). The transport attaches it and short-circuits a repeat of an
   already-succeeded key, so a retry can never double-charge.
2. **Retry with exponential backoff + full jitter** — bounded retries on transient
   (5xx / timeout) failures only; never on 4xx.
3. **A shared circuit breaker** — once failures to a dependency cross a threshold,
   the breaker opens and fails fast for a cool-down window instead of piling on.

`demo/main.py` keeps orchestrating the flow but calls the clients, which now call
the transport; the reliability policy lives in exactly one seam.

## Scope (files)

- `demo/resilience.py`
- `demo/clients/stripe.py`
- `demo/clients/github.py`
- `demo/main.py`

## Alternatives Considered

- **Per-client ad-hoc retry** (a `for` loop in each client) — rejected: duplicates
  the policy across clients, and the next dependency added re-solves it from
  scratch. It also makes the idempotency/retry ordering easy to get wrong
  per-client, which is exactly the dangerous case.
- **Adopt a library (e.g. `tenacity` / `stamina`) instead of writing the transport** —
  reasonable in production and noted as a real option, but rejected *for this
  scope*: the demo must stay dependency-light and the idempotency-before-retry
  coupling is the teaching point, so we keep it explicit.
- **Distributed circuit breaker (shared state in Redis) now** — rejected for this
  change; see the human override below.

## Consequences

- **Positive:** the double-charge bug is closed at the seam; transient failures
  become invisible to the user; an outage degrades gracefully instead of
  cascading. All three policies live in one auditable module.
- **Trade-offs:** the circuit-breaker state is **in-memory / per-process**. With
  more than one server instance each has its own breaker, so the fleet trips
  later than a single logical breaker would.
- **Risks flagged by council:**
  - *Retry storm / thundering herd* if backoff has no jitter (converged: staff +
    cloud-cost). Mitigated by **full jitter** + the breaker.
  - *Double charge* if retries ship before idempotency (BLOCKER: appsec + staff).
    Resolved by the ordered dependency in the Decision — idempotency lands first,
    in the same change.

## Council Verdict

**Proceed with modifications** — adversarial review by 5 personas (staff-engineer,
appsec-architect, cloud-cost-architect, senior-backend-engineer, lead-sdet).

- **Converged concern:** retries without jitter + a breaker cause a retry storm.
  Modification required: full jitter and a circuit breaker are in scope, not optional.
- **Blocker (resolved):** appsec + staff blocked "retries before idempotency" as a
  double-charge risk. Resolved by making idempotency the first dependency in the
  transport; retries are only enabled behind it.
- **Human override (recorded):** the council wanted distributed breaker state.
  Indranil overrode for this change — *"single-instance demo; a per-process breaker
  is honest for the scope and I don't want Redis on stage"* — and filed **ADR-0002**
  for distributed coordination as an explicit follow-up rather than silently
  dropping it.
