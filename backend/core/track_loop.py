"""
Background tracking loop — runs in a daemon thread so the asyncio event loop
is never blocked by NDI I/O or YOLO inference.

Thread → asyncio bridge
  session.push_frame(bgr)  uses  loop.call_soon_threadsafe(event.set)
  NDIVideoTrack.recv()      awaits session.next_frame()

PTZ control only fires when session.mode == 'auto_track'.
Manual mode still provides live video and updates telemetry.
"""

from __future__ import annotations
import collections
import logging
import threading
import time
from datetime import datetime
from typing import Optional

import cv2
import numpy as np

from .config import AppConfig
from .controllers import PanController, ZoomController
from .detection import BBox, Detector, SpeedEstimator
from .device import device_info
from .hud import draw_hud
from .ndi_io import NDIReceiver
from .ptz_cam import NDIPTZCamera
from .recorder import VideoRecorder
from .session import Session, get_session
from . import time_sync

logger = logging.getLogger(__name__)


# ── RTSP source (Reolink, generic) ─────────────────────────────────────────────

class RtspCapture:
    """
    OpenCV VideoCapture wrapper with the same interface as NDIReceiver.
    PTZ control is not available — handle is None.
    """

    def __init__(self, rtsp_url: str) -> None:
        self._url = rtsp_url
        self._cap: Optional[cv2.VideoCapture] = None
        self.handle = None  # no NDI recv handle → no PTZ via this path
        self.source_name = rtsp_url.split('@')[-1] if '@' in rtsp_url else rtsp_url

    def connect(self) -> None:
        self._cap = cv2.VideoCapture(self._url)
        if not self._cap.isOpened():
            raise RuntimeError(f"Could not open RTSP stream: {self._url}")

    def capture(self) -> tuple[Optional[np.ndarray], float]:
        now = time.time()
        if self._cap is None:
            return None, now
        ret, frame = self._cap.read()
        return (frame, now) if ret else (None, now)

    def close(self) -> None:
        if self._cap:
            self._cap.release()
            self._cap = None

    def __enter__(self) -> RtspCapture:
        self.connect()
        return self

    def __exit__(self, *_) -> None:
        self.close()


# ── TrackLoop ──────────────────────────────────────────────────────────────────

class TrackLoop:
    """
    Full capture → detect → control → draw → broadcast → record cycle.

    Instantiate, then call .run() from a daemon thread.  Call .stop() from
    any thread to signal a clean exit.
    """

    def __init__(self, session: Session) -> None:
        self._session = session
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:  # noqa: C901
        session = self._session
        cfg     = session.config

        proc_w, proc_h = cfg.video.process_res

        # ── Build pipeline ────────────────────────────────────────────────────
        detector  = Detector(cfg.track, cfg.device)
        info = device_info(detector.device)
        session.device      = str(detector.device)
        session.device_name = info.get("device_name", str(detector.device))

        pan_ctrl  = PanController(cfg.pan, cfg.command)
        zoom_ctrl = ZoomController(cfg.zoom, cfg.command)
        recorder  = VideoRecorder(cfg.record)
        speed_est = SpeedEstimator(cfg.speed, proc_w)
        fps_deque: collections.deque[float] = collections.deque(maxlen=30)
        last_track_t = 0.0

        # ── Choose capture source ─────────────────────────────────────────────
        if cfg.camera.reolink_rtsp_url:
            cap: RtspCapture | NDIReceiver = RtspCapture(cfg.camera.reolink_rtsp_url)
        else:
            cap = NDIReceiver(cfg.camera.source_match, cfg.camera.ndi_timeout_ms)

        ptz: Optional[NDIPTZCamera] = None

        try:
            cap.connect()
            session.connected  = True
            session.source_name = getattr(cap, 'source_name', cfg.camera.source_match)
            logger.info("Track loop connected → %s", session.source_name)

            if cap.handle is not None:
                ptz = NDIPTZCamera(cap.handle)
            session._ptz      = ptz
            session._receiver = cap

            # ── Main capture loop ─────────────────────────────────────────────
            while not self._stop.is_set():
                frame_raw, now = cap.capture()

                # Watchdog: no frame received this tick
                if frame_raw is None:
                    if ptz and (now - last_track_t > cfg.command.no_track_stop_sec):
                        if session.mode == 'auto_track':
                            pan_ctrl.force_stop(ptz)
                            zoom_ctrl.force_stop(ptz)
                    continue

                # Resize to processing resolution
                frame = cv2.resize(frame_raw, (proc_w, proc_h))
                frame_h, frame_w = frame.shape[:2]
                frame_cx = frame_w // 2

                # FPS estimate (sliding window)
                fps_deque.append(now)
                fps = (
                    len(fps_deque) / (fps_deque[-1] - fps_deque[0])
                    if len(fps_deque) >= 2 else 0.0
                )

                # ── Detection + tracking ──────────────────────────────────────
                confirmed, raw = detector.update(frame)
                primary: Optional[BBox] = (
                    confirmed[0] if confirmed
                    else (max(raw, key=lambda b: b.area) if raw else None)
                )
                detected = primary is not None

                if detected:
                    assert primary is not None
                    last_track_t = now
                    cx, cy = primary.cx, primary.cy
                    wfrac  = primary.width / frame_w

                    sp_px, sp_deg = speed_est.update(cx, cy, now)

                    primary.draw(frame)

                    # PTZ: compute always (keeps EMA warm), send only in auto_track
                    pan_desired  = pan_ctrl.compute(cx, frame_cx, frame_w)
                    zoom_desired = zoom_ctrl.compute(wfrac)
                    if session.mode == 'auto_track' and ptz is not None:
                        pan_ctrl.send(ptz,  pan_desired,  now)
                        zoom_ctrl.send(ptz, zoom_desired, now)

                    session.tracking.detected   = True
                    session.tracking.track_id   = primary.track_id
                    session.tracking.confidence = primary.conf
                    session.tracking.speed_px   = sp_px
                    session.tracking.speed_deg  = sp_deg
                    session.tracking.wfrac_ema  = zoom_ctrl.ema

                else:
                    speed_est.reset()
                    zoom_ctrl.reset()

                    session.tracking.detected   = False
                    session.tracking.track_id   = None
                    session.tracking.confidence = 0.0
                    session.tracking.speed_px   = 0.0
                    session.tracking.speed_deg  = 0.0

                    if ptz and (now - last_track_t > cfg.command.no_track_stop_sec):
                        if session.mode == 'auto_track':
                            pan_ctrl.force_stop(ptz)
                            zoom_ctrl.force_stop(ptz)

                session.tracking.fps = fps

                # ── Draw zone markers + HUD ───────────────────────────────────
                if session.mode == 'auto_track':
                    _draw_zones(frame, frame_cx, frame_h, cfg)
                _ts = datetime.fromtimestamp(now + time_sync.get_offset())
                draw_hud(
                    frame,
                    rec_on    = recorder.is_active,
                    fps       = fps,
                    elapsed   = recorder.elapsed,
                    total     = cfg.record.duration_sec,
                    speed_px  = session.tracking.speed_px,
                    speed_deg = session.tracking.speed_deg,
                    detected  = detected,
                    timestamp = _ts.strftime('%Y-%m-%d %H:%M:%S') + f'.{_ts.microsecond // 100000}',
                )

                # ── Push to WebRTC (thread → asyncio) ─────────────────────────
                session.push_frame(frame)

                # ── Recording ─────────────────────────────────────────────────
                if session.recording.is_active and not recorder.is_active:
                    recorder.start()
                    session.recording.total_sec = cfg.record.duration_sec
                    logger.info("Recording started")

                if recorder.is_active:
                    done = recorder.tick(frame, now)
                    session.recording.elapsed_sec = recorder.elapsed
                    if done:
                        session.recording.is_active = False
                        logger.info("Recording complete (%ss)", cfg.record.duration_sec)

                elif not session.recording.is_active and recorder.is_active:
                    recorder.stop()

        except Exception:
            logger.exception("Track loop error")

        finally:
            logger.info("Track loop exiting")
            if ptz:
                try:
                    ptz.stop()
                except Exception:
                    pass
            if recorder.is_active:
                recorder.stop()
            try:
                cap.close()
            except Exception:
                pass
            session.connected         = False
            session._ptz              = None
            session._receiver         = None
            session._track_task       = None
            session.device            = ""
            session.device_name       = ""
            session.tracking.fps      = 0.0
            session.tracking.detected = False


# ── Helpers ────────────────────────────────────────────────────────────────────

def _draw_zones(img: np.ndarray, frame_cx: int, frame_h: int, cfg: AppConfig) -> None:
    """Overlay pan dead-zone (cyan) and threshold band (gold) lines."""
    dz = cfg.pan.dead_zone_px
    th = cfg.pan.thresh_px
    for x, color in [
        (frame_cx - dz, (50, 200, 255)),
        (frame_cx + dz, (50, 200, 255)),
        (frame_cx - th, (0, 215, 255)),
        (frame_cx + th, (0, 215, 255)),
    ]:
        cv2.line(img, (x, 0), (x, frame_h), color, 1)


# ── Module-level singleton ─────────────────────────────────────────────────────

_loop_inst:  Optional[TrackLoop]       = None
_loop_thread: Optional[threading.Thread] = None


def start_track_loop(session: Optional[Session] = None) -> None:
    """
    Launch the tracking loop in a daemon thread.
    Non-blocking — returns immediately; connection happens inside the thread.
    Safe to call again: stops any existing loop first.
    """
    global _loop_inst, _loop_thread
    stop_track_loop()

    s = session or get_session()
    _loop_inst   = TrackLoop(s)
    _loop_thread = threading.Thread(
        target=_loop_inst.run, daemon=True, name="eagle-track-loop"
    )
    _loop_thread.start()
    logger.info("Track loop thread started")


def stop_track_loop() -> None:
    """Signal the loop to stop and wait up to 3 s for the thread to exit."""
    global _loop_inst, _loop_thread
    if _loop_inst:
        _loop_inst.stop()
        _loop_inst = None
    if _loop_thread and _loop_thread.is_alive():
        _loop_thread.join(timeout=3.0)
    _loop_thread = None


def is_running() -> bool:
    return _loop_thread is not None and _loop_thread.is_alive()
