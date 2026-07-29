"""
cursor_db.py — reads Cursor IDE's local SQLite database to extract:
  - Active composer session ID and model name
  - Per-session token counts (inputTokens / outputTokens) from bubbleId rows

Database location (resolved per platform by _cursor_db_path):
  macOS:   ~/Library/Application Support/Cursor/User/globalStorage/state.vscdb
  Linux:   ~/.config/Cursor/User/globalStorage/state.vscdb
  Windows: %APPDATA%/Cursor/User/globalStorage/state.vscdb

Key tables:
  ItemTable      — key/value (auth tokens, model preferences, extension state)
  cursorDiskKV   — composer sessions and per-message blobs (JSON, not protobuf)

Relevant key patterns in cursorDiskKV:
  composerData:<composerId>           — session metadata, modelConfig.modelName
  bubbleId:<composerId>:<messageId>   — per-message data, tokenCount.inputTokens/outputTokens
"""

import json
import os
import sqlite3
import sys
from pathlib import Path


def _cursor_db_path() -> Path:
    """
    Resolve Cursor's local state.vscdb path for the current platform.

    Honours the CURSOR_DB_PATH environment variable as an override (useful for
    non-standard installs, portable Cursor, or tests). Falls back to the
    platform default otherwise. The returned path may not exist — callers
    (_connect) treat a missing file as "no Cursor DB available".
    """
    override = os.environ.get("CURSOR_DB_PATH")
    if override:
        return Path(override)

    globalstorage = Path("User") / "globalStorage" / "state.vscdb"
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / "Cursor"
    elif sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA")
        base = (Path(appdata) if appdata else Path.home() / "AppData" / "Roaming") / "Cursor"
    else:  # linux and other posix
        xdg = os.environ.get("XDG_CONFIG_HOME")
        base = (Path(xdg) if xdg else Path.home() / ".config") / "Cursor"

    return base / globalstorage


# Resolved once at import; callers tolerate a missing file gracefully.
CURSOR_DB = _cursor_db_path()


def _connect() -> sqlite3.Connection | None:
    db_path = _cursor_db_path()
    if not db_path.exists():
        return None
    try:
        return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        return None


def get_active_composer() -> dict | None:
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


def get_model_for_composer(composer_id: str) -> str | None:
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
