"""
cursor_db.py — reads Cursor IDE's local SQLite database to extract:
  - Active composer session ID and model name
  - Per-session token counts (inputTokens / outputTokens) from bubbleId rows

Database location (macOS):
  ~/Library/Application Support/Cursor/User/globalStorage/state.vscdb

Key tables:
  ItemTable      — key/value (auth tokens, model preferences, extension state)
  cursorDiskKV   — composer sessions and per-message blobs (JSON, not protobuf)

Relevant key patterns in cursorDiskKV:
  composerData:<composerId>           — session metadata, modelConfig.modelName
  bubbleId:<composerId>:<messageId>   — per-message data, tokenCount.inputTokens/outputTokens
"""

import json
import sqlite3
from pathlib import Path
from typing import Optional

CURSOR_DB = (
    Path.home()
    / "Library"
    / "Application Support"
    / "Cursor"
    / "User"
    / "globalStorage"
    / "state.vscdb"
)


def _connect() -> Optional[sqlite3.Connection]:
    if not CURSOR_DB.exists():
        return None
    try:
        return sqlite3.connect(f"file:{CURSOR_DB}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        return None


def get_active_composer() -> Optional[dict]:
    """
    Returns the most recently active Cursor composer session.

    Scans composerData rows in reverse insertion order and returns the first
    one that has a non-empty modelName. This heuristic works well when the
    user has a single Cursor window open; with multiple windows it returns
    whichever window was most recently active.

    Returns:
        {"composer_id": str, "model": str} or None if DB unavailable.
    """
    con = _connect()
    if not con:
        return None
    try:
        rows = con.execute(
            "SELECT key, value FROM cursorDiskKV "
            "WHERE key LIKE 'composerData:%' "
            "ORDER BY rowid DESC LIMIT 30"
        ).fetchall()
        for key, value in rows:
            try:
                data = json.loads(value)
                # key format: composerData:<composerId>|<size> or composerData:<composerId>
                composer_id = key.split(":", 1)[1].split("|")[0]
                model = data.get("modelConfig", {}).get("modelName", "")
                if model:
                    return {"composer_id": composer_id, "model": model}
            except (json.JSONDecodeError, IndexError):
                continue
        return None
    finally:
        con.close()


def get_model_for_composer(composer_id: str) -> Optional[str]:
    """
    Returns the current modelName for a given composerId.
    Used by append_trace to detect mid-session model switches.
    """
    con = _connect()
    if not con:
        return None
    try:
        rows = con.execute(
            "SELECT value FROM cursorDiskKV WHERE key LIKE ? LIMIT 1",
            (f"composerData:{composer_id}%",),
        ).fetchall()
        if rows:
            data = json.loads(rows[0][0])
            return data.get("modelConfig", {}).get("modelName") or None
        return None
    except (json.JSONDecodeError, sqlite3.OperationalError):
        return None
    finally:
        con.close()


def get_token_counts(composer_id: str, since_iso: str) -> dict:
    """
    Sums inputTokens and outputTokens for all assistant turns (type=2) in a
    composer session that were created at or after since_iso.

    Args:
        composer_id: The Cursor composer session UUID.
        since_iso:   ISO 8601 timestamp (start_trace started_at). String
                     comparison works because Cursor stores ISO strings.

    Returns:
        {"tokens_in": int, "tokens_out": int}
    """
    con = _connect()
    if not con:
        return {"tokens_in": 0, "tokens_out": 0}
    try:
        rows = con.execute(
            "SELECT value FROM cursorDiskKV WHERE key LIKE ?",
            (f"bubbleId:{composer_id}:%",),
        ).fetchall()
        tokens_in = 0
        tokens_out = 0
        for (value,) in rows:
            try:
                data = json.loads(value)
                # Only count assistant turns (type=2); human turns are always 0/0
                if data.get("type") != 2:
                    continue
                created_at = data.get("createdAt", "")
                if created_at < since_iso:
                    continue
                tc = data.get("tokenCount", {})
                tokens_in += tc.get("inputTokens", 0)
                tokens_out += tc.get("outputTokens", 0)
            except (json.JSONDecodeError, TypeError):
                continue
        return {"tokens_in": tokens_in, "tokens_out": tokens_out}
    except sqlite3.OperationalError:
        return {"tokens_in": 0, "tokens_out": 0}
    finally:
        con.close()
