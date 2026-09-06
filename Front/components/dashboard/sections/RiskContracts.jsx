'use client'
import { Badge }   from '@/components/ui/Badge'
import { Button }  from '@/components/ui/Button'
import { Card }    from '@/components/ui/Card'
import { cn }      from '@/lib/utils'

/* Static Tailwind classes — must be complete strings for the scanner */
const RISK_CLS = {
  high:   'bg-danger-bg  text-danger',
  medium: 'bg-warning-bg text-warning',
  low:    'bg-success-bg text-success',
}
const riskLevel = r => r >= 7 ? 'high' : r >= 4 ? 'medium' : 'low'

export function RiskContracts({ contracts, t, isRtl }) {
  return (
    <Card>
      <div className={cn('flex justify-between items-start mb-5 flex-wrap gap-2', isRtl ? 'flex-row' : 'flex-row-reverse')}>
        <Button variant="ghost" size="sm">{t.viewAll} →</Button>
        <div className={isRtl ? 'text-right' : 'text-left'}>
          <h3 className="text-[16px] font-bold text-ink leading-tight">{t.riskTitle}</h3>
          <p className="text-[12.5px] text-ink-faint mt-1">{t.riskSub}</p>
        </div>
      </div>

      <div className="overflow-x-auto">
        <div className="min-w-[380px]">
          <div className="grid grid-cols-[1fr_1fr_1fr_64px] gap-3 px-4 py-2.5 bg-surface rounded-xl mb-1">
            {[t.colContract, t.colStatus, t.colLawyer, t.colRisk].map(h => (
              <div key={h} className={cn('text-xs font-bold text-ink-faint', isRtl ? 'text-right' : 'text-left')}>{h}</div>
            ))}
          </div>
          {contracts.map((c, i) => (
            <div key={i} className="grid grid-cols-[1fr_1fr_1fr_64px] gap-3 px-4 py-3.5 border-b border-surface last:border-0 items-center hover:bg-surface transition-colors rounded-lg">
              <div className={cn('text-[13px] font-semibold text-ink', isRtl ? 'text-right' : 'text-left')}>#{c.ref}</div>
              <div className={isRtl ? 'text-right' : 'text-left'}><Badge variant={c.statusVariant}>{c.label}</Badge></div>
              <div className={cn('text-[13px] text-ink-muted', isRtl ? 'text-right' : 'text-left')}>{c.lawyer}</div>
              <div className="flex justify-center">
                <span className={cn(
                  'inline-flex items-center justify-center w-9 h-9 rounded-xl text-[13px] font-bold',
                  RISK_CLS[riskLevel(c.risk)],
                )}>
                  {c.risk}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </Card>
  )
}
