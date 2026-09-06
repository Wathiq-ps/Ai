'use client'
import { Card } from '@/components/ui/Card'
import { cn }   from '@/lib/utils'

export function AiMonitor({ stats, kbHealth, t, isRtl }) {
  return (
    <Card navy>
      <div className={cn('flex items-center justify-between mb-5', isRtl ? 'flex-row' : 'flex-row-reverse')}>
        <span className="text-2xl" aria-hidden="true">✨</span>
        <div className={isRtl ? 'text-right' : 'text-left'}>
          <div className="text-[15px] font-bold text-white leading-tight">{t.aiMonitorTitle}</div>
          <div className="text-xs text-white/55 mt-0.5">{t.aiMonitorSub}</div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 mb-3">
        {stats.map((s, i) => (
          <div key={i} className={cn('bg-white/10 rounded-xl p-3.5', isRtl ? 'text-right' : 'text-left')}>
            <div className="text-[20px] font-bold text-white leading-none">{s.value}</div>
            <div className="text-xs text-white/55 mt-1">{s.label}</div>
          </div>
        ))}
      </div>

      <div className="bg-white/10 rounded-xl p-3.5">
        <div className={cn('flex justify-between mb-2', isRtl ? 'flex-row' : 'flex-row-reverse')}>
          <span className="text-xs font-bold text-brand-gold">{kbHealth}%</span>
          <span className="text-xs text-white/60">{t.aiKbHealth}</span>
        </div>
        <div className="h-2 bg-white/15 rounded-full overflow-hidden">
          <div className="h-full bg-brand-gold rounded-full transition-all duration-700" style={{ width: `${kbHealth}%` }} aria-hidden="true" />
        </div>
      </div>
    </Card>
  )
}
