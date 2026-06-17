import { useEffect, useRef, useState } from 'react'
import { clsx } from 'clsx'

interface VideoPlayerProps {
  stream:    MediaStream | null
  rtcState:  RTCPeerConnectionState
  rtcError?: string | null
  className?: string
}

const STATE_LABEL: Partial<Record<RTCPeerConnectionState, string>> = {
  new:          'Click Connect to start video',
  connecting:   'Connecting…',
  disconnected: 'Connection lost — retrying',
  closed:       'Stopped',
}

export function VideoPlayer({ stream, rtcState, rtcError, className }: VideoPlayerProps) {
  const videoRef  = useRef<HTMLVideoElement>(null)
  const [vidError, setVidError] = useState<string | null>(null)

  useEffect(() => {
    if (videoRef.current) {
      videoRef.current.srcObject = stream
      setVidError(null)
    }
  }, [stream])

  const showOverlay = rtcState !== 'connected' || !!rtcError || !!vidError
  const errorMsg    = rtcError ?? vidError

  const stateLabel = rtcState === 'failed'
    ? (rtcError ?? 'WebRTC failed')
    : (STATE_LABEL[rtcState] ?? `WebRTC: ${rtcState}`)

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
        onError={(e) => {
          const v = e.currentTarget
          const msg = v.error
            ? `Video error ${v.error.code}: ${v.error.message}`
            : 'Video element error'
          setVidError(msg)
        }}
      />
      {showOverlay && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-black/80">
          {rtcState === 'connecting' && (
            <span className="w-6 h-6 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
          )}
          <span className={clsx(
            'text-sm text-center px-4',
            errorMsg ? 'text-red-400' : 'text-white/50',
          )}>
            {errorMsg ?? stateLabel}
          </span>
        </div>
      )}
    </div>
  )
}
