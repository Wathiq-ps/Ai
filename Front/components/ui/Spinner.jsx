import { cn } from '@/lib/utils'

export function Spinner({ size = 16, className }) {
  return (
    <svg
      width={size} height={size} viewBox="0 0 24 24" fill="none"
      className={cn('animate-spin', className)} aria-hidden="true"
    >
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeOpacity=".25" />
      <path d="M4 12a8 8 0 018-8" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  )
}
