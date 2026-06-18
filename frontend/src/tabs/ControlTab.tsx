import { useCallback, useEffect, useRef, useState } from 'react'
import { Play, Square, Crosshair, Radio, CheckCircle2 } from 'lucide-react'
import { useWebRTC } from '../hooks/useWebRTC'
import { useGamepad } from '../hooks/useGamepad'
import { VideoPlayer } from '../components/VideoPlayer'
import { JoystickStatus } from '../components/JoystickStatus'
import { TelemetryPanel } from '../components/TelemetryPanel'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { SliderField, ToggleField } from '../components/ui/SliderField'
import { Badge, StatusDot } from '../components/ui/Badge'
import { api } from '../api/client'
import type { CameraConfig, CameraStatus, ConfigUpdate, WebSocketHook } from '../types'

const GAMEPAD_SEND_HZ     = 20
const GAMEPAD_INTERVAL_MS = 1000 / GAMEPAD_SEND_HZ

interface Props {
  ws:        WebSocketHook
  cameraId:  string | null
}

export function ControlTab({ ws, cameraId }: Props) {
  const { stream, rtcState, rtcError, startWebRTC, stopWebRTC } = useWebRTC(cameraId)
  const { telemetry, sendPanTilt, sendZoom, sendStop, sendAutofocus, setMode, setRecording } = ws
  const [camStatus,   setCamStatus]   = useState<CameraStatus | null>(null)
  const [loopLoading, setLoopLoading] = useState(false)
  const [config,      setConfig]      = useState<CameraConfig | null>(null)
  const [saveStatus,  setSaveStatus]  = useState<'idle' | 'saving' | 'saved'>('idle')
  const debounceRef = useRef<ReturnType<typeof setTimeout>>()

  useEffect(() => {
    if (!cameraId) return
    const fetch = () => api.cameras.status(cameraId).then(setCamStatus).catch(console.error)
    fetch()
    const id = setInterval(fetch, 2000)
    return () => clearInterval(id)
  }, [cameraId])

  useEffect(() => {
    if (!cameraId) return
    api.cameras.getConfig(cameraId).then(setConfig).catch(console.error)
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

  const patchConfig = useCallback((update: ConfigUpdate) => {
    if (!cameraId) return
    setConfig(prev => {
      if (!prev) return prev
      return {
        ...prev,
        pan:    { ...prev.pan,
          ...(update.pan_dead_zone_px !== undefined && { dead_zone_px: update.pan_dead_zone_px }),
          ...(update.pan_thresh_px   !== undefined && { thresh_px:    update.pan_thresh_px }),
          ...(update.pan_kp          !== undefined && { kp:           update.pan_kp }),
          ...(update.pan_max_speed   !== undefined && { max_speed:    update.pan_max_speed }),
          ...(update.pan_min_speed   !== undefined && { min_speed:    update.pan_min_speed }),
          ...(update.pan_invert      !== undefined && { invert:       update.pan_invert }),
        },
        zoom:   { ...prev.zoom,
          ...(update.zoom_in_frac   !== undefined && { zoom_in_frac:  update.zoom_in_frac }),
          ...(update.zoom_out_frac  !== undefined && { zoom_out_frac: update.zoom_out_frac }),
          ...(update.zoom_speed     !== undefined && { speed:         update.zoom_speed }),
          ...(update.zoom_invert    !== undefined && { invert:        update.zoom_invert }),
          ...(update.zoom_ema_alpha !== undefined && { ema_alpha:     update.zoom_ema_alpha }),
        },
        track:  { ...prev.track,
          ...(update.detect_classes !== undefined && { detect_classes: update.detect_classes }),
        },
        record: { ...prev.record,
          ...(update.record_duration_sec !== undefined && { duration_sec: update.record_duration_sec }),
          ...(update.record_fps          !== undefined && { fps:          update.record_fps }),
        },
        speed:  { ...prev.speed,
          ...(update.hfov_deg !== undefined && { hfov_deg: update.hfov_deg }),
        },
      }
    })
    setSaveStatus('saving')
    clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(async () => {
      try {
        await api.cameras.updateConfig(cameraId, update)
        setSaveStatus('saved')
        setTimeout(() => setSaveStatus('idle'), 1500)
      } catch (e) { console.error(e); setSaveStatus('idle') }
    }, 400)
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
      <div className="flex gap-4 max-w-7xl mx-auto">

        {/* ── Left panel: camera tuning ── */}
        <div className="w-56 shrink-0 space-y-3">

          <div className="flex items-center justify-between h-5">
            <span className="text-xs font-semibold text-white/40 uppercase tracking-wider">Tuning</span>
            {saveStatus === 'saved'  && <span className="text-xs text-green-400 flex gap-1 items-center"><CheckCircle2 size={11}/> Saved</span>}
            {saveStatus === 'saving' && <span className="text-xs text-white/30">Saving…</span>}
          </div>

          {config ? (
            <>
              <Card title="Pan Controller">
                <div className="space-y-3">
                  <SliderField label="Dead zone" unit="px" decimals={0} step={1}
                    min={0} max={200} value={config.pan.dead_zone_px}
                    onChange={v => patchConfig({ pan_dead_zone_px: Math.round(v) })} />
                  <SliderField label="Threshold" unit="px" decimals={0} step={1}
                    min={0} max={400} value={config.pan.thresh_px}
                    onChange={v => patchConfig({ pan_thresh_px: Math.round(v) })} />
                  <SliderField label="Gain (Kp)" step={0.05}
                    min={0.1} max={2.0} value={config.pan.kp}
                    onChange={v => patchConfig({ pan_kp: v })} />
                  <SliderField label="Max speed" step={0.05}
                    min={0.1} max={1.0} value={config.pan.max_speed}
                    onChange={v => patchConfig({ pan_max_speed: v })} />
                  <SliderField label="Min speed" step={0.01}
                    min={0.01} max={0.5} value={config.pan.min_speed}
                    onChange={v => patchConfig({ pan_min_speed: v })} />
                  <ToggleField label="Invert pan"
                    value={config.pan.invert}
                    onChange={v => patchConfig({ pan_invert: v })} />
                </div>
              </Card>

              <Card title="Zoom Controller">
                <div className="space-y-3">
                  <SliderField label="Zoom-in  <" step={0.01}
                    min={0.05} max={0.5} value={config.zoom.zoom_in_frac}
                    onChange={v => patchConfig({ zoom_in_frac: v })} />
                  <SliderField label="Zoom-out >" step={0.01}
                    min={0.1} max={0.9} value={config.zoom.zoom_out_frac}
                    onChange={v => patchConfig({ zoom_out_frac: v })} />
                  <SliderField label="Speed" step={0.05}
                    min={0.1} max={1.0} value={config.zoom.speed}
                    onChange={v => patchConfig({ zoom_speed: v })} />
                  <SliderField label="EMA α" step={0.01}
                    min={0.01} max={1.0} value={config.zoom.ema_alpha}
                    onChange={v => patchConfig({ zoom_ema_alpha: v })} />
                  <ToggleField label="Invert zoom"
                    value={config.zoom.invert}
                    onChange={v => patchConfig({ zoom_invert: v })} />
                </div>
              </Card>

              <Card title="Tracking">
                <div className="space-y-3">
                  <SliderField label="H-FOV" unit="°" decimals={0} step={1}
                    min={10} max={120} value={config.speed.hfov_deg}
                    onChange={v => patchConfig({ hfov_deg: v })} />
                </div>
              </Card>

              <Card title="Recording">
                <div className="space-y-3">
                  <SliderField label="Duration" unit="s" decimals={0} step={5}
                    min={5} max={300} value={config.record.duration_sec}
                    onChange={v => patchConfig({ record_duration_sec: Math.round(v) })} />
                  <div className="flex items-center gap-3">
                    <span className="w-24 shrink-0 text-xs text-white/50">FPS</span>
                    <select
                      value={config.record.fps}
                      onChange={e => patchConfig({ record_fps: parseInt(e.target.value) })}
                      className="flex-1 text-xs bg-surface-base border border-surface-border
                                 rounded px-2 py-1.5 text-white focus:outline-none focus:border-blue-500"
                    >
                      {[15, 20, 25, 30].map(fps => <option key={fps} value={fps}>{fps} fps</option>)}
                    </select>
                  </div>
                  <p className="text-xs text-white/25">
                    Output: {config.record.record_res[0]} × {config.record.record_res[1]} px
                  </p>
                </div>
              </Card>
            </>
          ) : (
            <p className="text-xs text-white/30 text-center py-4">
              {cameraId ? 'Loading…' : 'Select a camera'}
            </p>
          )}
        </div>

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
              <VideoPlayer stream={stream} rtcState={rtcState} rtcError={rtcError} />
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
                <>
                  <Button size="sm" className="w-full"
                    onClick={startCamera} loading={loopLoading}
                    disabled={!cameraId || (!camStatus?.source_match && !camStatus?.rtsp_url)}>
                    <Play size={11} /> Start Camera
                  </Button>
                  {camStatus && !camStatus.source_match && !camStatus.rtsp_url && (
                    <p className="text-xs text-white/30 text-center">
                      Configure a source in the Camera tab first
                    </p>
                  )}
                </>
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
