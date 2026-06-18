"""
Background tracking loop — runs in a daemon thread so the asyncio event loop
is never blocked by NDI I/O or YOLO inference.

State machine (auto_track mode)
────────────────────────────────
  idle     → camera at home, waiting
  scanning → camera executing boustrophedon sweep of the configured area
  locked   → camera following a confirmed detection

Transitions
  manual mode         → always idle (home on entry if home is set)
  auto_track, no scan → idle until detection; locked on detection
  auto_track + scan   → scanning → (conf ≥ threshold) → locked
                        → (target lost ≥ lock_off_sec) → scanning
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
from .controllers import PanController, ZoomController, ScanController
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
    """OpenCV VideoCapture wrapper with the same interface as NDIReceiver."""

    def __init__(self, rtsp_url: str) -> None:
        self._url = rtsp_url
        self._cap: Optional[cv2.VideoCapture] = None
        self.handle = None
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
    Instantiate, then call .run() from a daemon thread.
    """

    def __init__(self, session: Session) -> None:
        self._session = session
        self._stop    = threading.Event()

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
        scan_ctrl = ScanController(cfg.area, cfg.scan)
        recorder  = VideoRecorder(cfg.record)
        speed_est = SpeedEstimator(cfg.speed, proc_w)
        fps_deque: collections.deque[float] = collections.deque(maxlen=30)

        # ── State machine ─────────────────────────────────────────────────────
        scan_phase   = 'idle'   # 'idle' | 'scanning' | 'locked'
        lock_lost_t  = 0.0      # timestamp when target was last seen
        last_track_t = 0.0      # timestamp of last detection (for motor stop watchdog)
        home_sent    = False    # True after go_to(home) issued in idle phase

        # ── Choose capture source ─────────────────────────────────────────────
        cap: RtspCapture | NDIReceiver = (
            RtspCapture(cfg.camera.reolink_rtsp_url)
            if cfg.camera.reolink_rtsp_url
            else NDIReceiver(cfg.camera.source_match, cfg.camera.ndi_timeout_ms)
        )
        ptz: Optional[NDIPTZCamera] = None

        try:
            cap.connect()
            session.connected   = True
            session.source_name = getattr(cap, 'source_name', cfg.camera.source_match)
            logger.info("Track loop connected → %s", session.source_name)

            if cap.handle is not None:
                ptz = NDIPTZCamera(cap.handle)
            session._ptz      = ptz
            session._receiver = cap

            # ── Main capture loop ─────────────────────────────────────────────
            while not self._stop.is_set():
                frame_raw, now = cap.capture()

                # Watchdog: no frame this tick
                if frame_raw is None:
                    if ptz and (now - last_track_t > cfg.command.no_track_stop_sec):
                        if session.mode == 'auto_track' and scan_phase == 'locked':
                            pan_ctrl.force_stop(ptz)
                            zoom_ctrl.force_stop(ptz)
                    continue

                frame = cv2.resize(frame_raw, (proc_w, proc_h))
                frame_h, frame_w = frame.shape[:2]
                frame_cx = frame_w // 2

                # FPS (sliding window)
                fps_deque.append(now)
                fps = (
                    len(fps_deque) / (fps_deque[-1] - fps_deque[0])
                    if len(fps_deque) >= 2 else 0.0
                )

                # ── Detection ─────────────────────────────────────────────────
                confirmed, raw = detector.update(frame)

                # Apply confidence threshold — only raw detections are filtered;
                # confirmed (DeepSort) tracks do not carry per-frame confidence.
                min_conf = cfg.track.lock_confidence
                raw_ok   = [b for b in raw if b.conf >= min_conf]

                primary: Optional[BBox] = (
                    confirmed[0] if confirmed
                    else (max(raw_ok, key=lambda b: b.area) if raw_ok else None)
                )
                detected = primary is not None

                # ── State machine ─────────────────────────────────────────────
                if session.mode == 'auto_track':
                    if detected:
                        scan_phase   = 'locked'
                        lock_lost_t  = now
                        last_track_t = now
                        home_sent    = False

                        assert primary is not None
                        cx, cy = primary.cx, primary.cy
                        wfrac  = primary.width / frame_w

                        sp_px, sp_deg = speed_est.update(cx, cy, now)
                        primary.draw(frame)

                        pan_desired  = pan_ctrl.compute(cx, frame_cx, frame_w)
                        zoom_desired = zoom_ctrl.compute(wfrac)
                        if ptz is not None:
                            pan_ctrl.send(ptz,  pan_desired,  now)
                            zoom_ctrl.send(ptz, zoom_desired, now)

                        session.tracking.detected   = True
                        session.tracking.track_id   = primary.track_id
                        session.tracking.confidence = primary.conf
                        session.tracking.speed_px   = sp_px
                        session.tracking.speed_deg  = sp_deg
                        session.tracking.wfrac_ema  = zoom_ctrl.ema

                    else:
                        # Target not found this frame
                        speed_est.reset()
                        zoom_ctrl.reset()
                        session.tracking.detected   = False
                        session.tracking.track_id   = None
                        session.tracking.confidence = 0.0
                        session.tracking.speed_px   = 0.0
                        session.tracking.speed_deg  = 0.0

                        # Motor stop watchdog
                        if ptz and (now - last_track_t > cfg.command.no_track_stop_sec):
                            if scan_phase == 'locked':
                                pan_ctrl.force_stop(ptz)
                                zoom_ctrl.force_stop(ptz)

                        # State transition: locked → scanning/idle
                        if scan_phase == 'locked':
                            if now - lock_lost_t >= cfg.command.lock_off_sec:
                                if cfg.scan.enabled and cfg.area.enabled:
                                    scan_phase = 'scanning'
                                    logger.info("Lock lost — resuming scan")
                                else:
                                    scan_phase = 'idle'
                                    logger.info("Lock lost — returning idle")

                        # Ensure scan is running if configured
                        if scan_phase == 'idle' and cfg.scan.enabled and cfg.area.enabled:
                            scan_phase = 'scanning'
                            scan_ctrl.reset()
                            logger.info("Scan mode activated")

                        # Execute scan
                        if scan_phase == 'scanning' and ptz is not None:
                            scan_ctrl.tick(ptz, now)
                        elif scan_phase == 'idle' and ptz is not None:
                            # Return to home once (not every frame)
                            if cfg.home.is_set and not home_sent:
                                ptz.go_to(cfg.home.pan, cfg.home.tilt, cfg.home.zoom)
                                home_sent = True

                else:
                    # Manual mode: reset all state
                    if scan_phase != 'idle':
                        scan_phase = 'idle'
                        if ptz:
                            pan_ctrl.force_stop(ptz)
                            zoom_ctrl.force_stop(ptz)
                    speed_est.reset()
                    zoom_ctrl.reset()
                    session.tracking.detected   = False
                    session.tracking.track_id   = None
                    session.tracking.confidence = 0.0
                    session.tracking.speed_px   = 0.0
                    session.tracking.speed_deg  = 0.0

                    # Draw detections subtly — thin, muted boxes so the operator
                    # can see what the model sees without implying active tracking.
                    for b in raw_ok:
                        b.draw(frame, color=(130, 210, 170), thickness=1)

                session.tracking.fps        = fps
                session.tracking.scan_phase = scan_phase

                # ── Draw overlays ─────────────────────────────────────────────
                if session.mode == 'auto_track':
                    _draw_zones(frame, frame_cx, frame_h, cfg)
                    if scan_phase == 'scanning':
                        _draw_scan_overlay(frame, cfg)

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

                session.push_frame(frame)

                # ── Recording ─────────────────────────────────────────────────
                if session.recording.is_active and not recorder.is_active:
                    recorder.start()
                    session.recording.total_sec = cfg.record.duration_sec

                if recorder.is_active:
                    done = recorder.tick(frame, now)
                    session.recording.elapsed_sec = recorder.elapsed
                    if done:
                        session.recording.is_active = False

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
            session.connected              = False
            session._ptz                   = None
            session._receiver              = None
            session._track_task            = None
            session.device                 = ""
            session.device_name            = ""
            session.tracking.fps           = 0.0
            session.tracking.detected      = False
            session.tracking.scan_phase    = 'idle'


# ── Helpers ────────────────────────────────────────────────────────────────────

def _draw_zones(img: np.ndarray, frame_cx: int, frame_h: int, cfg: AppConfig) -> None:
    """Overlay pan dead-zone (cyan) line pair."""
    dz = cfg.pan.dead_zone_px
    for x, color in [
        (frame_cx - dz, (50, 200, 255)),
        (frame_cx + dz, (50, 200, 255)),
    ]:
        cv2.line(img, (x, 0), (x, frame_h), color, 1)


def _draw_scan_overlay(img: np.ndarray, cfg: AppConfig) -> None:
    """Draw a small SCANNING label so the operator knows the state."""
    cv2.putText(
        img, "SCANNING",
        (6, img.shape[0] - 8),
        cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 200, 255), 1, cv2.LINE_AA,
    )


# ── Module-level singleton ─────────────────────────────────────────────────────

_loop_inst:   Optional[TrackLoop]        = None
_loop_thread: Optional[threading.Thread] = None


def start_track_loop(session: Optional[Session] = None) -> None:
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
    global _loop_inst, _loop_thread
    if _loop_inst:
        _loop_inst.stop()
        _loop_inst = None
    if _loop_thread and _loop_thread.is_alive():
        _loop_thread.join(timeout=3.0)
    _loop_thread = None


def is_running() -> bool:
    return _loop_thread is not None and _loop_thread.is_alive()
