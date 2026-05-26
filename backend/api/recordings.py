from __future__ import annotations
import glob
import os
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..core.session import get_session

router = APIRouter(prefix="/api", tags=["recordings"])

_LOG_FOLDER = "joystick control logs (ms)"


# ── recordings ─────────────────────────────────────────────────────────────────

@router.get("/recordings")
async def list_recordings():
    output_dir = get_session().config.record.output_dir
    if not os.path.isdir(output_dir):
        return {"recordings": []}
    files = sorted(
        glob.glob(os.path.join(output_dir, "*.mp4")), reverse=True
    )
    return {
        "recordings": [
            {
                "filename": os.path.basename(f),
                "size_mb": round(os.path.getsize(f) / 1_000_000, 1),
                "modified": datetime.fromtimestamp(os.path.getmtime(f)).isoformat(),
            }
            for f in files
        ]
    }


@router.get("/recordings/{filename}")
async def download_recording(filename: str):
    # Guard against path traversal
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(400, "Invalid filename")
    path = os.path.join(get_session().config.record.output_dir, filename)
    if not os.path.isfile(path):
        raise HTTPException(404, "Recording not found")
    return FileResponse(path, media_type="video/mp4", filename=filename)


# ── joystick CSV logs ──────────────────────────────────────────────────────────

@router.get("/logs")
async def list_logs():
    if not os.path.isdir(_LOG_FOLDER):
        return {"logs": []}
    files = sorted(
        glob.glob(os.path.join(_LOG_FOLDER, "*.csv")), reverse=True
    )
    result = []
    for f in files:
        with open(f) as fh:
            row_count = sum(1 for _ in fh) - 1  # subtract header
        result.append({
            "filename": os.path.basename(f),
            "rows": max(0, row_count),
            "modified": datetime.fromtimestamp(os.path.getmtime(f)).isoformat(),
        })
    return {"logs": result}


@router.get("/logs/{filename}")
async def download_log(filename: str):
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(400, "Invalid filename")
    path = os.path.join(_LOG_FOLDER, filename)
    if not os.path.isfile(path):
        raise HTTPException(404, "Log not found")
    return FileResponse(path, media_type="text/csv", filename=filename)
