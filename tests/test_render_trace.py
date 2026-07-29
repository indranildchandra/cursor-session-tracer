"""
Unit tests for render_trace.py — tree builder and Mermaid renderer.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from render_trace import _escape_mermaid, build_event_tree, render_mermaid


# ---------------------------------------------------------------------------
# Sample fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def simple_events():
    return [
        {
            "step_id": "step_001",
            "parent_step_id": None,
            "type": "decision",
            "timestamp": "2026-05-09T14:32:18Z",
            "reason": "charge() has no idempotency key; a retry double-charges. Introducing a resilient transport.",
            "files_read": ["src/auth.py"],
            "files_modified": [],
            "files_created": [],
            "files_deleted": [],
            "notes": "",
        },
        {
            "step_id": "step_002",
            "parent_step_id": "step_001",
            "type": "file_modify",
            "timestamp": "2026-05-09T14:33:45Z",
            "reason": "Adding idempotency key before the retry loop so a retry reuses it.",
            "files_read": ["src/auth.py"],
            "files_modified": ["src/auth.py"],
            "files_created": [],
            "files_deleted": [],
            "notes": "",
        },
        {
            "step_id": "step_003",
            "parent_step_id": "step_002",
            "type": "file_modify",
            "timestamp": "2026-05-09T14:35:02Z",
            "reason": "Routing the receipt call through the same transport for consistent backoff.",
            "files_read": ["src/clients/github.py"],
            "files_modified": ["src/clients/github.py"],
            "files_created": [],
            "files_deleted": [],
            "notes": "",
        },
    ]


@pytest.fixture
def orphan_events():
    return [
        {
            "step_id": "step_001",
            "parent_step_id": None,
            "type": "decision",
            "timestamp": "2026-05-09T14:32:18Z",
            "reason": "Root decision",
            "files_read": [], "files_modified": [], "files_created": [], "files_deleted": [],
            "notes": "",
        },
        {
            "step_id": "step_003",
            "parent_step_id": "step_002",  # step_002 does not exist — orphan
            "type": "file_modify",
            "timestamp": "2026-05-09T14:35:02Z",
            "reason": "Orphaned event",
            "files_read": [], "files_modified": ["src/foo.py"], "files_created": [], "files_deleted": [],
            "notes": "",
        },
    ]


@pytest.fixture
def sample_data(simple_events):
    return {
        "session": {
            "session_id": "a1b2c3d4",
            "slug": "refactor_auth_clients",
            "task": "Refactor all API clients to use new token-based auth pattern",
            "started_at": "2026-05-09T14:32:01Z",
            "ended_at": "2026-05-09T15:14:32Z",
            "outcome": "completed",
            "repo_snapshot": ["src/auth.py", "src/clients/github.py"],
            "cursor_stats": {
                "model": "claude-sonnet-4-5",
                "tool_call_count": 3,
                "tokens_in": 12000,
                "tokens_out": 3400,
                "cost_usd": 0.0421,
            },
        },
        "events": simple_events,
    }


# ---------------------------------------------------------------------------
# build_event_tree
# ---------------------------------------------------------------------------

def test_build_event_tree_root_children(simple_events):
    tree = build_event_tree(simple_events)
    assert len(tree[None]) == 1
    assert tree[None][0]["step_id"] == "step_001"


def test_build_event_tree_child_chain(simple_events):
    tree = build_event_tree(simple_events)
    assert tree["step_001"][0]["step_id"] == "step_002"
    assert tree["step_002"][0]["step_id"] == "step_003"
    assert tree["step_003"] == []


def test_build_event_tree_orphan_attached_to_root(orphan_events):
    tree = build_event_tree(orphan_events)
    root_children = tree[None]
    assert len(root_children) == 2
    orphan = next(e for e in root_children if e["step_id"] == "step_003")
    assert orphan.get("_orphan") is True


def test_build_event_tree_empty():
    tree = build_event_tree([])
    assert tree[None] == []


# ---------------------------------------------------------------------------
# _escape_mermaid
# ---------------------------------------------------------------------------

def test_escape_mermaid_truncates():
    long_text = "a" * 100
    result = _escape_mermaid(long_text, max_len=50)
    assert len(result) <= 51  # 50 chars + ellipsis
    assert result.endswith("…")


def test_escape_mermaid_no_truncate_when_short():
    text = "short text"
    result = _escape_mermaid(text, max_len=50)
    assert result == "short text"


def test_escape_mermaid_replaces_quotes():
    result = _escape_mermaid('he said "hello"')
    assert '"' not in result


def test_escape_mermaid_replaces_brackets():
    result = _escape_mermaid("use [this] not [that]")
    assert "[" not in result
    assert "]" not in result


# ---------------------------------------------------------------------------
# render_mermaid
# ---------------------------------------------------------------------------

def test_render_mermaid_produces_flowchart(sample_data):
    output = render_mermaid(sample_data)
    assert output.startswith("flowchart TD")


def test_render_mermaid_contains_root(sample_data):
    output = render_mermaid(sample_data)
    assert "ROOT" in output


def test_render_mermaid_contains_all_steps(sample_data):
    output = render_mermaid(sample_data)
    assert "step001" in output
    assert "step002" in output
    assert "step003" in output


def test_render_mermaid_max_nodes_truncates(sample_data):
    output = render_mermaid(sample_data, max_nodes=2)
    assert "step003" not in output
    assert "TRUNCATED" in output


def test_render_mermaid_no_truncation_when_within_limit(sample_data):
    output = render_mermaid(sample_data, max_nodes=10)
    assert "TRUNCATED" not in output


def test_render_mermaid_arrows(sample_data):
    output = render_mermaid(sample_data)
    assert "-->" in output


def test_render_mermaid_decision_node_single_quoted(sample_data):
    """Regression: decision nodes must be ["…"] not [""…""] (malformed Mermaid)."""
    output = render_mermaid(sample_data)  # step_001 is a decision
    assert 'step001[""' not in output
    assert 'step001["' in output


# ---------------------------------------------------------------------------
# render_trace.py CLI (in-process, via click's CliRunner)
# ---------------------------------------------------------------------------

import render_trace as rt
from click.testing import CliRunner


def _write_session(tmp_path, monkeypatch, data, filename="143201_x.json"):
    """Point TRACES_ROOT at a tmp dir holding one session, return its --session arg."""
    root = tmp_path / ".cursor" / "traces"
    sess_dir = root / "20260509" / "a1b2c3d4"
    sess_dir.mkdir(parents=True)
    (sess_dir / filename).write_text(json.dumps(data))
    monkeypatch.setattr(rt, "TRACES_ROOT", root)
    return "20260509/a1b2c3d4"


def test_cli_terminal_mode_ok(tmp_path, sample_data, monkeypatch):
    session = _write_session(tmp_path, monkeypatch, sample_data)
    result = CliRunner().invoke(rt.main, ["--session", session])
    assert result.exit_code == 0, result.output
    assert "SESSION a1b2c3d4" in result.output


def test_cli_mermaid_mode_does_not_crash(tmp_path, monkeypatch):
    """Regression: Mermaid node shapes ([/…/], ["…"]) must not be parsed as Rich markup."""
    data = {
        "session": {
            "session_id": "a1b2c3d4", "slug": "s", "task": "t",
            "started_at": "2026-05-09T14:32:01Z", "ended_at": None, "outcome": None,
            "repo_snapshot": [], "cursor_stats": {},
        },
        "events": [
            {"step_id": "step_001", "parent_step_id": None, "type": "file_create",
             "timestamp": "2026-05-09T14:32:18Z", "reason": "Create demo/resilience.py transport",
             "files_read": [], "files_modified": [], "files_created": ["demo/resilience.py"],
             "files_deleted": [], "notes": ""},
        ],
    }
    session = _write_session(tmp_path, monkeypatch, data)
    result = CliRunner().invoke(rt.main, ["--session", session, "--mode", "mermaid"])
    assert result.exit_code == 0, result.output
    assert "flowchart TD" in result.output
    assert (tmp_path / ".cursor" / "traces" / "20260509" / "a1b2c3d4" / "diagram.mermaid").exists()


def test_cli_terminal_handles_brackets_in_task(tmp_path, sample_data, monkeypatch):
    """Free-text task with [brackets] must not break Rich markup parsing."""
    data = json.loads(json.dumps(sample_data))
    data["session"]["task"] = "Refactor [auth] and fix [BUG-123] in the flow"
    session = _write_session(tmp_path, monkeypatch, data)
    result = CliRunner().invoke(rt.main, ["--session", session])
    assert result.exit_code == 0, result.output
    assert "BUG-123" in result.output
