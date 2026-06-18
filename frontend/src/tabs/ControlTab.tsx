import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Play, Square, Crosshair, Radio, CheckCircle2, RefreshCw,
  ChevronUp, ChevronDown, ChevronLeft, ChevronRight,
  ZoomIn, ZoomOut, Focus, Home, ScanLine, MapPin, Bookmark,
} from 'lucide-react'
import { useWebRTC } from '../hooks/useWebRTC'
import { useGamepad } from '../hooks/useGamepad'
import { VideoPlayer } from '../components/VideoPlayer'
import { TelemetryPanel } from '../components/TelemetryPanel'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { SliderField, ToggleField } from '../components/ui/SliderField'
import { Badge, StatusDot } from '../components/ui/Badge'
import { api } from '../api/client'
import type { CameraConfig, CameraStatus, ConfigUpdate, UserProfile, WebSocketHook } from '../types'

const GAMEPAD_SEND_HZ     = 20
const GAMEPAD_INTERVAL_MS = 1000 / GAMEPAD_SEND_HZ
const PTZ_SPEED           = 0.5

const RES_OPTIONS: [number, number][] = [
  [1920, 1080],
  [1280, 720],
  [854, 480],
]

const DURATION_OPTIONS = [
  { label: '30 seconds',  value: 30 },
  { label: '5 minutes',   value: 300 },
  { label: '20 minutes',  value: 1200 },
  { label: '30 minutes',  value: 1800 },
  { label: '⚠ Unlimited', value: 0 },
]

// ── Helpers ────────────────────────────────────────────────────────────────────

function AxisBar({ label, value }: { label: string; value: number }) {
  const pct = ((value + 1) / 2) * 100
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-8 shrink-0 text-white/40">{label}</span>
      <div className="relative flex-1 h-2 bg-surface-border rounded-full overflow-hidden">
        <span className="absolute left-1/2 -translate-x-px w-px h-full bg-white/20" />
        <div className="absolute top-0 h-full bg-blue-500 rounded-full transition-all duration-75"
             style={{ width: `${pct}%` }} />
      </div>
      <span className="w-10 text-right font-mono text-white/60">{value.toFixed(2)}</span>
    </div>
  )
}

function PtzBtn({
  children, className = '', onActivate, onDeactivate,
}: {
  children: React.ReactNode
  className?: string
  onActivate:   () => void
  onDeactivate: () => void
}) {
  const ivRef = useRef<ReturnType<typeof setInterval>>()
  const start = () => {
    onActivate()
    ivRef.current = setInterval(onActivate, GAMEPAD_INTERVAL_MS)
  }
  const stop = () => {
    clearInterval(ivRef.current)
    onDeactivate()
  }
  return (
    <button
      className={`flex items-center justify-center rounded border border-surface-border
                  bg-surface-raised text-white/70 hover:bg-surface-hover hover:text-white
                  active:bg-blue-700 active:border-blue-500 select-none touch-none ${className}`}
      onPointerDown={start}
      onPointerUp={stop}
      onPointerLeave={stop}
    >
      {children}
    </button>
  )
}

// ── Tuning section component ───────────────────────────────────────────────────

interface TuningProps {
  config:      CameraConfig
  patchConfig: (u: ConfigUpdate) => void
  SaveDot:     () => React.ReactElement | null
}

function TrackingTuning({ config, patchConfig, SaveDot }: TuningProps) {
  return (
    <Card>
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-white/40 uppercase tracking-wider flex items-center gap-1.5">
            <Crosshair size={12} /> Tracking Tuning
          </span>
          <SaveDot />
        </div>

        {/* Detection */}
        <details open>
          <summary className="cursor-pointer select-none list-none text-[10px] font-semibold
                             text-white/40 uppercase tracking-wider hover:text-white/60 pb-2">
            Detection
          </summary>
          <div className="space-y-2 pl-1">
            <SliderField
              label="Lock confidence" unit="%" decimals={0} step={1}
              min={10} max={95}
              value={Math.round(config.track.lock_confidence * 100)}
              onChange={v => patchConfig({ lock_confidence: v / 100 })}
              tooltip="Minimum detection confidence to lock onto a target and begin following. Higher = fewer false locks."
            />
            <SliderField
              label="Lock-off delay" unit="s" decimals={1} step={0.5}
              min={0.5} max={15}
              value={config.command.lock_off_sec}
              onChange={v => patchConfig({ lock_off_sec: v })}
              tooltip="How long the camera waits after losing a target before resuming scanning or returning home."
            />
            <SliderField
              label="Track memory" unit="fr" decimals={0} step={1}
              min={5} max={90}
              value={config.track.tracker_max_age}
              onChange={v => patchConfig({ tracker_max_age: Math.round(v) })}
              tooltip="Frames the tracker remembers a target through brief occlusion. Higher = tolerates longer gaps but may create ghost tracks."
            />
          </div>
        </details>

        {/* Pan */}
        <details open>
          <summary className="cursor-pointer select-none list-none text-[10px] font-semibold
                             text-white/40 uppercase tracking-wider hover:text-white/60 pb-2">
            Pan
          </summary>
          <div className="space-y-2 pl-1">
            <SliderField
              label="Stable zone H" unit="px" decimals={0} step={1}
              min={0} max={200} value={config.pan.stable_zone_h_px}
              onChange={v => patchConfig({ pan_stable_zone_h_px: Math.round(v) })}
              tooltip="Horizontal pixel band around frame centre — no pan correction inside this width."
            />
            <SliderField
              label="Stable zone V" unit="px" decimals={0} step={1}
              min={0} max={200} value={config.pan.stable_zone_v_px}
              onChange={v => patchConfig({ pan_stable_zone_v_px: Math.round(v) })}
              tooltip="Vertical pixel band around frame centre — sets the height of the stable-zone box overlay."
            />
            <SliderField
              label="Gain (Kp)" step={0.05}
              min={0.1} max={2.0} value={config.pan.kp}
              onChange={v => patchConfig({ pan_kp: v })}
              tooltip="Proportional gain — how aggressively the camera chases offset. Too high causes overshoot."
            />
            <SliderField
              label="Max speed" step={0.05}
              min={0.1} max={1.0} value={config.pan.max_speed}
              onChange={v => patchConfig({ pan_max_speed: v })}
              tooltip="Maximum PTZ pan speed (0–1 scale)."
            />
            <SliderField
              label="Min speed" step={0.01}
              min={0.01} max={0.5} value={config.pan.min_speed}
              onChange={v => patchConfig({ pan_min_speed: v })}
              tooltip="Minimum nonzero speed floor to overcome motor stiction."
            />
          </div>
        </details>

        {/* Zoom */}
        <details open>
          <summary className="cursor-pointer select-none list-none text-[10px] font-semibold
                             text-white/40 uppercase tracking-wider hover:text-white/60 pb-2">
            Zoom
          </summary>
          <div className="space-y-2 pl-1">
            <SliderField
              label="Zoom-in  <" step={0.01}
              min={0.05} max={0.5} value={config.zoom.zoom_in_frac}
              onChange={v => patchConfig({ zoom_in_frac: v })}
              tooltip="Zoom in when target bbox is smaller than this fraction of frame width. Raise to keep more distance."
            />
            <SliderField
              label="Zoom-out >" step={0.01}
              min={0.1} max={0.9} value={config.zoom.zoom_out_frac}
              onChange={v => patchConfig({ zoom_out_frac: v })}
              tooltip="Zoom out when target bbox is larger than this fraction of frame width."
            />
            <SliderField
              label="Speed" step={0.05}
              min={0.1} max={1.0} value={config.zoom.speed}
              onChange={v => patchConfig({ zoom_speed: v })} />
            <SliderField
              label="Smoothing α" step={0.01}
              min={0.01} max={1.0} value={config.zoom.ema_alpha}
              onChange={v => patchConfig({ zoom_ema_alpha: v })}
              tooltip="EMA smoothing on bbox size. Lower = less zoom hunting but slower response."
            />
          </div>
        </details>

        {/* Speed */}
        <div className="pt-1 border-t border-surface-border">
          <SliderField
            label="H-FOV" unit="°" decimals={0} step={1}
            min={10} max={120} value={config.speed.hfov_deg}
            onChange={v => patchConfig({ hfov_deg: v })}
            tooltip="Horizontal field of view in degrees — used for angular speed readout only."
          />
        </div>
      </div>
    </Card>
  )
}

// ── Behaviour (home / area / scan) ────────────────────────────────────────────

interface BehaviourProps extends TuningProps {
  cameraId: string | null
}

function BehaviourPanel({ config, patchConfig, SaveDot, cameraId }: BehaviourProps) {
  const [goingHome, setGoingHome] = useState(false)

  const handleGoHome = useCallback(async () => {
    if (!cameraId) return
    setGoingHome(true)
    try { await api.cameras.goHome(cameraId) }
    catch (e) { console.error(e) }
    finally   { setGoingHome(false) }
  }, [cameraId])

  const saveHome = useCallback(() => {
    patchConfig({ home_is_set: true })
  }, [patchConfig])

  return (
    <Card>
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-white/40 uppercase tracking-wider flex items-center gap-1.5">
            <ScanLine size={12} /> Auto Behaviour
          </span>
          <SaveDot />
        </div>

        {/* Home Position */}
        <details open>
          <summary className="cursor-pointer select-none list-none flex items-center gap-1.5
                             text-[10px] font-semibold text-white/40 uppercase tracking-wider
                             hover:text-white/60 pb-2">
            <Home size={10} /> Home Position
            {config.home.is_set && <span className="text-green-400/60 normal-case font-normal">● saved</span>}
          </summary>
          <div className="space-y-2 pl-1">
            <p className="text-[10px] text-white/30 leading-snug">
              Set where the camera rests when not tracking. Values range -1 to 1
              for pan/tilt, 0 to 1 for zoom.
            </p>
            <SliderField
              label="Pan" step={0.01} min={-1} max={1}
              value={config.home.pan} onChange={v => patchConfig({ home_pan: v })} />
            <SliderField
              label="Tilt" step={0.01} min={-1} max={1}
              value={config.home.tilt} onChange={v => patchConfig({ home_tilt: v })} />
            <SliderField
              label="Zoom" step={0.01} min={0} max={1}
              value={config.home.zoom} onChange={v => patchConfig({ home_zoom: v })} />
            <div className="flex gap-2 pt-1">
              <Button size="sm" className="flex-1" onClick={saveHome}
                variant={config.home.is_set ? 'ghost' : 'primary'}>
                <MapPin size={11} />
                {config.home.is_set ? 'Update Home' : 'Save as Home'}
              </Button>
              <Button size="sm" variant="ghost" className="flex-1"
                disabled={!config.home.is_set || !cameraId}
                loading={goingHome} onClick={handleGoHome}>
                <Home size={11} /> Go Home
              </Button>
            </div>
          </div>
        </details>

        {/* Tracking Area */}
        <details>
          <summary className="cursor-pointer select-none list-none flex items-center gap-1.5
                             text-[10px] font-semibold text-white/40 uppercase tracking-wider
                             hover:text-white/60 pb-2">
            Tracking Area
            <span className={`normal-case font-normal ${config.area.enabled ? 'text-blue-400/60' : 'text-white/20'}`}>
              {config.area.enabled ? '● on' : '○ off'}
            </span>
          </summary>
          <div className="space-y-2 pl-1">
            <p className="text-[10px] text-white/30 leading-snug">
              Rectangular PTZ region for scanning. When enabled, Auto Scan stays
              within this area. Values are in the same -1 to 1 coordinate space
              as pan/tilt commands.
            </p>
            <ToggleField label="Enable area" value={config.area.enabled}
              onChange={v => patchConfig({ area_enabled: v })} />
            <div className="grid grid-cols-2 gap-x-4 gap-y-1">
              <SliderField label="Pan min" step={0.01} min={-1} max={0}
                value={config.area.pan_min}
                onChange={v => patchConfig({ area_pan_min: v })} />
              <SliderField label="Pan max" step={0.01} min={0} max={1}
                value={config.area.pan_max}
                onChange={v => patchConfig({ area_pan_max: v })} />
              <SliderField label="Tilt min" step={0.01} min={-1} max={0}
                value={config.area.tilt_min}
                onChange={v => patchConfig({ area_tilt_min: v })} />
              <SliderField label="Tilt max" step={0.01} min={0} max={1}
                value={config.area.tilt_max}
                onChange={v => patchConfig({ area_tilt_max: v })} />
            </div>
            <SliderField label="Scan zoom" step={0.01} min={0} max={1}
              value={config.area.scan_zoom}
              onChange={v => patchConfig({ area_scan_zoom: v })}
              tooltip="Zoom level held while scanning. Wide angle (low value) gives wider field of view."
            />
          </div>
        </details>

        {/* Auto Scan */}
        <details>
          <summary className="cursor-pointer select-none list-none flex items-center gap-1.5
                             text-[10px] font-semibold text-white/40 uppercase tracking-wider
                             hover:text-white/60 pb-2">
            Auto Scan
            <span className={`normal-case font-normal ${config.scan.enabled ? 'text-amber-400/70' : 'text-white/20'}`}>
              {config.scan.enabled ? '● on' : '○ off'}
            </span>
          </summary>
          <div className="space-y-2 pl-1">
            <p className="text-[10px] text-white/30 leading-snug">
              Camera sweeps the tracking area in a boustrophedon (lawnmower)
              grid while waiting for a target. Requires Tracking Area to be
              enabled. When a target is detected above the confidence threshold,
              scanning stops and the camera locks on.
            </p>
            <ToggleField label="Enable scan"
              value={config.scan.enabled}
              onChange={v => patchConfig({ scan_enabled: v })} />
            {config.scan.enabled && (
              <>
                <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                  <SliderField label="Rows" unit="" decimals={0} step={1}
                    min={1} max={8} value={config.scan.rows}
                    onChange={v => patchConfig({ scan_rows: Math.round(v) })}
                    tooltip="Number of tilt rows in the sweep grid."
                  />
                  <SliderField label="Columns" unit="" decimals={0} step={1}
                    min={2} max={12} value={config.scan.cols}
                    onChange={v => patchConfig({ scan_cols: Math.round(v) })}
                    tooltip="Pan positions per row."
                  />
                </div>
                <SliderField label="Travel time" unit="s" decimals={1} step={0.5}
                  min={1} max={10} value={config.scan.travel_sec}
                  onChange={v => patchConfig({ scan_travel_sec: v })}
                  tooltip="Time allowed for the camera to arrive at each scan position before observation starts."
                />
                <SliderField label="Dwell time" unit="s" decimals={1} step={0.5}
                  min={0.5} max={15} value={config.scan.dwell_sec}
                  onChange={v => patchConfig({ scan_dwell_sec: v })}
                  tooltip="How long the camera observes at each position. Must be long enough for the model to detect subjects."
                />
              </>
            )}
          </div>
        </details>
      </div>
    </Card>
  )
}

// ── Saved profiles ─────────────────────────────────────────────────────────────

function ProfilesCard({ cameraId, onLoaded }: { cameraId: string | null; onLoaded: () => void }) {
  const [profiles,  setProfiles] = useState<UserProfile[]>([])
  const [newName,   setNewName]  = useState('')
  const [saving,    setSaving]   = useState(false)
  const [flash,     setFlash]    = useState<string | null>(null)

  const refresh = useCallback(() => {
    api.profiles.list().then(r => setProfiles(r.profiles)).catch(console.error)
  }, [])

  useEffect(() => { refresh() }, [refresh])

  const showFlash = (msg: string) => {
    setFlash(msg)
    setTimeout(() => setFlash(null), 2000)
  }

  const handleSave = async () => {
    if (!cameraId || !newName.trim()) return
    setSaving(true)
    try {
      await api.profiles.save(newName.trim(), cameraId)
      setNewName('')
      refresh()
      showFlash('Saved')
    } catch (e) { console.error(e) }
    finally   { setSaving(false) }
  }

  const handleLoad = async (name: string) => {
    if (!cameraId) return
    try {
      await api.profiles.load(name, cameraId)
      onLoaded()
      showFlash(`Loaded`)
    } catch (e) { console.error(e) }
  }

  const handleDelete = async (name: string) => {
    try {
      await api.profiles.remove(name)
      refresh()
    } catch (e) { console.error(e) }
  }

  return (
    <Card>
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-white/40 uppercase tracking-wider flex items-center gap-1.5">
            <Bookmark size={12} /> Profiles
          </span>
          {flash && <span className="text-xs text-green-400">{flash}</span>}
        </div>

        <div className="flex gap-1">
          <input
            value={newName}
            onChange={e => setNewName(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSave()}
            placeholder="Profile name…"
            className="flex-1 min-w-0 text-xs bg-surface-base border border-surface-border
                       rounded px-2 py-1 text-white placeholder:text-white/20
                       focus:outline-none focus:border-blue-500"
          />
          <Button size="sm" onClick={handleSave}
            disabled={!cameraId || !newName.trim()} loading={saving}>
            Save
          </Button>
        </div>

        {profiles.length === 0 ? (
          <p className="text-[11px] text-white/20 text-center py-1">No saved profiles</p>
        ) : (
          <div className="space-y-1 max-h-40 overflow-y-auto pr-0.5">
            {profiles.map(p => (
              <div key={p.name} className="flex items-center gap-1 text-xs">
                <span className="flex-1 min-w-0 truncate text-white/70" title={p.name}>
                  {p.name}
                </span>
                <button
                  onClick={() => handleLoad(p.name)}
                  className="shrink-0 px-1.5 py-0.5 rounded text-[10px]
                             bg-blue-700/40 hover:bg-blue-600/60 text-blue-300
                             border border-blue-800/60 transition-colors">
                  Load
                </button>
                <button
                  onClick={() => handleDelete(p.name)}
                  className="shrink-0 px-1.5 py-0.5 rounded text-[10px]
                             bg-surface-raised hover:bg-red-900/40 text-white/30
                             hover:text-red-400 border border-surface-border transition-colors">
                  ✕
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </Card>
  )
}

// ── Main tab ───────────────────────────────────────────────────────────────────

interface Props {
  ws:       WebSocketHook
  cameraId: string | null
}

export function ControlTab({ ws, cameraId }: Props) {
  const { stream, rtcState, rtcError, startWebRTC, stopWebRTC } = useWebRTC(cameraId)
  const { telemetry, sendPanTilt, sendZoom, sendStop, sendAutofocus, setMode, setRecording } = ws

  const [camStatus,   setCamStatus]   = useState<CameraStatus | null>(null)
  const [loopLoading, setLoopLoading] = useState(false)
  const [config,      setConfig]      = useState<CameraConfig | null>(null)
  const [saveStatus,  setSaveStatus]  = useState<'idle' | 'saving' | 'saved'>('idle')
  const debounceRef = useRef<ReturnType<typeof setTimeout>>()

  // Camera status polling
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

  // Auto-connect video when camera starts running
  const rtcStateRef   = useRef(rtcState)
  const wasRunningRef = useRef(false)
  useEffect(() => { rtcStateRef.current = rtcState }, [rtcState])
  useEffect(() => {
    const running = camStatus?.running ?? false
    if (running && !wasRunningRef.current &&
        rtcStateRef.current !== 'connecting' && rtcStateRef.current !== 'connected') {
      startWebRTC()
    }
    wasRunningRef.current = running
  }, [camStatus?.running, startWebRTC])

  // Gamepad
  interface PadInfo { index: number; id: string }
  const [detectedPads, setDetectedPads] = useState<PadInfo[]>([])
  const [activePadIdx, setActivePadIdx] = useState<number | null>(null)

  const scanGamepads = useCallback(() => {
    const found = Array.from(navigator.getGamepads())
      .flatMap((gp, i): PadInfo[] => gp ? [{ index: i, id: gp.id }] : [])
    setDetectedPads(found)
    if (found.length > 0 && activePadIdx === null) setActivePadIdx(found[0].index)
  }, [activePadIdx])

  useEffect(() => {
    const onConnect = (e: GamepadEvent) => {
      setDetectedPads(prev =>
        prev.some(p => p.index === e.gamepad.index) ? prev
          : [...prev, { index: e.gamepad.index, id: e.gamepad.id }],
      )
      setActivePadIdx(prev => prev ?? e.gamepad.index)
    }
    const onDisconnect = (e: GamepadEvent) => {
      setDetectedPads(prev => prev.filter(p => p.index !== e.gamepad.index))
      setActivePadIdx(prev => prev === e.gamepad.index ? null : prev)
    }
    window.addEventListener('gamepadconnected',    onConnect)
    window.addEventListener('gamepaddisconnected', onDisconnect)
    return () => {
      window.removeEventListener('gamepadconnected',    onConnect)
      window.removeEventListener('gamepaddisconnected', onDisconnect)
    }
  }, [])

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

  const gamepad = useGamepad(handleAxes, activePadIdx)
  useEffect(() => { if (gamepad.btnStop)  sendStop() },      [gamepad.btnStop,  sendStop])
  useEffect(() => { if (gamepad.btnFocus) sendAutofocus() }, [gamepad.btnFocus, sendAutofocus])

  // Camera controls
  const startCamera = useCallback(async () => {
    if (!cameraId) return
    try { setLoopLoading(true); await api.cameras.start(cameraId); setCamStatus(await api.cameras.status(cameraId)) }
    catch (e) { console.error(e) }
    finally   { setLoopLoading(false) }
  }, [cameraId])

  const stopCamera = useCallback(async () => {
    if (!cameraId) return
    try { setLoopLoading(true); await api.cameras.stop(cameraId); setCamStatus(await api.cameras.status(cameraId)) }
    catch (e) { console.error(e) }
    finally   { setLoopLoading(false) }
  }, [cameraId])

  // Config patch with debounced save
  const patchConfig = useCallback((update: ConfigUpdate) => {
    if (!cameraId) return
    setConfig(prev => {
      if (!prev) return prev
      return {
        ...prev,
        pan: { ...prev.pan,
          ...(update.pan_stable_zone_h_px   !== undefined && { stable_zone_h_px:   update.pan_stable_zone_h_px }),
          ...(update.pan_stable_zone_v_px !== undefined && { stable_zone_v_px: update.pan_stable_zone_v_px }),
          ...(update.pan_kp             !== undefined && { kp:             update.pan_kp }),
          ...(update.pan_max_speed      !== undefined && { max_speed:      update.pan_max_speed }),
          ...(update.pan_min_speed      !== undefined && { min_speed:      update.pan_min_speed }),
          ...(update.pan_invert         !== undefined && { invert:         update.pan_invert }),
        },
        zoom: { ...prev.zoom,
          ...(update.zoom_in_frac   !== undefined && { zoom_in_frac:  update.zoom_in_frac }),
          ...(update.zoom_out_frac  !== undefined && { zoom_out_frac: update.zoom_out_frac }),
          ...(update.zoom_speed     !== undefined && { speed:         update.zoom_speed }),
          ...(update.zoom_invert    !== undefined && { invert:        update.zoom_invert }),
          ...(update.zoom_ema_alpha !== undefined && { ema_alpha:     update.zoom_ema_alpha }),
        },
        track: { ...prev.track,
          ...(update.detect_classes  !== undefined && { detect_classes:  update.detect_classes }),
          ...(update.lock_confidence !== undefined && { lock_confidence: update.lock_confidence }),
          ...(update.tracker_max_age !== undefined && { tracker_max_age: update.tracker_max_age }),
        },
        command: { ...prev.command,
          ...(update.no_track_stop_sec !== undefined && { no_track_stop_sec: update.no_track_stop_sec }),
          ...(update.lock_off_sec      !== undefined && { lock_off_sec:      update.lock_off_sec }),
        },
        record: { ...prev.record,
          ...(update.record_duration_sec !== undefined && { duration_sec: update.record_duration_sec }),
          ...(update.record_fps          !== undefined && { fps:          update.record_fps }),
          ...(update.record_res          !== undefined && { record_res:   update.record_res }),
        },
        speed: { ...prev.speed,
          ...(update.hfov_deg !== undefined && { hfov_deg: update.hfov_deg }),
        },
        home: { ...prev.home,
          ...(update.home_pan    !== undefined && { pan:    update.home_pan }),
          ...(update.home_tilt   !== undefined && { tilt:   update.home_tilt }),
          ...(update.home_zoom   !== undefined && { zoom:   update.home_zoom }),
          ...(update.home_is_set !== undefined && { is_set: update.home_is_set }),
        },
        area: { ...prev.area,
          ...(update.area_enabled   !== undefined && { enabled:   update.area_enabled }),
          ...(update.area_pan_min   !== undefined && { pan_min:   update.area_pan_min }),
          ...(update.area_pan_max   !== undefined && { pan_max:   update.area_pan_max }),
          ...(update.area_tilt_min  !== undefined && { tilt_min:  update.area_tilt_min }),
          ...(update.area_tilt_max  !== undefined && { tilt_max:  update.area_tilt_max }),
          ...(update.area_scan_zoom !== undefined && { scan_zoom: update.area_scan_zoom }),
        },
        scan: { ...prev.scan,
          ...(update.scan_enabled    !== undefined && { enabled:    update.scan_enabled }),
          ...(update.scan_rows       !== undefined && { rows:       update.scan_rows }),
          ...(update.scan_cols       !== undefined && { cols:       update.scan_cols }),
          ...(update.scan_travel_sec !== undefined && { travel_sec: update.scan_travel_sec }),
          ...(update.scan_dwell_sec  !== undefined && { dwell_sec:  update.scan_dwell_sec }),
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

  // Derived display values
  const isRecording = telemetry?.rec_active ?? false
  const mode        = telemetry?.mode       ?? 'manual'
  const scanPhase   = telemetry?.scan_phase ?? 'idle'
  const isUnlimited = (telemetry?.rec_total ?? -1) === 0
  const recPct      = (!isUnlimited && telemetry)
    ? Math.min(100, (telemetry.rec_elapsed / Math.max(1, telemetry.rec_total)) * 100)
    : 0

  const durationValue = config
    ? (DURATION_OPTIONS.find(o => o.value === config.record.duration_sec)?.value ?? DURATION_OPTIONS[0].value)
    : 30

  const SaveDot = () => saveStatus === 'saved'
    ? <span className="text-xs text-green-400 flex gap-1 items-center"><CheckCircle2 size={11}/> Saved</span>
    : saveStatus === 'saving'
    ? <span className="text-xs text-white/30">Saving…</span>
    : null

  const padName = (id: string) => id.split('(')[0].trim() || 'Controller'

  return (
    <div className="h-full overflow-auto px-1 py-2">
      <div className="flex gap-3">

        {/* ── Left panel ──────────────────────────────────────────────────── */}
        <div className="w-52 shrink-0 space-y-3">

          <Card title="Camera">
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <StatusDot active={camStatus?.running ?? false} />
                <span className="text-xs text-white/50 flex-1 truncate">
                  {camStatus?.running ? (camStatus.source_name || 'Running') : 'Not running'}
                </span>
              </div>
              {camStatus?.device_name && (
                <div className="text-xs text-white/30 truncate font-mono" title={camStatus.device}>
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
                  <Button size="sm" className="w-full" onClick={startCamera} loading={loopLoading}
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

          {/* Joystick */}
          <Card>
            <div className="space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-white/40 uppercase tracking-wider">Joystick</span>
                {gamepad.connected && <StatusDot active />}
              </div>
              <div className="flex gap-1.5">
                <select
                  value={activePadIdx ?? ''}
                  onChange={e => setActivePadIdx(e.target.value === '' ? null : parseInt(e.target.value))}
                  className="flex-1 min-w-0 text-xs bg-surface-base border border-surface-border
                             rounded px-2 py-1 text-white focus:outline-none focus:border-blue-500">
                  <option value="">— none —</option>
                  {detectedPads.map(pad => (
                    <option key={pad.index} value={pad.index}>
                      {padName(pad.id).slice(0, 22)}
                    </option>
                  ))}
                </select>
                <button onClick={scanGamepads} title="Scan for controllers"
                  className="shrink-0 px-2 py-1 rounded border border-surface-border
                             bg-surface-raised hover:bg-surface-hover text-white/50
                             hover:text-white transition-colors">
                  <RefreshCw size={11} />
                </button>
              </div>
              {detectedPads.length === 0 && (
                <p className="text-[11px] text-white/25 text-center leading-snug">
                  Press a button on your<br />controller, then scan
                </p>
              )}
              {gamepad.connected && (
                <div className="space-y-1.5 pt-1 border-t border-surface-border">
                  <AxisBar label="Pan"  value={gamepad.pan} />
                  <AxisBar label="Tilt" value={gamepad.tilt} />
                  <AxisBar label="Zoom" value={gamepad.zoom} />
                </div>
              )}
              {gamepad.connected && (
                <div className="flex gap-1.5">
                  <button onClick={sendStop}
                    className="flex-1 py-1.5 text-xs rounded bg-red-900/50 hover:bg-red-700/60
                               text-red-300 border border-red-800/60 transition-colors">
                    ✕ Stop
                  </button>
                  <button onClick={sendAutofocus}
                    className="flex-1 py-1.5 text-xs rounded bg-surface-raised hover:bg-surface-hover
                               text-white/60 hover:text-white border border-surface-border transition-colors">
                    ◎ Focus
                  </button>
                </div>
              )}
            </div>
          </Card>

          {/* Recording */}
          <Card>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-white/40 uppercase tracking-wider">Recording</span>
                <SaveDot />
              </div>
              {config ? (
                <>
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="w-20 shrink-0 text-xs text-white/50">Duration</span>
                      <select value={durationValue}
                        onChange={e => patchConfig({ record_duration_sec: parseInt(e.target.value) })}
                        className="flex-1 text-xs bg-surface-base border border-surface-border
                                   rounded px-2 py-1 text-white focus:outline-none focus:border-blue-500">
                        {DURATION_OPTIONS.map(opt => (
                          <option key={opt.value} value={opt.value}
                            className={opt.value === 0 ? 'text-amber-400' : ''}>
                            {opt.label}
                          </option>
                        ))}
                      </select>
                    </div>
                    {durationValue === 0 && (
                      <p className="text-xs text-amber-400/70 pl-[88px]">Record until stopped</p>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-20 shrink-0 text-xs text-white/50">FPS</span>
                    <select value={config.record.fps}
                      onChange={e => patchConfig({ record_fps: parseInt(e.target.value) })}
                      className="flex-1 text-xs bg-surface-base border border-surface-border
                                 rounded px-2 py-1 text-white focus:outline-none focus:border-blue-500">
                      {[15, 20, 25, 30].map(fps => (
                        <option key={fps} value={fps}>{fps} fps</option>
                      ))}
                    </select>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-20 shrink-0 text-xs text-white/50">Resolution</span>
                    <select
                      value={`${config.record.record_res[0]}x${config.record.record_res[1]}`}
                      onChange={e => {
                        const [w, h] = e.target.value.split('x').map(Number)
                        patchConfig({ record_res: [w, h] })
                      }}
                      className="flex-1 text-xs bg-surface-base border border-surface-border
                                 rounded px-2 py-1 text-white focus:outline-none focus:border-blue-500">
                      {RES_OPTIONS.map(([w, h]) => (
                        <option key={`${w}x${h}`} value={`${w}x${h}`}>{w}×{h}</option>
                      ))}
                    </select>
                  </div>
                </>
              ) : (
                <p className="text-xs text-white/30 text-center py-1">
                  {cameraId ? 'Loading…' : 'Select a camera'}
                </p>
              )}
              <div className="pt-1 border-t border-surface-border">
                {isRecording ? (
                  <div className="space-y-2">
                    <div className="space-y-1">
                      <div className="flex justify-between text-xs">
                        <span className="text-red-400 font-medium flex items-center gap-1">
                          <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse inline-block" />
                          Recording
                        </span>
                        {isUnlimited
                          ? <span className="font-mono text-amber-400/80">{telemetry?.rec_elapsed.toFixed(0)}s ∞</span>
                          : <span className="font-mono text-white/60">{telemetry?.rec_elapsed.toFixed(0)}s / {telemetry?.rec_total.toFixed(0)}s</span>
                        }
                      </div>
                      {isUnlimited
                        ? <div className="h-1.5 bg-surface-border rounded-full overflow-hidden">
                            <div className="h-full bg-amber-500 rounded-full animate-pulse" style={{ width: '40%' }} />
                          </div>
                        : <div className="h-1.5 bg-surface-border rounded-full overflow-hidden">
                            <div className="h-full bg-red-500 rounded-full transition-all duration-500"
                                 style={{ width: `${recPct}%` }} />
                          </div>
                      }
                    </div>
                    <Button variant="ghost" size="sm" className="w-full" onClick={() => setRecording('stop')}>
                      <Square size={11} /> Stop Recording
                    </Button>
                  </div>
                ) : (
                  <Button variant="danger" size="sm" className="w-full" onClick={() => setRecording('start')}>
                    <Radio size={11} /> Start Recording
                  </Button>
                )}
              </div>
            </div>
          </Card>
        </div>

        {/* ── Center: Video + Tuning ───────────────────────────────────────── */}
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
                    : <Button size="sm" onClick={startWebRTC} disabled={!cameraId}
                              loading={rtcState === 'connecting'}>
                        Connect Video
                      </Button>}
                </div>
              </div>
              <VideoPlayer stream={stream} rtcState={rtcState} rtcError={rtcError} />
            </div>
          </Card>

          {config && (
            <>
              <TrackingTuning config={config} patchConfig={patchConfig} SaveDot={SaveDot} />
              <BehaviourPanel config={config} patchConfig={patchConfig} SaveDot={SaveDot} cameraId={cameraId} />
            </>
          )}
        </div>

        {/* ── Right panel ──────────────────────────────────────────────────── */}
        <div className="w-52 shrink-0 space-y-3">

          <Card title="Telemetry">
            <TelemetryPanel telemetry={telemetry} />
          </Card>

          <Card title="PTZ Control">
            <div className="space-y-2">
              <div className="grid gap-1" style={{ gridTemplateColumns: '1fr 1fr 1fr' }}>
                <div />
                <PtzBtn className="h-10 w-full"
                  onActivate={() => sendPanTilt(0, PTZ_SPEED)} onDeactivate={sendStop}>
                  <ChevronUp size={18} />
                </PtzBtn>
                <div />
                <PtzBtn className="h-10 w-full"
                  onActivate={() => sendPanTilt(PTZ_SPEED, 0)} onDeactivate={sendStop}>
                  <ChevronLeft size={18} />
                </PtzBtn>
                <button onClick={sendStop}
                  className="h-10 flex items-center justify-center rounded border border-surface-border
                             bg-surface-raised text-white/30 hover:text-red-400 hover:border-red-700
                             hover:bg-red-900/30 text-base font-bold transition-colors">
                  ■
                </button>
                <PtzBtn className="h-10 w-full"
                  onActivate={() => sendPanTilt(-PTZ_SPEED, 0)} onDeactivate={sendStop}>
                  <ChevronRight size={18} />
                </PtzBtn>
                <div />
                <PtzBtn className="h-10 w-full"
                  onActivate={() => sendPanTilt(0, -PTZ_SPEED)} onDeactivate={sendStop}>
                  <ChevronDown size={18} />
                </PtzBtn>
                <div />
              </div>
              <div className="grid grid-cols-2 gap-1">
                <PtzBtn className="h-9 w-full"
                  onActivate={() => sendZoom(PTZ_SPEED)} onDeactivate={sendStop}>
                  <ZoomIn size={14} className="mr-1" /><span className="text-xs">In</span>
                </PtzBtn>
                <PtzBtn className="h-9 w-full"
                  onActivate={() => sendZoom(-PTZ_SPEED)} onDeactivate={sendStop}>
                  <ZoomOut size={14} className="mr-1" /><span className="text-xs">Out</span>
                </PtzBtn>
              </div>
              <div className="space-y-1 pt-1 border-t border-surface-border">
                <Button variant="ghost" size="sm" className="w-full" onClick={sendStop}>
                  Stop All Motion
                </Button>
                <Button variant="ghost" size="sm" className="w-full" onClick={sendAutofocus}>
                  <Focus size={11} /> Autofocus
                </Button>
              </div>
            </div>
          </Card>

          <Card title="Mode">
            <div className="flex gap-2">
              {(['manual', 'auto_track'] as const).map(m => (
                <button key={m} onClick={() => setMode(m)}
                  className={[
                    'flex-1 py-2 text-xs font-medium rounded border transition-colors',
                    mode === m
                      ? m === 'manual'
                        ? 'bg-blue-600 border-blue-500 text-white'
                        : 'bg-green-700 border-green-600 text-white'
                      : 'bg-surface-raised border-surface-border text-white/40 hover:text-white/70',
                  ].join(' ')}>
                  {m === 'auto_track' && <Crosshair size={11} className="inline mr-1" />}
                  {m === 'manual' ? 'Manual' : 'Auto-track'}
                </button>
              ))}
            </div>

            {/* Scan phase indicator */}
            {mode === 'auto_track' && (
              <div className="mt-2 flex items-center justify-center gap-1.5">
                {scanPhase === 'locked'   && <>
                  <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
                  <span className="text-xs text-green-400">Target Locked</span>
                </>}
                {scanPhase === 'scanning' && <>
                  <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
                  <span className="text-xs text-amber-400">Scanning…</span>
                </>}
                {scanPhase === 'idle'     && <>
                  <span className="w-2 h-2 rounded-full bg-white/20" />
                  <span className="text-xs text-white/30">Idle</span>
                </>}
              </div>
            )}
          </Card>

          <ProfilesCard
            cameraId={cameraId}
            onLoaded={() => {
              if (cameraId) api.cameras.getConfig(cameraId).then(setConfig).catch(console.error)
            }}
          />

        </div>
      </div>
    </div>
  )
}
