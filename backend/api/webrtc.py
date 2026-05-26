from __future__ import annotations
import asyncio
import logging

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from av import VideoFrame

from ..core.session import get_session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/webrtc", tags=["webrtc"])

# All active peer connections — kept so we can close them on shutdown
_pcs: set[RTCPeerConnection] = set()

# Black fallback frame returned before any camera is connected
_BLACK_FRAME = np.zeros((288, 480, 3), dtype=np.uint8)


class NDIVideoTrack(VideoStreamTrack):
    """
    aiortc VideoStreamTrack that delivers frames from Session to the browser.

    Awaits session.next_frame() which is unblocked by session.push_frame()
    called from the synchronous NDI capture thread via call_soon_threadsafe.
    Falls back to a black frame if the camera is not yet connected.
    """

    kind = "video"

    def __init__(self, session) -> None:
        super().__init__()
        self._session = session

    async def recv(self) -> VideoFrame:
        pts, time_base = await self.next_timestamp()

        frame_bgr = self._session.latest_frame()
        if frame_bgr is None:
            frame_bgr = _BLACK_FRAME
        else:
            # Wait for the next pushed frame (max 100ms to avoid stalling)
            try:
                frame_bgr = await asyncio.wait_for(self._session.next_frame(), timeout=0.1)
            except asyncio.TimeoutError:
                frame_bgr = self._session.latest_frame() or _BLACK_FRAME

        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        video_frame = VideoFrame.from_ndarray(rgb, format="rgb24")
        video_frame.pts = pts
        video_frame.time_base = time_base
        return video_frame


# ── signaling endpoint ─────────────────────────────────────────────────────────

class OfferRequest(BaseModel):
    sdp: str
    type: str


@router.post("/offer")
async def webrtc_offer(req: OfferRequest):
    """
    WebRTC SDP offer/answer exchange.
    Browser sends its offer; server adds an NDI video track and returns the answer.
    ICE negotiation proceeds over the Tailscale peer addresses automatically.
    """
    session = get_session()
    pc = RTCPeerConnection()
    _pcs.add(pc)

    @pc.on("connectionstatechange")
    async def on_state_change():
        logger.info("WebRTC state: %s", pc.connectionState)
        if pc.connectionState in ("failed", "closed"):
            await pc.close()
            _pcs.discard(pc)

    pc.addTrack(NDIVideoTrack(session))

    offer = RTCSessionDescription(sdp=req.sdp, type=req.type)
    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}


# ── lifecycle ──────────────────────────────────────────────────────────────────

async def close_all() -> None:
    """Gracefully close every active peer connection on server shutdown."""
    if _pcs:
        await asyncio.gather(*[pc.close() for pc in list(_pcs)], return_exceptions=True)
    _pcs.clear()
