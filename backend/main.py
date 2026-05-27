from __future__ import annotations
import logging
import os
import webbrowser
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from .api import cameras, ptz, webrtc, recordings
from .api import system as system_api
from .api import models as models_api
from .api.webrtc import close_all
from .core.camera_manager import get_manager
from .core.device import select_device, device_info

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Optional API-key auth ──────────────────────────────────────────────────────
# Set  WILDLIFE_API_KEY  env var on the server to require a key from clients.
# Leave unset for open access (trusted-LAN / Tailscale only deployments).
_API_KEY: str = os.environ.get("WILDLIFE_API_KEY", "")


@asynccontextmanager
async def lifespan(app: FastAPI):
    manager = get_manager()
    manager.init_async()            # binds all existing sessions to the event loop

    # Log startup device info from the default camera session
    default = manager.get("cam-1")
    if default:
        dev  = select_device(default.session.config.device.device)
        info = device_info(dev)
        logger.info(
            "Wildlife PTZ Camera Tracker starting — inference device: %s",
            info.get("device_name", str(dev)),
        )
        if info.get("vram_gb"):
            logger.info("  VRAM: %.1f GB  CUDA: %s  SM: %s  Jetson: %s",
                        info["vram_gb"], info.get("cuda_version", "?"),
                        info.get("sm_capability", "?"), info.get("is_jetson", False))

    yield
    logger.info("Wildlife PTZ Camera Tracker shutting down")
    manager.stop_all()
    await close_all()


app = FastAPI(
    title="Wildlife PTZ Camera Tracker",
    version="2.0.0",
    lifespan=lifespan,
)

# ── CORS ───────────────────────────────────────────────────────────────────────
# Allow any origin so the GitHub Pages frontend (and any other static host)
# can reach the server over Tailscale HTTPS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Optional API-key middleware ────────────────────────────────────────────────
@app.middleware("http")
async def api_key_guard(request: Request, call_next) -> Response:
    if _API_KEY and request.url.path.startswith("/api/"):
        key = (
            request.headers.get("X-API-Key") or
            request.query_params.get("api_key") or ""
        )
        if key != _API_KEY:
            return Response(
                content='{"detail":"Invalid or missing API key"}',
                status_code=401,
                media_type="application/json",
            )
    return await call_next(request)


# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(cameras.router)
app.include_router(ptz.router)
app.include_router(webrtc.router)
app.include_router(recordings.router)
app.include_router(system_api.router)
app.include_router(models_api.router)

# ── Serve the React SPA (production build) ────────────────────────────────────
_static = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_static):
    _assets = os.path.join(_static, "assets")
    if os.path.isdir(_assets):
        app.mount("/assets", StaticFiles(directory=_assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        return FileResponse(os.path.join(_static, "index.html"))


# ── Entry point ────────────────────────────────────────────────────────────────

def run(host: str = "0.0.0.0", port: int = 8080) -> None:
    webbrowser.open(f"http://localhost:{port}")
    uvicorn.run("backend.main:app", host=host, port=port, log_level="info")


if __name__ == "__main__":
    run()
