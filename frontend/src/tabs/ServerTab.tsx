import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import { useServer } from '../context/ServerContext'
import type { SystemInfo, SystemMetrics } from '../types'

// ── Gauge bar ──────────────────────────────────────────────────────────────────

const GAUGE_COLORS: Record<string, string> = {
  blue:   'bg-blue-500',
  purple: 'bg-purple-500',
  green:  'bg-green-500',
  teal:   'bg-teal-500',
}

function Gauge({ label, value, max, unit, color = 'blue' }: {
  label: string; value: number; max: number; unit: string; color?: string
}) {
  const pct = Math.min(100, Math.round((value / max) * 100))
  const barColor = pct > 85 ? 'bg-red-500' : pct > 65 ? 'bg-amber-500' : (GAUGE_COLORS[color] ?? 'bg-blue-500')
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-white/60">
        <span>{label}</span>
        <span className="font-mono text-white">{value.toFixed(1)} {unit}</span>
      </div>
      <div className="h-1.5 bg-surface-base rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all ${barColor}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

function StatRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between py-1 border-b border-surface-border/40 last:border-0">
      <span className="text-xs text-white/50">{label}</span>
      <span className="text-xs text-white font-mono">{value}</span>
    </div>
  )
}

// ── History chart ──────────────────────────────────────────────────────────────

interface Sample {
  t:       number        // epoch ms
  cpu:     number        // 0-100 %
  mem:     number        // 0-100 %
  gpuUtil: number | null // 0-100 %
  gpuTemp: number | null // °C  (plotted 0-100, compatible scale)
}

const MAX_SAMPLES = 3600   // 2 h at 2-second resolution

const TIME_WINDOWS = [
  { label: '5m',  ms:   5 * 60_000 },
  { label: '15m', ms:  15 * 60_000 },
  { label: '1h',  ms:  60 * 60_000 },
  { label: '2h',  ms: 120 * 60_000 },
]

const CHART_SERIES: {
  key:      string
  label:    string
  unit:     string
  color:    string
  dot:      string
  getValue: (s: Sample) => number | null
}[] = [
  { key: 'cpu',     label: 'CPU',      unit: '%',  color: '#3b82f6', dot: 'bg-blue-500',   getValue: s => s.cpu },
  { key: 'mem',     label: 'Memory',   unit: '%',  color: '#a855f7', dot: 'bg-purple-500', getValue: s => s.mem },
  { key: 'gpuUtil', label: 'GPU Util', unit: '%',  color: '#22c55e', dot: 'bg-green-500',  getValue: s => s.gpuUtil },
  { key: 'gpuTemp', label: 'GPU Temp', unit: '°C', color: '#f59e0b', dot: 'bg-amber-500',  getValue: s => s.gpuTemp },
]

function buildSegments(
  pts: Sample[],
  getValue: (s: Sample) => number | null,
  xOf: (t: number) => number,
  yOf: (v: number) => number,
): string[] {
  const segs: string[][] = [[]]
  for (const s of pts) {
    const v = getValue(s)
    if (v == null) {
      if (segs[segs.length - 1].length > 0) segs.push([])
    } else {
      segs[segs.length - 1].push(`${xOf(s.t).toFixed(1)},${yOf(v).toFixed(1)}`)
    }
  }
  return segs.filter(seg => seg.length >= 2).map(seg => seg.join(' '))
}

function HistoryChart({ samples, windowMs }: { samples: Sample[]; windowMs: number }) {
  const now    = Date.now()
  const cutoff = now - windowMs
  const pts    = samples.filter(s => s.t >= cutoff)

  const W = 600, H = 140
  const PL = 28, PR = 8, PT = 6, PB = 20
  const cw = W - PL - PR
  const ch = H - PT - PB

  const tMin = cutoff
  const tMax = now

  const xOf = (t: number) => PL + ((t - tMin) / (tMax - tMin)) * cw
  const yOf = (v: number) => PT + ch - (Math.min(100, Math.max(0, v)) / 100) * ch

  const fmtTime = (ms: number) => {
    const d = new Date(ms)
    return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  }

  const xLabels = Array.from({ length: 5 }, (_, i) => {
    const t = tMin + (tMax - tMin) * (i / 4)
    return { t, x: xOf(t), label: fmtTime(t) }
  })

  if (pts.length < 2) {
    return (
      <div className="flex items-center justify-center text-xs text-white/25" style={{ height: `${H}px` }}>
        Collecting data…
      </div>
    )
  }

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height: `${H}px` }}>
      {/* Horizontal grid lines */}
      {[0, 25, 50, 75, 100].map(v => (
        <g key={v}>
          <line
            x1={PL} y1={yOf(v)} x2={W - PR} y2={yOf(v)}
            stroke="rgba(255,255,255,0.06)" strokeWidth="1"
          />
          <text x={PL - 4} y={yOf(v) + 3.5} textAnchor="end"
            fill="rgba(255,255,255,0.22)" fontSize="7.5">
            {v}
          </text>
        </g>
      ))}

      {/* Chart border */}
      <rect x={PL} y={PT} width={cw} height={ch}
        fill="none" stroke="rgba(255,255,255,0.07)" strokeWidth="0.5" />

      {/* Series lines */}
      {CHART_SERIES.map(({ key, color, getValue }) =>
        buildSegments(pts, getValue, xOf, yOf).map((points, i) => (
          <polyline key={`${key}-${i}`} points={points}
            fill="none" stroke={color} strokeWidth="1.5"
            strokeLinejoin="round" strokeLinecap="round" opacity="0.9"
          />
        ))
      )}

      {/* X-axis time labels */}
      {xLabels.map(({ t, x, label }) => (
        <text key={t} x={x} y={H - 4} textAnchor="middle"
          fill="rgba(255,255,255,0.22)" fontSize="7.5">
          {label}
        </text>
      ))}
    </svg>
  )
}

// ── Main tab ───────────────────────────────────────────────────────────────────

export function ServerTab() {
  const { server, disconnect } = useServer()
  const [metrics,   setMetrics]   = useState<SystemMetrics | null>(null)
  const [info,      setInfo]      = useState<SystemInfo | null>(null)
  const [error,     setError]     = useState<string | null>(null)
  const [samples,   setSamples]   = useState<Sample[]>([])
  const [windowIdx, setWindowIdx] = useState(0)

  // Keep a stable ref to samples for the polling closure
  const samplesRef = useRef(samples)
  useEffect(() => { samplesRef.current = samples }, [samples])

  useEffect(() => {
    let alive = true
    api.system.info()
      .then(d => { if (alive) setInfo(d) })
      .catch(() => {})
    return () => { alive = false }
  }, [])

  useEffect(() => {
    let alive = true
    const poll = async () => {
      try {
        const d = await api.system.metrics()
        if (!alive) return
        setMetrics(d)
        setError(null)

        // Append sample to history ring buffer
        if (d.cpu_percent != null) {
          const sample: Sample = {
            t:       Date.now(),
            cpu:     d.cpu_percent,
            mem:     d.memory?.percent ?? 0,
            gpuUtil: d.gpu?.utilization_pct ?? null,
            gpuTemp: d.gpu?.temperature_c   ?? null,
          }
          setSamples(prev => {
            const next = [...prev, sample]
            return next.length > MAX_SAMPLES ? next.slice(next.length - MAX_SAMPLES) : next
          })
        }
      } catch (e: unknown) {
        if (alive) setError(e instanceof Error ? e.message : String(e))
      }
    }
    poll()
    const id = setInterval(poll, 2000)
    return () => { alive = false; clearInterval(id) }
  }, [])

  const windowMs = TIME_WINDOWS[windowIdx].ms

  return (
    <div className="h-full overflow-y-auto p-4 space-y-4 max-w-2xl mx-auto">

      {/* Connection info */}
      <div className="bg-surface-panel border border-surface-border rounded-xl p-4">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm font-semibold text-white">{server?.name}</p>
            <p className="text-xs text-white/40 mt-0.5 font-mono break-all">{server?.url}</p>
          </div>
          <button
            onClick={disconnect}
            className="text-xs text-white/30 hover:text-red-400 transition-colors shrink-0 ml-4"
          >
            Disconnect
          </button>
        </div>
      </div>

      {/* Platform info */}
      {info && (
        <div className="bg-surface-panel border border-surface-border rounded-xl p-4">
          <h3 className="text-xs font-semibold text-white/50 uppercase tracking-wider mb-3">
            Platform
          </h3>
          <StatRow label="OS"        value={`${info.os} ${info.machine}`} />
          <StatRow label="Python"    value={info.python} />
          <StatRow label="Inference" value={info.device_name || info.device} />
          <StatRow label="Device"    value={info.device} />
        </div>
      )}

      {/* Live metrics */}
      {error ? (
        <div className="bg-surface-panel border border-surface-border rounded-xl p-4">
          <p className="text-xs text-red-400">{error}</p>
          <p className="text-xs text-white/30 mt-1">
            Install psutil on the server: <code>pip install psutil</code>
          </p>
        </div>
      ) : metrics ? (
        <>
          {/* CPU + Memory */}
          <div className="bg-surface-panel border border-surface-border rounded-xl p-4 space-y-3">
            <h3 className="text-xs font-semibold text-white/50 uppercase tracking-wider">
              CPU &amp; Memory
            </h3>
            {metrics.cpu_percent != null && (
              <Gauge label="CPU" value={metrics.cpu_percent} max={100} unit="%" color="blue" />
            )}
            {metrics.memory?.total_gb > 0 && (
              <>
                <Gauge
                  label="Memory"
                  value={metrics.memory.used_gb}
                  max={metrics.memory.total_gb}
                  unit="GB"
                  color="purple"
                />
                <div className="text-xs text-white/30 text-right">
                  {metrics.memory.used_gb.toFixed(1)} / {metrics.memory.total_gb.toFixed(1)} GB
                  &nbsp;({metrics.memory.percent.toFixed(0)}%)
                </div>
              </>
            )}
          </div>

          {/* GPU */}
          {metrics.gpu ? (
            <div className="bg-surface-panel border border-surface-border rounded-xl p-4 space-y-3">
              <h3 className="text-xs font-semibold text-white/50 uppercase tracking-wider">
                GPU — {metrics.gpu.name}
              </h3>
              <Gauge label="GPU Utilisation" value={metrics.gpu.utilization_pct} max={100} unit="%" color="green" />
              {metrics.gpu.memory_used_gb != null && metrics.gpu.memory_total_gb != null && (
                <>
                  <Gauge
                    label="VRAM"
                    value={metrics.gpu.memory_used_gb}
                    max={metrics.gpu.memory_total_gb}
                    unit="GB"
                    color="teal"
                  />
                  <div className="text-xs text-white/30 text-right">
                    {metrics.gpu.memory_used_gb.toFixed(1)} / {metrics.gpu.memory_total_gb.toFixed(1)} GB
                  </div>
                </>
              )}
              {(metrics.gpu.temperature_c != null || metrics.gpu.power_watts != null) && (
                <div className="flex flex-wrap gap-6 pt-3 mt-1 border-t border-surface-border/50">
                  {metrics.gpu.temperature_c != null && (
                    <div className="space-y-0.5">
                      <p className="text-[10px] font-semibold text-white/40 uppercase tracking-wider">
                        Temperature
                      </p>
                      <p className="text-base font-mono text-white">
                        {metrics.gpu.temperature_c.toFixed(1)}&thinsp;°C
                      </p>
                    </div>
                  )}
                  {metrics.gpu.power_watts != null && (
                    <div className="space-y-0.5">
                      <p className="text-[10px] font-semibold text-white/40 uppercase tracking-wider">
                        Power
                      </p>
                      <p className="text-base font-mono text-white">
                        {metrics.gpu.power_watts}&thinsp;W
      </p>
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : (
            <div className="bg-surface-panel border border-surface-border rounded-xl p-4">
              <p className="text-xs text-white/30">
                GPU metrics unavailable.
                {info?.device === 'mps' && ' On Apple Silicon, power/thermal data requires a separate tool (e.g. asitop).'}
              </p>
            </div>
          )}

          {/* History chart */}
          <div className="bg-surface-panel border border-surface-border rounded-xl p-4 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-semibold text-white/50 uppercase tracking-wider">
                History
              </h3>
              <div className="flex gap-1">
                {TIME_WINDOWS.map((w, i) => (
                  <button
                    key={w.label}
                    onClick={() => setWindowIdx(i)}
                    className={[
                      'px-2 py-0.5 text-[11px] rounded border transition-colors',
                      windowIdx === i
                        ? 'bg-blue-600/40 border-blue-500/60 text-blue-300'
                        : 'bg-surface-raised border-surface-border text-white/35 hover:text-white/60',
                    ].join(' ')}
                  >
                    {w.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Legend */}
            <div className="flex flex-wrap gap-x-4 gap-y-1">
              {CHART_SERIES.map(s => (
                <div key={s.key} className="flex items-center gap-1.5">
                  <span className={`w-2.5 h-2.5 rounded-sm ${s.dot}`} />
                  <span className="text-[11px] text-white/50">
                    {s.label}
                    <span className="text-white/25 ml-0.5">{s.unit}</span>
                  </span>
                </div>
              ))}
            </div>

            <HistoryChart samples={samples} windowMs={windowMs} />
          </div>
        </>
      ) : (
        <div className="text-xs text-white/30 p-4">Loading metrics…</div>
      )}
    </div>
  )
}
