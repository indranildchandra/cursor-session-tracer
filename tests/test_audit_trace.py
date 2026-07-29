"""
Tests for audit_trace.py — the plan-vs-path faithfulness check.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import audit_trace as at


# ---------------------------------------------------------------------------
# ADR scope parsing
# ---------------------------------------------------------------------------

ADR_SAMPLE = """# ADR-0009: Something

- **Status:** Accepted

## Context

Prose bullet that is not a path:
- this is a sentence with spaces

## Scope (files)

<!-- a comment bullet should be ignored -->
- `demo/auth.py`
- demo/clients/github.py
- `demo/clients/stripe.py`

## Alternatives Considered

- `not/a/scope/file.py` — this is under a different heading, must be ignored
"""


def test_parse_adr_scope_extracts_only_scope_paths():
    scope = at.parse_adr_scope(ADR_SAMPLE)
    assert scope == ["demo/auth.py", "demo/clients/github.py", "demo/clients/stripe.py"]


def test_parse_adr_scope_ignores_prose_and_other_sections():
    scope = at.parse_adr_scope(ADR_SAMPLE)
    assert "this is a sentence with spaces" not in scope
    assert "not/a/scope/file.py" not in scope


def test_parse_real_adr_0001():
    adr = Path(__file__).parent.parent / "docs" / "adr" / "ADR-0001-resilient-idempotent-checkout.md"
    scope = at.parse_adr_scope(adr.read_text())
    assert set(scope) == {
        "demo/resilience.py",
        "demo/clients/stripe.py",
        "demo/clients/github.py",
        "demo/main.py",
    }


# ---------------------------------------------------------------------------
# collect_touched
# ---------------------------------------------------------------------------

def test_collect_touched_unions_change_kinds_and_separates_reads():
    events = [
        {"files_read": ["a.py"], "files_modified": ["b.py"], "files_created": [], "files_deleted": []},
        {"files_read": ["b.py"], "files_modified": [], "files_created": ["c.py"], "files_deleted": ["d.py"]},
    ]
    touched = at.collect_touched(events)
    assert touched["changed"] == {"b.py", "c.py", "d.py"}
    assert touched["read"] == {"a.py", "b.py"}


# ---------------------------------------------------------------------------
# audit verdict
# ---------------------------------------------------------------------------

SCOPE = ["demo/resilience.py", "demo/main.py", "demo/clients/github.py", "demo/clients/stripe.py"]


def test_audit_faithful_when_changes_within_scope():
    touched = {"changed": {"demo/resilience.py", "demo/clients/stripe.py"}, "read": {"demo/main.py"}}
    result = at.audit(SCOPE, touched)
    assert result["faithful"] is True
    assert result["verdict"] == "FAITHFUL"
    assert result["drift"] == []
    assert set(result["implemented"]) == {"demo/resilience.py", "demo/clients/stripe.py"}
    assert "demo/main.py" in result["planned_not_touched"]


def test_audit_flags_drift_for_out_of_scope_change():
    # The agent also edited an unrelated module the ADR never scoped -> drift.
    touched = {"changed": {"demo/resilience.py", "demo/logging_config.py"}, "read": set()}
    result = at.audit(SCOPE, touched)
    assert result["faithful"] is False
    assert result["verdict"] == "DRIFT DETECTED"
    assert result["drift"] == ["demo/logging_config.py"]


def test_audit_reads_outside_scope_are_informational_not_drift():
    touched = {"changed": {"demo/resilience.py"}, "read": {"demo/unrelated.py"}}
    result = at.audit(SCOPE, touched)
    assert result["faithful"] is True
    assert "demo/unrelated.py" in result["reads_outside_scope"]
    assert "demo/unrelated.py" not in result["drift"]
