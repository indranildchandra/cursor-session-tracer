#!/usr/bin/env bash
# Start the cursor-session-tracer MCP + FastAPI server

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d ".venv" ]; then
  echo "ERROR: .venv not found. Run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi

echo "Starting cursor-session-tracer on http://127.0.0.1:8080"
echo "  MCP endpoint:     http://127.0.0.1:8080/mcp"
echo "  Health:           http://127.0.0.1:8080/health"
echo "  Sessions list:    http://127.0.0.1:8080/sessions"
echo ""

.venv/bin/uvicorn src.app:app --host 127.0.0.1 --port 8080 --reload
