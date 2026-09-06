'use client'
import { Card }          from '@/components/ui/Card'
import { SectionHeader } from '@/components/ui/SectionHeader'
import { cn }            from '@/lib/utils'

export function SystemAlerts({ alerts, t, isRtl }) {
  return (
    <Card>
      <SectionHeader title={t.alertsTitle} linkLabel={t.viewAll} isRtl={isRtl} />
      <div className="flex flex-col">
        {alerts.map((a, i) => (
          <div
            key={i}
            className={cn(
              'flex items-start gap-3 py-3.5',
              i < alerts.length - 1 && 'border-b border-border',
              isRtl ? 'flex-row' : 'flex-row-reverse',
            )}
          >
            <span className="text-xs text-ink-faint shrink-0 mt-0.5">{a.time}</span>
            <span className={cn(
              'flex-1 text-[13px] font-semibold text-ink leading-relaxed',
              isRtl ? 'text-right' : 'text-left',
            )}>
              {a.icon} {a.text}
            </span>
          </div>
        ))}
      </div>
    </Card>
  )
}
