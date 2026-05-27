from __future__ import annotations
import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..core.camera_manager import get_manager

router = APIRouter()

_TELEMETRY_INTERVAL = 0.1   # seconds between outbound telemetry pushes


@router.websocket("/ws/ptz/{camera_id}")
async def ptz_ws(ws: WebSocket, camera_id: str) -> None:
    """
    Bidirectional WebSocket for PTZ commands (inbound) and telemetry (outbound).

    Inbound message schemas
    ───────────────────────
    pan_tilt   {"type": "pan_tilt",  "pan": float, "tilt": float}
    zoom       {"type": "zoom",      "speed": float}
    stop       {"type": "stop"}
    autofocus  {"type": "autofocus"}
    mode       {"type": "mode",      "mode": "manual"|"auto_track"}
    record     {"type": "record",    "action": "start"|"stop"}

    Outbound: {"type": "telemetry", ...session.to_telemetry()} at 10 Hz.
    """
    entry = get_manager().get(camera_id)
    if entry is None:
        await ws.close(code=4004, reason=f"Camera '{camera_id}' not found")
        return

    await ws.accept()
    session = entry.session
    last_telemetry_t = 0.0

    try:
        while True:
            now = asyncio.get_event_loop().time()

            try:
                raw = await asyncio.wait_for(ws.receive_text(), timeout=0.05)
                await _dispatch(json.loads(raw), session)
            except asyncio.TimeoutError:
                pass

            if now - last_telemetry_t >= _TELEMETRY_INTERVAL:
                await ws.send_json({"type": "telemetry", **session.to_telemetry()})
                last_telemetry_t = now

    except WebSocketDisconnect:
        pass


async def _dispatch(msg: dict, session) -> None:
    ptz = session._ptz
    t   = msg.get("type")

    if t == "pan_tilt":
        if ptz:
            ptz.pan_tilt_speed(msg.get("pan", 0.0), msg.get("tilt", 0.0))

    elif t == "zoom":
        if ptz:
            ptz.zoom_speed(msg.get("speed", 0.0))

    elif t == "stop":
        if ptz:
            ptz.stop()

    elif t == "autofocus":
        if ptz:
            ptz.autofocus()

    elif t == "mode":
        new_mode = msg.get("mode", "manual")
        if new_mode in ("manual", "auto_track"):
            session.mode = new_mode

    elif t == "record":
        action = msg.get("action")
        if action == "start" and not session.recording.is_active:
            session.recording.is_active = True
            session.recording.total_sec = session.config.record.duration_sec
        elif action == "stop":
            session.recording.is_active = False
