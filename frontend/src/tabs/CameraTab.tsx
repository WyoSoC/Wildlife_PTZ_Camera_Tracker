import { useCallback, useEffect, useState } from 'react'
import {
  RefreshCw, Wifi, Camera, CheckCircle2, Play, Square, Plus, Trash2,
  Download, Loader, ExternalLink, Clock, AlertCircle,
} from 'lucide-react'
import { api } from '../api/client'
import { useServer } from '../context/ServerContext'
import type { CameraConfig, CameraStatus, ModelInfo, NDISource, NtpStatus } from '../types'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { StatusDot } from '../components/ui/Badge'

// ── Model card helpers ────────────────────────────────────────────────────────

const HF_BASE = 'https://huggingface.co/'

function HFLink({ repoId }: { repoId: string | null }) {
  if (!repoId) return null
  return (
    <a
      href={HF_BASE + repoId}
      target="_blank"
      rel="noopener noreferrer"
      onClick={e => e.stopPropagation()}
      className="shrink-0 text-orange-400/60 hover:text-orange-400 transition-colors"
      title={`View on HuggingFace: ${repoId}`}
    >
      <ExternalLink size={11} />
    </a>
  )
}

interface ModelSectionProps {
  models:      ModelInfo[]
  activePath:  string
  downloading: Set<string>
  dlError:     Record<string, string>
  onSwitch:    (name: string) => void
  onDownload:  (name: string) => void
  speciesLimit?: number
}

function ModelSection({ models, activePath, downloading, dlError, onSwitch, onDownload, speciesLimit = 3 }: ModelSectionProps) {
  if (!models.length) return <p className="text-xs text-white/30 text-center py-2">None</p>
  return (
    <div className="grid grid-cols-2 gap-2">
      {models.map(m => {
        const active  = activePath === m.path || activePath === m.name + '.pt'
        const isDling = downloading.has(m.name)
        const err     = dlError[m.name]

        if (!m.downloaded) {
          return (
            <div key={m.name}
              className="p-2.5 rounded-lg border border-surface-border bg-surface-raised text-xs space-y-1.5"
            >
              <div className="flex items-start justify-between gap-1">
                <p className="font-medium text-white/60 truncate">{m.description}</p>
                <HFLink repoId={m.repo_id} />
              </div>
              {m.species.length > 0 && (
                <p className="text-white/30 truncate">
                  {m.species.slice(0, speciesLimit).join(', ')}
                  {m.species.length > speciesLimit && ` +${m.species.length - speciesLimit} more`}
                </p>
              )}
              {err && <p className="text-red-400/80 text-[10px] truncate">{err}</p>}
              {m.auto_download ? (
                <button onClick={() => onDownload(m.name)} disabled={isDling}
                  className="flex items-center gap-1 text-blue-400 hover:text-blue-300 disabled:opacity-50 transition-colors"
                >
                  {isDling
                    ? <><Loader size={11} className="animate-spin" /> Downloading…</>
                    : <><Download size={11} /> Download</>
                  }
                </button>
              ) : (
                <span className="text-white/25 italic">Coming soon</span>
              )}
            </div>
          )
        }

        return (
          <button key={m.name} onClick={() => onSwitch(m.name)}
            className={[
              'text-left p-2.5 rounded-lg border text-xs transition-colors',
              active
                ? 'bg-green-900/30 border-green-700/60'
                : 'bg-surface-raised border-surface-border hover:border-blue-600/40',
            ].join(' ')}
          >
            <div className="flex items-start justify-between gap-1">
              <p className="font-medium text-white truncate">{m.description}</p>
              <div className="flex items-center gap-1 shrink-0">
                <HFLink repoId={m.repo_id} />
                {active && <CheckCircle2 size={12} className="text-green-400 mt-0.5" />}
              </div>
            </div>
            {m.species.length > 0 && (
              <p className="text-white/35 mt-0.5 truncate">
                {m.species.slice(0, speciesLimit).join(', ')}
                {m.species.length > speciesLimit && ` +${m.species.length - speciesLimit} more`}
              </p>
            )}
          </button>
        )
      })}
    </div>
  )
}

// ── Custom model form ─────────────────────────────────────────────────────────

interface CustomModelFormProps {
  onAdded: () => void
}

function CustomModelForm({ onAdded }: CustomModelFormProps) {
  const [repoUrl,   setRepoUrl]   = useState('')
  const [filename,  setFilename]  = useState('best.pt')
  const [localName, setLocalName] = useState('')
  const [busy,      setBusy]      = useState(false)
  const [error,     setError]     = useState('')
  const [done,      setDone]      = useState('')

  const submit = useCallback(async () => {
    if (!repoUrl.trim()) return
    setBusy(true); setError(''); setDone('')
    try {
      const res = await api.models.addCustom(
        repoUrl.trim(),
        filename.trim() || 'best.pt',
        localName.trim() || undefined,
      )
      setDone(`Saved as "${res.name}"`)
      setRepoUrl(''); setLocalName('')
      onAdded()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }, [repoUrl, filename, localName, onAdded])

  return (
    <Card title="Add Custom HuggingFace Model">
      <div className="space-y-2 text-xs">
        <div>
          <label className="text-white/40 block mb-1">HuggingFace URL or owner/repo</label>
          <input
            type="text"
            placeholder="https://huggingface.co/owner/repo  or  owner/repo"
            value={repoUrl}
            onChange={e => setRepoUrl(e.target.value)}
            className="w-full bg-surface-base border border-surface-border rounded px-2 py-1.5
                       text-white placeholder-white/20 focus:outline-none focus:border-blue-500"
          />
        </div>
        <div className="flex gap-2">
          <div className="flex-1">
            <label className="text-white/40 block mb-1">Filename in repo</label>
            <input
              type="text"
              placeholder="best.pt"
              value={filename}
              onChange={e => setFilename(e.target.value)}
              className="w-full bg-surface-base border border-surface-border rounded px-2 py-1.5
                         text-white placeholder-white/20 focus:outline-none focus:border-blue-500"
            />
          </div>
          <div className="flex-1">
            <label className="text-white/40 block mb-1">Local name (optional)</label>
            <input
              type="text"
              placeholder="my_model"
              value={localName}
              onChange={e => setLocalName(e.target.value)}
              className="w-full bg-surface-base border border-surface-border rounded px-2 py-1.5
                         text-white placeholder-white/20 focus:outline-none focus:border-blue-500"
            />
          </div>
        </div>
        {error && (
          <p className="flex items-center gap-1 text-red-400/80 text-[10px]">
            <AlertCircle size={10} /> {error}
          </p>
        )}
        {done && <p className="text-green-400/80 text-[10px]">{done}</p>}
        <div className="flex items-center gap-3">
          <Button size="sm" disabled={!repoUrl.trim() || busy} onClick={submit}>
            {busy ? <><Loader size={11} className="animate-spin" /> Downloading…</> : <><Download size={11} /> Download</>}
          </Button>
          <a
            href="https://github.com/gojian/Wildlife_PTZ_Camera_Tracker/blob/main/docs/custom_models.md"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-white/30 hover:text-white/60 transition-colors"
          >
            <ExternalLink size={10} /> How to prepare a model
          </a>
        </div>
      </div>
    </Card>
  )
}

// ── NTP Time Sync card ────────────────────────────────────────────────────────

function TimeSyncCard() {
  const [ntp,   setNtp]   = useState<NtpStatus | null>(null)
  const [busy,  setBusy]  = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    api.system.ntpStatus().then(setNtp).catch(() => {})
  }, [])

  const sync = useCallback(async () => {
    setBusy(true); setError('')
    try {
      const res = await api.system.ntpSync()
      setNtp(res)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Sync failed')
    } finally {
      setBusy(false)
    }
  }, [])

  return (
    <Card title="Time Sync (NTP)">
      <div className="space-y-2 text-xs">
        {ntp ? (
          <>
            <div className="flex items-center gap-2">
              <Clock size={11} className={ntp.synced ? 'text-green-400' : 'text-white/30'} />
              <span className={ntp.synced ? 'text-green-300' : 'text-white/40'}>
                {ntp.synced ? 'Synced' : 'Not synced'}
              </span>
            </div>
            {ntp.synced && (
              <>
                <div className="text-white/50">
                  Offset: <span className="text-white/80 font-mono">
                    {ntp.offset_sec >= 0 ? '+' : ''}{ntp.offset_sec.toFixed(3)} s
                  </span>
                </div>
                <div className="text-white/40 truncate">Server: {ntp.server}</div>
                {ntp.last_sync && (
                  <div className="text-white/30 text-[10px]">
                    Last: {new Date(ntp.last_sync).toLocaleString()}
                  </div>
                )}
              </>
            )}
          </>
        ) : (
          <p className="text-white/30">Loading…</p>
        )}
        {error && <p className="text-red-400/70 text-[10px]">{error}</p>}
        <Button size="sm" className="w-full" loading={busy} onClick={sync}>
          <RefreshCw size={11} /> Sync Now
        </Button>
      </div>
    </Card>
  )
}

// ── Main tab ──────────────────────────────────────────────────────────────────

export function CameraTab() {
  const { cameras, activeCameraId, setActiveCameraId, refreshCameras, server } = useServer()
  const cameraId = activeCameraId

  const [sources,     setSources]     = useState<NDISource[]>([])
  const [scanning,    setScanning]    = useState(false)
  const [config,      setConfig]      = useState<CameraConfig | null>(null)
  const [camStatus,   setCamStatus]   = useState<CameraStatus | null>(null)
  const [models,      setModels]      = useState<ModelInfo[]>([])
  const [reolinkUrl,  setReolinkUrl]  = useState('')
  const [loopLoading, setLoopLoading] = useState(false)
  const [downloading, setDownloading] = useState<Set<string>>(new Set())
  const [dlError,     setDlError]     = useState<Record<string, string>>({})

  const refreshModels = useCallback(() =>
    api.models.list().then(r => setModels(r.models)).catch(console.error)
  , [])

  // Load config, status, models when active camera changes
  useEffect(() => {
    if (!cameraId) return
    api.cameras.getConfig(cameraId).then(setConfig).catch(console.error)
    api.cameras.status(cameraId).then(setCamStatus).catch(console.error)
    refreshModels()
  }, [cameraId, refreshModels])

  const scan = useCallback(async () => {
    setScanning(true)
    try {
      const { sources: found } = await api.cameras.discover()
      setSources(found)
    } catch (e) { console.error(e) }
    finally   { setScanning(false) }
  }, [])

  // Auto-scan on tab mount
  useEffect(() => { scan() }, [scan])

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
      await refreshModels()
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      setDlError(prev => ({ ...prev, [name]: msg }))
    } finally {
      setDownloading(prev => { const n = new Set(prev); n.delete(name); return n })
    }
  }, [refreshModels])

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
                <p className="text-xs text-white/30 text-center py-2">No NDI sources found</p>
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

          {/* Time Sync */}
          <TimeSyncCard />
        </div>

        {/* ── Right panel: config ── */}
        <div className="flex-1 space-y-3">
          <h2 className="text-sm font-semibold text-white/60">
            {server?.name ?? 'server-1'}: AI Models Management
          </h2>

          {config && cameraId ? (
            <div className="space-y-3">

              {/* General multi-species models */}
              <Card title="General Models">
                <ModelSection
                  models={models.filter(m => m.source === 'general' || m.source === 'megadetector')}
                  activePath={config.track.model_path}
                  downloading={downloading}
                  dlError={dlError}
                  onSwitch={switchModel}
                  onDownload={downloadModel}
                  speciesLimit={4}
                />
              </Card>

              {/* Specialized single-species models */}
              {(() => {
                const specialized       = models.filter(m => m.source === 'specialized')
                const specDownloaded    = specialized.filter(m => m.downloaded)
                const specNotDownloaded = specialized.filter(m => !m.downloaded)
                return (
                  <Card title="Specialized Models">
                    <div className="space-y-2">
                      {specDownloaded.length === 0 && specNotDownloaded.length === 0 && (
                        <p className="text-xs text-white/30 text-center py-2">None</p>
                      )}

                      {/* Downloaded: always visible at top */}
                      {specDownloaded.length > 0 && (
                        <ModelSection
                          models={specDownloaded}
                          activePath={config.track.model_path}
                          downloading={downloading}
                          dlError={dlError}
                          onSwitch={switchModel}
                          onDownload={downloadModel}
                          speciesLimit={1}
                        />
                      )}

                      {/* Not-downloaded: collapsed by default */}
                      {specNotDownloaded.length > 0 && (
                        <details className="group">
                          <summary className="cursor-pointer select-none list-none flex items-center gap-1
                                             text-[10px] font-semibold text-white/30 uppercase tracking-wider
                                             hover:text-white/50 transition-colors py-0.5 px-1">
                            <span className="group-open:rotate-90 transition-transform inline-block">▶</span>
                            Available to Download ({specNotDownloaded.length})
                          </summary>
                          <div className="mt-2">
                            <ModelSection
                              models={specNotDownloaded}
                              activePath={config.track.model_path}
                              downloading={downloading}
                              dlError={dlError}
                              onSwitch={switchModel}
                              onDownload={downloadModel}
                              speciesLimit={1}
                            />
                          </div>
                        </details>
                      )}
                    </div>
                  </Card>
                )
              })()}

              {/* Custom .pt files */}
              {models.some(m => m.source === 'custom') && (
                <Card title="Custom Models">
                  <ModelSection
                    models={models.filter(m => m.source === 'custom')}
                    activePath={config.track.model_path}
                    downloading={downloading}
                    dlError={dlError}
                    onSwitch={switchModel}
                    onDownload={downloadModel}
                  />
                </Card>
              )}

              {/* COCO fallback models */}
              <details className="group">
                <summary className="cursor-pointer text-[10px] font-semibold text-white/25
                                    uppercase tracking-wider select-none hover:text-white/40
                                    transition-colors list-none flex items-center gap-1 px-1 py-0.5">
                  <span className="group-open:rotate-90 transition-transform inline-block">▶</span>
                  COCO Baseline Models
                </summary>
                <div className="grid grid-cols-2 gap-2 mt-2">
                  {models.filter(m => m.source === 'ultralytics').map(m => {
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
                        <p className="text-white/20 mt-0.5 uppercase text-[10px] tracking-wide">{m.name}</p>
                      </button>
                    )
                  })}
                </div>
              </details>

              {/* Add custom HuggingFace model */}
              <CustomModelForm onAdded={refreshModels} />

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
