#!/usr/bin/env bash
# Start the Ouroboros platform on port 8000. Set OFFLINE=1 to replay cached work only.
set -euo pipefail
cd "$(dirname "$0")"
PORT="${PORT:-8000}"
echo "Ouroboros platform: http://127.0.0.1:${PORT}"
exec .venv/bin/python -m uvicorn app.server:app --host 127.0.0.1 --port "$PORT"
