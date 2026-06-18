interface SliderFieldProps {
  label:    string
  value:    number
  min:      number
  max:      number
  step?:    number
  unit?:    string
  decimals?: number
  tooltip?: string
  onChange: (v: number) => void
}

export function SliderField({
  label, value, min, max, step = 0.01, unit = '', decimals = 2, tooltip, onChange,
}: SliderFieldProps) {
  return (
    <div className="flex items-center gap-3">
      <span
        className="w-28 shrink-0 text-xs text-white/50 cursor-default"
        title={tooltip}
      >
        {label}{tooltip && <span className="ml-1 text-white/20">ⓘ</span>}
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="flex-1"
      />
      <span className="w-16 text-right text-xs font-mono text-white/80">
        {value.toFixed(decimals)}{unit}
      </span>
    </div>
  )
}

interface ToggleFieldProps {
  label:    string
  value:    boolean
  onChange: (v: boolean) => void
}

export function ToggleField({ label, value, onChange }: ToggleFieldProps) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-xs text-white/50">{label}</span>
      <button
        onClick={() => onChange(!value)}
        className={`relative w-9 h-5 rounded-full transition-colors ${
          value ? 'bg-blue-600' : 'bg-surface-border'
        }`}
      >
        <span
          className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform ${
            value ? 'translate-x-4' : 'translate-x-0'
          }`}
        />
      </button>
    </div>
  )
}
