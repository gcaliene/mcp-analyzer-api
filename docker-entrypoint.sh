#!/bin/bash
set -e

# Start the github_analysis server (port 8000 by default)
uv run -m servers.github_analysis.server &

# Wait for the server to start (optional: add health check or sleep)
sleep 5

# Start the FastAPI client (port 8001)
uvicorn client:app --reload --port 8001 --host 0.0.0.0 