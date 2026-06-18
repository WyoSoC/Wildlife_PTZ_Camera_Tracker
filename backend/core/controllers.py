from __future__ import annotations
from typing import Optional, TYPE_CHECKING

from .config import PanConfig, ZoomConfig, CommandConfig, AreaConfig, ScanConfig

if TYPE_CHECKING:
    from .ptz_cam import NDIPTZCamera


class PanController:
    """
    Proportional pan with a single dead-zone band.
    Speed = kp × (offset / half_frame_width), clamped to [min_speed, max_speed].
    """

    def __init__(self, pan: PanConfig, cmd: CommandConfig) -> None:
        self._pan = pan
        self._cmd = cmd
        self._last_speed: float = 0.0
        self._last_sent:  float = 0.0

    def compute(self, cx: int, frame_cx: int, frame_w: int) -> float:
        """Return desired pan speed in [-max_speed, +max_speed]."""
        dx = cx - frame_cx
        if abs(dx) <= self._pan.dead_zone_px:
            return 0.0
        dx_norm = dx / (frame_w * 0.5)
        raw = max(-self._pan.max_speed, min(self._pan.max_speed, self._pan.kp * dx_norm))
        if self._pan.invert:
            raw = -raw
        # Enforce minimum speed so motor overcomes stiction
        if 0.0 < abs(raw) < self._pan.min_speed:
            raw = self._pan.min_speed if raw > 0 else -self._pan.min_speed
        return raw

    def send(self, ptz: 'NDIPTZCamera', desired: float, now: float) -> None:
        if now - self._last_sent < self._cmd.min_interval_sec:
            return
        if abs(desired - self._last_speed) <= self._cmd.eps:
            return
        ptz.pan_tilt_speed(desired)
        self._last_speed = desired
        self._last_sent  = now

    def force_stop(self, ptz: 'NDIPTZCamera') -> None:
        if self._last_speed != 0.0:
            ptz.pan_tilt_speed(0.0, 0.0)
            self._last_speed = 0.0


class ZoomController:
    """
    EMA-smoothed zoom with hysteresis band.
    Zooms in when bbox width < zoom_in_frac × frame width.
    Zooms out when bbox width > zoom_out_frac × frame width.
    """

    def __init__(self, zoom: ZoomConfig, cmd: CommandConfig) -> None:
        self._zoom = zoom
        self._cmd  = cmd
        self._ema:        Optional[float] = None
        self._last_speed: float           = 0.0
        self._last_sent:  float           = 0.0

    def compute(self, wfrac: float) -> float:
        """Update EMA of bbox-width fraction; return desired zoom speed."""
        self._ema = (
            wfrac
            if self._ema is None
            else self._zoom.ema_alpha * wfrac + (1.0 - self._zoom.ema_alpha) * self._ema
        )
        if   self._ema < self._zoom.zoom_in_frac:  raw =  self._zoom.speed
        elif self._ema > self._zoom.zoom_out_frac: raw = -self._zoom.speed
        else:                                       raw =  0.0
        return -raw if self._zoom.invert else raw

    @property
    def ema(self) -> float:
        return self._ema or 0.0

    def send(self, ptz: 'NDIPTZCamera', desired: float, now: float) -> None:
        if now - self._last_sent < self._cmd.min_interval_sec:
            return
        if abs(desired - self._last_speed) <= self._cmd.eps:
            return
        ptz.zoom_speed(desired)
        self._last_speed = desired
        self._last_sent  = now

    def force_stop(self, ptz: 'NDIPTZCamera') -> None:
        if self._last_speed != 0.0:
            ptz.zoom_speed(0.0)
            self._last_speed = 0.0

    def reset(self) -> None:
        self._ema = None


class ScanController:
    """
    Boustrophedon (lawnmower) sweep of the configured area.

    Builds a grid of (pan, tilt) positions from AreaConfig.  The camera is
    commanded to each position via go_to(), allowed travel_sec to arrive, then
    dwells for dwell_sec before advancing.  Rows alternate pan direction so the
    camera moves efficiently without doubling back.

    Call tick() every frame while in scanning state.  tick() is a no-op until
    the controller is enabled.  The sweep continues from where it left off if
    the camera briefly locks onto a target and then loses it.
    """

    def __init__(self, area: AreaConfig, scan: ScanConfig) -> None:
        self._area = area
        self._scan = scan
        self._positions: list[tuple[float, float]] = []
        self._idx    = 0
        self._t_last = 0.0
        self._phase  = 'init'   # 'init' | 'travelling' | 'dwelling'
        self._rebuild()

    # ── public API ─────────────────────────────────────────────────────────────

    def reset(self) -> None:
        """Restart sweep from the first position (call on config change)."""
        self._rebuild()

    def tick(self, ptz: 'NDIPTZCamera', now: float) -> None:
        """Advance the scan pattern. Call every frame while scanning."""
        if not self._positions:
            return

        pan, tilt = self._positions[self._idx]

        if self._phase == 'init':
            ptz.go_to(pan, tilt, self._area.scan_zoom)
            self._t_last = now
            self._phase  = 'travelling'

        elif self._phase == 'travelling':
            if now - self._t_last >= self._scan.travel_sec:
                self._t_last = now
                self._phase  = 'dwelling'

        elif self._phase == 'dwelling':
            if now - self._t_last >= self._scan.dwell_sec:
                self._idx = (self._idx + 1) % len(self._positions)
                pan, tilt = self._positions[self._idx]
                ptz.go_to(pan, tilt, self._area.scan_zoom)
                self._t_last = now
                self._phase  = 'travelling'

    @property
    def current_target(self) -> tuple[float, float]:
        if self._positions:
            return self._positions[self._idx]
        return (0.0, 0.0)

    @property
    def phase(self) -> str:
        return self._phase

    # ── internal ───────────────────────────────────────────────────────────────

    def _rebuild(self) -> None:
        a    = self._area
        s    = self._scan
        rows = max(1, s.rows)
        cols = max(2, s.cols)

        tilts = [
            a.tilt_min + (a.tilt_max - a.tilt_min) * r / max(1, rows - 1)
            for r in range(rows)
        ]
        pans = [
            a.pan_min + (a.pan_max - a.pan_min) * c / max(1, cols - 1)
            for c in range(cols)
        ]

        self._positions = []
        for ri, tilt in enumerate(tilts):
            row_pans = pans if ri % 2 == 0 else list(reversed(pans))
            for pan in row_pans:
                self._positions.append((pan, tilt))

        self._idx   = 0
        self._phase = 'init'
