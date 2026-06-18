from __future__ import annotations
try:
    import NDIlib as ndi
except ImportError:
    ndi = None  # type: ignore[assignment]


class NDIPTZCamera:
    """
    Sends PTZ velocity commands to an NDI PTZ camera via metadata XML.

    Zoom broadcasts both ntk_ptz_* and ndi_ptz_* namespaces for maximum
    hardware compatibility across BirdDog, Bolin, and other NDI PTZ cameras.
    Pan/tilt uses ntk_ only (sufficient across all tested hardware).
    Includes a legacy SDK fallback for older NDIlib Python bindings.
    """

    def __init__(self, recv) -> None:
        self._recv = recv

    # ── public API ─────────────────────────────────────────────────────────────

    def pan_tilt_speed(self, pan: float, tilt: float = 0.0) -> None:
        pan, tilt = _clamp(pan), _clamp(tilt)
        self._send(
            f'<ntk_ptz_pan_tilt_speed pan_speed="{pan:.3f}" tilt_speed="{tilt:.3f}"/>'
        )

    def zoom_speed(self, zoom: float) -> None:
        z = _clamp(zoom)
        self._send(f'<ntk_ptz_zoom_speed zoom_speed="{z:.3f}"/>')
        self._send(f'<ndi_ptz_zoom_speed zoom_speed="{z:.3f}"/>')

    def stop(self) -> None:
        self.pan_tilt_speed(0.0, 0.0)
        self.zoom_speed(0.0)

    def go_to(self, pan: float, tilt: float, zoom: float = 0.5) -> None:
        """
        Absolute PTZ position command.
        pan/tilt: -1.0 (left/down) to 1.0 (right/up).
        zoom:      0.0 (wide-angle) to 1.0 (full tele).
        Sends both ntk_ and ndi_ namespaces for maximum camera compatibility.
        """
        pan  = _clamp(pan)
        tilt = _clamp(tilt)
        zoom = _clamp(zoom, 0.0, 1.0)
        self._send(f'<ntk_ptz_pan_tilt_zoom pan="{pan:.3f}" tilt="{tilt:.3f}" zoom="{zoom:.3f}"/>')
        self._send(f'<ndi_ptz_pan_tilt_zoom pan="{pan:.3f}" tilt="{tilt:.3f}" zoom="{zoom:.3f}"/>')

    def autofocus(self) -> None:
        self._send('<ntk_ptz_focus_auto autofocus="on"/>')

    # ── internal ───────────────────────────────────────────────────────────────

    def _send(self, xml: str) -> None:
        try:
            meta = ndi.MetadataFrame()
            meta.data, meta.timecode = xml, 0
            ndi.recv_send_metadata(self._recv, meta)
        except Exception:
            # Legacy binding fallback (older NDIlib Python wrappers)
            try:
                m = ndi.NDIlib_metadata_frame_t()
                payload = xml.encode("utf-8")
                m.p_data, m.length, m.timecode = payload, len(payload), 0
                ndi.recv_send_metadata(self._recv, m)
            except Exception as exc:
                raise RuntimeError(f"PTZ XML send failed: {exc}") from exc


def _clamp(v: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(v)))

