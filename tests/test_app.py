"""
Tests for the FastAPI app (src/app.py) — the /health and /sessions endpoints.
"""

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.app import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "service": "cursor-session-tracer"}


def test_root_is_health_alias():
    # "/" is registered as a health alias before the MCP mount.
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_sessions_shape():
    resp = client.get("/sessions")
    assert resp.status_code == 200
    body = resp.json()
    assert "sessions" in body and "total" in body
    assert isinstance(body["sessions"], list)
    assert body["total"] == len(body["sessions"])


def test_sessions_include_adr_id_field():
    """Every listed session exposes the adr_id link field (plan ↔ path)."""
    body = client.get("/sessions").json()
    for s in body["sessions"]:
        assert "adr_id" in s
        assert "session_id" in s
        assert "cursor_stats" in s


def test_sessions_lists_committed_sample():
    """The committed sample trace(s) should be discoverable via the endpoint."""
    body = client.get("/sessions").json()
    ids = {s["session_id"] for s in body["sessions"]}
    # At least one committed sample ships with the repo.
    assert {"a1b2c3d4", "dde097e6"} & ids, f"expected a committed sample in {ids}"
