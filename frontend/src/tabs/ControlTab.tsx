import { useCallback, useEffect, useRef, useState } from 'react'
import { Play, Square, Crosshair, Radio } from 'lucide-react'
import { useWebRTC } from '../hooks/useWebRTC'
import { useGamepad } from '../hooks/useGamepad'
import { VideoPlayer } from '../components/VideoPlayer'
import { JoystickStatus } from '../components/JoystickStatus'
import { TelemetryPanel } from '../components/TelemetryPanel'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Badge, StatusDot } from '../components/ui/Badge'
import { api } from '../api/client'
import type { CameraStatus, WebSocketHook } from '../types'

const GAMEPAD_SEND_HZ     = 20
const GAMEPAD_INTERVAL_MS = 1000 / GAMEPAD_SEND_HZ

interface Props {
  ws:        WebSocketHook
  cameraId:  string | null
}

export function ControlTab({ ws, cameraId }: Props) {
  const { stream, rtcState, startWebRTC, stopWebRTC } = useWebRTC(cameraId)
  const { telemetry, sendPanTilt, sendZoom, sendStop, sendAutofocus, setMode, setRecording } = ws
  const [camStatus,   setCamStatus]   = useState<CameraStatus | null>(null)
  const [loopLoading, setLoopLoading] = useState(false)

  useEffect(() => {
    if (!cameraId) return
    api.cameras.status(cameraId).then(setCamStatus).catch(console.error)
  }, [cameraId])

  const startCamera = useCallback(async () => {
    if (!cameraId) return
    try {
      setLoopLoading(true)
      await api.cameras.start(cameraId)
      setCamStatus(await api.cameras.status(cameraId))
    } catch (e) { console.error(e) }
    finally { setLoopLoading(false) }
  }, [cameraId])

  const stopCamera = useCallback(async () => {
    if (!cameraId) return
    try {
      setLoopLoading(true)
      await api.cameras.stop(cameraId)
      setCamStatus(await api.cameras.status(cameraId))
    } catch (e) { console.error(e) }
    finally { setLoopLoading(false) }
  }, [cameraId])

  const lastSendMs = useRef(0)
  const modeRef    = useRef(telemetry?.mode ?? 'manual')
  useEffect(() => { modeRef.current = telemetry?.mode ?? 'manual' }, [telemetry?.mode])

  const handleAxes = useCallback(
    (pan: number, tilt: number, zoom: number) => {
      if (modeRef.current !== 'manual') return
      const now = performance.now()
      if (now - lastSendMs.current < GAMEPAD_INTERVAL_MS) return
      lastSendMs.current = now
      sendPanTilt(pan, tilt)
      sendZoom(zoom)
    },
    [sendPanTilt, sendZoom],
  )

  const gamepad = useGamepad(handleAxes)

  useEffect(() => { if (gamepad.btnStop)  sendStop() },     [gamepad.btnStop,  sendStop])
  useEffect(() => { if (gamepad.btnFocus) sendAutofocus() }, [gamepad.btnFocus, sendAutofocus])

  const isRecording = telemetry?.rec_active ?? false
  const mode        = telemetry?.mode ?? 'manual'
  const recPct      = telemetry
    ? Math.min(100, (telemetry.rec_elapsed / Math.max(1, telemetry.rec_total)) * 100)
    : 0

  return (
    <div className="h-full overflow-auto p-4">
      <div className="flex gap-4 max-w-6xl mx-auto">

        {/* ── Video + joystick ── */}
        <div className="flex-1 min-w-0 space-y-3">
          <Card>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {isRecording && <Badge color="red" pulse>REC</Badge>}
                  {telemetry && (
                    <span className="text-xs text-white/40 font-mono">
                      {telemetry.fps.toFixed(1)} fps
                      {telemetry.detected && ` · ${telemetry.speed_deg.toFixed(1)}°/s`}
                    </span>
                  )}
                </div>
                <div className="flex gap-2">
                  {rtcState === 'connected'
                    ? <Button size="sm" variant="ghost" onClick={stopWebRTC}>Disconnect</Button>
                    : <Button size="sm" onClick={startWebRTC}
                              disabled={!cameraId}
                              loading={rtcState === 'connecting'}>
                        Connect Video
                      </Button>
                  }
                </div>
              </div>
              <VideoPlayer stream={stream} rtcState={rtcState} />
            </div>
          </Card>

          <Card title="Joystick">
            <JoystickStatus state={gamepad} onStop={sendStop} onAutofocus={sendAutofocus} />
          </Card>
        </div>

        {/* ── Controls ── */}
        <div className="w-64 shrink-0 space-y-3">

          <Card title="Camera">
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <StatusDot active={camStatus?.running ?? false} />
                <span className="text-xs text-white/50 flex-1 truncate">
                  {camStatus?.running
                    ? (camStatus.source_name || 'Running')
                    : 'Not running'}
                </span>
              </div>
              {camStatus?.device_name && (
                <div className="text-xs text-white/30 truncate font-mono"
                     title={camStatus.device}>
                  {camStatus.device_name}
                </div>
              )}
              {camStatus?.running ? (
                <Button variant="ghost" size="sm" className="w-full"
                  onClick={stopCamera} loading={loopLoading}>
                  <Square size={11} /> Stop Camera
                </Button>
              ) : (
                <Button size="sm" className="w-full"
                  onClick={startCamera} loading={loopLoading}
                  disabled={!cameraId || !camStatus?.source_name}>
                  <Play size={11} /> Start Camera
                </Button>
              )}
            </div>
          </Card>

          <Card title="Mode">
            <div className="flex gap-2">
              {(['manual', 'auto_track'] as const).map(m => (
                <button
                  key={m}
                  onClick={() => setMode(m)}
                  className={[
                    'flex-1 py-2 text-xs font-medium rounded border transition-colors',
                    mode === m
                      ? m === 'manual'
                        ? 'bg-blue-600 border-blue-500 text-white'
                        : 'bg-green-700 border-green-600 text-white'
                      : 'bg-surface-raised border-surface-border text-white/40 hover:text-white/70',
                  ].join(' ')}
                >
                  {m === 'auto_track' && <Crosshair size={11} className="inline mr-1" />}
                  {m === 'manual' ? 'Manual' : 'Auto-track'}
                </button>
              ))}
            </div>
          </Card>

          <Card title="Recording">
            <div className="space-y-3">
              {isRecording ? (
                <>
                  <div className="space-y-1">
                    <div className="flex justify-between text-xs">
                      <span className="text-red-400 font-medium flex items-center gap-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse inline-block" />
                        Recording
                      </span>
                      <span className="font-mono text-white/60">
                        {telemetry?.rec_elapsed.toFixed(0)}s / {telemetry?.rec_total.toFixed(0)}s
                      </span>
                    </div>
                    <div className="h-1.5 bg-surface-border rounded-full overflow-hidden">
                      <div className="h-full bg-red-500 rounded-full transition-all duration-500"
                           style={{ width: `${recPct}%` }} />
                    </div>
                  </div>
                  <Button variant="ghost" size="sm" className="w-full"
                    onClick={() => setRecording('stop')}>
                    <Square size={11} /> Stop Recording
                  </Button>
                </>
              ) : (
                <Button variant="danger" size="sm" className="w-full"
                  onClick={() => setRecording('start')}>
                  <Radio size={11} /> Start Recording
                </Button>
              )}
            </div>
          </Card>

          <Card title="PTZ Quick">
            <div className="space-y-2">
              <Button variant="ghost" size="sm" className="w-full" onClick={sendStop}>
                Stop All Motion
              </Button>
              <Button variant="ghost" size="sm" className="w-full" onClick={sendAutofocus}>
                Trigger Autofocus
              </Button>
            </div>
          </Card>

          <Card title="Telemetry">
            <TelemetryPanel telemetry={telemetry} />
          </Card>
        </div>
      </div>
    </div>
  )
}
