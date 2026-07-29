# ADR-NNNN: <short decision title>

<!--
An ADR is the DISTILLED DECISION that comes out of an adversarial review
(the review-council skill). The full debate transcript lives in
docs/design-review.md; this file is the permanent, quotable record of WHAT was
planned and WHY. The implementation trace (cursor-session-tracer) records what
was actually DONE, and links back here via adr_id.

    ADR  = the plan   (this file, from adversarial review)
    Trace = the path  (.cursor/traces/..., from implementation)
    audit_trace.py checks the path stayed faithful to the plan.
-->

- **Status:** Proposed | Accepted | Superseded by ADR-XXXX
- **Date:** YYYY-MM-DD
- **Deciders:** <human owner> + review-council (<N> personas)
- **Review record:** `docs/design-review.md` (<YYYY-MM-DD HH:MM:SS> entry)
- **Implemented by trace:** `<session_id>` (or `pending`)

## Context

<The forces at play: the problem, the constraints, what triggered this decision.
State the situation neutrally — someone reading this in a year should understand
why a decision was even needed.>

## Decision

<The change we are making, in active voice. "We will …". One paragraph.>

## Scope (files)

<!--
Machine-readable. audit_trace.py parses this list and compares it against the
files the implementation trace actually touched. Anything the trace changes that
is NOT listed here is flagged as LLD drift. Keep paths repo-relative, one per
bullet. Backticks optional.
-->

- `path/to/file_one.py`
- `path/to/file_two.py`

## Alternatives Considered

- **<Option A>** — <why rejected>
- **<Option B>** — <why rejected>

## Consequences

- **Positive:** <what gets better>
- **Trade-offs:** <what we accept as cost>
- **Risks flagged by council:** <converged concerns / blockers, or "none">

## Council Verdict

<`Proceed as-is` | `Proceed with modifications` | `Redesign required`> — from
adversarial review by <N> personas. <Top converged concern. Any blocker + how it
was resolved. Any human override + rationale.>
