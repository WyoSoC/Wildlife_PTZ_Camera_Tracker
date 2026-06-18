from __future__ import annotations
import logging
import os
import subprocess
import time
from datetime import datetime
from typing import Optional

import cv2
import numpy as np

from .config import RecordConfig

logger = logging.getLogger(__name__)


def _make_ffmpeg_cmd(path: str, width: int, height: int, fps: int) -> list[str]:
    """
    Build the ffmpeg command that reads raw BGR24 frames from stdin.
    Tries h264_nvenc (RTX NVENC) first, falls back to libx264.
    -movflags +faststart places the moov atom at the front so browsers
    can play the file without downloading it fully.
    """
    base = [
        "ffmpeg", "-y",
        "-f", "rawvideo", "-vcodec", "rawvideo",
        "-s", f"{width}x{height}",
        "-pix_fmt", "bgr24",
        "-r", str(fps),
        "-i", "pipe:0",
        "-movflags", "+faststart",
        "-an",          # no audio
    ]
    nvenc = base + ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "23", path]
    x264  = base + ["-c:v", "libx264",    "-preset", "fast", "-crf", "23", path]

    # Probe NVENC availability with a 0-frame encode
    probe = subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "nullsrc=s=64x64:d=0",
         "-c:v", "h264_nvenc", "-f", "null", "-"],
        capture_output=True,
    )
    if probe.returncode == 0:
        logger.info("Recorder: using h264_nvenc (NVENC)")
        return nvenc
    logger.info("Recorder: NVENC unavailable, using libx264")
    return x264


class VideoRecorder:
    """
    CFR-paced H.264 writer via ffmpeg subprocess.

    Writes frames at a fixed target FPS regardless of capture rate —
    duplicates the latest frame when fast, never drops when slow.
    Output is browser-playable H.264/MP4 with faststart.
    """

    def __init__(self, cfg: RecordConfig) -> None:
        self._cfg          = cfg
        self._proc: Optional[subprocess.Popen] = None
        self._next_write_t = 0.0
        self._frames_written = 0
        self._frame_period = 1.0 / cfg.fps
        self._target_frames = int(cfg.fps * cfg.duration_sec)
        self._w, self._h   = cfg.record_res  # (width, height)

    # ── properties ─────────────────────────────────────────────────────────────

    @property
    def is_active(self) -> bool:
        return self._proc is not None

    @property
    def elapsed(self) -> float:
        return self._frames_written / self._cfg.fps if self._proc else 0.0

    # ── control ────────────────────────────────────────────────────────────────

    def start(self, timestamp: Optional[str] = None) -> None:
        os.makedirs(self._cfg.output_dir, exist_ok=True)
        ts   = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(self._cfg.output_dir, f"output_{ts}_with_box.mp4")
        cmd  = _make_ffmpeg_cmd(path, self._w, self._h, self._cfg.fps)
        self._proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._next_write_t   = time.time()
        self._frames_written = 0
        logger.info("Recording → %s  (%dx%d @ %d fps)", path, self._w, self._h, self._cfg.fps)

    def stop(self) -> None:
        if self._proc:
            try:
                self._proc.stdin.close()
                self._proc.wait(timeout=15)
            except Exception:
                self._proc.kill()
                self._proc.wait()
            self._proc = None

    # ── per-frame tick ─────────────────────────────────────────────────────────

    def tick(self, frame: np.ndarray, now: float) -> bool:
        """
        Write frame(s) to maintain CFR cadence.
        Returns True once the clip is complete (caller should stop recording).
        frame must already have any overlays (boxes, HUD) burned in.
        """
        if not self._proc:
            return False

        resized = cv2.resize(frame, (self._w, self._h))

        while now >= self._next_write_t and self._frames_written < self._target_frames:
            try:
                self._proc.stdin.write(resized.tobytes())
            except BrokenPipeError:
                logger.error("Recorder: ffmpeg pipe broke — stopping")
                self._proc = None
                return True
            self._frames_written += 1
            self._next_write_t  += self._frame_period

        if self._frames_written >= self._target_frames:
            self.stop()
            return True
        return False
