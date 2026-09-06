'use client'
import { Card }          from '@/components/ui/Card'
import { SectionHeader } from '@/components/ui/SectionHeader'
import { cn }            from '@/lib/utils'

export function PaymentsList({ payments, t, isRtl }) {
  return (
    <Card>
      <SectionHeader title={t.paymentsTitle} linkLabel={t.viewAll} isRtl={isRtl} />
      <div className="flex flex-col">
        {payments.map((p, i) => (
          <div
            key={i}
            className={cn(
              'flex items-center gap-3 py-3.5',
              i < payments.length - 1 && 'border-b border-border',
              isRtl ? 'flex-row' : 'flex-row-reverse',
            )}
          >
            <div className={cn('flex items-center gap-2 shrink-0', isRtl ? 'flex-row' : 'flex-row-reverse')}>
              <span className={cn(
                'w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold shrink-0',
                p.ok ? 'bg-success-bg text-success' : 'bg-danger-bg text-danger',
              )}>
                {p.ok ? '✓' : '✕'}
              </span>
              <span className="text-sm font-bold text-ink">{p.amount}</span>
            </div>

            <div className={cn('flex-1 min-w-0', isRtl ? 'text-right' : 'text-left')}>
              <div className="text-[13px] font-semibold text-ink truncate">{p.ref}</div>
              <div className="text-xs text-ink-faint mt-0.5">{p.id} · {p.time}</div>
            </div>
          </div>
        ))}
      </div>
    </Card>
  )
}
