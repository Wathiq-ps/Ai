import { cn } from '@/lib/utils'

/**
 * SectionHeader — reusable card header used in every section.
 * RTL/LTR aware.
 */
export function SectionHeader({ title, linkLabel, onLink, isRtl, className }) {
  return (
    <div className={cn(
      'flex items-center justify-between mb-5',
      isRtl ? 'flex-row' : 'flex-row-reverse',
      className,
    )}>
      {linkLabel && (
        <button
          onClick={onLink}
          className="text-sm font-semibold text-brand-navy bg-transparent border-none cursor-pointer hover:underline transition-all shrink-0"
        >
          {linkLabel}
        </button>
      )}
      <h3 className="text-[15.5px] font-bold text-ink m-0 leading-tight">
        {title}
      </h3>
    </div>
  )
}
