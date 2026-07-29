# Contributing

Thanks for helping improve cursor-session-tracer. This project dogfoods its own loop — plan (ADR) → path (trace) → check (`audit_trace.py`) — and we ask contributors to follow the same model when the change is architectural.

## Getting started

Requires **Python 3.12** and a working **Cursor** install if you are exercising the MCP integration.

```bash
git clone https://github.com/indranildchandra/cursor-session-tracer
cd cursor-session-tracer
make setup          # macOS: make setup PYTHON=/Library/Frameworks/Python.framework/Versions/3.12/bin/python3
make test
make server         # optional — needed to test MCP tools from Cursor
```

See [README.md](README.md#quickstart) for prerequisites (Cursor versions, Homebrew demo tools).

## Where help goes furthest

See [Roadmap / future scope](README.md#roadmap--future-scope) in the README. Highest-impact areas today:

- Pluggable trace store (`TraceStore` interface + Neo4j / ClickHouse backends)
- CI integration for `audit_trace.py --json`
- Agentic reviewer layered on the audit diff
- Opt-in per-session cost capture (`cost_usd` from token counts)

Bug fixes, docs, tests, and renderer/audit improvements are always welcome.

## Pull request checklist

Before opening a PR:

- [ ] `make test` passes on **Python 3.12**
- [ ] Changes are scoped to the issue — no drive-by refactors
- [ ] New behavior has tests when the change is non-trivial
- [ ] `demo/` stays in the **naive starting state** unless the PR intentionally changes the demo premise (the canary `tests/test_demo.py` enforces this)
- [ ] No secrets, `.env` files, or local Cursor DB paths committed
- [ ] Runtime traces under `.cursor/traces/` are **not** committed unless you are deliberately updating the whitelisted sample under `20260729/` (see `.gitignore`)
- [ ] `diagram.mermaid` is not committed (generated artifact)

## Code conventions

- Match the style of the file you edit — this is a small Python codebase, not a framework.
- Prefer minimal, focused diffs over new abstractions for one-off logic.
- Type hints and docstrings where they clarify non-obvious behavior; don't annotate the obvious.
- MCP surface stays at **three tools** (`start_trace`, `append_trace`, `end_trace`) unless there is a strong design reason to expand it.

Run tests:

```bash
make test
# or: .venv/bin/python -m pytest tests/ -q -k test_name
```

## Architectural changes — dogfood the loop

If your PR changes behavior, schema, or multi-file architecture:

1. **Plan** — run `/design-review` in Cursor (or extend an existing ADR if the scope fits).
2. **Record** — add or update an ADR in `docs/adr/` using [TEMPLATE.md](docs/adr/TEMPLATE.md). Keep `## Scope (files)` accurate — `audit_trace.py` parses it.
3. **Implement** — with the tracer running: `start_trace(..., adr_id="ADR-NNNN")`.
4. **Attach to the PR:**
   - the ADR (or diff to an existing one)
   - the trace file path (or commit the trace if it is the new canonical sample)
   - output of `python audit_trace.py --session <date>/<id>`
   - output of `python audit_trace.py --session <date>/<id> --json | jq .`

```bash
make server   # terminal 1
# implement in Cursor with tracing enabled
python render_trace.py --session YYYYMMDD/<session_id>
python audit_trace.py  --session YYYYMMDD/<session_id>
python audit_trace.py  --session YYYYMMDD/<session_id> --json | jq .
```

Smaller fixes (typos, single-function bugs, test gaps) do not need an ADR — use judgment.

## Demo and docs

- Presenter commands: [DEMO-RUNBOOK.md](DEMO-RUNBOOK.md)
- Architecture and talk design: [DESIGN-PLAN.md](DESIGN-PLAN.md)
- ADR model: [docs/adr/README.md](docs/adr/README.md)

If you update demo flow or CLI output, update the runbook and any affected screenshots under `demo_screenshots/` when the visual output changes materially.

## Questions

Open a [GitHub issue](https://github.com/indranildchandra/cursor-session-tracer/issues) for bugs, design questions, or coordination on larger roadmap items before starting a large PR.
