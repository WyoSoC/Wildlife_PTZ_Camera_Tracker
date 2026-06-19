from __future__ import annotations
import logging
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import numpy as np

# NDIlib is a native optional dependency (NDI Tools SDK wheel).
# The server starts normally without it; NDI features raise RuntimeError at
# call time so Reolink / RTSP connections still work.
try:
    import NDIlib as ndi
    _NDI_AVAILABLE = True
except ImportError:
    ndi = None  # type: ignore[assignment]
    _NDI_AVAILABLE = False

logger = logging.getLogger(__name__)
if not _NDI_AVAILABLE:
    logger.warning(
        "NDIlib not found — NDI source discovery and NDI camera connections "
        "are disabled. Install the NDI Tools SDK wheel to enable them. "
        "Reolink RTSP connections are unaffected."
    )


@dataclass
class NDISourceInfo:
    name: str


def ndi_discover(wait_sec: float = 2.0) -> list[NDISourceInfo]:
    """Scan the LAN for NDI sources. Blocks for wait_sec, then returns."""
    if not _NDI_AVAILABLE:
        raise RuntimeError(
            "NDIlib is not installed. "
            "Install the NDI Tools SDK wheel to use NDI discovery."
        )
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
        if not _NDI_AVAILABLE:
            raise RuntimeError(
                "NDIlib is not installed. "
                "Install the NDI Tools SDK wheel to connect to NDI cameras."
            )
        self.source_match = source_match
        self.timeout_ms = timeout_ms
        self.source_name: str = ""
        self.last_position: Optional[dict] = None   # {"pan", "tilt", "zoom", "ts"}
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

        desc = ndi.RecvCreateV3()
        desc.color_format      = ndi.RECV_COLOR_FORMAT_BGRX_BGRA  # always deliver decoded BGRA
        desc.bandwidth         = ndi.RECV_BANDWIDTH_HIGHEST
        desc.allow_video_fields = False                             # deinterlace; simplifies decode
        self._recv = ndi.recv_create_v3(desc)
        if not self._recv:
            raise RuntimeError("ndi.recv_create_v3 failed")
        ndi.recv_connect(self._recv, matched)
        self.source_name = matched.ndi_name
        self._error_frame_count = 0

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
                self._parse_position_metadata(m)
            except Exception as exc:
                logger.debug("Metadata parse error: %s", exc)
            finally:
                try:
                    ndi.recv_free_metadata(self._recv, m)
                except Exception:
                    pass

        if t != ndi.FRAME_TYPE_VIDEO:
            return None, now

        bgr = _decode_frame(v)
        ndi.recv_free_video_v2(self._recv, v)

        if bgr is not None:
            self._error_frame_count = getattr(self, "_error_frame_count", 0) + 1
            if self._error_frame_count == 1:
                logger.info(
                    "NDI source '%s': %dx%d  stride=%d  FourCC=0x%08X",
                    self.source_name, v.xres, v.yres,
                    v.line_stride_in_bytes, v.FourCC,
                )
            if self._error_frame_count == 1 or self._error_frame_count % 300 == 0:
                mean = float(np.mean(bgr))
                if mean < 8.0:  # almost entirely black — NDI error frame
                    logger.warning(
                        "NDI frames from '%s' appear black (mean brightness %.1f). "
                        "The camera is likely sending NDI|HX (H.264/H.265 compressed) "
                        "which requires the NDI Runtime codec library. "
                        "Fix option 1: install the NDI Runtime — https://ndi.video/for-developers/ndi-sdk/ "
                        "Fix option 2: configure the camera to output standard NDI (not NDI|HX).",
                        self.source_name, mean,
                    )

        return bgr, now

    def _parse_position_metadata(self, m) -> None:
        """Parse a camera-sent PTZ position metadata frame into last_position."""
        # Extract raw XML — NDIlib binding versions expose frame data differently
        raw: Optional[str] = None
        data = getattr(m, "data", None)
        if data is not None:
            if isinstance(data, str):
                raw = data
            elif isinstance(data, (bytes, bytearray)):
                raw = data.decode("utf-8", errors="replace")
            else:
                # ctypes array or similar — try length-bounded bytes()
                try:
                    length = getattr(m, "length", None) or len(data)
                    raw = bytes(data[:length]).decode("utf-8", errors="replace")
                except Exception:
                    pass
        if raw is None:
            # Older SDK: p_data + length
            raw = bytes(m.p_data[: m.length]).decode("utf-8", errors="replace")

        raw = raw.strip()
        if not raw:
            return

        logger.debug("NDI metadata recv: %s", raw[:300])

        root = ET.fromstring(raw)
        _POS_TAGS = {"ntk_ptz_pan_tilt_zoom", "ndi_ptz_pan_tilt_zoom"}
        el = root if root.tag in _POS_TAGS else next(
            (root.find(f".//{tag}") for tag in _POS_TAGS if root.find(f".//{tag}") is not None),
            None,
        )
        if el is not None and "pan" in el.attrib:
            self.last_position = {
                "pan":  float(el.get("pan",  0.0)),
                "tilt": float(el.get("tilt", 0.0)),
                "zoom": float(el.get("zoom", 0.5)),
                "ts":   time.time(),
            }
            logger.debug(
                "PTZ position: pan=%.3f tilt=%.3f zoom=%.3f",
                self.last_position["pan"], self.last_position["tilt"], self.last_position["zoom"],
            )

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
    h, w   = v_frame.yres, v_frame.xres
    stride = v_frame.line_stride_in_bytes  # bytes per row including any padding
    raw    = np.frombuffer(bytes(v_frame.data), np.uint8)
    n      = len(raw)

    # BGRA / BGRX — 4 bytes per pixel (requested via RECV_COLOR_FORMAT_BGRX_BGRA)
    bpp4_stride = stride if stride > 0 else w * 4
    if n >= bpp4_stride * h and bpp4_stride >= w * 4:
        # Use numpy stride tricks to skip row-padding without copying rows one by one
        arr = np.lib.stride_tricks.as_strided(
            raw, shape=(h, w, 4), strides=(bpp4_stride, 4, 1)
        )
        return cv2.cvtColor(np.ascontiguousarray(arr), cv2.COLOR_BGRA2BGR)

    # UYVY — 2 bytes per pixel (fallback; some SDK paths deliver this)
    bpp2_stride = stride if stride > 0 else w * 2
    if n >= bpp2_stride * h and bpp2_stride >= w * 2:
        arr = np.lib.stride_tricks.as_strided(
            raw, shape=(h, w, 2), strides=(bpp2_stride, 2, 1)
        )
        return cv2.cvtColor(np.ascontiguousarray(arr), cv2.COLOR_YUV2BGR_UYVY)

    raise ValueError(
        f"Unsupported NDI frame: {n} bytes for {w}×{h} "
        f"stride={stride} "
        f"(expected ≥{w*4*h} for BGRA or ≥{w*2*h} for UYVY)"
    )
