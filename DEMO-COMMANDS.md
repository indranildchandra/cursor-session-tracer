# DEMO COMMANDS

Quick reference — full walkthrough in [DEMO-RUNBOOK.md](DEMO-RUNBOOK.md).

```bash
# Setup (Python 3.12). macOS: append PYTHON=/Library/Frameworks/Python.framework/Versions/3.12/bin/python3
make setup
make server            # tracer on http://127.0.0.1:8080  (leave running)
make test

# Show the bug:
.venv/bin/python -c "from demo.clients.stripe import StripeClient as S; c=S(); c.charge('cus',5000); c.charge('cus',5000); print('charges:',len(c.charges))"
```

In the Cursor agent chat:

```
/design-review the checkout flow in demo/ — Stripe charge + GitHub receipt, currently unguarded
Implement ADR-0001 ... and start a trace with adr_id="ADR-0001".
```

Then, from a terminal:

```bash
python render_trace.py --session YYYYMMDD/<session_id>          # reasoning tree
python audit_trace.py  --session YYYYMMDD/<session_id>          # plan vs. path (or: make audit SESSION=…)
python audit_trace.py  --session YYYYMMDD/<session_id> --json   # CI/PR gate (exit 1 on drift)
```
