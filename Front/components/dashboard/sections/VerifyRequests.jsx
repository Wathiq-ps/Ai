'use client'
import { Badge }         from '@/components/ui/Badge'
import { Card }          from '@/components/ui/Card'
import { cn }            from '@/lib/utils'

export function VerifyRequests({ requests, t, isRtl }) {
  return (
    <Card>
      <div className={cn('flex items-center justify-between mb-5 flex-wrap gap-3', isRtl ? 'flex-row' : 'flex-row-reverse')}>
        {/* Pill tabs */}
        <div className={cn('flex gap-1 bg-surface rounded-xl p-1', isRtl ? 'flex-row' : 'flex-row-reverse')}>
          <button className="text-[13px] font-semibold text-ink-faint bg-transparent rounded-lg px-3.5 py-1.5 border-none cursor-pointer hover:text-ink-muted transition-colors">
            {t.verifyTabLawyer} ١٦
          </button>
          <button className="text-[13px] font-bold text-brand-navy bg-white rounded-lg px-3.5 py-1.5 border-none cursor-pointer shadow-sm">
            {t.verifyTabProperty} ١٨
          </button>
        </div>
        <h3 className="text-[16px] font-bold text-ink m-0">{t.verifyTitle}</h3>
      </div>

      <div className="flex flex-col gap-2.5">
        {requests.map((r, i) => (
          <div
            key={i}
            className={cn(
              'flex items-center flex-wrap gap-3 px-4 py-3.5 rounded-xl border',
              r.priority === 'high' ? 'bg-danger-bg border-border-verify' : 'bg-surface border-border',
              isRtl ? 'flex-row' : 'flex-row-reverse',
            )}
          >
            <div className="flex gap-2 shrink-0">
              <button className="text-xs font-bold px-3 py-1.5 rounded-lg border border-danger text-danger bg-transparent cursor-pointer hover:bg-danger-bg transition-colors">
                {t.rejectBtn}
              </button>
              <button className="text-xs font-bold px-3 py-1.5 rounded-lg bg-success-bg border border-border-success text-success cursor-pointer hover:opacity-80 transition-colors">
                {t.approveBtn}
              </button>
            </div>
            <div className={cn('flex-1 min-w-0', isRtl ? 'text-right' : 'text-left')}>
              <div className={cn('flex items-center gap-2 mb-1 flex-wrap', isRtl ? 'justify-end' : 'justify-start')}>
                {r.priority === 'high' && <Badge variant="danger">{t.highPriorityBadge}</Badge>}
                <span className="text-[13.5px] font-bold text-ink">{isRtl ? r.nameAr : r.nameEn}</span>
              </div>
              <span className="text-xs text-ink-faint">{r.id} · {isRtl ? r.typeAr : r.typeEn} · {isRtl ? r.timeAr : r.timeEn}</span>
            </div>
          </div>
        ))}
      </div>

      <div className="text-center mt-4">
        <button className="text-[13px] font-semibold text-brand-navy bg-transparent border-none cursor-pointer hover:underline">
          {t.verifyShowAll} (47) ↓
        </button>
      </div>
    </Card>
  )
}
