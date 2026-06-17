#!/usr/bin/env python3
"""
Start the Eagle Tracker server.

Run from the project root (the directory that contains backend/ and frontend/):

    python run_server.py               # production  — serves pre-built frontend
    python run_server.py --dev         # development — enables uvicorn --reload
    python run_server.py --port 8080   # custom port
"""
import argparse
import os
import sys

# Ensure the project root is on sys.path so `import backend` resolves correctly
# regardless of which directory the user invoked this script from.
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import uvicorn  # noqa: E402 — must come after sys.path fix


def main() -> None:
    parser = argparse.ArgumentParser(description="Eagle Tracker server")
    parser.add_argument("--host",  default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port",  default=9090, type=int, help="Bind port (default: 9090)")
    parser.add_argument("--dev",   action="store_true", help="Enable auto-reload (development)")
    args = parser.parse_args()

    # Change to the project root so relative paths inside the app (static/,
    # videos/, logs/) resolve correctly.
    os.chdir(ROOT)

    uvicorn.run(
        "backend.main:app",
        host=args.host,
        port=args.port,
        reload=args.dev,
        reload_dirs=["backend"] if args.dev else None,
    )


if __name__ == "__main__":
    main()
