from __future__ import annotations
import asyncio
import logging

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from av import VideoFrame

from ..core.camera_manager import get_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/webrtc", tags=["webrtc"])

_pcs: set[RTCPeerConnection] = set()
_BLACK_FRAME = np.zeros((288, 480, 3), dtype=np.uint8)


class NDIVideoTrack(VideoStreamTrack):
    """Delivers frames from a camera Session to the browser via WebRTC."""

    kind = "video"

    def __init__(self, session) -> None:
        super().__init__()
        self._session = session

    async def recv(self) -> VideoFrame:
        pts, time_base = await self.next_timestamp()

        frame_bgr = self._session.latest_frame()
        if frame_bgr is None:
            try:
                frame_bgr = await asyncio.wait_for(self._session.next_frame(), timeout=0.1)
            except asyncio.TimeoutError:
                frame_bgr = _BLACK_FRAME
        else:
            try:
                frame_bgr = await asyncio.wait_for(self._session.next_frame(), timeout=0.1)
            except asyncio.TimeoutError:
                pass  # keep the frame_bgr we already have

        rgb         = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        video_frame = VideoFrame.from_ndarray(rgb, format="rgb24")
        video_frame.pts       = pts
        video_frame.time_base = time_base
        return video_frame


class OfferRequest(BaseModel):
    sdp:  str
    type: str


@router.post("/{camera_id}/offer")
async def webrtc_offer(camera_id: str, req: OfferRequest):
    """SDP offer/answer for a specific camera."""
    entry = get_manager().get(camera_id)
    if entry is None:
        raise HTTPException(404, f"Camera '{camera_id}' not found")

    pc = RTCPeerConnection()
    _pcs.add(pc)

    @pc.on("connectionstatechange")
    async def on_state_change():
        logger.info("WebRTC [%s] state: %s", camera_id, pc.connectionState)
        if pc.connectionState in ("failed", "closed"):
            await pc.close()
            _pcs.discard(pc)

    pc.addTrack(NDIVideoTrack(entry.session))

    offer = RTCSessionDescription(sdp=req.sdp, type=req.type)
    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}


async def close_all() -> None:
    if _pcs:
        await asyncio.gather(*[pc.close() for pc in list(_pcs)], return_exceptions=True)
    _pcs.clear()
