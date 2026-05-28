#!/usr/bin/env bash
# Start the Wildlife PTZ Camera Tracker backend on Jetson Orin Nano
# Usage: ./start_server.sh [--reload]
set -e
cd "$(dirname "$0")"

RELOAD=${1:-}
exec .venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8080 $RELOAD
