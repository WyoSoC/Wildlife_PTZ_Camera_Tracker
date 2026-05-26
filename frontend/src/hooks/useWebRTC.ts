import { useCallback, useRef, useState } from 'react'
import { api } from '../api/client'

const ICE_SERVERS: RTCIceServer[] = [
  { urls: 'stun:stun.l.google.com:19302' },
]

// How long to wait for ICE gathering before sending the offer anyway
const ICE_GATHER_TIMEOUT_MS = 3000

export function useWebRTC() {
  const pcRef = useRef<RTCPeerConnection | null>(null)
  const [stream, setStream] = useState<MediaStream | null>(null)
  const [rtcState, setRtcState] = useState<RTCPeerConnectionState>('new')

  const start = useCallback(async () => {
    if (pcRef.current) return

    const pc = new RTCPeerConnection({ iceServers: ICE_SERVERS })
    pcRef.current = pc

    pc.onconnectionstatechange = () => setRtcState(pc.connectionState)
    pc.ontrack = (e) => { if (e.streams[0]) setStream(e.streams[0]) }

    // Declare intent to receive video only (no local camera needed)
    pc.addTransceiver('video', { direction: 'recvonly' })

    const offer = await pc.createOffer()
    await pc.setLocalDescription(offer)

    // Wait for ICE gathering or timeout — whichever comes first
    await new Promise<void>((resolve) => {
      if (pc.iceGatheringState === 'complete') { resolve(); return }
      const done = () => { resolve() }
      pc.addEventListener('icegatheringstatechange', () => {
        if (pc.iceGatheringState === 'complete') done()
      })
      setTimeout(done, ICE_GATHER_TIMEOUT_MS)
    })

    const { sdp, type } = await api.webrtc.offer(
      pc.localDescription!.sdp,
      pc.localDescription!.type,
    )
    await pc.setRemoteDescription({ sdp, type: type as RTCSdpType })
  }, [])

  const stop = useCallback(() => {
    pcRef.current?.close()
    pcRef.current = null
    setStream(null)
    setRtcState('closed')
  }, [])

  return { stream, rtcState, startWebRTC: start, stopWebRTC: stop }
}
