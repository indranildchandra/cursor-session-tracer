"""
Unit tests for MCP tool functions in src/mcp_server.py.
Tests call the underlying Python functions directly — no HTTP, no Cursor.

cursor_db is monkeypatched throughout:
  - get_active_composer  → returns a fake composer_id + model
  - get_model_for_composer → returns the same model (no mid-session switch)
  - get_token_counts     → returns fake token counts
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import src.file_utils as fu
import src.mcp_server as ms
from src.mcp_server import append_trace, end_trace, start_trace

FAKE_COMPOSER = {"composer_id": "abc12345-fake", "model": "claude-sonnet-4-6"}
FAKE_TOKENS = {"tokens_in": 12000, "tokens_out": 3500}


@pytest.fixture(autouse=True)
def patch_all(tmp_path, monkeypatch):
    """Redirect trace I/O to a temp dir and stub out all cursor_db calls."""
    monkeypatch.setattr(fu, "TRACES_ROOT", tmp_path / ".cursor" / "traces")
    monkeypatch.setattr(ms, "get_active_composer", lambda: FAKE_COMPOSER)
    monkeypatch.setattr(ms, "get_model_for_composer", lambda cid: FAKE_COMPOSER["model"])
    monkeypatch.setattr(ms, "get_token_counts", lambda cid, since: FAKE_TOKENS)


# ---------------------------------------------------------------------------
# start_trace
# ---------------------------------------------------------------------------

def test_start_trace_returns_session_id_and_path():
    result = start_trace(
        task_description="Refactor all API clients to use new token auth",
        files_in_scope=["src/auth.py", "src/clients/github.py"],
    )
    assert "session_id" in result
    assert len(result["session_id"]) == 8
    assert "trace_file_path" in result
    assert result["trace_file_path"].endswith(".json")


def test_start_trace_creates_json_file():
    result = start_trace(
        task_description="Add logging to the payment service",
        files_in_scope=["src/payment.py"],
    )
    assert Path(result["trace_file_path"]).exists()


def test_start_trace_json_structure():
    result = start_trace(
        task_description="Fix bug in auth middleware",
        files_in_scope=["src/middleware.py", "src/auth.py"],
    )
    data = json.loads(Path(result["trace_file_path"]).read_text())
    sess = data["session"]
    assert sess["session_id"] == result["session_id"]
    assert sess["task"] == "Fix bug in auth middleware"
    assert sess["ended_at"] is None
    assert sess["outcome"] is None
    assert sess["repo_snapshot"] == ["src/middleware.py", "src/auth.py"]
    assert data["events"] == []


def test_start_trace_cursor_stats_auto_populated():
    result = start_trace("Test task", [])
    data = json.loads(Path(result["trace_file_path"]).read_text())
    stats = data["session"]["cursor_stats"]
    assert stats["tool_call_count"] == 0
    assert stats["model"] == "claude-sonnet-4-6"
    assert stats["composer_id"] == "abc12345-fake"
    assert stats["tokens_in"] is None  # populated at end_trace


def test_start_trace_slug_in_filename():
    result = start_trace("Migrate database schema to postgres", ["db/schema.sql"])
    assert "migrate_database_schema_to_postgres" in result["trace_file_path"]


def test_start_trace_no_cursor_db(monkeypatch):
    """If cursor_db is unavailable, model and composer_id fall back to None gracefully."""
    monkeypatch.setattr(ms, "get_active_composer", lambda: None)
    result = start_trace("Task with no DB", [])
    data = json.loads(Path(result["trace_file_path"]).read_text())
    stats = data["session"]["cursor_stats"]
    assert stats["model"] is None
    assert stats["composer_id"] is None


def test_start_trace_adr_id_none_by_default():
    result = start_trace("Task with no ADR", ["src/x.py"])
    data = json.loads(Path(result["trace_file_path"]).read_text())
    assert data["session"]["adr_id"] is None


def test_start_trace_links_adr_id():
    """When an adr_id is passed, the trace records which ADR it implements."""
    result = start_trace(
        "Implement resilient idempotent checkout",
        ["demo/resilience.py"],
        adr_id="ADR-0001",
    )
    data = json.loads(Path(result["trace_file_path"]).read_text())
    assert data["session"]["adr_id"] == "ADR-0001"


# ---------------------------------------------------------------------------
# append_trace
# ---------------------------------------------------------------------------

@pytest.fixture
def active_session():
    return start_trace(
        task_description="Refactor API clients",
        files_in_scope=["src/auth.py", "src/clients/github.py"],
    )


def test_append_trace_returns_step_id(active_session):
    result = append_trace(
        session_id=active_session["session_id"],
        type="decision",
        reason="charge() is not idempotent; a retry double-charges. Routing it through resilience.py.",
        files_read=["src/auth.py"],
        files_modified=[],
        files_created=[],
        files_deleted=[],
        parent_step_id="",
    )
    assert result == {"step_id": "step_001"}


def test_append_trace_increments_step_id(active_session):
    sid = active_session["session_id"]
    r1 = append_trace(
        session_id=sid, type="decision", reason="First decision",
        files_read=[], files_modified=[], files_created=[], files_deleted=[],
        parent_step_id="",
    )
    r2 = append_trace(
        session_id=sid, type="file_modify", reason="Modify auth.py",
        files_read=[], files_modified=["src/auth.py"], files_created=[], files_deleted=[],
        parent_step_id=r1["step_id"],
    )
    assert r1["step_id"] == "step_001"
    assert r2["step_id"] == "step_002"


def test_append_trace_writes_event_to_file(active_session):
    sid = active_session["session_id"]
    append_trace(
        session_id=sid, type="decision",
        reason="Choosing BearerTokenAuth because downstream clients need .headers",
        files_read=["src/auth.py"], files_modified=[], files_created=[], files_deleted=[],
        parent_step_id="",
    )
    data = json.loads(Path(active_session["trace_file_path"]).read_text())
    assert len(data["events"]) == 1
    event = data["events"][0]
    assert event["step_id"] == "step_001"
    assert event["type"] == "decision"
    assert event["files_read"] == ["src/auth.py"]


def test_append_trace_parent_step_id_stored(active_session):
    sid = active_session["session_id"]
    r1 = append_trace(
        session_id=sid, type="decision", reason="Root decision",
        files_read=[], files_modified=[], files_created=[], files_deleted=[],
        parent_step_id="",
    )
    r2 = append_trace(
        session_id=sid, type="file_modify", reason="Child action",
        files_read=[], files_modified=["src/auth.py"], files_created=[], files_deleted=[],
        parent_step_id=r1["step_id"],
    )
    data = json.loads(Path(active_session["trace_file_path"]).read_text())
    child_event = next(e for e in data["events"] if e["step_id"] == r2["step_id"])
    assert child_event["parent_step_id"] == "step_001"


def test_append_trace_increments_tool_call_count(active_session):
    sid = active_session["session_id"]
    for _ in range(3):
        append_trace(
            session_id=sid, type="file_read", reason="Reading file",
            files_read=["src/auth.py"], files_modified=[], files_created=[], files_deleted=[],
            parent_step_id="",
        )
    data = json.loads(Path(active_session["trace_file_path"]).read_text())
    assert data["session"]["cursor_stats"]["tool_call_count"] == 3


def test_append_trace_model_override_logged_on_switch(active_session, monkeypatch):
    """When model changes mid-session, the event gets a model_override field."""
    monkeypatch.setattr(ms, "get_model_for_composer", lambda cid: "claude-opus-4-6")
    sid = active_session["session_id"]
    append_trace(
        session_id=sid, type="decision", reason="Mid-session model switch",
        files_read=[], files_modified=[], files_created=[], files_deleted=[],
        parent_step_id="",
    )
    data = json.loads(Path(active_session["trace_file_path"]).read_text())
    event = data["events"][0]
    assert event.get("model_override") == "claude-opus-4-6"


def test_append_trace_no_model_override_when_same(active_session):
    """When model is unchanged, no model_override field is written."""
    sid = active_session["session_id"]
    append_trace(
        session_id=sid, type="decision", reason="Same model throughout",
        files_read=[], files_modified=[], files_created=[], files_deleted=[],
        parent_step_id="",
    )
    data = json.loads(Path(active_session["trace_file_path"]).read_text())
    assert "model_override" not in data["events"][0]


def test_append_trace_unknown_session_raises():
    with pytest.raises(FileNotFoundError):
        append_trace(
            session_id="00000000", type="decision", reason="x",
            files_read=[], files_modified=[], files_created=[], files_deleted=[],
            parent_step_id="",
        )


# ---------------------------------------------------------------------------
# end_trace
# ---------------------------------------------------------------------------

def test_end_trace_writes_ended_at_and_outcome(active_session):
    sid = active_session["session_id"]
    end_trace(session_id=sid, outcome="completed")
    data = json.loads(Path(active_session["trace_file_path"]).read_text())
    assert data["session"]["outcome"] == "completed"
    assert data["session"]["ended_at"] is not None


def test_end_trace_returns_trace_file_path(active_session):
    result = end_trace(session_id=active_session["session_id"], outcome="partial")
    assert "trace_file_path" in result
    assert result["trace_file_path"].endswith(".json")


def test_end_trace_auto_populates_tokens(active_session):
    sid = active_session["session_id"]
    result = end_trace(session_id=sid, outcome="completed")
    data = json.loads(Path(active_session["trace_file_path"]).read_text())
    stats = data["session"]["cursor_stats"]
    assert stats["tokens_in"] == FAKE_TOKENS["tokens_in"]
    assert stats["tokens_out"] == FAKE_TOKENS["tokens_out"]
    assert result["tokens_in"] == FAKE_TOKENS["tokens_in"]
    assert result["tokens_out"] == FAKE_TOKENS["tokens_out"]


def test_end_trace_tokens_null_when_no_composer(monkeypatch):
    """If cursor_db returned no composer_id, tokens stay None."""
    monkeypatch.setattr(ms, "get_active_composer", lambda: None)
    sess = start_trace("No DB task", [])
    end_trace(session_id=sess["session_id"], outcome="aborted")
    data = json.loads(Path(sess["trace_file_path"]).read_text())
    stats = data["session"]["cursor_stats"]
    assert stats["tokens_in"] is None
    assert stats["tokens_out"] is None


def test_end_trace_invalid_outcome_raises(active_session):
    with pytest.raises(ValueError, match="outcome must be one of"):
        end_trace(session_id=active_session["session_id"], outcome="done")


def test_end_trace_unknown_session_raises():
    with pytest.raises(FileNotFoundError):
        end_trace(session_id="00000000", outcome="completed")


# ---------------------------------------------------------------------------
# Full lifecycle integration test
# ---------------------------------------------------------------------------

def test_full_session_lifecycle():
    """start → append x3 → end → verify JSON including auto token counts."""
    r0 = start_trace(
        task_description="Migrate database schema to use UUIDs",
        files_in_scope=["db/schema.sql", "src/models.py", "src/migrations/001.py"],
    )
    sid = r0["session_id"]

    r1 = append_trace(
        session_id=sid, type="decision",
        reason="schema.sql uses integer PKs. Migrating to UUID requires changes in models.py and migration script.",
        files_read=["db/schema.sql"], files_modified=[], files_created=[], files_deleted=[],
        parent_step_id="",
    )
    r2 = append_trace(
        session_id=sid, type="file_modify",
        reason="Updating User model to use UUID primary key instead of auto-increment int.",
        files_read=["src/models.py"], files_modified=["src/models.py"], files_created=[], files_deleted=[],
        parent_step_id=r1["step_id"],
    )
    append_trace(
        session_id=sid, type="file_create",
        reason="Creating migration 002.py to ALTER TABLE users and backfill UUID values.",
        files_read=[], files_modified=[], files_created=["src/migrations/002.py"], files_deleted=[],
        parent_step_id=r2["step_id"],
    )

    end_result = end_trace(session_id=sid, outcome="completed")

    data = json.loads(Path(end_result["trace_file_path"]).read_text())
    assert len(data["events"]) == 3
    assert data["session"]["outcome"] == "completed"
    assert data["session"]["cursor_stats"]["model"] == "claude-sonnet-4-6"
    assert data["session"]["cursor_stats"]["tokens_in"] == FAKE_TOKENS["tokens_in"]
    assert data["session"]["cursor_stats"]["tokens_out"] == FAKE_TOKENS["tokens_out"]

    # Verify parent chain
    step_ids = [e["step_id"] for e in data["events"]]
    parent_ids = [e["parent_step_id"] for e in data["events"]]
    assert step_ids == ["step_001", "step_002", "step_003"]
    assert parent_ids[0] is None
    assert parent_ids[1] == "step_001"
    assert parent_ids[2] == "step_002"
