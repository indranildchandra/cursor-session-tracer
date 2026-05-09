"""
Unit tests for src/file_utils.py
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Make src importable without install
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.file_utils import (
    build_trace_path,
    generate_session_id,
    generate_slug,
    next_step_id,
    now_iso,
    read_trace,
    resolve_trace_path,
    write_trace,
)


# ---------------------------------------------------------------------------
# generate_session_id
# ---------------------------------------------------------------------------

def test_session_id_is_8_chars():
    sid = generate_session_id()
    assert len(sid) == 8


def test_session_id_is_hex():
    sid = generate_session_id()
    int(sid, 16)  # should not raise


def test_session_id_unique():
    ids = {generate_session_id() for _ in range(100)}
    assert len(ids) == 100


# ---------------------------------------------------------------------------
# generate_slug
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("desc,expected", [
    ("Refactor all API clients to use new token-based auth", "refactor_all_api_clients_to"),
    ("  fix  bug in   auth  module  ", "fix_bug_in_auth_module"),
    ("Add logging to the payment service NOW!", "add_logging_to_the_payment"),
    ("One", "one"),
    ("", "unnamed_task"),
    ("!!!###", "unnamed_task"),
])
def test_generate_slug(desc, expected):
    assert generate_slug(desc) == expected


def test_slug_strips_non_alphanumeric():
    slug = generate_slug("Fix: auth.py token-refresh bug!")
    assert all(c.isalnum() or c == "_" for c in slug)


def test_slug_max_five_words():
    desc = "one two three four five six seven eight"
    slug = generate_slug(desc)
    assert slug == "one_two_three_four_five"


# ---------------------------------------------------------------------------
# next_step_id
# ---------------------------------------------------------------------------

def test_next_step_id_empty():
    assert next_step_id([]) == "step_001"


def test_next_step_id_increments():
    events = [{"step_id": "step_001"}, {"step_id": "step_002"}]
    assert next_step_id(events) == "step_003"


def test_next_step_id_zero_padded():
    events = [{}] * 9
    assert next_step_id(events) == "step_010"


# ---------------------------------------------------------------------------
# now_iso
# ---------------------------------------------------------------------------

def test_now_iso_format():
    ts = now_iso()
    from datetime import datetime, timezone
    parsed = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
    assert parsed is not None


# ---------------------------------------------------------------------------
# build_trace_path
# ---------------------------------------------------------------------------

def test_build_trace_path():
    p = build_trace_path("20260509", "a1b2c3d4", "refactor_auth_clients", "143201")
    assert str(p) == ".cursor/traces/20260509/a1b2c3d4/143201_refactor_auth_clients.json"


# ---------------------------------------------------------------------------
# write_trace / read_trace
# ---------------------------------------------------------------------------

def test_write_read_roundtrip(tmp_path):
    trace_file = tmp_path / "test.json"
    data = {"session": {"session_id": "abc123"}, "events": []}
    write_trace(trace_file, data)
    assert trace_file.exists()
    result = read_trace(trace_file)
    assert result == data


def test_write_creates_parent_dirs(tmp_path):
    nested = tmp_path / "a" / "b" / "c" / "trace.json"
    write_trace(nested, {"x": 1})
    assert nested.exists()


def test_write_valid_json(tmp_path):
    trace_file = tmp_path / "t.json"
    data = {"session": {}, "events": [{"step_id": "step_001"}]}
    write_trace(trace_file, data)
    with open(trace_file) as f:
        parsed = json.load(f)
    assert parsed == data


# ---------------------------------------------------------------------------
# resolve_trace_path
# ---------------------------------------------------------------------------

def test_resolve_trace_path_finds_file(tmp_path, monkeypatch):
    import src.file_utils as fu
    monkeypatch.setattr(fu, "TRACES_ROOT", tmp_path)

    session_id = "deadbeef"
    session_dir = tmp_path / "20260509" / session_id
    session_dir.mkdir(parents=True)
    trace_file = session_dir / "143201_test_task.json"
    trace_file.write_text("{}")

    result = fu.resolve_trace_path(session_id)
    assert result == trace_file


def test_resolve_trace_path_returns_most_recent(tmp_path, monkeypatch):
    import src.file_utils as fu
    monkeypatch.setattr(fu, "TRACES_ROOT", tmp_path)

    session_id = "cafebabe"
    session_dir = tmp_path / "20260509" / session_id
    session_dir.mkdir(parents=True)
    (session_dir / "120000_first.json").write_text("{}")
    (session_dir / "150000_second.json").write_text("{}")

    result = fu.resolve_trace_path(session_id)
    assert result.name == "150000_second.json"


def test_resolve_trace_path_raises_if_missing(tmp_path, monkeypatch):
    import src.file_utils as fu
    monkeypatch.setattr(fu, "TRACES_ROOT", tmp_path)

    with pytest.raises(FileNotFoundError):
        fu.resolve_trace_path("nonexistent")
