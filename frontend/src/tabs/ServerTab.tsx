import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { useServer } from '../context/ServerContext'
import type { SystemInfo, SystemMetrics } from '../types'

function Gauge({ label, value, max, unit, color = 'blue' }: {
  label: string; value: number; max: number; unit: string; color?: string
}) {
  const pct = Math.min(100, Math.round((value / max) * 100))
  const barColor = pct > 85 ? 'bg-red-500' : pct > 65 ? 'bg-amber-500' : `bg-${color}-500`
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

export function ServerTab() {
  const { server, disconnect } = useServer()
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null)
  const [info,    setInfo]    = useState<SystemInfo | null>(null)
  const [error,   setError]   = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    const fetchInfo = async () => {
      try { const d = await api.system.info(); if (alive) setInfo(d) }
      catch { /* server may not have psutil yet */ }
    }
    fetchInfo()
    return () => { alive = false }
  }, [])

  useEffect(() => {
    let alive = true
    const poll = async () => {
      try {
        const d = await api.system.metrics()
        if (alive) { setMetrics(d); setError(null) }
      } catch (e: unknown) {
        if (alive) setError(e instanceof Error ? e.message : String(e))
      }
    }
    poll()
    const id = setInterval(poll, 2000)
    return () => { alive = false; clearInterval(id) }
  }, [])

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
          <StatRow label="OS"          value={`${info.os} ${info.machine}`} />
          <StatRow label="Python"      value={info.python} />
          <StatRow label="Inference"   value={info.device_name || info.device} />
          <StatRow label="Device"      value={info.device} />
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
                  ({metrics.memory.percent.toFixed(0)}%)
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
              <Gauge
                label="VRAM"
                value={metrics.gpu.memory_used_gb}
                max={metrics.gpu.memory_total_gb}
                unit="GB"
                color="teal"
              />
              <div className="flex gap-6 pt-1">
                <StatRow label="Temp" value={`${metrics.gpu.temperature_c} °C`} />
                {metrics.gpu.power_watts != null && (
                  <StatRow label="Power" value={`${metrics.gpu.power_watts} W`} />
                )}
              </div>
            </div>
          ) : (
            <div className="bg-surface-panel border border-surface-border rounded-xl p-4">
              <p className="text-xs text-white/30">
                No NVIDIA GPU detected — GPU metrics unavailable.<br />
                On Apple Silicon, power/thermal data requires a separate tool.
              </p>
            </div>
          )}
        </>
      ) : (
        <div className="text-xs text-white/30 p-4">Loading metrics…</div>
      )}
    </div>
  )
}
