import { useCallback, useEffect, useRef, useState } from 'react'
import { RefreshCw, Wifi, Camera, CheckCircle2, Play, Square } from 'lucide-react'
import { api } from '../api/client'
import type { CameraConfig, CameraStatus, ConfigUpdate, NDISource } from '../types'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { SliderField, ToggleField } from '../components/ui/SliderField'
import { StatusDot } from '../components/ui/Badge'

const YOLO_MODELS = ['yolov8n.pt', 'yolov8s.pt', 'yolov8m.pt']
const CLASS_OPTIONS = [
  { value: 0,    label: 'Person' },
  { value: 2,    label: 'Car' },
  { value: 16,   label: 'Dog' },
  { value: null, label: 'All objects' },
]

export function CameraTab() {
  const [sources, setSources] = useState<NDISource[]>([])
  const [scanning, setScanning] = useState(false)
  const [config, setConfig] = useState<CameraConfig | null>(null)
  const [camStatus, setCamStatus] = useState<CameraStatus | null>(null)
  const [reolinkUrl, setReolinkUrl] = useState('')
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'saved'>('idle')
  const [loopLoading, setLoopLoading] = useState(false)
  const debounceRef = useRef<ReturnType<typeof setTimeout>>()

  // Load config + initial status on mount
  useEffect(() => {
    api.cameras.getConfig().then(setConfig).catch(console.error)
    api.cameras.status().then(setCamStatus).catch(console.error)
  }, [])

  const scan = useCallback(async () => {
    setScanning(true)
    try {
      const { sources: found } = await api.cameras.discover()
      setSources(found)
    } catch (e) {
      console.error(e)
    } finally {
      setScanning(false)
    }
  }, [])

  const connectAndStart = useCallback(async (source: NDISource) => {
    try {
      await api.cameras.connect(source.name, source.type)
      setLoopLoading(true)
      await api.cameras.start()
      const s = await api.cameras.status()
      setCamStatus(s)
    } catch (e) {
      console.error(e)
    } finally {
      setLoopLoading(false)
    }
  }, [])

  const connectReolink = useCallback(async () => {
    if (!reolinkUrl) return
    const label = reolinkUrl.split('@').pop() ?? reolinkUrl
    try {
      await api.cameras.connect(label, 'reolink', reolinkUrl)
      setLoopLoading(true)
      await api.cameras.start()
      const s = await api.cameras.status()
      setCamStatus(s)
    } catch (e) {
      console.error(e)
    } finally {
      setLoopLoading(false)
    }
  }, [reolinkUrl])

  const stopCamera = useCallback(async () => {
    try {
      setLoopLoading(true)
      await api.cameras.stop()
      const s = await api.cameras.status()
      setCamStatus(s)
    } catch (e) {
      console.error(e)
    } finally {
      setLoopLoading(false)
    }
  }, [])

  // Debounced config update
  const patchConfig = useCallback((update: ConfigUpdate) => {
    setConfig(prev => {
      if (!prev) return prev
      return {
        ...prev,
        pan: {
          ...prev.pan,
          ...(update.pan_dead_zone_px !== undefined && { dead_zone_px: update.pan_dead_zone_px }),
          ...(update.pan_thresh_px   !== undefined && { thresh_px:    update.pan_thresh_px }),
          ...(update.pan_kp          !== undefined && { kp:           update.pan_kp }),
          ...(update.pan_max_speed   !== undefined && { max_speed:    update.pan_max_speed }),
          ...(update.pan_min_speed   !== undefined && { min_speed:    update.pan_min_speed }),
          ...(update.pan_invert      !== undefined && { invert:       update.pan_invert }),
        },
        zoom: {
          ...prev.zoom,
          ...(update.zoom_in_frac   !== undefined && { zoom_in_frac:  update.zoom_in_frac }),
          ...(update.zoom_out_frac  !== undefined && { zoom_out_frac: update.zoom_out_frac }),
          ...(update.zoom_speed     !== undefined && { speed:         update.zoom_speed }),
          ...(update.zoom_invert    !== undefined && { invert:        update.zoom_invert }),
          ...(update.zoom_ema_alpha !== undefined && { ema_alpha:     update.zoom_ema_alpha }),
        },
        track: {
          ...prev.track,
          ...(update.detect_classes !== undefined && { detect_classes: update.detect_classes }),
        },
        record: {
          ...prev.record,
          ...(update.record_duration_sec !== undefined && { duration_sec: update.record_duration_sec }),
          ...(update.record_fps          !== undefined && { fps:          update.record_fps }),
        },
        speed: {
          ...prev.speed,
          ...(update.hfov_deg !== undefined && { hfov_deg: update.hfov_deg }),
        },
      }
    })

    setSaveStatus('saving')
    clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(async () => {
      try {
        await api.cameras.updateConfig(update)
        setSaveStatus('saved')
        setTimeout(() => setSaveStatus('idle'), 1500)
      } catch (e) {
        console.error(e)
        setSaveStatus('idle')
      }
    }, 400)
  }, [])

  return (
    <div className="h-full overflow-auto p-4">
      <div className="flex gap-4 max-w-6xl mx-auto">

        {/* ── Left panel: source discovery ── */}
        <div className="w-72 shrink-0 space-y-3">
          <Card title="NDI Sources">
            <div className="space-y-2">
              <Button
                onClick={scan}
                loading={scanning}
                size="sm"
                className="w-full"
              >
                <RefreshCw size={12} />
                {scanning ? 'Scanning…' : 'Scan Network'}
              </Button>

              {sources.length === 0 && !scanning && (
                <p className="text-xs text-white/30 text-center py-3">
                  No sources found. Click Scan.
                </p>
              )}

              {sources.map((src) => {
                const active = camStatus?.source_name === src.name && camStatus?.running
                return (
                  <div
                    key={src.name}
                    className="flex items-center gap-2 p-2 rounded-md bg-surface-raised
                               border border-surface-border hover:border-blue-600/50
                               transition-colors group"
                  >
                    <Wifi size={13} className="text-blue-400 shrink-0" />
                    <span className="flex-1 text-xs truncate" title={src.name}>
                      {src.name}
                    </span>
                    {active
                      ? <CheckCircle2 size={13} className="text-green-400 shrink-0" />
                      : (
                        <button
                          onClick={() => connectAndStart(src)}
                          className="text-xs text-blue-400 hover:text-blue-300 opacity-0
                                     group-hover:opacity-100 transition-opacity"
                        >
                          Use
                        </button>
                      )
                    }
                  </div>
                )
              })}
            </div>
          </Card>

          <Card title="Reolink RTSP">
            <div className="space-y-2">
              <input
                type="text"
                placeholder="rtsp://user:pass@192.168.1.x/…"
                value={reolinkUrl}
                onChange={(e) => setReolinkUrl(e.target.value)}
                className="w-full text-xs bg-surface-base border border-surface-border
                           rounded px-2.5 py-1.5 text-white placeholder-white/20
                           focus:outline-none focus:border-blue-500"
              />
              <Button
                size="sm"
                className="w-full"
                disabled={!reolinkUrl}
                onClick={connectReolink}
              >
                <Camera size={12} /> Connect RTSP
              </Button>
            </div>
          </Card>

          {/* Camera loop status + controls */}
          {camStatus && (
            <div className={[
              'flex items-center gap-2 px-3 py-2 rounded-md border',
              camStatus.running
                ? 'bg-green-900/30 border-green-800/50'
                : 'bg-surface-raised border-surface-border',
            ].join(' ')}>
              <StatusDot active={camStatus.running} />
              <span className="text-xs truncate flex-1" title={camStatus.source_name}>
                {camStatus.running
                  ? <span className="text-green-300">{camStatus.source_name || 'Running'}</span>
                  : <span className="text-white/40">Stopped</span>
                }
              </span>
              {camStatus.running ? (
                <button
                  onClick={stopCamera}
                  disabled={loopLoading}
                  className="shrink-0 p-1 rounded hover:bg-surface-border text-red-400/70
                             hover:text-red-400 disabled:opacity-40"
                  title="Stop capture"
                >
                  <Square size={11} />
                </button>
              ) : camStatus.source_name ? (
                <button
                  onClick={() => connectAndStart({ name: camStatus.source_name, type: 'ndi' })}
                  disabled={loopLoading}
                  className="shrink-0 p-1 rounded hover:bg-surface-border text-green-400/70
                             hover:text-green-400 disabled:opacity-40"
                  title="Start capture"
                >
                  <Play size={11} />
                </button>
              ) : null}
            </div>
          )}
        </div>

        {/* ── Right panel: configuration ── */}
        <div className="flex-1 space-y-3">
          {/* Save status */}
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-white/60">Camera Configuration</h2>
            {saveStatus === 'saved' && (
              <span className="text-xs text-green-400 flex items-center gap-1">
                <CheckCircle2 size={11} /> Saved
              </span>
            )}
            {saveStatus === 'saving' && (
              <span className="text-xs text-white/30">Saving…</span>
            )}
          </div>

          {config ? (
            <div className="grid grid-cols-2 gap-3">

              {/* Pan */}
              <Card title="Pan Controller">
                <div className="space-y-3">
                  <SliderField label="Dead zone"   unit="px" decimals={0} step={1}
                    min={0} max={200} value={config.pan.dead_zone_px}
                    onChange={(v) => patchConfig({ pan_dead_zone_px: Math.round(v) })} />
                  <SliderField label="Threshold"   unit="px" decimals={0} step={1}
                    min={0} max={400} value={config.pan.thresh_px}
                    onChange={(v) => patchConfig({ pan_thresh_px: Math.round(v) })} />
                  <SliderField label="Gain (Kp)"   step={0.05}
                    min={0.1} max={2.0} value={config.pan.kp}
                    onChange={(v) => patchConfig({ pan_kp: v })} />
                  <SliderField label="Max speed"   step={0.05}
                    min={0.1} max={1.0} value={config.pan.max_speed}
                    onChange={(v) => patchConfig({ pan_max_speed: v })} />
                  <SliderField label="Min speed"   step={0.01}
                    min={0.01} max={0.5} value={config.pan.min_speed}
                    onChange={(v) => patchConfig({ pan_min_speed: v })} />
                  <ToggleField label="Invert pan"
                    value={config.pan.invert}
                    onChange={(v) => patchConfig({ pan_invert: v })} />
                </div>
              </Card>

              {/* Zoom */}
              <Card title="Zoom Controller">
                <div className="space-y-3">
                  <SliderField label="Zoom-in  <"  step={0.01}
                    min={0.05} max={0.5} value={config.zoom.zoom_in_frac}
                    onChange={(v) => patchConfig({ zoom_in_frac: v })} />
                  <SliderField label="Zoom-out >"  step={0.01}
                    min={0.1} max={0.9} value={config.zoom.zoom_out_frac}
                    onChange={(v) => patchConfig({ zoom_out_frac: v })} />
                  <SliderField label="Speed"        step={0.05}
                    min={0.1} max={1.0} value={config.zoom.speed}
                    onChange={(v) => patchConfig({ zoom_speed: v })} />
                  <SliderField label="EMA α"        step={0.01}
                    min={0.01} max={1.0} value={config.zoom.ema_alpha}
                    onChange={(v) => patchConfig({ zoom_ema_alpha: v })} />
                  <ToggleField label="Invert zoom"
                    value={config.zoom.invert}
                    onChange={(v) => patchConfig({ zoom_invert: v })} />
                </div>
              </Card>

              {/* Detection */}
              <Card title="Detection">
                <div className="space-y-3">
                  <div className="flex items-center gap-3">
                    <span className="w-28 shrink-0 text-xs text-white/50">YOLO model</span>
                    <select
                      value={config.track.model_path}
                      onChange={() => { /* model changes need reconnect, handled elsewhere */ }}
                      className="flex-1 text-xs bg-surface-base border border-surface-border
                                 rounded px-2 py-1.5 text-white focus:outline-none focus:border-blue-500"
                    >
                      {YOLO_MODELS.map(m => <option key={m} value={m}>{m}</option>)}
                    </select>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="w-28 shrink-0 text-xs text-white/50">Track class</span>
                    <select
                      value={config.track.detect_classes ?? 'null'}
                      onChange={(e) => {
                        const v = e.target.value === 'null' ? null : parseInt(e.target.value)
                        patchConfig({ detect_classes: v })
                      }}
                      className="flex-1 text-xs bg-surface-base border border-surface-border
                                 rounded px-2 py-1.5 text-white focus:outline-none focus:border-blue-500"
                    >
                      {CLASS_OPTIONS.map(o => (
                        <option key={String(o.value)} value={String(o.value)}>{o.label}</option>
                      ))}
                    </select>
                  </div>
                  <SliderField label="H-FOV"        unit="°" decimals={0} step={1}
                    min={10} max={120} value={config.speed.hfov_deg}
                    onChange={(v) => patchConfig({ hfov_deg: v })} />
                </div>
              </Card>

              {/* Recording */}
              <Card title="Recording">
                <div className="space-y-3">
                  <SliderField label="Duration"  unit="s" decimals={0} step={5}
                    min={5} max={300} value={config.record.duration_sec}
                    onChange={(v) => patchConfig({ record_duration_sec: Math.round(v) })} />
                  <div className="flex items-center gap-3">
                    <span className="w-28 shrink-0 text-xs text-white/50">Record FPS</span>
                    <select
                      value={config.record.fps}
                      onChange={(e) => patchConfig({ record_fps: parseInt(e.target.value) })}
                      className="flex-1 text-xs bg-surface-base border border-surface-border
                                 rounded px-2 py-1.5 text-white focus:outline-none focus:border-blue-500"
                    >
                      {[15, 20, 25, 30].map(fps => <option key={fps} value={fps}>{fps} fps</option>)}
                    </select>
                  </div>
                  <div className="text-xs text-white/30 pt-1">
                    Output: {config.record.record_res[0]} × {config.record.record_res[1]} px
                  </div>
                </div>
              </Card>

            </div>
          ) : (
            <div className="flex items-center justify-center h-40">
              <span className="text-white/30 text-sm">Loading configuration…</span>
            </div>
          )}
        </div>

      </div>
    </div>
  )
}
