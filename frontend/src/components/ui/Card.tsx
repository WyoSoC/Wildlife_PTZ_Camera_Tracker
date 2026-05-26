import { type HTMLAttributes } from 'react'
import { clsx } from 'clsx'

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  title?: string
}

export function Card({ title, className, children, ...rest }: CardProps) {
  return (
    <div
      className={clsx(
        'rounded-lg border border-surface-border bg-surface-panel',
        className,
      )}
      {...rest}
    >
      {title && (
        <div className="px-4 py-2.5 border-b border-surface-border">
          <h3 className="text-xs font-semibold tracking-widest text-white/40 uppercase">
            {title}
          </h3>
        </div>
      )}
      <div className="p-4">{children}</div>
    </div>
  )
}
