# Reference solution — post-`ADR-0001` demo output

This folder is a **snapshot of what the live demo produces**: the files the agent
creates/changes when it implements
[`ADR-0001`](../docs/adr/ADR-0001-resilient-idempotent-checkout.md) against the naive
`demo/` checkout service.

```
files-changed post-demo-run/
├── demo/
│   ├── resilience.py            # NEW — idempotency → retry(backoff+jitter) → circuit breaker
│   ├── main.py                  # CHANGED — /checkout routed through the transport
│   ├── clients/{stripe,github}.py  # CHANGED — mutating calls go through the transport
│   ├── auth.py                  # unchanged — included so the tree runs
│   └── __init__.py, clients/__init__.py   # unchanged package markers
└── tests/
    └── test_resilience.py       # deterministic tests for dedupe / retry / breaker-open
```

The `resilience.py`, `main.py`, and two client files are the **files the demo
changes**; `auth.py` and the `__init__.py` markers are unchanged and included only so
this tree is a complete, runnable package.

## Why it lives here and not in `demo/`

The repo's `demo/` is intentionally the **naive starting state** — the canary
`tests/test_demo.py::TestNaiveStartingState` asserts that `demo/resilience.py` does
**not** exist, so the talk always starts from the broken version. The finished
implementation therefore can't live in `demo/`; it lives here as a reference.

Because of that, `test_resilience.py` imports `demo.resilience`, which only exists
*inside this folder*. It is deliberately **excluded from the main suite** (see
`pyproject.toml` → `testpaths = ["tests"]`), so `pytest` / CI never try to collect it
against the naive tree.

## Running the reference tests

Point Python at this folder as the import root:

```bash
cd "files-changed post-demo-run"
PYTHONPATH=. ../.venv/bin/python -m pytest tests/ -q
```

## Regenerating it

Run the demo loop (see [DEMO-RUNBOOK.md](../DEMO-RUNBOOK.md)); the agent produces these
files. Copy the changed files here if you want to refresh the reference.
