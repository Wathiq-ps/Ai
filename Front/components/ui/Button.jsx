import { cn } from '@/lib/utils'

const VARIANTS = {
  primary:      'bg-brand-navy text-white hover:bg-brand-navy-hover shadow-sm',
  outline:      'border border-border text-ink-muted bg-white hover:bg-surface hover:border-brand-periwinkle',
  ghost:        'text-brand-navy bg-transparent hover:bg-brand-navy-light',
  danger:       'bg-danger text-white hover:bg-danger-hover',
  navy_outline: 'border border-brand-navy text-brand-navy bg-transparent hover:bg-brand-navy-light',
  gold:         'bg-brand-gold text-brand-navy hover:bg-brand-gold-hover font-bold',
}

const SIZES = {
  xs:   'px-3 py-1 text-xs rounded-lg',
  sm:   'px-4 py-2 text-[13px] rounded-xl',
  md:   'px-5 py-2.5 text-sm rounded-xl',
  lg:   'px-6 py-3 text-[15px] rounded-xl',
  full: 'w-full px-5 py-3 text-[15px] rounded-xl',
}

export function Button({ variant = 'primary', size = 'md', className, children, ...props }) {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center gap-2 font-semibold font-sans',
        'cursor-pointer transition-all duration-150 select-none whitespace-nowrap',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-navy/30',
        VARIANTS[variant] ?? VARIANTS.primary,
        SIZES[size] ?? SIZES.md,
        className,
      )}
      {...props}
    >
      {children}
    </button>
  )
}
