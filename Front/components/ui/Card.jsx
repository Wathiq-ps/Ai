import { cn } from '@/lib/utils'

/**
 * Card — shared wrapper for every dashboard section.
 * Replaces the repeated inline style={{ background, border, borderRadius, padding, boxShadow }}
 * that was copy-pasted across all 11 section components.
 */
export function Card({ className, children, navy = false, ...props }) {
  return (
    <div
      className={cn(
        'rounded-[18px] p-7',
        navy
          ? 'bg-brand-navy shadow-sidebar'
          : 'bg-white border border-border shadow-card',
        className,
      )}
      {...props}
    >
      {children}
    </div>
  )
}
