"""
File utilities for cursor-session-tracer.
Handles slug generation, path resolution, and JSON read/write.
"""

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path


TRACES_ROOT = Path(".cursor/traces")


def generate_session_id() -> str:
    return str(uuid.uuid4())[:8]


def generate_slug(task_description: str) -> str:
    """First 5 words of task, lowercased, underscored, non-alphanumeric stripped."""
    words = task_description.strip().split()[:5]
    slug = "_".join(re.sub(r"[^a-z0-9]", "", w.lower()) for w in words)
    return slug or "unnamed_task"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_date_dir() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def get_time_prefix() -> str:
    return datetime.now(timezone.utc).strftime("%H%M%S")


def build_trace_path(date_dir: str, session_id: str, slug: str, time_prefix: str) -> Path:
    return TRACES_ROOT / date_dir / session_id / f"{time_prefix}_{slug}.json"


def resolve_trace_path(session_id: str) -> Path:
    """
    Scan .cursor/traces for the session directory and return the most recent JSON file.
    Raises FileNotFoundError if not found.
    """
    session_dirs = list(TRACES_ROOT.glob(f"*/{session_id}"))
    if not session_dirs:
        raise FileNotFoundError(f"No trace directory found for session_id={session_id!r}")
    session_dir = session_dirs[0]
    json_files = sorted(session_dir.glob("*.json"))
    if not json_files:
        raise FileNotFoundError(f"No JSON files in trace directory: {session_dir}")
    return json_files[-1]  # most recent


def read_trace(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_trace(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def next_step_id(events: list) -> str:
    return f"step_{len(events) + 1:03d}"
