from __future__ import annotations
import os
import time
from datetime import datetime
from typing import Optional

import cv2
import numpy as np

from .config import RecordConfig


class VideoRecorder:
    """
    CFR-paced MP4 writer.

    Writes frames at a fixed target FPS regardless of how fast the capture
    loop runs — duplicates the latest frame when the loop is fast, never
    drops frames when it is slow. This guarantees constant frame-rate output
    that media players and timestamp-based analysis expect.
    """

    def __init__(self, cfg: RecordConfig) -> None:
        self._cfg = cfg
        self._writer: Optional[cv2.VideoWriter] = None
        self._next_write_t: float = 0.0
        self._frames_written: int = 0
        self._frame_period: float = 1.0 / cfg.fps
        self._target_frames: int = int(cfg.fps * cfg.duration_sec)

    # ── properties ─────────────────────────────────────────────────────────────

    @property
    def is_active(self) -> bool:
        return self._writer is not None

    @property
    def elapsed(self) -> float:
        return self._frames_written / self._cfg.fps if self._writer else 0.0

    # ── control ────────────────────────────────────────────────────────────────

    def start(self, timestamp: Optional[str] = None) -> None:
        os.makedirs(self._cfg.output_dir, exist_ok=True)
        ts = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(self._cfg.output_dir, f"output_{ts}_with_box.mp4")
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        self._writer = cv2.VideoWriter(path, fourcc, self._cfg.fps, self._cfg.record_res)
        self._next_write_t = time.time()
        self._frames_written = 0

    def stop(self) -> None:
        if self._writer:
            self._writer.release()
            self._writer = None

    # ── per-frame tick ─────────────────────────────────────────────────────────

    def tick(self, frame: np.ndarray, now: float) -> bool:
        """
        Write frame(s) to maintain CFR cadence.
        Returns True once the clip is complete (caller should stop recording).
        frame must already have any overlays (boxes, HUD) burned in.
        """
        if not self._writer:
            return False

        while now >= self._next_write_t and self._frames_written < self._target_frames:
            rec = cv2.resize(frame, self._cfg.record_res)
            self._writer.write(rec)
            self._frames_written += 1
            self._next_write_t += self._frame_period

        if self._frames_written >= self._target_frames:
            self.stop()
            return True
        return False
