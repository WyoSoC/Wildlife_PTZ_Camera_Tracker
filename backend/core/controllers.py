from __future__ import annotations
from typing import Optional

from .config import PanConfig, ZoomConfig, CommandConfig
from .ptz_cam import NDIPTZCamera


class PanController:
    """
    Proportional pan with dead-zone and outer threshold band.
    Maintains its own rate-limit state so main loop stays clean.
    """

    def __init__(self, pan: PanConfig, cmd: CommandConfig) -> None:
        self._pan = pan
        self._cmd = cmd
        self._last_speed: float = 0.0
        self._last_sent: float = 0.0

    def compute(self, cx: int, frame_cx: int, frame_w: int) -> float:
        """Return desired pan speed in [-max_speed, +max_speed]."""
        dx = cx - frame_cx
        # Both dead-zone and threshold band produce zero — two-band structure
        # kept intentionally for future slow-pan mode in the middle band.
        if abs(dx) <= self._pan.dead_zone_px or abs(dx) <= self._pan.thresh_px:
            return 0.0
        dx_norm = dx / (frame_w * 0.5)
        raw = max(-self._pan.max_speed, min(self._pan.max_speed, self._pan.kp * dx_norm))
        if self._pan.invert:
            raw = -raw
        # Enforce minimum speed so motor overcomes stiction
        if 0.0 < abs(raw) < self._pan.min_speed:
            raw = self._pan.min_speed if raw > 0 else -self._pan.min_speed
        return raw

    def send(self, ptz: NDIPTZCamera, desired: float, now: float) -> None:
        """Issue PTZ command only if rate limit and epsilon threshold allow."""
        if now - self._last_sent < self._cmd.min_interval_sec:
            return
        if abs(desired - self._last_speed) <= self._cmd.eps:
            return
        ptz.pan_tilt_speed(desired)
        self._last_speed = desired
        self._last_sent = now

    def force_stop(self, ptz: NDIPTZCamera) -> None:
        if self._last_speed != 0.0:
            ptz.pan_tilt_speed(0.0, 0.0)
            self._last_speed = 0.0


class ZoomController:
    """
    EMA-smoothed zoom with hysteresis band.
    Maintains its own rate-limit and EMA state.
    """

    def __init__(self, zoom: ZoomConfig, cmd: CommandConfig) -> None:
        self._zoom = zoom
        self._cmd = cmd
        self._ema: Optional[float] = None
        self._last_speed: float = 0.0
        self._last_sent: float = 0.0

    def compute(self, wfrac: float) -> float:
        """
        Update EMA of bbox-width fraction and return desired zoom speed.
        wfrac = bbox_width / frame_width (0..1)
        """
        self._ema = (
            wfrac
            if self._ema is None
            else self._zoom.ema_alpha * wfrac + (1.0 - self._zoom.ema_alpha) * self._ema
        )
        if self._ema < self._zoom.zoom_in_frac:
            raw = self._zoom.speed
        elif self._ema > self._zoom.zoom_out_frac:
            raw = -self._zoom.speed
        else:
            raw = 0.0
        return -raw if self._zoom.invert else raw

    @property
    def ema(self) -> float:
        return self._ema or 0.0

    def send(self, ptz: NDIPTZCamera, desired: float, now: float) -> None:
        if now - self._last_sent < self._cmd.min_interval_sec:
            return
        if abs(desired - self._last_speed) <= self._cmd.eps:
            return
        ptz.zoom_speed(desired)
        self._last_speed = desired
        self._last_sent = now

    def force_stop(self, ptz: NDIPTZCamera) -> None:
        if self._last_speed != 0.0:
            ptz.zoom_speed(0.0)
            self._last_speed = 0.0

    def reset(self) -> None:
        self._ema = None
