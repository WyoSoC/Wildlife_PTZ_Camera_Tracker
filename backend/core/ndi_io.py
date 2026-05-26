from __future__ import annotations
import time
from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import numpy as np
import NDIlib as ndi


@dataclass
class NDISourceInfo:
    name: str


def ndi_discover(wait_sec: float = 2.0) -> list[NDISourceInfo]:
    """Scan the LAN for NDI sources. Blocks for wait_sec, then returns."""
    if not ndi.initialize():
        raise RuntimeError("NDI init failed")
    finder = ndi.find_create_v2()
    time.sleep(wait_sec)
    sources = ndi.find_get_current_sources(finder) or []
    result = [NDISourceInfo(name=s.ndi_name) for s in sources]
    ndi.find_destroy(finder)
    ndi.destroy()
    return result


class NDIReceiver:
    """
    Connects to a single NDI source and decodes frames to BGR numpy arrays.

    Usage:
        with NDIReceiver("birddog") as recv:
            bgr, ts = recv.capture()
            ptz = NDIPTZCamera(recv.handle)
    """

    def __init__(self, source_match: str, timeout_ms: int = 50) -> None:
        self.source_match = source_match
        self.timeout_ms = timeout_ms
        self.source_name: str = ""
        self._finder = None
        self._recv = None

    # ── lifecycle ──────────────────────────────────────────────────────────────

    def connect(self) -> None:
        if not ndi.initialize():
            raise RuntimeError("NDI init failed")
        self._finder = ndi.find_create_v2()
        time.sleep(1.0)
        sources = ndi.find_get_current_sources(self._finder) or []
        matched = next(
            (s for s in sources if self.source_match.lower() in s.ndi_name.lower()),
            None,
        )
        if matched is None:
            raise RuntimeError(
                f"NDI source containing '{self.source_match}' not found. "
                f"Available: {[s.ndi_name for s in sources]}"
            )
        self._recv = ndi.recv_create_v3()
        if not self._recv:
            raise RuntimeError("ndi.recv_create_v3 failed")
        ndi.recv_connect(self._recv, matched)
        self.source_name = matched.ndi_name

    def close(self) -> None:
        for fn, arg in [(ndi.recv_destroy, self._recv), (ndi.find_destroy, self._finder)]:
            try:
                if arg is not None:
                    fn(arg)
            except Exception:
                pass
        try:
            ndi.destroy()
        except Exception:
            pass
        self._recv = self._finder = None

    # ── frame capture ──────────────────────────────────────────────────────────

    def capture(self) -> Tuple[Optional[np.ndarray], float]:
        """
        Capture one frame. Returns (bgr_array, wall_time) on a video frame,
        or (None, wall_time) for timeout / audio / metadata frames.
        """
        now = time.time()
        t, v, _a, m = ndi.recv_capture_v2(self._recv, self.timeout_ms)

        if t == ndi.FRAME_TYPE_METADATA and m is not None:
            try:
                ndi.recv_free_metadata(self._recv, m)
            except Exception:
                pass

        if t != ndi.FRAME_TYPE_VIDEO:
            return None, now

        bgr = _decode_frame(v)
        ndi.recv_free_video_v2(self._recv, v)
        return bgr, now

    @property
    def handle(self):
        """Raw NDI recv handle, needed by NDIPTZCamera."""
        return self._recv

    # ── context manager ────────────────────────────────────────────────────────

    def __enter__(self) -> NDIReceiver:
        self.connect()
        return self

    def __exit__(self, *_) -> None:
        self.close()


# ── internal helpers ───────────────────────────────────────────────────────────

def _decode_frame(v_frame) -> np.ndarray:
    h, w = v_frame.yres, v_frame.xres
    fb = bytes(v_frame.data)
    if len(fb) == w * h * 4:
        return cv2.cvtColor(
            np.frombuffer(fb, np.uint8).reshape((h, w, 4)), cv2.COLOR_BGRA2BGR
        )
    if len(fb) == w * h * 2:
        return cv2.cvtColor(
            np.frombuffer(fb, np.uint8).reshape((h, w, 2)), cv2.COLOR_YUV2BGR_UYVY
        )
    raise ValueError(f"Unsupported NDI frame: {len(fb)} bytes for {w}×{h}")
