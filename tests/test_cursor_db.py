"""
Unit tests for src/cursor_db.py — Cursor SQLite usage auto-capture.

These build a throwaway SQLite database matching Cursor's cursorDiskKV schema
and point cursor_db at it via the CURSOR_DB_PATH override, so no real Cursor
install is required. Also covers per-platform path resolution and the graceful
degradation path when no DB is present.
"""

import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import src.cursor_db as cdb


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

def test_env_override_wins(monkeypatch):
    monkeypatch.setenv("CURSOR_DB_PATH", "/tmp/custom/state.vscdb")
    assert cdb._cursor_db_path() == Path("/tmp/custom/state.vscdb")


def test_macos_default_path(monkeypatch):
    monkeypatch.delenv("CURSOR_DB_PATH", raising=False)
    monkeypatch.setattr(sys, "platform", "darwin")
    p = cdb._cursor_db_path()
    assert p.parts[-4:] == ("Cursor", "User", "globalStorage", "state.vscdb")
    assert "Application Support" in str(p)


def test_linux_default_path(monkeypatch):
    monkeypatch.delenv("CURSOR_DB_PATH", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setattr(sys, "platform", "linux")
    p = cdb._cursor_db_path()
    assert str(p).endswith(".config/Cursor/User/globalStorage/state.vscdb")


def test_windows_default_path(monkeypatch):
    monkeypatch.delenv("CURSOR_DB_PATH", raising=False)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", "C:\\Users\\x\\AppData\\Roaming")
    p = cdb._cursor_db_path()
    assert p.name == "state.vscdb"
    assert "Cursor" in p.parts


# ---------------------------------------------------------------------------
# Graceful degradation — no DB present
# ---------------------------------------------------------------------------

def test_missing_db_returns_none(monkeypatch, tmp_path):
    monkeypatch.setenv("CURSOR_DB_PATH", str(tmp_path / "does_not_exist.vscdb"))
    assert cdb.get_active_composer() is None
    assert cdb.get_model_for_composer("anything") is None
    assert cdb.get_token_counts("anything", "2026-01-01T00:00:00Z") == {
        "tokens_in": 0,
        "tokens_out": 0,
    }


# ---------------------------------------------------------------------------
# Real SQLite fixture matching Cursor's cursorDiskKV schema
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_cursor_db(tmp_path, monkeypatch):
    db_path = tmp_path / "state.vscdb"
    con = sqlite3.connect(db_path)
    con.execute("CREATE TABLE cursorDiskKV (key TEXT PRIMARY KEY, value TEXT)")

    composer_id = "abc12345-fake-composer"
    con.execute(
        "INSERT INTO cursorDiskKV (key, value) VALUES (?, ?)",
        (
            f"composerData:{composer_id}",
            json.dumps({"modelConfig": {"modelName": "claude-sonnet-4-6"}}),
        ),
    )
    # Assistant turn (type=2) after the session start — counted
    con.execute(
        "INSERT INTO cursorDiskKV (key, value) VALUES (?, ?)",
        (
            f"bubbleId:{composer_id}:m1",
            json.dumps(
                {"type": 2, "createdAt": "2026-05-09T15:00:00Z",
                 "tokenCount": {"inputTokens": 1000, "outputTokens": 300}}
            ),
        ),
    )
    # Assistant turn before the session start — excluded by since filter
    con.execute(
        "INSERT INTO cursorDiskKV (key, value) VALUES (?, ?)",
        (
            f"bubbleId:{composer_id}:m0",
            json.dumps(
                {"type": 2, "createdAt": "2026-05-09T10:00:00Z",
                 "tokenCount": {"inputTokens": 9999, "outputTokens": 9999}}
            ),
        ),
    )
    # Human turn (type=1) — never counted even if after start
    con.execute(
        "INSERT INTO cursorDiskKV (key, value) VALUES (?, ?)",
        (
            f"bubbleId:{composer_id}:m2",
            json.dumps(
                {"type": 1, "createdAt": "2026-05-09T15:01:00Z",
                 "tokenCount": {"inputTokens": 500, "outputTokens": 0}}
            ),
        ),
    )
    con.commit()
    con.close()

    monkeypatch.setenv("CURSOR_DB_PATH", str(db_path))
    return composer_id


def test_get_active_composer(fake_cursor_db):
    result = cdb.get_active_composer()
    assert result == {"composer_id": fake_cursor_db, "model": "claude-sonnet-4-6"}


def test_get_model_for_composer(fake_cursor_db):
    assert cdb.get_model_for_composer(fake_cursor_db) == "claude-sonnet-4-6"


def test_get_token_counts_respects_since_and_type(fake_cursor_db):
    # Only the single assistant turn at 15:00 counts (10:00 is before start,
    # human turn at 15:01 is type=1).
    counts = cdb.get_token_counts(fake_cursor_db, "2026-05-09T14:00:00Z")
    assert counts == {"tokens_in": 1000, "tokens_out": 300}


def test_get_token_counts_since_excludes_all(fake_cursor_db):
    counts = cdb.get_token_counts(fake_cursor_db, "2026-05-09T20:00:00Z")
    assert counts == {"tokens_in": 0, "tokens_out": 0}
