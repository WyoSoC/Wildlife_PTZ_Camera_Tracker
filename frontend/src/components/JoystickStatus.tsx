import type { GamepadState } from '../hooks/useGamepad'
import { StatusDot } from './ui/Badge'

interface AxisBarProps {
  label: string
  value: number  // [-1..1]
}

function AxisBar({ label, value }: AxisBarProps) {
  // Map [-1..1] → [0..100]%
  const pct = ((value + 1) / 2) * 100

  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-8 shrink-0 text-white/40">{label}</span>
      <div className="relative flex-1 h-2 bg-surface-border rounded-full overflow-hidden">
        {/* centre tick */}
        <span className="absolute left-1/2 -translate-x-px w-px h-full bg-white/20" />
        <div
          className="absolute top-0 h-full bg-blue-500 rounded-full transition-all duration-75"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="w-12 text-right font-mono text-white/60">{value.toFixed(2)}</span>
    </div>
  )
}

interface Props {
  state: GamepadState
  onStop?: () => void
  onAutofocus?: () => void
}

export function JoystickStatus({ state, onStop, onAutofocus }: Props) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <StatusDot active={state.connected} />
        <span className="text-sm text-white/70 truncate min-w-0">
          {state.connected
            ? state.name.split('(')[0].trim() || 'Gamepad'
            : 'No gamepad detected'}
        </span>
      </div>

      {state.connected && (
        <>
          <div className="space-y-1.5">
            <AxisBar label="Pan"  value={state.pan}  />
            <AxisBar label="Tilt" value={state.tilt} />
            <AxisBar label="Zoom" value={state.zoom} />
          </div>

          <div className="flex gap-2 pt-1">
            <button
              onClick={onStop}
              className="flex-1 py-1.5 text-xs rounded bg-red-900/50 hover:bg-red-700/60
                         text-red-300 border border-red-800/60 transition-colors"
            >
              ✕ Stop
            </button>
            <button
              onClick={onAutofocus}
              className="flex-1 py-1.5 text-xs rounded bg-surface-raised hover:bg-surface-border
                         text-white/60 hover:text-white border border-surface-border transition-colors"
            >
              ◎ Autofocus
            </button>
          </div>
        </>
      )}
    </div>
  )
}
