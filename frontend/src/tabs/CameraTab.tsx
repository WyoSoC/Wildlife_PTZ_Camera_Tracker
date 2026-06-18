import { useCallback, useEffect, useRef, useState } from 'react'
import { RefreshCw, Wifi, Camera, CheckCircle2, Play, Square, Plus, Trash2, Download, Loader } from 'lucide-react'
import { api } from '../api/client'
import { useServer } from '../context/ServerContext'
import type { CameraConfig, CameraStatus, ConfigUpdate, ModelInfo, NDISource } from '../types'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { SliderField, ToggleField } from '../components/ui/SliderField'
import { StatusDot } from '../components/ui/Badge'

export function CameraTab() {
  const { cameras, activeCameraId, setActiveCameraId, refreshCameras } = useServer()
  const cameraId = activeCameraId

  const [sources,     setSources]     = useState<NDISource[]>([])
  const [scanning,    setScanning]    = useState(false)
  const [config,      setConfig]      = useState<CameraConfig | null>(null)
  const [camStatus,   setCamStatus]   = useState<CameraStatus | null>(null)
  const [models,      setModels]      = useState<ModelInfo[]>([])
  const [reolinkUrl,  setReolinkUrl]  = useState('')
  const [saveStatus,  setSaveStatus]  = useState<'idle' | 'saving' | 'saved'>('idle')
  const [loopLoading, setLoopLoading] = useState(false)
  const [downloading, setDownloading] = useState<Set<string>>(new Set())
  const [dlError,     setDlError]     = useState<Record<string, string>>({})
  const debounceRef = useRef<ReturnType<typeof setTimeout>>()

  // Load config, status, models when active camera changes
  useEffect(() => {
    if (!cameraId) return
    api.cameras.getConfig(cameraId).then(setConfig).catch(console.error)
    api.cameras.status(cameraId).then(setCamStatus).catch(console.error)
    api.models.list().then(r => setModels(r.models)).catch(console.error)
  }, [cameraId])

  const scan = useCallback(async () => {
    setScanning(true)
    try {
      const { sources: found } = await api.cameras.discover()
      setSources(found)
    } catch (e) { console.error(e) }
    finally   { setScanning(false) }
  }, [])

  const connectAndStart = useCallback(async (source: NDISource) => {
    if (!cameraId) return
    try {
      await api.cameras.connect(cameraId, source.name, source.type)
      setLoopLoading(true)
      await api.cameras.start(cameraId)
      setCamStatus(await api.cameras.status(cameraId))
    } catch (e) { console.error(e) }
    finally   { setLoopLoading(false) }
  }, [cameraId])

  const connectReolink = useCallback(async () => {
    if (!cameraId || !reolinkUrl) return
    const label = reolinkUrl.split('@').pop() ?? reolinkUrl
    try {
      await api.cameras.connect(cameraId, label, 'reolink', reolinkUrl)
      setLoopLoading(true)
      await api.cameras.start(cameraId)
      setCamStatus(await api.cameras.status(cameraId))
    } catch (e) { console.error(e) }
    finally   { setLoopLoading(false) }
  }, [cameraId, reolinkUrl])

  const startCamera = useCallback(async () => {
    if (!cameraId) return
    try {
      setLoopLoading(true)
      await api.cameras.start(cameraId)
      setCamStatus(await api.cameras.status(cameraId))
    } catch (e) { console.error(e) }
    finally   { setLoopLoading(false) }
  }, [cameraId])

  const stopCamera = useCallback(async () => {
    if (!cameraId) return
    try {
      setLoopLoading(true)
      await api.cameras.stop(cameraId)
      setCamStatus(await api.cameras.status(cameraId))
    } catch (e) { console.error(e) }
    finally   { setLoopLoading(false) }
  }, [cameraId])

  const addCamera = useCallback(async () => {
    try {
      const { camera_id } = await api.cameras.create()
      await refreshCameras()
      setActiveCameraId(camera_id)
    } catch (e) { console.error(e) }
  }, [refreshCameras, setActiveCameraId])

  const removeCamera = useCallback(async (id: string) => {
    if (!confirm(`Remove camera ${id}?`)) return
    try {
      await api.cameras.remove(id)
      await refreshCameras()
    } catch (e) { console.error(e) }
  }, [refreshCameras])

  const switchModel = useCallback(async (modelName: string) => {
    if (!cameraId) return
    try {
      await api.cameras.switchModel(cameraId, modelName)
      setConfig(await api.cameras.getConfig(cameraId))
    } catch (e) { console.error(e) }
  }, [cameraId])

  const downloadModel = useCallback(async (name: string) => {
    setDownloading(prev => new Set(prev).add(name))
    setDlError(prev => { const n = { ...prev }; delete n[name]; return n })
    try {
      await api.models.download(name)
      const { models: refreshed } = await api.models.list()
      setModels(refreshed)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      setDlError(prev => ({ ...prev, [name]: msg }))
    } finally {
      setDownloading(prev => { const n = new Set(prev); n.delete(name); return n })
    }
  }, [])

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
          ...(update.model_path     !== undefined && { model_path:     update.model_path }),
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

  return (
    <div className="h-full overflow-auto p-4">
      <div className="flex gap-4 max-w-6xl mx-auto">

        {/* ── Left panel ── */}
        <div className="w-72 shrink-0 space-y-3">

          {/* NDI discovery */}
          <Card title="NDI Sources">
            <div className="space-y-2">
              <Button onClick={scan} loading={scanning} size="sm" className="w-full">
                <RefreshCw size={12} />
                {scanning ? 'Scanning…' : 'Scan Network'}
              </Button>
              {sources.length === 0 && !scanning && (
                <p className="text-xs text-white/30 text-center py-2">No sources — click Scan</p>
              )}
              {sources.map((src) => {
                const active = camStatus?.source_name === src.name && camStatus?.running
                return (
                  <div
                    key={src.name}
                    className="flex items-center gap-2 p-2 rounded-md bg-surface-raised
                               border border-surface-border hover:border-blue-600/50 group"
                  >
                    <Wifi size={13} className="text-blue-400 shrink-0" />
                    <span className="flex-1 text-xs truncate">{src.name}</span>
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

          {/* Camera list */}
          <Card title="Cameras">
            <div className="space-y-1.5">
              {cameras.map(c => (
                <div
                  key={c.camera_id}
                  onClick={() => setActiveCameraId(c.camera_id)}
                  className={[
                    'flex items-center gap-2 px-2.5 py-2 rounded-md border cursor-pointer transition-colors',
                    c.camera_id === activeCameraId
                      ? 'bg-blue-900/30 border-blue-700/60'
                      : 'bg-surface-raised border-surface-border hover:border-blue-600/30',
                  ].join(' ')}
                >
                  <StatusDot active={c.running} />
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium text-white truncate">{c.camera_id}</p>
                    {c.source_name && (
                      <p className="text-xs text-white/35 truncate">{c.source_name}</p>
                    )}
                  </div>
                  {cameras.length > 1 && (
                    <button
                      onClick={e => { e.stopPropagation(); removeCamera(c.camera_id) }}
                      className="p-0.5 text-white/20 hover:text-red-400 transition-colors"
                    >
                      <Trash2 size={11} />
                    </button>
                  )}
                </div>
              ))}
              <button
                onClick={addCamera}
                className="w-full flex items-center justify-center gap-1 py-1.5 text-xs
                           text-white/30 hover:text-white/60 border border-dashed border-surface-border
                           hover:border-blue-700/40 rounded-md transition-colors"
              >
                <Plus size={11} /> Add Camera
              </button>
            </div>
          </Card>

          {/* Reolink RTSP */}
          <Card title="Reolink / RTSP">
            <div className="space-y-2">
              <input
                type="text"
                placeholder="rtsp://user:pass@192.168.1.x/…"
                value={reolinkUrl}
                onChange={e => setReolinkUrl(e.target.value)}
                className="w-full text-xs bg-surface-base border border-surface-border
                           rounded px-2.5 py-1.5 text-white placeholder-white/20
                           focus:outline-none focus:border-blue-500"
              />
              <Button size="sm" className="w-full" disabled={!reolinkUrl} onClick={connectReolink}>
                <Camera size={12} /> Connect RTSP
              </Button>
            </div>
          </Card>

          {/* Status */}
          {camStatus && (
            <div className={[
              'flex items-center gap-2 px-3 py-2 rounded-md border',
              camStatus.running
                ? 'bg-green-900/30 border-green-800/50'
                : 'bg-surface-raised border-surface-border',
            ].join(' ')}>
              <StatusDot active={camStatus.running} />
              <span className="text-xs truncate flex-1">
                {camStatus.running
                  ? <span className="text-green-300">{camStatus.source_name || 'Running'}</span>
                  : <span className="text-white/40">Stopped</span>
                }
              </span>
              {camStatus.running ? (
                <button onClick={stopCamera} disabled={loopLoading}
                  className="shrink-0 p-1 text-red-400/70 hover:text-red-400 disabled:opacity-40">
                  <Square size={11} />
                </button>
              ) : camStatus.source_name ? (
                <button onClick={startCamera} disabled={loopLoading}
                  className="shrink-0 p-1 text-green-400/70 hover:text-green-400 disabled:opacity-40">
                  <Play size={11} />
                </button>
              ) : null}
            </div>
          )}
        </div>

        {/* ── Right panel: config ── */}
        <div className="flex-1 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-white/60">
              Configuration — {cameraId ?? '—'}
            </h2>
            {saveStatus === 'saved'  && <span className="text-xs text-green-400 flex gap-1 items-center"><CheckCircle2 size={11}/> Saved</span>}
            {saveStatus === 'saving' && <span className="text-xs text-white/30">Saving…</span>}
          </div>

          {config && cameraId ? (
            <div className="grid grid-cols-2 gap-3">

              {/* Wildlife model */}
              <Card title="Wildlife Model" className="col-span-2">
                <div className="space-y-4">

                  {/* UWyo wildlife models */}
                  {(() => {
                    const wildlife = models.filter(m => m.source === 'uwyo')
                    if (!wildlife.length) return null
                    return (
                      <div className="space-y-2">
                        <p className="text-[10px] font-semibold text-white/40 uppercase tracking-wider">
                          UWyo Wildlife Models
                        </p>
                        <div className="grid grid-cols-2 gap-2">
                          {wildlife.map(m => {
                            const active  = config.track.model_path === m.path ||
                                            config.track.model_path === m.name + '.pt'
                            const isDling = downloading.has(m.name)
                            const err     = dlError[m.name]

                            if (!m.downloaded) {
                              return (
                                <div key={m.name}
                                  className="p-2.5 rounded-lg border border-surface-border bg-surface-raised text-xs space-y-1.5"
                                >
                                  <p className="font-medium text-white/60 truncate">{m.description}</p>
                                  {m.species.length > 0 && (
                                    <p className="text-white/30 truncate">
                                      {m.species.slice(0, 3).join(', ')}
                                      {m.species.length > 3 && ` +${m.species.length - 3}`}
                                    </p>
                                  )}
                                  {err && <p className="text-red-400/80 text-[10px] truncate">{err}</p>}
                                  <button
                                    onClick={() => downloadModel(m.name)}
                                    disabled={isDling}
                                    className="flex items-center gap-1 text-blue-400 hover:text-blue-300
                                               disabled:opacity-50 transition-colors"
                                  >
                                    {isDling
                                      ? <><Loader size={11} className="animate-spin" /> Downloading…</>
                                      : <><Download size={11} /> Download</>
                                    }
                                  </button>
                                </div>
                              )
                            }

                            return (
                              <button
                                key={m.name}
                                onClick={() => switchModel(m.name)}
                                className={[
                                  'text-left p-2.5 rounded-lg border text-xs transition-colors',
                                  active
                                    ? 'bg-green-900/30 border-green-700/60'
                                    : 'bg-surface-raised border-surface-border hover:border-blue-600/40',
                                ].join(' ')}
                              >
                                <div className="flex items-start justify-between gap-1">
                                  <p className="font-medium text-white truncate">{m.description}</p>
                                  {active && <CheckCircle2 size={12} className="shrink-0 text-green-400 mt-0.5" />}
                                </div>
                                {m.species.length > 0 && (
                                  <p className="text-white/35 mt-0.5 truncate">
                                    {m.species.slice(0, 3).join(', ')}
                                    {m.species.length > 3 && ` +${m.species.length - 3}`}
                                  </p>
                                )}
                              </button>
                            )
                          })}
                        </div>
                      </div>
                    )
                  })()}

                  {/* MegaDetector */}
                  {(() => {
                    const megadetector = models.filter(m => m.source === 'megadetector')
                    if (!megadetector.length) return null
                    return (
                      <div className="space-y-2">
                        <p className="text-[10px] font-semibold text-white/40 uppercase tracking-wider">
                          MegaDetector
                        </p>
                        <div className="grid grid-cols-2 gap-2">
                          {megadetector.map(m => {
                            const active  = config.track.model_path === m.path ||
                                            config.track.model_path === m.name + '.pt'
                            const isDling = downloading.has(m.name)
                            const err     = dlError[m.name]

                            if (!m.downloaded) {
                              return (
                                <div key={m.name}
                                  className="p-2.5 rounded-lg border border-surface-border bg-surface-raised text-xs space-y-1.5"
                                >
                                  <p className="font-medium text-white/60 truncate">{m.description}</p>
                                  <p className="text-white/30 truncate">{m.species.join(', ')}</p>
                                  {err && <p className="text-red-400/80 text-[10px] truncate">{err}</p>}
                                  <button
                                    onClick={() => downloadModel(m.name)}
                                    disabled={isDling}
                                    className="flex items-center gap-1 text-blue-400 hover:text-blue-300
                                               disabled:opacity-50 transition-colors"
                                  >
                                    {isDling
                                      ? <><Loader size={11} className="animate-spin" /> Downloading…</>
                                      : <><Download size={11} /> Download (~700 MB)</>
                                    }
                                  </button>
                                </div>
                              )
                            }

                            return (
                              <button key={m.name} onClick={() => switchModel(m.name)}
                                className={[
                                  'text-left p-2.5 rounded-lg border text-xs transition-colors',
                                  active
                                    ? 'bg-green-900/30 border-green-700/60'
                                    : 'bg-surface-raised border-surface-border hover:border-blue-600/40',
                                ].join(' ')}
                              >
                                <div className="flex items-start justify-between gap-1">
                                  <p className="font-medium text-white truncate">{m.description}</p>
                                  {active && <CheckCircle2 size={12} className="shrink-0 text-green-400 mt-0.5" />}
                                </div>
                                <p className="text-white/35 mt-0.5 truncate">{m.species.join(', ')}</p>
                              </button>
                            )
                          })}
                        </div>
                      </div>
                    )
                  })()}

                  {/* Other custom .pt files */}
                  {(() => {
                    const other = models.filter(m => m.source === 'custom' && m.downloaded)
                    if (!other.length) return null
                    return (
                      <div className="space-y-2">
                        <p className="text-[10px] font-semibold text-white/40 uppercase tracking-wider">
                          Other Custom
                        </p>
                        <div className="grid grid-cols-2 gap-2">
                          {other.map(m => {
                            const active = config.track.model_path === m.path ||
                                           config.track.model_path === m.name + '.pt'
                            return (
                              <button key={m.name} onClick={() => switchModel(m.name)}
                                className={[
                                  'text-left p-2.5 rounded-lg border text-xs transition-colors',
                                  active
                                    ? 'bg-green-900/30 border-green-700/60'
                                    : 'bg-surface-raised border-surface-border hover:border-blue-600/40',
                                ].join(' ')}
                              >
                                <div className="flex items-start justify-between gap-1">
                                  <p className="font-medium text-white truncate">{m.description}</p>
                                  {active && <CheckCircle2 size={12} className="shrink-0 text-green-400 mt-0.5" />}
                                </div>
                              </button>
                            )
                          })}
                        </div>
                      </div>
                    )
                  })()}

                  {/* COCO fallback models */}
                  {(() => {
                    const coco = models.filter(m => m.source === 'ultralytics')
                    if (!coco.length) return null
                    return (
                      <details className="group">
                        <summary className="cursor-pointer text-[10px] font-semibold text-white/25
                                            uppercase tracking-wider select-none hover:text-white/40
                                            transition-colors list-none flex items-center gap-1">
                          <span className="group-open:rotate-90 transition-transform inline-block">▶</span>
                          COCO Fallback Models
                        </summary>
                        <div className="grid grid-cols-2 gap-2 mt-2">
                          {coco.map(m => {
                            const active = config.track.model_path === m.path ||
                                           config.track.model_path === m.name + '.pt'
                            return (
                              <button key={m.name} onClick={() => switchModel(m.name)}
                                className={[
                                  'text-left p-2.5 rounded-lg border text-xs transition-colors',
                                  active
                                    ? 'bg-green-900/30 border-green-700/60'
                                    : 'bg-surface-raised border-surface-border hover:border-white/10',
                                ].join(' ')}
                              >
                                <div className="flex items-start justify-between gap-1">
                                  <p className="font-medium text-white/50 truncate">{m.description}</p>
                                  {active && <CheckCircle2 size={12} className="shrink-0 text-green-400 mt-0.5" />}
                                </div>
                                <p className="text-white/20 mt-0.5 uppercase text-[10px] tracking-wide">
                                  {m.name}
                                </p>
                              </button>
                            )
                          })}
                        </div>
                      </details>
                    )
                  })()}

                </div>
              </Card>

              {/* Pan */}
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

              {/* Zoom */}
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

              {/* Detection */}
              <Card title="Tracking">
                <div className="space-y-3">
                  <SliderField label="H-FOV" unit="°" decimals={0} step={1}
                    min={10} max={120} value={config.speed.hfov_deg}
                    onChange={v => patchConfig({ hfov_deg: v })} />
                </div>
              </Card>

              {/* Recording */}
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
            </div>
          ) : (
            <div className="flex items-center justify-center h-40">
              <span className="text-white/30 text-sm">
                {cameraId ? 'Loading configuration…' : 'Select a camera'}
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
