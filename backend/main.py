from __future__ import annotations
import logging
import os
import webbrowser
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from .api import cameras, ptz, webrtc, recordings
from .api.webrtc import close_all
from .core.device import select_device, device_info
from .core.session import get_session
from .core.track_loop import stop_track_loop

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    dev = select_device(get_session().config.device.device)
    info = device_info(dev)
    logger.info(
        "Eagle Tracker starting — inference device: %s",
        info.get("device_name", str(dev)),
    )
    if info.get("vram_gb"):
        logger.info("  VRAM: %.1f GB  CUDA: %s  SM: %s  Jetson: %s",
                    info["vram_gb"], info.get("cuda_version", "?"),
                    info.get("sm_capability", "?"), info.get("is_jetson", False))
    get_session().init_async()
    yield
    logger.info("Eagle Tracker server shutting down")
    stop_track_loop()
    await close_all()


app = FastAPI(title="Eagle Tracker", version="1.0.0", lifespan=lifespan)

# Allow the Vite dev server (port 5173) to call the API during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8080"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cameras.router)
app.include_router(ptz.router)
app.include_router(webrtc.router)
app.include_router(recordings.router)

# ── Serve the React SPA ────────────────────────────────────────────────────────
# Populated by `vite build` → `scripts/build.sh` copies dist/ here
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
    """
    Called by PyInstaller binary and `python -m backend`.
    Opens the browser automatically so the user just double-clicks the app.
    """
    webbrowser.open(f"http://localhost:{port}")
    uvicorn.run(
        "backend.main:app",
        host=host,
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    run()
