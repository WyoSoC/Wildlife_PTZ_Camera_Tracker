from __future__ import annotations
import asyncio
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..core.ndi_io import ndi_discover
from ..core.config import PROFILES
from ..core.session import get_session
from ..core.track_loop import start_track_loop, stop_track_loop, is_running

router = APIRouter(prefix="/api/cameras", tags=["cameras"])


# ── discovery ──────────────────────────────────────────────────────────────────

@router.get("/discover")
async def discover():
    """
    Scan the LAN for NDI sources (~2s).
    Returns list of {name, type} objects.
    """
    try:
        sources = await asyncio.get_event_loop().run_in_executor(None, ndi_discover)
        return {"sources": [{"name": s.name, "type": "ndi"} for s in sources]}
    except Exception as exc:
        raise HTTPException(500, str(exc))


# ── connection ─────────────────────────────────────────────────────────────────

class ConnectRequest(BaseModel):
    source_match: str
    source_type: str = "ndi"        # "ndi" | "reolink"
    rtsp_url: Optional[str] = None  # required when source_type == "reolink"


@router.post("/connect")
async def connect(req: ConnectRequest):
    """
    Tell the session which camera to use.
    Actual NDI connection is established when the tracking loop starts.
    """
    session = get_session()
    session.config.camera.source_match = req.source_match
    if req.rtsp_url:
        session.config.camera.reolink_rtsp_url = req.rtsp_url
    session.source_name = req.source_match
    return {"status": "ok", "source": req.source_match}


@router.post("/disconnect")
async def disconnect():
    stop_track_loop()
    return {"status": "ok"}


# ── loop control ───────────────────────────────────────────────────────────────

@router.post("/start")
async def start():
    """
    Start the background tracking/capture loop.
    The source must be set via /connect first.
    """
    session = get_session()
    if not session.config.camera.source_match and not session.config.camera.reolink_rtsp_url:
        raise HTTPException(400, "No camera source configured. Call /connect first.")
    start_track_loop(session)
    return {"status": "ok", "running": True}


@router.post("/stop")
async def stop():
    """Stop the background tracking/capture loop."""
    stop_track_loop()
    return {"status": "ok", "running": False}


@router.get("/status")
async def status():
    session = get_session()
    return {
        "connected":   session.connected,
        "running":     is_running(),
        "source_name": session.source_name,
        "mode":        session.mode,
        "device":      session.device,
        "device_name": session.device_name,
    }


# ── config CRUD ────────────────────────────────────────────────────────────────

class ConfigUpdate(BaseModel):
    pan_dead_zone_px: Optional[int] = None
    pan_thresh_px: Optional[int] = None
    pan_kp: Optional[float] = None
    pan_max_speed: Optional[float] = None
    pan_min_speed: Optional[float] = None
    pan_invert: Optional[bool] = None
    zoom_in_frac: Optional[float] = None
    zoom_out_frac: Optional[float] = None
    zoom_speed: Optional[float] = None
    zoom_invert: Optional[bool] = None
    zoom_ema_alpha: Optional[float] = None
    detect_classes: Optional[int] = None
    record_duration_sec: Optional[float] = None
    record_fps: Optional[int] = None
    hfov_deg: Optional[float] = None


@router.put("/config")
async def update_config(update: ConfigUpdate):
    cfg = get_session().config
    p, z, t, r, s = cfg.pan, cfg.zoom, cfg.track, cfg.record, cfg.speed

    if update.pan_dead_zone_px is not None:   p.dead_zone_px = update.pan_dead_zone_px
    if update.pan_thresh_px is not None:      p.thresh_px = update.pan_thresh_px
    if update.pan_kp is not None:             p.kp = update.pan_kp
    if update.pan_max_speed is not None:      p.max_speed = update.pan_max_speed
    if update.pan_min_speed is not None:      p.min_speed = update.pan_min_speed
    if update.pan_invert is not None:         p.invert = update.pan_invert
    if update.zoom_in_frac is not None:       z.zoom_in_frac = update.zoom_in_frac
    if update.zoom_out_frac is not None:      z.zoom_out_frac = update.zoom_out_frac
    if update.zoom_speed is not None:         z.speed = update.zoom_speed
    if update.zoom_invert is not None:        z.invert = update.zoom_invert
    if update.zoom_ema_alpha is not None:     z.ema_alpha = update.zoom_ema_alpha
    if update.detect_classes is not None:     t.detect_classes = update.detect_classes
    if update.record_duration_sec is not None: r.duration_sec = update.record_duration_sec
    if update.record_fps is not None:         r.fps = update.record_fps
    if update.hfov_deg is not None:           s.hfov_deg = update.hfov_deg

    return {"status": "ok"}


@router.get("/config")
async def get_config():
    cfg = get_session().config
    return {
        "camera": {
            "source_match": cfg.camera.source_match,
            "reolink_rtsp_url": cfg.camera.reolink_rtsp_url,
        },
        "pan": {
            "dead_zone_px": cfg.pan.dead_zone_px,
            "thresh_px": cfg.pan.thresh_px,
            "kp": cfg.pan.kp,
            "max_speed": cfg.pan.max_speed,
            "min_speed": cfg.pan.min_speed,
            "invert": cfg.pan.invert,
        },
        "zoom": {
            "zoom_in_frac": cfg.zoom.zoom_in_frac,
            "zoom_out_frac": cfg.zoom.zoom_out_frac,
            "speed": cfg.zoom.speed,
            "invert": cfg.zoom.invert,
            "ema_alpha": cfg.zoom.ema_alpha,
        },
        "track": {
            "detect_classes": cfg.track.detect_classes,
            "model_path": cfg.track.model_path,
        },
        "record": {
            "duration_sec": cfg.record.duration_sec,
            "fps": cfg.record.fps,
            "record_res": list(cfg.record.record_res),
        },
        "speed": {
            "hfov_deg": cfg.speed.hfov_deg,
        },
    }


# ── profiles ───────────────────────────────────────────────────────────────────

@router.get("/profiles")
async def list_profiles():
    return {"profiles": list(PROFILES.keys())}


@router.post("/profiles/{name}/load")
async def load_profile(name: str):
    if name not in PROFILES:
        raise HTTPException(404, f"Profile '{name}' not found. Available: {list(PROFILES.keys())}")
    get_session().config = PROFILES[name]
    return {"status": "ok", "profile": name}
