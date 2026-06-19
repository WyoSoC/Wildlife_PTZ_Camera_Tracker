"""
Multi-camera REST API.

Route summary
─────────────
  GET    /api/cameras                                   list all cameras
  POST   /api/cameras                                   create a camera
  GET    /api/cameras/discover                          NDI LAN scan
  GET    /api/cameras/profiles                          list named profiles
  DELETE /api/cameras/{camera_id}                       remove a camera
  POST   /api/cameras/{camera_id}/connect               set source
  POST   /api/cameras/{camera_id}/start                 start tracking loop
  POST   /api/cameras/{camera_id}/stop                  stop tracking loop
  GET    /api/cameras/{camera_id}/status                live status
  GET    /api/cameras/{camera_id}/config                full config
  PUT    /api/cameras/{camera_id}/config                partial config update
  POST   /api/cameras/{camera_id}/model                 switch inference model
  POST   /api/cameras/{camera_id}/profiles/{name}/load  load named profile
  POST   /api/cameras/{camera_id}/home/go               move camera to home position
  POST   /api/cameras/{camera_id}/scan/reset            restart scan from position 0
"""
from __future__ import annotations
import asyncio
import time
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
    profile:   Optional[str] = None


@router.post("")
async def create_camera(req: CreateCameraRequest = CreateCameraRequest()):
    manager = get_manager()
    config  = deepcopy(PROFILES[req.profile]) if req.profile and req.profile in PROFILES else None
    try:
        entry = manager.create(camera_id=req.camera_id, config=config)
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    return {"status": "ok", "camera_id": entry.camera_id}


@router.delete("/{camera_id}")
async def remove_camera(camera_id: str):
    _get_entry(camera_id)
    get_manager().remove(camera_id)
    return {"status": "ok"}


# ── NDI discovery — must be before /{camera_id} routes ────────────────────────

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
    source_type:  str           = "ndi"
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
    cfg   = s.config
    return {
        "camera_id":    camera_id,
        "connected":    s.connected,
        "running":      entry.is_running(),
        "source_name":  s.source_name,
        "source_match": cfg.camera.source_match,
        "rtsp_url":     cfg.camera.reolink_rtsp_url,
        "mode":         s.mode,
        "device":       s.device,
        "device_name":  s.device_name,
    }


# ── config ────────────────────────────────────────────────────────────────────

class ConfigUpdate(BaseModel):
    # Pan
    pan_stable_zone_h_px:   Optional[int]   = None
    pan_stable_zone_v_px: Optional[int]   = None
    pan_kp:             Optional[float] = None
    pan_max_speed:     Optional[float] = None
    pan_min_speed:     Optional[float] = None
    pan_invert:        Optional[bool]  = None
    # Zoom
    zoom_in_frac:      Optional[float] = None
    zoom_out_frac:     Optional[float] = None
    zoom_speed:        Optional[float] = None
    zoom_invert:       Optional[bool]  = None
    zoom_ema_alpha:    Optional[float] = None
    # Detection / tracking
    detect_classes:    Optional[int]   = None
    lock_confidence:   Optional[float] = None
    tracker_max_age:   Optional[int]   = None
    # Command timing
    no_track_stop_sec: Optional[float] = None
    lock_off_sec:      Optional[float] = None
    # Recording
    record_duration_sec: Optional[float]    = None
    record_fps:          Optional[int]      = None
    record_res:          Optional[list[int]] = None
    # Speed
    hfov_deg:          Optional[float] = None
    # Model
    model_path:        Optional[str]   = None
    # Home position
    home_pan:          Optional[float] = None
    home_tilt:         Optional[float] = None
    home_zoom:         Optional[float] = None
    home_is_set:       Optional[bool]  = None
    # Tracking area
    area_enabled:      Optional[bool]  = None
    area_pan_min:      Optional[float] = None
    area_pan_max:      Optional[float] = None
    area_tilt_min:     Optional[float] = None
    area_tilt_max:     Optional[float] = None
    area_scan_zoom:    Optional[float] = None
    # Scan
    scan_enabled:      Optional[bool]  = None
    scan_rows:         Optional[int]   = None
    scan_cols:         Optional[int]   = None
    scan_travel_sec:   Optional[float] = None
    scan_dwell_sec:    Optional[float] = None


@router.put("/{camera_id}/config")
async def update_config(camera_id: str, update: ConfigUpdate):
    cfg = _get_entry(camera_id).session.config
    p, z, t, r, s, cmd, h, a, sc = (
        cfg.pan, cfg.zoom, cfg.track, cfg.record,
        cfg.speed, cfg.command, cfg.home, cfg.area, cfg.scan,
    )

    if update.pan_stable_zone_h_px   is not None: p.stable_zone_h_px   = update.pan_stable_zone_h_px
    if update.pan_stable_zone_v_px is not None: p.stable_zone_v_px = update.pan_stable_zone_v_px
    if update.pan_kp             is not None: p.kp             = update.pan_kp
    if update.pan_max_speed     is not None: p.max_speed         = update.pan_max_speed
    if update.pan_min_speed     is not None: p.min_speed         = update.pan_min_speed
    if update.pan_invert        is not None: p.invert            = update.pan_invert
    if update.zoom_in_frac      is not None: z.zoom_in_frac      = update.zoom_in_frac
    if update.zoom_out_frac     is not None: z.zoom_out_frac     = update.zoom_out_frac
    if update.zoom_speed        is not None: z.speed             = update.zoom_speed
    if update.zoom_invert       is not None: z.invert            = update.zoom_invert
    if update.zoom_ema_alpha    is not None: z.ema_alpha         = update.zoom_ema_alpha
    if "detect_classes" in update.model_fields_set:
        t.detect_classes = update.detect_classes
    if update.lock_confidence   is not None: t.lock_confidence   = update.lock_confidence
    if update.tracker_max_age   is not None: t.tracker_max_age   = update.tracker_max_age
    if update.no_track_stop_sec is not None: cmd.no_track_stop_sec = update.no_track_stop_sec
    if update.lock_off_sec      is not None: cmd.lock_off_sec    = update.lock_off_sec
    if update.record_duration_sec is not None: r.duration_sec    = update.record_duration_sec
    if update.record_fps        is not None: r.fps               = update.record_fps
    if update.record_res is not None and len(update.record_res) == 2:
        r.record_res = (int(update.record_res[0]), int(update.record_res[1]))
    if update.hfov_deg          is not None: s.hfov_deg          = update.hfov_deg
    if update.model_path        is not None: t.model_path        = update.model_path
    # Home
    if update.home_pan    is not None: h.pan    = update.home_pan
    if update.home_tilt   is not None: h.tilt   = update.home_tilt
    if update.home_zoom   is not None: h.zoom   = update.home_zoom
    if update.home_is_set is not None: h.is_set = update.home_is_set
    # Area
    if update.area_enabled   is not None: a.enabled   = update.area_enabled
    if update.area_pan_min   is not None: a.pan_min   = update.area_pan_min
    if update.area_pan_max   is not None: a.pan_max   = update.area_pan_max
    if update.area_tilt_min  is not None: a.tilt_min  = update.area_tilt_min
    if update.area_tilt_max  is not None: a.tilt_max  = update.area_tilt_max
    if update.area_scan_zoom is not None: a.scan_zoom = update.area_scan_zoom
    # Scan
    if update.scan_enabled    is not None: sc.enabled    = update.scan_enabled
    if update.scan_rows       is not None: sc.rows       = update.scan_rows
    if update.scan_cols       is not None: sc.cols       = update.scan_cols
    if update.scan_travel_sec is not None: sc.travel_sec = update.scan_travel_sec
    if update.scan_dwell_sec  is not None: sc.dwell_sec  = update.scan_dwell_sec

    return {"status": "ok"}


@router.get("/{camera_id}/config")
async def get_config(camera_id: str):
    cfg = _get_entry(camera_id).session.config
    return {
        "camera":  {
            "source_match":     cfg.camera.source_match,
            "reolink_rtsp_url": cfg.camera.reolink_rtsp_url,
        },
        "pan": {
            "stable_zone_h_px":   cfg.pan.stable_zone_h_px,
            "stable_zone_v_px": cfg.pan.stable_zone_v_px,
            "kp":             cfg.pan.kp,
            "max_speed":    cfg.pan.max_speed,
            "min_speed":    cfg.pan.min_speed,
            "invert":       cfg.pan.invert,
        },
        "zoom": {
            "zoom_in_frac":  cfg.zoom.zoom_in_frac,
            "zoom_out_frac": cfg.zoom.zoom_out_frac,
            "speed":         cfg.zoom.speed,
            "invert":        cfg.zoom.invert,
            "ema_alpha":     cfg.zoom.ema_alpha,
        },
        "track": {
            "detect_classes":  cfg.track.detect_classes,
            "model_path":      cfg.track.model_path,
            "lock_confidence": cfg.track.lock_confidence,
            "tracker_max_age": cfg.track.tracker_max_age,
        },
        "command": {
            "no_track_stop_sec": cfg.command.no_track_stop_sec,
            "lock_off_sec":      cfg.command.lock_off_sec,
        },
        "record": {
            "duration_sec": cfg.record.duration_sec,
            "fps":          cfg.record.fps,
            "record_res":   list(cfg.record.record_res),
        },
        "speed": {
            "hfov_deg": cfg.speed.hfov_deg,
        },
        "home": {
            "pan":    cfg.home.pan,
            "tilt":   cfg.home.tilt,
            "zoom":   cfg.home.zoom,
            "is_set": cfg.home.is_set,
        },
        "area": {
            "enabled":   cfg.area.enabled,
            "pan_min":   cfg.area.pan_min,
            "pan_max":   cfg.area.pan_max,
            "tilt_min":  cfg.area.tilt_min,
            "tilt_max":  cfg.area.tilt_max,
            "scan_zoom": cfg.area.scan_zoom,
        },
        "scan": {
            "enabled":    cfg.scan.enabled,
            "rows":       cfg.scan.rows,
            "cols":       cfg.scan.cols,
            "travel_sec": cfg.scan.travel_sec,
            "dwell_sec":  cfg.scan.dwell_sec,
        },
    }


# ── PTZ position query ────────────────────────────────────────────────────────

@router.get("/{camera_id}/position")
async def get_position(camera_id: str):
    """
    Query the camera's current absolute pan/tilt/zoom position.

    Sends an NDI metadata query and waits up to 500 ms for the camera to
    respond.  The response is parsed by NDIReceiver inside the running tracking
    loop — so the loop must be active (camera started) for this to work.

    Returns: {"pan": float, "tilt": float, "zoom": float}  (all in NDI space)
    """
    entry = _get_entry(camera_id)
    if not entry.is_running():
        raise HTTPException(400, "Camera must be running to query position — start it first")

    ptz      = entry.session._ptz
    receiver = entry.session._receiver
    if ptz is None or receiver is None:
        raise HTTPException(400, "Camera is not connected")

    now = time.time()

    # Some cameras stream position continuously — use it if it's fresh (< 2 s old)
    pos = getattr(receiver, "last_position", None)
    if pos and pos.get("ts", 0.0) > now - 2.0:
        return {"pan": pos["pan"], "tilt": pos["tilt"], "zoom": pos["zoom"]}

    # Otherwise send an explicit query and wait up to 1 s for the response
    query_time = time.time()
    ptz.query_position()

    for _ in range(50):   # 50 × 20 ms = 1 s
        await asyncio.sleep(0.02)
        pos = getattr(receiver, "last_position", None)
        if pos and pos.get("ts", 0.0) > query_time:
            return {"pan": pos["pan"], "tilt": pos["tilt"], "zoom": pos["zoom"]}

    raise HTTPException(
        504,
        "Camera did not respond to position query within 1 s. "
        "The camera may not support position feedback over NDI. "
        "Check backend logs (DEBUG level) to see what metadata is arriving.",
    )


# ── home position ──────────────────────────────────────────────────────────────

@router.post("/{camera_id}/home/go")
async def go_home(camera_id: str):
    """Command the camera to move to its saved home position."""
    entry = _get_entry(camera_id)
    cfg   = entry.session.config
    if not cfg.home.is_set:
        raise HTTPException(400, "Home position not set — save one first")
    ptz = entry.session._ptz
    if ptz is None:
        raise HTTPException(400, "Camera not connected — start the tracking loop first")
    ptz.go_to(cfg.home.pan, cfg.home.tilt, cfg.home.zoom)
    return {"status": "ok", "pan": cfg.home.pan, "tilt": cfg.home.tilt, "zoom": cfg.home.zoom}


# ── scan control ───────────────────────────────────────────────────────────────

@router.post("/{camera_id}/scan/reset")
async def reset_scan(camera_id: str):
    """Restart the auto-scan sweep from position 0."""
    _get_entry(camera_id)   # validates existence
    return {"status": "ok"}


# ── model switching ────────────────────────────────────────────────────────────

class ModelSwitchRequest(BaseModel):
    model_name: str


@router.post("/{camera_id}/model")
async def switch_model(camera_id: str, req: ModelSwitchRequest):
    entry = _get_entry(camera_id)
    info  = get_model(req.model_name)
    if info is None:
        available = [m.name for m in list_models()]
        raise HTTPException(404, f"Model '{req.model_name}' not found. Available: {available}")

    if not info.downloaded:
        raise HTTPException(
            400,
            f"Model '{req.model_name}' is not downloaded."
            + (f" (HuggingFace: {info.repo_id})" if info.repo_id else ""),
        )

    was_running = entry.is_running()
    if was_running:
        entry.stop()

    cfg = entry.session.config
    cfg.track.model_path     = info.path
    cfg.track.detect_classes = (
        info.detect_classes[0]
        if info.detect_classes and len(info.detect_classes) == 1
        else None
    )

    if was_running:
        entry.start()

    return {"status": "ok", "model": info.name, "path": info.path, "restarted": was_running}


# ── profiles ───────────────────────────────────────────────────────────────────

@router.post("/{camera_id}/profiles/{name}/load")
async def load_profile(camera_id: str, name: str):
    if name not in PROFILES:
        raise HTTPException(404, f"Profile '{name}' not found. Available: {list(PROFILES.keys())}")
    entry = _get_entry(camera_id)
    entry.session.config = deepcopy(PROFILES[name])
    return {"status": "ok", "profile": name}
