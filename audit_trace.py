#!/usr/bin/env python3
"""
audit_trace.py — the plan-vs-path faithfulness check.

Reads an ADR (the plan) and an implementation trace (the path) and reports
whether the implementation stayed faithful to the declared scope. The core
signal is **LLD drift**: files the trace changed that the ADR never put in
scope.

This is the deterministic core of "the PR review of the future": an independent
reviewer that has both the plan and the path, and can flag divergence without
reconstructing intent from the diff. An agentic reviewer adds judgement on top;
this tool supplies the ground-truth diff between planned and actual file surface.

Usage:
    python audit_trace.py --session 20260509/a1b2c3d4
    python audit_trace.py --session 20260509/a1b2c3d4 --adr docs/adr/ADR-0001-resilient-idempotent-checkout.md
    python audit_trace.py --session 20260509/a1b2c3d4 --json

Exit code: 0 if faithful (no drift), 1 if drift detected or inputs missing.
"""

import json
import re
import sys
from pathlib import Path

import click
from rich.console import Console

TRACES_ROOT = Path(".cursor/traces")
ADR_ROOT = Path("docs/adr")
console = Console()


# ---------------------------------------------------------------------------
# ADR parsing
# ---------------------------------------------------------------------------

def parse_adr_scope(adr_text: str) -> list[str]:
    """
    Extract the repo-relative file paths listed under the '## Scope (files)'
    section of an ADR. Reads bullet lines until the next '## ' heading.
    Strips backticks and ignores HTML comments / blank lines.
    """
    lines = adr_text.splitlines()
    in_scope = False
    files: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            # Enter on the Scope heading, exit on the next section heading.
            in_scope = stripped.lower().startswith("## scope")
            continue
        if not in_scope:
            continue
        if stripped.startswith("<!--") or stripped.startswith("-->") or not stripped:
            continue
        if stripped.startswith("- ") or stripped.startswith("* "):
            item = stripped[2:].strip().strip("`").strip()
            # Guard against prose bullets — a path has no spaces.
            if item and " " not in item:
                files.append(item)
    return files


def resolve_adr_path(adr_id: str) -> Path | None:
    """Resolve an adr_id like 'ADR-0001' to docs/adr/ADR-0001-*.md."""
    if not adr_id:
        return None
    matches = sorted(ADR_ROOT.glob(f"{adr_id}*.md"))
    return matches[0] if matches else None


# ---------------------------------------------------------------------------
# Trace loading
# ---------------------------------------------------------------------------

def load_trace_events(session_dir: Path) -> tuple[dict, list[dict]]:
    """Merge all JSON files under a session dir (restart-safe). Returns (session, events)."""
    json_files = sorted(session_dir.glob("*.json"))
    session: dict = {}
    events: list[dict] = []
    for jf in json_files:
        data = json.loads(jf.read_text())
        if not session:
            session = data.get("session", {})
        events.extend(data.get("events", []))
    return session, events


def collect_touched(events: list[dict]) -> dict:
    """Union file paths across events, split by change kind vs read-only."""
    changed: set[str] = set()
    read: set[str] = set()
    for e in events:
        for key in ("files_modified", "files_created", "files_deleted"):
            changed.update(e.get(key) or [])
        read.update(e.get("files_read") or [])
    return {"changed": changed, "read": read}


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------

def audit(scope: list[str], touched: dict) -> dict:
    scope_set = set(scope)
    changed = touched["changed"]
    read = touched["read"]

    implemented = sorted(scope_set & changed)
    planned_not_touched = sorted(scope_set - changed)
    drift = sorted(changed - scope_set)                 # changed but never planned
    reads_outside_scope = sorted(read - scope_set - changed)

    return {
        "verdict": "FAITHFUL" if not drift else "DRIFT DETECTED",
        "faithful": not drift,
        "implemented": implemented,
        "planned_not_touched": planned_not_touched,
        "drift": drift,
        "reads_outside_scope": reads_outside_scope,
        "scope_size": len(scope_set),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@click.command()
@click.option("--session", required=True, help="Date/session_id, e.g. 20260509/a1b2c3d4")
@click.option("--adr", "adr_path", default=None, help="Path to the ADR. If omitted, resolved from the trace's adr_id.")
@click.option("--json", "as_json", is_flag=True, default=False, help="Emit JSON (for a PR comment / CI gate)")
def main(session: str, adr_path: str | None, as_json: bool):
    """Audit an implementation trace against its ADR's declared scope."""
    parts = session.strip("/").split("/")
    if len(parts) != 2:
        console.print("[red]--session must be DATE/SESSION_ID, e.g. 20260509/a1b2c3d4[/red]")
        sys.exit(1)
    session_dir = TRACES_ROOT / parts[0] / parts[1]
    if not session_dir.exists():
        console.print(f"[red]Session directory not found: {session_dir}[/red]")
        sys.exit(1)

    sess, events = load_trace_events(session_dir)

    # Resolve the ADR: explicit --adr wins, else the trace's adr_id.
    resolved_adr = Path(adr_path) if adr_path else resolve_adr_path(sess.get("adr_id") or "")
    if not resolved_adr or not resolved_adr.exists():
        msg = (
            f"No ADR found. Trace adr_id={sess.get('adr_id')!r}. "
            "Pass --adr explicitly, or set adr_id at start_trace."
        )
        if as_json:
            print(json.dumps({"verdict": "NO ADR", "faithful": False, "error": msg}, indent=2))
        else:
            console.print(f"[red]{msg}[/red]")
        sys.exit(1)

    scope = parse_adr_scope(resolved_adr.read_text())
    touched = collect_touched(events)
    result = audit(scope, touched)
    result["adr"] = str(resolved_adr)
    result["session_id"] = sess.get("session_id")
    result["adr_id"] = sess.get("adr_id")

    if as_json:
        print(json.dumps(result, indent=2))
        sys.exit(0 if result["faithful"] else 1)

    # Human-readable report
    color = "green" if result["faithful"] else "red"
    console.print()
    console.rule(f"[bold {color}]Plan vs. Path — {result['verdict']}[/bold {color}]")
    console.print(f"[dim]ADR:[/dim]   {resolved_adr}")
    console.print(f"[dim]Trace:[/dim] session {sess.get('session_id')} | adr_id={sess.get('adr_id')}")
    console.print()

    console.print(f"[bold green]✓ Implemented in scope[/bold green] ({len(result['implemented'])}/{result['scope_size']}):")
    for f in result["implemented"]:
        console.print(f"    [green]{f}[/green]")

    if result["planned_not_touched"]:
        console.print(f"\n[bold yellow]○ Planned but not touched[/bold yellow] ({len(result['planned_not_touched'])}):")
        for f in result["planned_not_touched"]:
            console.print(f"    [yellow]{f}[/yellow]")

    if result["drift"]:
        console.print(f"\n[bold red]✗ LLD DRIFT — changed but not in the ADR[/bold red] ({len(result['drift'])}):")
        for f in result["drift"]:
            console.print(f"    [red]{f}[/red]  [dim]← reviewer should ask why[/dim]")

    if result["reads_outside_scope"]:
        console.print(f"\n[dim]· Read outside scope (informational, {len(result['reads_outside_scope'])}): "
                      f"{', '.join(result['reads_outside_scope'])}[/dim]")

    console.print()
    if result["faithful"]:
        console.print("[bold green]Verdict: the path stayed faithful to the plan.[/bold green]")
    else:
        console.print("[bold red]Verdict: the implementation drifted from the plan. "
                      "Surface the drift for human review.[/bold red]")
    console.print()
    sys.exit(0 if result["faithful"] else 1)


if __name__ == "__main__":
    main()
