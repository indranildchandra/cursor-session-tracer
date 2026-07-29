# ADR-0002: Distributed circuit-breaker coordination

- **Status:** Proposed
- **Date:** 2026-05-09
- **Deciders:** TBD — to be taken through `/design-review` before acceptance
- **Supersedes / relates to:** follow-up to **ADR-0001** (resilient, idempotent checkout)
- **Implemented by trace:** none yet

## Context

ADR-0001 introduced a circuit breaker in `demo/resilience.py`, but with **in-memory,
per-process** state. The review council flagged, and the human override accepted, that
this is honest only for a single-instance deployment: with more than one server instance,
each keeps its own breaker, so the fleet trips later and less coherently than a single
logical breaker would. ADR-0001 deferred the fix here rather than silently dropping it.

This ADR is a **placeholder for that follow-up decision**. It is intentionally not yet
decided — it should be taken through `/design-review` (adversarial review) like any other
architectural decision, which is the whole point of the workflow this repo demonstrates.

## Decision

*Not yet decided.* Options to weigh in review (non-exhaustive):

- **Shared state in Redis** — a breaker keyed per dependency, backed by Redis so all
  instances observe the same open/closed state. Trade-off: adds an external dependency and
  a new failure mode (what happens when Redis itself is down?).
- **Gossip / probabilistic breaker** — instances share failure signals without a central
  store. Trade-off: eventual consistency, more complex to reason about.
- **Accept per-process breakers** — do nothing; rely on each instance converging quickly.
  Trade-off: slower fleet-wide response during an outage.

## Scope (files)

*To be defined during review.* Expected to touch `demo/resilience.py` and any new
coordination module.

## Consequences

To be recorded once the decision is made.

## Council Verdict

Pending — this ADR has not yet been through `/design-review`.
