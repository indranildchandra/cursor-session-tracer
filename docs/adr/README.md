# Architecture Decision Records (ADRs)

This directory holds the **plan** half of the two-artifact model:

```
ADR   = the plan   — what was decided and why, distilled from adversarial review
Trace = the path   — what the agent actually did, recorded by cursor-session-tracer
```

## Where each artifact comes from

| Artifact | Produced by | Lives in | Answers |
|---|---|---|---|
| **ADR** | `review-council` skill (`/design-review`) — the adversarial review | `docs/adr/ADR-NNNN-*.md` | *What did we plan, and why?* |
| Review transcript | same council run | `docs/design-review.md` | *How did the council argue its way there?* |
| **Trace** | `cursor-session-tracer` MCP tools during implementation | `.cursor/traces/<date>/<id>/*.json` | *What did the agent actually do?* |

The ADR is the crisp, permanent decision record. The full council debate (all
persona findings, converged concerns, blockers, human overrides) is appended to
`docs/design-review.md`; the ADR distills it into Context / Decision / Scope /
Alternatives / Consequences / Verdict.

## The link

An implementation session links back to its ADR by passing `adr_id` to
`start_trace` (e.g. `adr_id="ADR-0001"`). The trace then declares which plan it is
executing, and `render_trace.py` shows it in the header.

## Checking plan vs. path

`audit_trace.py` is the deterministic faithfulness check — the independent
reviewer that reads both artifacts and flags **LLD drift**: files the trace
changed that the ADR never put in scope.

```bash
# Resolve the ADR automatically from the trace's adr_id:
python audit_trace.py --session 20260729/dde097e6

# Or point at a specific ADR:
python audit_trace.py --session 20260729/dde097e6 --adr docs/adr/ADR-0001-resilient-idempotent-checkout.md

# Machine-readable, for a PR comment / CI gate (exit 1 on drift):
python audit_trace.py --session 20260729/dde097e6 --json | jq .
```

## Writing a new ADR

Copy `TEMPLATE.md` to `ADR-NNNN-<slug>.md` (next number, kebab-case slug). Keep
the `## Scope (files)` list accurate — `audit_trace.py` parses it, so it is a
machine contract, not just prose.
