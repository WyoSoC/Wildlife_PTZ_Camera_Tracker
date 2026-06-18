"""
User-saved tracking configuration profiles.

Profiles capture the auto-tracking parameters (pan, zoom, detection,
command timing, home position, area, scan) and store them as JSON files
in the ./profiles/ directory at the project root.  They are independent of
the hard-coded hardware profiles (BIRDDOG, BOLIN) defined in config.py.

Route summary
─────────────
  GET    /api/profiles              list all saved profiles
  POST   /api/profiles              save current camera config as a profile
  POST   /api/profiles/{name}/load  apply a saved profile to a camera
  DELETE /api/profiles/{name}       delete a profile
"""
from __future__ import annotations
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..core.camera_manager import get_manager

router = APIRouter(prefix="/api/profiles", tags=["profiles"])

_PROFILES_DIR = Path("profiles")


# ── helpers ────────────────────────────────────────────────────────────────────

def _dir() -> Path:
    _PROFILES_DIR.mkdir(exist_ok=True)
    return _PROFILES_DIR


def _safe_name(name: str) -> str:
    """Convert arbitrary user input to a filesystem-safe slug."""
    name = name.strip()
    name = re.sub(r'[^\w\- ]', '', name)
    name = re.sub(r'\s+', '_', name)
    return name[:64] or 'profile'


def _path(name: str) -> Path:
    return _dir() / f"{_safe_name(name)}.json"


def _extract(cfg) -> dict:
    """Pull the tracking-relevant subset of AppConfig into a plain dict."""
    return {
        "pan": {
            "dead_zone_px": cfg.pan.dead_zone_px,
            "kp":           cfg.pan.kp,
            "max_speed":    cfg.pan.max_speed,
            "min_speed":    cfg.pan.min_speed,
        },
        "zoom": {
            "zoom_in_frac":  cfg.zoom.zoom_in_frac,
            "zoom_out_frac": cfg.zoom.zoom_out_frac,
            "speed":         cfg.zoom.speed,
            "ema_alpha":     cfg.zoom.ema_alpha,
        },
        "track": {
            "lock_confidence": cfg.track.lock_confidence,
            "tracker_max_age": cfg.track.tracker_max_age,
        },
        "command": {
            "no_track_stop_sec": cfg.command.no_track_stop_sec,
            "lock_off_sec":      cfg.command.lock_off_sec,
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


def _apply(cfg, data: dict) -> None:
    """Write a saved profile dict back into a live AppConfig (tolerates missing keys)."""
    pan  = data.get("pan",     {})
    zoom = data.get("zoom",    {})
    trk  = data.get("track",   {})
    cmd  = data.get("command", {})
    spd  = data.get("speed",   {})
    home = data.get("home",    {})
    area = data.get("area",    {})
    scan = data.get("scan",    {})

    if "dead_zone_px" in pan: cfg.pan.dead_zone_px = int(pan["dead_zone_px"])
    if "kp"           in pan: cfg.pan.kp           = float(pan["kp"])
    if "max_speed"    in pan: cfg.pan.max_speed    = float(pan["max_speed"])
    if "min_speed"    in pan: cfg.pan.min_speed    = float(pan["min_speed"])

    if "zoom_in_frac"  in zoom: cfg.zoom.zoom_in_frac  = float(zoom["zoom_in_frac"])
    if "zoom_out_frac" in zoom: cfg.zoom.zoom_out_frac = float(zoom["zoom_out_frac"])
    if "speed"         in zoom: cfg.zoom.speed         = float(zoom["speed"])
    if "ema_alpha"     in zoom: cfg.zoom.ema_alpha     = float(zoom["ema_alpha"])

    if "lock_confidence" in trk: cfg.track.lock_confidence = float(trk["lock_confidence"])
    if "tracker_max_age" in trk: cfg.track.tracker_max_age = int(trk["tracker_max_age"])

    if "no_track_stop_sec" in cmd: cfg.command.no_track_stop_sec = float(cmd["no_track_stop_sec"])
    if "lock_off_sec"      in cmd: cfg.command.lock_off_sec      = float(cmd["lock_off_sec"])

    if "hfov_deg" in spd: cfg.speed.hfov_deg = float(spd["hfov_deg"])

    if "pan"    in home: cfg.home.pan    = float(home["pan"])
    if "tilt"   in home: cfg.home.tilt   = float(home["tilt"])
    if "zoom"   in home: cfg.home.zoom   = float(home["zoom"])
    if "is_set" in home: cfg.home.is_set = bool(home["is_set"])

    if "enabled"   in area: cfg.area.enabled   = bool(area["enabled"])
    if "pan_min"   in area: cfg.area.pan_min   = float(area["pan_min"])
    if "pan_max"   in area: cfg.area.pan_max   = float(area["pan_max"])
    if "tilt_min"  in area: cfg.area.tilt_min  = float(area["tilt_min"])
    if "tilt_max"  in area: cfg.area.tilt_max  = float(area["tilt_max"])
    if "scan_zoom" in area: cfg.area.scan_zoom = float(area["scan_zoom"])

    if "enabled"    in scan: cfg.scan.enabled    = bool(scan["enabled"])
    if "rows"       in scan: cfg.scan.rows       = int(scan["rows"])
    if "cols"       in scan: cfg.scan.cols       = int(scan["cols"])
    if "travel_sec" in scan: cfg.scan.travel_sec = float(scan["travel_sec"])
    if "dwell_sec"  in scan: cfg.scan.dwell_sec  = float(scan["dwell_sec"])


# ── endpoints ──────────────────────────────────────────────────────────────────

@router.get("")
async def list_profiles():
    """Return all saved tracking profiles sorted by save date (newest first)."""
    profiles = []
    for p in sorted(_dir().glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True):
        try:
            data = json.loads(p.read_text())
            profiles.append({
                "name":        data.get("name", p.stem),
                "saved_at":    data.get("saved_at"),
                "description": data.get("description", ""),
            })
        except Exception:
            pass
    return {"profiles": profiles}


class SaveRequest(BaseModel):
    name:        str
    camera_id:   str
    description: Optional[str] = ""


@router.post("")
async def save_profile(req: SaveRequest):
    """Capture the current tracking config of a camera and write it to disk."""
    entry = get_manager().get(req.camera_id)
    if entry is None:
        raise HTTPException(404, f"Camera '{req.camera_id}' not found")

    safe = _safe_name(req.name)
    if not safe:
        raise HTTPException(400, "Profile name must contain at least one alphanumeric character")

    payload = {
        "name":        safe,
        "saved_at":    datetime.now(tz=timezone.utc).isoformat(),
        "description": (req.description or "").strip(),
        "config":      _extract(entry.session.config),
    }
    _path(safe).write_text(json.dumps(payload, indent=2))
    return {"status": "saved", "name": safe}


class LoadRequest(BaseModel):
    camera_id: str


@router.post("/{name}/load")
async def load_profile(name: str, req: LoadRequest):
    """Apply a saved profile to a camera's live config (takes effect immediately)."""
    p = _path(name)
    if not p.exists():
        raise HTTPException(404, f"Profile '{name}' not found")

    entry = get_manager().get(req.camera_id)
    if entry is None:
        raise HTTPException(404, f"Camera '{req.camera_id}' not found")

    try:
        data = json.loads(p.read_text())
        _apply(entry.session.config, data.get("config", {}))
    except Exception as exc:
        raise HTTPException(500, f"Failed to apply profile: {exc}")

    return {"status": "loaded", "name": data.get("name", name)}


@router.delete("/{name}")
async def delete_profile(name: str):
    """Permanently delete a saved profile."""
    p = _path(name)
    if not p.exists():
        raise HTTPException(404, f"Profile '{name}' not found")
    p.unlink()
    return {"status": "deleted", "name": name}
