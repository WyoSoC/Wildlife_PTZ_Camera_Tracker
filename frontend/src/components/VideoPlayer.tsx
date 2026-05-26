import { useEffect, useRef } from 'react'
import { clsx } from 'clsx'

interface VideoPlayerProps {
  stream: MediaStream | null
  rtcState: RTCPeerConnectionState
  className?: string
}

const STATE_LABEL: Partial<Record<RTCPeerConnectionState, string>> = {
  new:          'Click Connect to start video',
  connecting:   'Connecting…',
  disconnected: 'Connection lost — retrying',
  failed:       'WebRTC failed',
  closed:       'Stopped',
}

export function VideoPlayer({ stream, rtcState, className }: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null)

  useEffect(() => {
    if (videoRef.current) {
      videoRef.current.srcObject = stream
    }
  }, [stream])

  const showOverlay = rtcState !== 'connected'

  return (
    <div
      className={clsx(
        'relative bg-black rounded-lg overflow-hidden',
        'aspect-video w-full',
        className,
      )}
    >
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        className="w-full h-full object-contain"
      />
      {showOverlay && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-black/80">
          {rtcState === 'connecting' && (
            <span className="w-6 h-6 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
          )}
          <span className="text-white/50 text-sm text-center px-4">
            {STATE_LABEL[rtcState] ?? `WebRTC: ${rtcState}`}
          </span>
        </div>
      )}
    </div>
  )
}
