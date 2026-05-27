"""
Multi-camera session manager.

Each camera is identified by a string ID (e.g. "cam-1").
CameraManager owns a Session and a TrackLoop thread for each camera.
A default camera ("cam-1") is created automatically at startup.
"""
from __future__ import annotations
import asyncio
import logging
import threading
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Optional

from .config import AppConfig, BIRDDOG
from .session import Session
from .track_loop import TrackLoop

logger = logging.getLogger(__name__)


# ── Per-camera entry ───────────────────────────────────────────────────────────

@dataclass
class CameraEntry:
    camera_id: str
    session: Session
    _loop_inst:   Optional[TrackLoop]       = field(default=None, repr=False)
    _loop_thread: Optional[threading.Thread] = field(default=None, repr=False)

    def is_running(self) -> bool:
        return self._loop_thread is not None and self._loop_thread.is_alive()

    def start(self) -> None:
        self._stop_thread()
        self._loop_inst   = TrackLoop(self.session)
        self._loop_thread = threading.Thread(
            target=self._loop_inst.run,
            daemon=True,
            name=f"track-loop-{self.camera_id}",
        )
        self._loop_thread.start()
        logger.info("Camera %s: track loop started", self.camera_id)

    def stop(self) -> None:
        self._stop_thread()

    def _stop_thread(self) -> None:
        if self._loop_inst:
            self._loop_inst.stop()
            self._loop_inst = None
        if self._loop_thread and self._loop_thread.is_alive():
            self._loop_thread.join(timeout=3.0)
        self._loop_thread = None

    def to_dict(self) -> dict:
        s = self.session
        return {
            "camera_id":   self.camera_id,
            "source_name": s.source_name,
            "connected":   s.connected,
            "running":     self.is_running(),
            "mode":        s.mode,
            "device":      s.device,
            "device_name": s.device_name,
        }


# ── Manager ────────────────────────────────────────────────────────────────────

class CameraManager:
    def __init__(self) -> None:
        self._cameras: dict[str, CameraEntry] = {}
        self._counter  = 0
        self._lock     = threading.Lock()
        self._async_loop: Optional[asyncio.AbstractEventLoop] = None

    # Called once from FastAPI lifespan (async context)
    def init_async(self) -> None:
        self._async_loop = asyncio.get_running_loop()
        for entry in self._cameras.values():
            entry.session.init_async()

    def _next_id(self) -> str:
        self._counter += 1
        return f"cam-{self._counter}"

    # ── CRUD ───────────────────────────────────────────────────────────────────

    def create(
        self,
        camera_id: Optional[str] = None,
        config: Optional[AppConfig] = None,
    ) -> CameraEntry:
        with self._lock:
            cid = camera_id or self._next_id()
            if cid in self._cameras:
                raise ValueError(f"Camera '{cid}' already exists")
            session = Session()
            session.config = deepcopy(config or BIRDDOG)
            # If the event loop is already running (camera added after startup),
            # initialise the async frame bridge immediately.
            if self._async_loop and self._async_loop.is_running():
                self._async_loop.call_soon_threadsafe(session.init_async)
            entry = CameraEntry(camera_id=cid, session=session)
            self._cameras[cid] = entry
            logger.info("Camera %s created", cid)
            return entry

    def get(self, camera_id: str) -> Optional[CameraEntry]:
        return self._cameras.get(camera_id)

    def remove(self, camera_id: str) -> None:
        entry = self._cameras.pop(camera_id, None)
        if entry:
            entry.stop()
            logger.info("Camera %s removed", camera_id)

    def list(self) -> list[dict]:
        return [e.to_dict() for e in self._cameras.values()]

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def stop_all(self) -> None:
        for entry in list(self._cameras.values()):
            entry.stop()
        logger.info("All camera loops stopped")


# ── Module-level singleton ─────────────────────────────────────────────────────

_manager = CameraManager()
# Create the default camera at import time
_manager.create("cam-1")


def get_manager() -> CameraManager:
    return _manager
