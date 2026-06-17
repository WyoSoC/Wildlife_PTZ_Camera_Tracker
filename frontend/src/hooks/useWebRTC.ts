import { useCallback, useRef, useState } from 'react'
import { api } from '../api/client'

const ICE_SERVERS: RTCIceServer[] = [
  { urls: 'stun:stun.l.google.com:19302' },
]

const ICE_GATHER_TIMEOUT_MS = 3000

/** Reorder codec list so VP8 is first — avoids "Video decoder not found" on
 *  Linux Chrome, which may lack an H.264 decoder in some builds. */
function preferVP8(transceiver: RTCRtpTransceiver) {
  const caps = RTCRtpReceiver.getCapabilities?.('video')
  if (!caps) return
  const vp8   = caps.codecs.filter(c => c.mimeType === 'video/VP8')
  const rtx   = caps.codecs.filter(c => c.mimeType === 'video/rtx')
  const other = caps.codecs.filter(c => c.mimeType !== 'video/VP8' && c.mimeType !== 'video/rtx')
  try {
    transceiver.setCodecPreferences([...vp8, ...other, ...rtx])
  } catch {
    // setCodecPreferences not supported — ignore, VP8 will usually still work
  }
}

export function useWebRTC(cameraId: string | null) {
  const pcRef = useRef<RTCPeerConnection | null>(null)
  const [stream,   setStream]   = useState<MediaStream | null>(null)
  const [rtcState, setRtcState] = useState<RTCPeerConnectionState>('new')
  const [rtcError, setRtcError] = useState<string | null>(null)

  const start = useCallback(async () => {
    if (!cameraId || pcRef.current) return
    setRtcError(null)

    const pc = new RTCPeerConnection({ iceServers: ICE_SERVERS })
    pcRef.current = pc

    pc.onconnectionstatechange = () => {
      setRtcState(pc.connectionState)
      if (pc.connectionState === 'failed') {
        setRtcError('ICE connection failed — check network / Tailscale')
      }
    }
    pc.ontrack = (e) => { if (e.streams[0]) setStream(e.streams[0]) }

    const transceiver = pc.addTransceiver('video', { direction: 'recvonly' })
    preferVP8(transceiver)

    const offer = await pc.createOffer()
    await pc.setLocalDescription(offer)

    await new Promise<void>((resolve) => {
      if (pc.iceGatheringState === 'complete') { resolve(); return }
      pc.addEventListener('icegatheringstatechange', () => {
        if (pc.iceGatheringState === 'complete') resolve()
      })
      setTimeout(resolve, ICE_GATHER_TIMEOUT_MS)
    })

    try {
      const { sdp, type } = await api.webrtc.offer(
        cameraId,
        pc.localDescription!.sdp,
        pc.localDescription!.type,
      )
      await pc.setRemoteDescription({ sdp, type: type as RTCSdpType })
    } catch (err) {
      setRtcError(err instanceof Error ? err.message : String(err))
      setRtcState('failed')
      pc.close()
      pcRef.current = null
    }
  }, [cameraId])

  const stop = useCallback(() => {
    pcRef.current?.close()
    pcRef.current = null
    setStream(null)
    setRtcState('closed')
    setRtcError(null)
  }, [])

  return { stream, rtcState, rtcError, startWebRTC: start, stopWebRTC: stop }
}
