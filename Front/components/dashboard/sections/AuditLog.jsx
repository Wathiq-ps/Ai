'use client'
import { Card }          from '@/components/ui/Card'
import { SectionHeader } from '@/components/ui/SectionHeader'
import { cn }            from '@/lib/utils'

/* Tailwind-safe classes — defined statically so Tailwind can detect them */
const TYPE_CLS = {
  A: 'bg-surface text-brand-navy',
  B: 'bg-surface-2 text-ink-muted',
  X: 'bg-danger-bg text-danger',
}

export function AuditLog({ logs, t, isRtl }) {
  return (
    <Card>
      <SectionHeader title={t.auditTitle} linkLabel={t.viewAll} isRtl={isRtl} />
      <div className="flex flex-col">
        {logs.map((a, i) => (
          <div
            key={i}
            className={cn(
              'flex items-center gap-3 py-3.5',
              i < logs.length - 1 && 'border-b border-border',
              isRtl ? 'flex-row' : 'flex-row-reverse',
            )}
          >
            <div
              className={cn(
                'w-8 h-8 rounded-full shrink-0 flex items-center justify-center text-xs font-bold',
                TYPE_CLS[a.type] ?? TYPE_CLS.B,
              )}
              aria-hidden="true"
            >
              {a.type}
            </div>
            <div className={cn('flex-1 min-w-0', isRtl ? 'text-right' : 'text-left')}>
              <div className="text-[13px] font-semibold text-ink truncate">{a.user}</div>
              <div className="text-xs text-ink-faint truncate mt-0.5">{a.action}</div>
            </div>
            <span className="text-xs text-ink-faint shrink-0">{a.time}</span>
          </div>
        ))}
      </div>
    </Card>
  )
}
