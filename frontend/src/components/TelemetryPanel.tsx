import type { Telemetry } from '../types'

interface RowProps {
  label: string
  value: string
  highlight?: boolean
}

function Row({ label, value, highlight = false }: RowProps) {
  return (
    <div className="flex justify-between items-baseline text-xs">
      <span className="text-white/40">{label}</span>
      <span className={`font-mono ${highlight ? 'text-green-400' : 'text-white/80'}`}>
        {value}
      </span>
    </div>
  )
}

interface Props {
  telemetry: Telemetry | null
}

export function TelemetryPanel({ telemetry }: Props) {
  if (!telemetry) {
    return <p className="text-xs text-white/30">Waiting for telemetry…</p>
  }

  return (
    <div className="space-y-1.5">
      <Row label="FPS"       value={telemetry.fps.toFixed(1)} />
      <Row
        label="Detected"
        value={telemetry.detected ? 'YES' : 'NO'}
        highlight={telemetry.detected}
      />
      {telemetry.track_id !== null && (
        <Row label="Track ID"    value={String(telemetry.track_id)} />
      )}
      {telemetry.detected && (
        <>
          <Row label="Confidence"  value={`${(telemetry.confidence * 100).toFixed(0)}%`} />
          <Row label="Speed"       value={`${telemetry.speed_px.toFixed(0)} px/s`} />
          <Row label=""            value={`${telemetry.speed_deg.toFixed(1)} °/s`} />
          <Row label="Zoom EMA"    value={telemetry.wfrac_ema.toFixed(3)} />
        </>
      )}
      <div className="pt-1 border-t border-surface-border mt-1">
        <Row
          label="Mode"
          value={telemetry.mode === 'auto_track' ? 'Auto-track' : 'Manual'}
          highlight={telemetry.mode === 'auto_track'}
        />
        <Row label="Camera"   value={telemetry.source_name || '—'} />
      </div>
    </div>
  )
}
