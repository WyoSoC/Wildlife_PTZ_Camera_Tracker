"""
Multi-camera REST API.

Route summary
─────────────
  GET  /api/cameras                              list all cameras
  POST /api/cameras                              create a camera
  GET  /api/cameras/discover                     NDI LAN scan
  GET  /api/cameras/profiles                     list named profiles
  DELETE /api/cameras/{camera_id}                remove a camera
  POST /api/cameras/{camera_id}/connect          set source
  POST /api/cameras/{camera_id}/start            start tracking loop
  POST /api/cameras/{camera_id}/stop             stop tracking loop
  GET  /api/cameras/{camera_id}/status           live status
  GET  /api/cameras/{camera_id}/config           full config
  PUT  /api/cameras/{camera_id}/config           partial config update
  POST /api/cameras/{camera_id}/model            switch inference model
  POST /api/cameras/{camera_id}/profiles/{name}/load   load named profile
"""
from __future__ import annotations
import asyncio
from copy import deepcopy
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..core.camera_manager import get_manager
from ..core.config import PROFILES
from ..core.models import get_model, list_models
from ..core.ndi_io import ndi_discover

router = APIRouter(prefix="/api/cameras", tags=["cameras"])


# ── helpers ────────────────────────────────────────────────────────────────────

def _get_entry(camera_id: str):
    entry = get_manager().get(camera_id)
    if entry is None:
        raise HTTPException(404, f"Camera '{camera_id}' not found")
    return entry


# ── top-level camera management ────────────────────────────────────────────────

@router.get("")
async def list_cameras():
    return {"cameras": get_manager().list()}


class CreateCameraRequest(BaseModel):
    camera_id: Optional[str] = None
    profile:   Optional[str] = None   # load a named profile as initial config


@router.post("")
async def create_camera(req: CreateCameraRequest = CreateCameraRequest()):
    manager = get_manager()
    config  = deepcopy(PROFILES[req.profile]) if req.profile and req.profile in PROFILES else None
    try:
        entry = manager.create(camera_id=req.camera_id, config=config)
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    # init_async is scheduled by manager.create() if the loop is already running
    return {"status": "ok", "camera_id": entry.camera_id}


@router.delete("/{camera_id}")
async def remove_camera(camera_id: str):
    _get_entry(camera_id)
    get_manager().remove(camera_id)
    return {"status": "ok"}


# ── NDI discovery (global — no camera_id) ─────────────────────────────────────
# Must be registered BEFORE /{camera_id} routes or FastAPI will match "discover"
# as a camera_id.

@router.get("/discover")
async def discover():
    try:
        sources = await asyncio.get_event_loop().run_in_executor(None, ndi_discover)
        return {"sources": [{"name": s.name, "type": "ndi"} for s in sources]}
    except Exception as exc:
        raise HTTPException(500, str(exc))


@router.get("/profiles")
async def list_profiles():
    return {"profiles": list(PROFILES.keys())}


# ── per-camera routes ──────────────────────────────────────────────────────────

class ConnectRequest(BaseModel):
    source_match: str
    source_type:  str           = "ndi"    # "ndi" | "reolink"
    rtsp_url:     Optional[str] = None


@router.post("/{camera_id}/connect")
async def connect(camera_id: str, req: ConnectRequest):
    entry = _get_entry(camera_id)
    cfg   = entry.session.config
    cfg.camera.source_match = req.source_match
    if req.rtsp_url:
        cfg.camera.reolink_rtsp_url = req.rtsp_url
    entry.session.source_name = req.source_match
    return {"status": "ok", "source": req.source_match}


@router.post("/{camera_id}/start")
async def start(camera_id: str):
    entry = _get_entry(camera_id)
    cfg   = entry.session.config
    if not cfg.camera.source_match and not cfg.camera.reolink_rtsp_url:
        raise HTTPException(400, "No source configured — call /connect first")
    entry.start()
    return {"status": "ok", "running": True}


@router.post("/{camera_id}/stop")
async def stop(camera_id: str):
    _get_entry(camera_id).stop()
    return {"status": "ok", "running": False}


@router.get("/{camera_id}/status")
async def status(camera_id: str):
    entry = _get_entry(camera_id)
    s     = entry.session
    return {
        "camera_id":   camera_id,
        "connected":   s.connected,
        "running":     entry.is_running(),
        "source_name": s.source_name,
        "mode":        s.mode,
        "device":      s.device,
        "device_name": s.device_name,
    }


# ── config ────────────────────────────────────────────────────────────────────

class ConfigUpdate(BaseModel):
    pan_dead_zone_px:   Optional[int]   = None
    pan_thresh_px:      Optional[int]   = None
    pan_kp:             Optional[float] = None
    pan_max_speed:      Optional[float] = None
    pan_min_speed:      Optional[float] = None
    pan_invert:         Optional[bool]  = None
    zoom_in_frac:       Optional[float] = None
    zoom_out_frac:      Optional[float] = None
    zoom_speed:         Optional[float] = None
    zoom_invert:        Optional[bool]  = None
    zoom_ema_alpha:     Optional[float] = None
    detect_classes:     Optional[int]   = None
    record_duration_sec: Optional[float] = None
    record_fps:         Optional[int]   = None
    hfov_deg:           Optional[float] = None
    model_path:         Optional[str]   = None


@router.put("/{camera_id}/config")
async def update_config(camera_id: str, update: ConfigUpdate):
    cfg = _get_entry(camera_id).session.config
    p, z, t, r, s = cfg.pan, cfg.zoom, cfg.track, cfg.record, cfg.speed

    if update.pan_dead_zone_px   is not None: p.dead_zone_px     = update.pan_dead_zone_px
    if update.pan_thresh_px      is not None: p.thresh_px        = update.pan_thresh_px
    if update.pan_kp             is not None: p.kp               = update.pan_kp
    if update.pan_max_speed      is not None: p.max_speed        = update.pan_max_speed
    if update.pan_min_speed      is not None: p.min_speed        = update.pan_min_speed
    if update.pan_invert         is not None: p.invert           = update.pan_invert
    if update.zoom_in_frac       is not None: z.zoom_in_frac     = update.zoom_in_frac
    if update.zoom_out_frac      is not None: z.zoom_out_frac    = update.zoom_out_frac
    if update.zoom_speed         is not None: z.speed            = update.zoom_speed
    if update.zoom_invert        is not None: z.invert           = update.zoom_invert
    if update.zoom_ema_alpha     is not None: z.ema_alpha        = update.zoom_ema_alpha
    if update.detect_classes     is not None: t.detect_classes   = update.detect_classes
    if update.record_duration_sec is not None: r.duration_sec    = update.record_duration_sec
    if update.record_fps         is not None: r.fps              = update.record_fps
    if update.hfov_deg           is not None: s.hfov_deg         = update.hfov_deg
    if update.model_path         is not None: t.model_path       = update.model_path

    return {"status": "ok"}


@router.get("/{camera_id}/config")
async def get_config(camera_id: str):
    cfg = _get_entry(camera_id).session.config
    return {
        "camera":  {"source_match": cfg.camera.source_match,
                    "reolink_rtsp_url": cfg.camera.reolink_rtsp_url},
        "pan":     {"dead_zone_px": cfg.pan.dead_zone_px, "thresh_px": cfg.pan.thresh_px,
                    "kp": cfg.pan.kp, "max_speed": cfg.pan.max_speed,
                    "min_speed": cfg.pan.min_speed, "invert": cfg.pan.invert},
        "zoom":    {"zoom_in_frac": cfg.zoom.zoom_in_frac, "zoom_out_frac": cfg.zoom.zoom_out_frac,
                    "speed": cfg.zoom.speed, "invert": cfg.zoom.invert,
                    "ema_alpha": cfg.zoom.ema_alpha},
        "track":   {"detect_classes": cfg.track.detect_classes, "model_path": cfg.track.model_path},
        "record":  {"duration_sec": cfg.record.duration_sec, "fps": cfg.record.fps,
                    "record_res": list(cfg.record.record_res)},
        "speed":   {"hfov_deg": cfg.speed.hfov_deg},
    }


# ── model switching ────────────────────────────────────────────────────────────

class ModelSwitchRequest(BaseModel):
    model_name: str   # must match a ModelInfo.name in the registry


@router.post("/{camera_id}/model")
async def switch_model(camera_id: str, req: ModelSwitchRequest):
    entry = _get_entry(camera_id)
    info  = get_model(req.model_name)
    if info is None:
        available = [m.name for m in list_models()]
        raise HTTPException(404, f"Model '{req.model_name}' not found. Available: {available}")

    was_running = entry.is_running()
    if was_running:
        entry.stop()

    cfg = entry.session.config
    cfg.track.model_path     = info.path
    cfg.track.detect_classes = info.detect_classes[0] if info.detect_classes and len(info.detect_classes) == 1 else None

    if was_running:
        entry.start()

    return {
        "status":    "ok",
        "model":     info.name,
        "path":      info.path,
        "restarted": was_running,
    }


# ── profiles ───────────────────────────────────────────────────────────────────

@router.post("/{camera_id}/profiles/{name}/load")
async def load_profile(camera_id: str, name: str):
    if name not in PROFILES:
        raise HTTPException(404, f"Profile '{name}' not found. Available: {list(PROFILES.keys())}")
    entry = _get_entry(camera_id)
    entry.session.config = deepcopy(PROFILES[name])
    return {"status": "ok", "profile": name}
