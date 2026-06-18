from __future__ import annotations
import glob
import os
import shutil
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..core.session import get_session

router = APIRouter(prefix="/api", tags=["recordings"])

_LOG_FOLDER = "joystick control logs (ms)"


def _output_dir() -> str:
    return get_session().config.record.output_dir


def _bin_dir() -> str:
    return os.path.join(_output_dir(), "deleted")


def _recording_info(path: str) -> dict:
    return {
        "filename": os.path.basename(path),
        "size_mb":  round(os.path.getsize(path) / 1_000_000, 1),
        "modified": datetime.fromtimestamp(os.path.getmtime(path)).isoformat(),
    }


def _safe_filename(filename: str) -> None:
    """Raise 400 if filename looks like a path traversal attempt."""
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(400, "Invalid filename")


# ── Active recordings ──────────────────────────────────────────────────────────

@router.get("/recordings")
async def list_recordings():
    d = _output_dir()
    if not os.path.isdir(d):
        return {"recordings": []}
    files = sorted(glob.glob(os.path.join(d, "*.mp4")), reverse=True)
    return {"recordings": [_recording_info(f) for f in files]}


# ── Recycle bin — MUST be defined before /recordings/{filename} ───────────────
# FastAPI matches literal paths before parameterised ones only when the literal
# route appears first in the router, so keep this block above the {filename} routes.

@router.get("/recordings/bin")
async def list_bin():
    d = _bin_dir()
    if not os.path.isdir(d):
        return {"recordings": []}
    files = sorted(glob.glob(os.path.join(d, "*.mp4")), reverse=True)
    return {"recordings": [_recording_info(f) for f in files]}


@router.post("/recordings/bin/{filename}/restore")
async def restore_recording(filename: str):
    _safe_filename(filename)
    src = os.path.join(_bin_dir(), filename)
    if not os.path.isfile(src):
        raise HTTPException(404, "File not in recycle bin")
    dst = os.path.join(_output_dir(), filename)
    shutil.move(src, dst)
    return {"status": "ok", "restored_to": dst}


@router.delete("/recordings/bin")
async def empty_bin():
    d = _bin_dir()
    if not os.path.isdir(d):
        return {"status": "ok", "deleted": 0}
    files = glob.glob(os.path.join(d, "*.mp4"))
    for f in files:
        os.remove(f)
    return {"status": "ok", "deleted": len(files)}


# ── Per-recording routes (parameterised — keep after literal /bin routes) ──────

@router.delete("/recordings/{filename}")
async def soft_delete_recording(filename: str):
    """Move a recording to the recycle bin (deleted/ subfolder)."""
    _safe_filename(filename)
    src = os.path.join(_output_dir(), filename)
    if not os.path.isfile(src):
        raise HTTPException(404, "Recording not found")
    d = _bin_dir()
    os.makedirs(d, exist_ok=True)
    shutil.move(src, os.path.join(d, filename))
    return {"status": "ok"}


@router.get("/recordings/{filename}")
async def download_recording(filename: str):
    _safe_filename(filename)
    path = os.path.join(_output_dir(), filename)
    if not os.path.isfile(path):
        raise HTTPException(404, "Recording not found")
    return FileResponse(path, media_type="video/mp4", filename=filename)


# ── Joystick CSV logs ──────────────────────────────────────────────────────────

@router.get("/logs")
async def list_logs():
    if not os.path.isdir(_LOG_FOLDER):
        return {"logs": []}
    files = sorted(glob.glob(os.path.join(_LOG_FOLDER, "*.csv")), reverse=True)
    result = []
    for f in files:
        with open(f) as fh:
            row_count = sum(1 for _ in fh) - 1  # subtract header
        result.append({
            "filename": os.path.basename(f),
            "rows":     max(0, row_count),
            "modified": datetime.fromtimestamp(os.path.getmtime(f)).isoformat(),
        })
    return {"logs": result}


@router.get("/logs/{filename}")
async def download_log(filename: str):
    _safe_filename(filename)
    path = os.path.join(_LOG_FOLDER, filename)
    if not os.path.isfile(path):
        raise HTTPException(404, "Log not found")
    return FileResponse(path, media_type="text/csv", filename=filename)
