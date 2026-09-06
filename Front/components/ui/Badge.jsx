import { cn } from '@/lib/utils'

const VARIANTS = {
  success: 'bg-success-bg text-success',
  warning: 'bg-warning-bg text-warning',
  danger:  'bg-danger-bg text-danger',
  info:    'bg-info-bg text-info',
  navy:    'bg-brand-navy-light text-brand-navy',
  gold:    'bg-brand-gold-light text-brand-gold-ink',
  muted:   'bg-surface-2 text-ink-muted',
}

export function Badge({ variant = 'navy', className, children }) {
  return (
    <span className={cn(
      'inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full',
      'text-xs font-semibold font-sans whitespace-nowrap',
      VARIANTS[variant] ?? VARIANTS.navy,
      className,
    )}>
      {children}
    </span>
  )
}
