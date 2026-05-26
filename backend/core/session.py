from __future__ import annotations
import asyncio
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

import numpy as np

from .config import AppConfig, BIRDDOG

if TYPE_CHECKING:
    from .ptz_cam import NDIPTZCamera
    from .ndi_io import NDIReceiver


@dataclass
class TrackingState:
    detected:    bool           = False
    track_id:    Optional[int]  = None
    confidence:  float          = 0.0
    speed_px:    float          = 0.0
    speed_deg:   float          = 0.0
    wfrac_ema:   float          = 0.0
    fps:         float          = 0.0


@dataclass
class RecordingState:
    is_active:   bool  = False
    elapsed_sec: float = 0.0
    total_sec:   float = 0.0


class Session:
    """
    Application-wide singleton.

    Holds the active camera connection, current config, running mode,
    latest decoded frame (for WebRTC broadcast), and live telemetry.
    Shared between the background tracking thread and all async API handlers.

    Frame bridge (thread → asyncio)
    ────────────────────────────────
    1. Asyncio startup calls  init_async()  which stores the running loop
       and creates the asyncio.Event on that loop.
    2. The tracking thread calls  push_frame(bgr)  which stores the frame
       and calls  loop.call_soon_threadsafe(event.set)  — safe from any thread.
    3. NDIVideoTrack.recv()  awaits  next_frame()  which waits on that event.
    """

    def __init__(self) -> None:
        self.config:      AppConfig = BIRDDOG
        self.connected:   bool      = False
        self.source_name: str       = ""
        self.mode:        str       = "manual"   # "manual" | "auto_track"

        self.tracking  = TrackingState()
        self.recording = RecordingState()

        # Frame bridge — initialised by init_async() once the event loop runs
        self._loop:         Optional[asyncio.AbstractEventLoop] = None
        self._frame_event:  Optional[asyncio.Event]             = None
        self._latest_frame: Optional[np.ndarray]                = None

        # Camera objects set when connected
        self._receiver:    Optional[object] = None   # NDIReceiver | RtspCapture
        self._ptz:         Optional[object] = None   # NDIPTZCamera

        # Handle to background asyncio task (unused currently; kept for future)
        self._track_task:  Optional[asyncio.Task] = None  # type: ignore[type-arg]

    # ── Async initialisation (call once from FastAPI lifespan) ─────────────────

    def init_async(self) -> None:
        """
        Bind this session to the running event loop and create the frame
        Event on it.  Must be called from an async context (e.g. lifespan).
        """
        self._loop        = asyncio.get_running_loop()
        self._frame_event = asyncio.Event()

    # ── Frame bridge ───────────────────────────────────────────────────────────

    def push_frame(self, frame: np.ndarray) -> None:
        """
        Called from the synchronous capture thread to deliver a new frame.
        Thread-safe: uses call_soon_threadsafe so the asyncio event is set
        from within the event loop thread, not from the caller thread.
        """
        self._latest_frame = frame
        if self._loop is not None and self._frame_event is not None:
            self._loop.call_soon_threadsafe(self._frame_event.set)

    async def next_frame(self, timeout: float = 0.1) -> Optional[np.ndarray]:
        """
        Await the next pushed frame (used by NDIVideoTrack.recv).
        Returns the frame, or None on timeout.
        """
        if self._frame_event is None:
            return self._latest_frame
        try:
            await asyncio.wait_for(self._frame_event.wait(), timeout=timeout)
            self._frame_event.clear()
        except asyncio.TimeoutError:
            pass
        return self._latest_frame

    def latest_frame(self) -> Optional[np.ndarray]:
        return self._latest_frame

    # ── Telemetry snapshot ─────────────────────────────────────────────────────

    def to_telemetry(self) -> dict:
        return {
            "connected":    self.connected,
            "source_name":  self.source_name,
            "mode":         self.mode,
            "fps":          round(self.tracking.fps, 1),
            "detected":     self.tracking.detected,
            "track_id":     self.tracking.track_id,
            "confidence":   round(self.tracking.confidence, 3),
            "speed_px":     round(self.tracking.speed_px, 1),
            "speed_deg":    round(self.tracking.speed_deg, 2),
            "wfrac_ema":    round(self.tracking.wfrac_ema, 3),
            "rec_active":   self.recording.is_active,
            "rec_elapsed":  round(self.recording.elapsed_sec, 1),
            "rec_total":    self.recording.total_sec,
        }


# ── Module-level singleton ─────────────────────────────────────────────────────

_session = Session()


def get_session() -> Session:
    return _session
