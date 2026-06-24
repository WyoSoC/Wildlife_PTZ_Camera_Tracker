#!/usr/bin/env bash
# Wildlife PTZ Camera Tracker — all-in-one local launcher
#
# Builds the React frontend if not already built, then starts the backend
# server so the full UI is reachable at http://<jetson-ip>:9090 with no
# internet connection required.
#
# Usage:
#   ./start_client.sh            # auto-detect host, port 9090
#   ./start_client.sh --rebuild  # force a fresh frontend build
#   ./start_client.sh --port 9090
set -e
cd "$(dirname "$0")"

PORT=9090
REBUILD=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --port)    PORT="$2"; shift 2 ;;
        --rebuild) REBUILD=1; shift ;;
        *)         echo "Unknown option: $1"; exit 1 ;;
    esac
done

VENV_PYTHON=".venv/bin/python"
VENV_UVICORN=".venv/bin/uvicorn"

# ── Sanity checks ─────────────────────────────────────────────────────────────
if [[ ! -x "$VENV_PYTHON" ]]; then
    echo "ERROR: .venv not found. Run:  python3 backend/install.py"
    exit 1
fi

# ── Frontend build ────────────────────────────────────────────────────────────
STATIC_DIR="backend/static"
INDEX="$STATIC_DIR/index.html"

needs_build=0
[[ $REBUILD -eq 1 ]] && needs_build=1
[[ ! -f "$INDEX" ]] && needs_build=1

if [[ $needs_build -eq 1 ]]; then
    echo "Building frontend..."

    # Find a usable node/npm — check NVM, then PATH
    NODE=""
    NPM=""
    if [[ -f "$HOME/.nvm/nvm.sh" ]]; then
        # shellcheck disable=SC1091
        source "$HOME/.nvm/nvm.sh"
        NODE="$(which node 2>/dev/null || true)"
        NPM="$(which npm 2>/dev/null || true)"
    fi
    [[ -z "$NODE" ]] && NODE="$(which node 2>/dev/null || true)"
    [[ -z "$NPM" ]]  && NPM="$(which npm 2>/dev/null || true)"

    if [[ -z "$NODE" || -z "$NPM" ]]; then
        echo ""
        echo "ERROR: node/npm not found. Install Node 20+ first:"
        echo "  curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash"
        echo "  source ~/.nvm/nvm.sh && nvm install 20"
        echo ""
        if [[ -f "$INDEX" ]]; then
            echo "Falling back to existing frontend build."
            needs_build=0
        else
            echo "No pre-built frontend available. Server will return 404 on /."
            echo "API endpoints (/api/*) still work."
        fi
    else
        echo "  node $("$NODE" --version)   npm $("$NPM" --version)"
        echo "  Installing npm dependencies..."
        (cd frontend && "$NPM" install --silent)
        echo "  Building..."
        (cd frontend && "$NPM" run build)

        # Copy build output into backend/static/
        rm -rf "$STATIC_DIR"
        mkdir -p "$STATIC_DIR"
        cp -r frontend/dist/* "$STATIC_DIR/"
        echo "  Frontend built → $STATIC_DIR"
    fi
else
    echo "Frontend already built (use --rebuild to refresh)."
fi

# ── Detect local IP for convenience message ───────────────────────────────────
LOCAL_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
TAILSCALE_IP="$(tailscale ip -4 2>/dev/null | head -1 || true)"

echo ""
echo "Starting Wildlife PTZ Camera Tracker backend..."
echo "  Local:     http://${LOCAL_IP:-localhost}:${PORT}"
[[ -n "$TAILSCALE_IP" ]] && echo "  Tailscale: http://${TAILSCALE_IP}:${PORT}"
echo ""

exec "$VENV_UVICORN" backend.main:app --host 0.0.0.0 --port "$PORT"
