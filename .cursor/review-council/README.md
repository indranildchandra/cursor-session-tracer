# review-council (Cursor)

Adversarial design review that produces an **ADR**. Invoked as the Cursor command
[`/design-review`](../commands/design-review.md).

```
.cursor/
├── commands/
│   └── design-review.md          # the /design-review command (the protocol)
└── review-council/
    ├── standard-personas/        # 20+ expert lenses — load only the 3–6 selected
    └── user-generated-personas/  # project-specific personas you add
```

The command runs a council of independent expert personas that debate and converge
on a verdict, then distils the decision into `docs/adr/ADR-NNNN-*.md` (full
transcript to `docs/design-review.md`). That ADR is the *plan*; a
cursor-session-tracer trace linked by `adr_id` is the *path*; `audit_trace.py`
checks one against the other. See [`docs/adr/README.md`](../../docs/adr/README.md).

## Install into another repo

Copy `.cursor/commands/design-review.md` and `.cursor/review-council/` into the
target repo's `.cursor/` directory, plus `docs/adr/TEMPLATE.md`. Cursor picks the
command up automatically — type `/design-review` in the agent chat. See the repo
[DEMO-RUNBOOK.md](../../DEMO-RUNBOOK.md) for the full install + demo flow.
