import { clsx } from 'clsx'

type BadgeColor = 'green' | 'red' | 'blue' | 'yellow' | 'gray'

const colors: Record<BadgeColor, string> = {
  green:  'bg-green-900/50  text-green-400  border-green-800',
  red:    'bg-red-900/50    text-red-400    border-red-800',
  blue:   'bg-blue-900/50   text-blue-400   border-blue-800',
  yellow: 'bg-yellow-900/50 text-yellow-400 border-yellow-800',
  gray:   'bg-white/5       text-white/40   border-white/10',
}

interface BadgeProps {
  color?: BadgeColor
  pulse?: boolean
  children: React.ReactNode
}

export function Badge({ color = 'gray', pulse = false, children }: BadgeProps) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-medium border',
        colors[color],
      )}
    >
      {pulse && (
        <span
          className={clsx(
            'w-1.5 h-1.5 rounded-full animate-pulse',
            color === 'red' ? 'bg-red-400' : 'bg-green-400',
          )}
        />
      )}
      {children}
    </span>
  )
}

export function StatusDot({ active, className }: { active: boolean; className?: string }) {
  return (
    <span
      className={clsx(
        'w-2 h-2 rounded-full shrink-0',
        active ? 'bg-green-400' : 'bg-red-500',
        className,
      )}
    />
  )
}
