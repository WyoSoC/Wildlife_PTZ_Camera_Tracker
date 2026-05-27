import { useCallback, useRef, useState } from 'react'
import { api } from '../api/client'

const ICE_SERVERS: RTCIceServer[] = [
  { urls: 'stun:stun.l.google.com:19302' },
]

const ICE_GATHER_TIMEOUT_MS = 3000

export function useWebRTC(cameraId: string | null) {
  const pcRef = useRef<RTCPeerConnection | null>(null)
  const [stream,   setStream]   = useState<MediaStream | null>(null)
  const [rtcState, setRtcState] = useState<RTCPeerConnectionState>('new')

  const start = useCallback(async () => {
    if (!cameraId || pcRef.current) return

    const pc = new RTCPeerConnection({ iceServers: ICE_SERVERS })
    pcRef.current = pc

    pc.onconnectionstatechange = () => setRtcState(pc.connectionState)
    pc.ontrack = (e) => { if (e.streams[0]) setStream(e.streams[0]) }

    pc.addTransceiver('video', { direction: 'recvonly' })

    const offer = await pc.createOffer()
    await pc.setLocalDescription(offer)

    await new Promise<void>((resolve) => {
      if (pc.iceGatheringState === 'complete') { resolve(); return }
      pc.addEventListener('icegatheringstatechange', () => {
        if (pc.iceGatheringState === 'complete') resolve()
      })
      setTimeout(resolve, ICE_GATHER_TIMEOUT_MS)
    })

    const { sdp, type } = await api.webrtc.offer(
      cameraId,
      pc.localDescription!.sdp,
      pc.localDescription!.type,
    )
    await pc.setRemoteDescription({ sdp, type: type as RTCSdpType })
  }, [cameraId])

  const stop = useCallback(() => {
    pcRef.current?.close()
    pcRef.current = null
    setStream(null)
    setRtcState('closed')
  }, [])

  return { stream, rtcState, startWebRTC: start, stopWebRTC: stop }
}
