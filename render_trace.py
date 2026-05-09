#!/usr/bin/env python3
"""
Terminal renderer for cursor-session-tracer.

Usage:
    python render_trace.py --session 20260509/a1b2c3d4
    python render_trace.py --session 20260509/a1b2c3d4 --verbose
    python render_trace.py --session 20260509/a1b2c3d4 --files-only
    python render_trace.py --session 20260509/a1b2c3d4 --mode mermaid
"""

import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.text import Text
from rich.tree import Tree

TRACES_ROOT = Path(".cursor/traces")
console = Console()

REASON_TRUNCATE = 120  # chars for non-verbose mode
MERMAID_REASON_TRUNCATE = 50


# ---------------------------------------------------------------------------
# Tree building
# ---------------------------------------------------------------------------

def build_event_tree(events: list[dict]) -> dict:
    """
    Build a dict mapping step_id -> list of child events.
    Root events (parent_step_id is None or "") go under key None.
    Orphans (parent not found) are attached to None with [ORPHAN] prefix.
    """
    by_id = {e["step_id"]: e for e in events}
    children: dict = {None: []}

    for e in events:
        children[e["step_id"]] = []

    for e in events:
        parent = e.get("parent_step_id") or None
        if parent and parent not in by_id:
            # orphan — attach to root, flag it
            e = dict(e)
            e["_orphan"] = True
            parent = None
        children.setdefault(parent, []).append(e)

    return children


def fmt_files(label: str, files: list[str]) -> str:
    if not files:
        return f"  {label}: (none)"
    return f"  {label}: {', '.join(files)}"


# ---------------------------------------------------------------------------
# Terminal renderer
# ---------------------------------------------------------------------------

def render_terminal(data: dict, verbose: bool, files_only: bool, file_label: str) -> None:
    sess = data["session"]
    events = data["events"]
    children = build_event_tree(events)

    header = (
        f"SESSION {sess['session_id']} | {sess['slug']} | "
        f"started {sess.get('started_at', '?')} | "
        f"{sess.get('outcome') or 'in-progress'}"
    )
    if sess.get("ended_at"):
        header += f" {sess['ended_at']}"

    console.print()
    console.rule(f"[bold cyan]{file_label}[/bold cyan]")
    console.print(f"[bold]{header}[/bold]")

    stats = sess.get("cursor_stats", {})
    if any(v is not None for v in stats.values()):
        parts = []
        if stats.get("model"):
            parts.append(f"model={stats['model']}")
        if stats.get("tool_call_count") is not None:
            parts.append(f"tool_calls={stats['tool_call_count']}")
        if stats.get("tokens_in") is not None:
            parts.append(f"tokens_in={stats['tokens_in']}")
        if stats.get("tokens_out") is not None:
            parts.append(f"tokens_out={stats['tokens_out']}")
        if stats.get("cost_usd") is not None:
            parts.append(f"cost_usd=${stats['cost_usd']:.4f}")
        console.print(f"[dim]cursor_stats: {' | '.join(parts)}[/dim]")

    console.print(f"[dim]task: {sess['task']}[/dim]")
    console.print()

    if not events:
        console.print("[italic dim]No events recorded yet.[/italic dim]")
        return

    tree = Tree(f"[bold yellow]Session {sess['session_id']}[/bold yellow]")
    _add_children(tree, None, children, verbose, files_only)
    console.print(tree)


def _add_children(parent_node, parent_id, children: dict, verbose: bool, files_only: bool):
    for event in children.get(parent_id, []):
        step_id = event["step_id"]
        event_type = event["type"]
        ts = event.get("timestamp", "")
        is_orphan = event.get("_orphan", False)

        label_prefix = "[ORPHAN] " if is_orphan else ""
        color = {
            "decision": "bold green",
            "file_modify": "yellow",
            "file_create": "cyan",
            "file_delete": "red",
            "file_read": "blue",
            "tool_call": "magenta",
            "checkpoint": "bold white",
        }.get(event_type, "white")

        label = Text()
        label.append(f"{label_prefix}{step_id}", style=color)
        label.append(f" [{event_type}]  ", style="dim")
        label.append(ts[11:19] if len(ts) > 10 else ts, style="dim")

        node = parent_node.add(label)

        if not files_only:
            reason = event.get("reason", "")
            if reason:
                if not verbose and len(reason) > REASON_TRUNCATE:
                    reason = reason[:REASON_TRUNCATE] + "…"
                node.add(Text(f"reason: {reason}", style="italic"))

        read_f = event.get("files_read", [])
        mod_f = event.get("files_modified", [])
        cre_f = event.get("files_created", [])
        del_f = event.get("files_deleted", [])

        if read_f:
            node.add(Text(f"read:     {', '.join(read_f)}", style="dim blue"))
        if mod_f:
            node.add(Text(f"modified: {', '.join(mod_f)}", style="dim yellow"))
        if cre_f:
            node.add(Text(f"created:  {', '.join(cre_f)}", style="dim cyan"))
        if del_f:
            node.add(Text(f"deleted:  {', '.join(del_f)}", style="dim red"))

        if not files_only and event.get("notes"):
            node.add(Text(f"notes: {event['notes']}", style="dim"))

        _add_children(node, step_id, children, verbose, files_only)


# ---------------------------------------------------------------------------
# Mermaid renderer
# ---------------------------------------------------------------------------

def _escape_mermaid(text: str, max_len: int = MERMAID_REASON_TRUNCATE) -> str:
    truncated = text[:max_len] + ("…" if len(text) > max_len else "")
    return truncated.replace('"', "'").replace("[", "(").replace("]", ")")


def render_mermaid(data: dict, max_nodes: int = 0) -> str:
    sess = data["session"]
    events = data["events"]

    if max_nodes and len(events) > max_nodes:
        events = events[:max_nodes]
        truncated = True
    else:
        truncated = False

    lines = [
        "flowchart TD",
        f'    ROOT(["{sess["session_id"]} | {sess["slug"]}"])',
    ]
    by_id = {e["step_id"]: e for e in events}

    for event in events:
        sid = event["step_id"]
        safe_sid = sid.replace("_", "")
        label = _escape_mermaid(event.get("reason") or event["type"])
        etype = event["type"]

        shape_open, shape_close = {
            "decision": ('["', '"]'),
            "file_modify": ("(", ")"),
            "file_create": ("[/", "/]"),
            "file_delete": ("[\\", "\\]"),
            "file_read": ("[", "]"),
            "tool_call": ("{{", "}}"),
            "checkpoint": ("([", "])"),
        }.get(etype, ("[", "]"))

        lines.append(f'    {safe_sid}{shape_open}"{label}"{shape_close}')

        parent = event.get("parent_step_id") or None
        if parent and parent in by_id:
            safe_parent = parent.replace("_", "")
            lines.append(f"    {safe_parent} --> {safe_sid}")
        else:
            lines.append(f"    ROOT --> {safe_sid}")

    if truncated:
        lines.append(f'    TRUNCATED["… truncated at {max_nodes} nodes"]')

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@click.command()
@click.option("--session", required=True, help="Date/session_id, e.g. 20260509/a1b2c3d4")
@click.option("--verbose", is_flag=True, default=False, help="Print full reason text without truncation")
@click.option("--files-only", is_flag=True, default=False, help="Print only file touch summary, omit reason text")
@click.option("--mode", default="terminal", type=click.Choice(["terminal", "mermaid"]), help="Output mode")
@click.option("--max-nodes", default=0, help="(mermaid) cap node count, 0=unlimited")
def main(session: str, verbose: bool, files_only: bool, mode: str, max_nodes: int):
    """Render a cursor-session-tracer trace to terminal tree or Mermaid diagram."""
    parts = session.strip("/").split("/")
    if len(parts) != 2:
        console.print("[red]--session must be DATE/SESSION_ID, e.g. 20260509/a1b2c3d4[/red]")
        sys.exit(1)

    date_dir, session_id = parts
    session_dir = TRACES_ROOT / date_dir / session_id

    if not session_dir.exists():
        console.print(f"[red]Session directory not found: {session_dir}[/red]")
        sys.exit(1)

    json_files = sorted(session_dir.glob("*.json"))
    if not json_files:
        console.print(f"[red]No JSON files in: {session_dir}[/red]")
        sys.exit(1)

    if mode == "mermaid":
        # Merge all files' events for mermaid (restart scenario)
        all_events = []
        merged_data: dict = {}
        for jf in json_files:
            with open(jf) as f:
                d = json.load(f)
            if not merged_data:
                merged_data = d
            all_events.extend(d.get("events", []))
        merged_data["events"] = all_events
        mermaid_str = render_mermaid(merged_data, max_nodes=max_nodes)
        out_path = session_dir / "diagram.mermaid"
        out_path.write_text(mermaid_str + "\n")
        console.print(mermaid_str)
        console.print(f"\n[dim]Saved to: {out_path}[/dim]")
    else:
        for i, jf in enumerate(json_files):
            with open(jf) as f:
                data = json.load(f)
            file_label = jf.name
            if len(json_files) > 1:
                file_label += f"  [{i + 1}/{len(json_files)}]"
            render_terminal(data, verbose=verbose, files_only=files_only, file_label=file_label)


if __name__ == "__main__":
    main()
