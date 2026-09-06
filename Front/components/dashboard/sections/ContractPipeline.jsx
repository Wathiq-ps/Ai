'use client'
import { Card }          from '@/components/ui/Card'
import { SectionHeader } from '@/components/ui/SectionHeader'
import { cn }            from '@/lib/utils'

export function ContractPipeline({ labels, counts, t, isRtl }) {
  return (
    <Card>
      <SectionHeader title={t.contractLife} linkLabel={`${t.viewAllContracts} →`} isRtl={isRtl} />
      <p className={cn('text-[13px] text-ink-faint -mt-2 mb-5', isRtl ? 'text-right' : 'text-left')}>
        {t.contractSub}
      </p>
      <div className="pipeline-scroll">
        <div className="pipeline-row" style={{ gap: 0 }}>
          {labels.map((label, i) => (
            <div key={i} className="pipeline-stage">
              <div className="pipeline-node">
                <div className={`pipeline-circle${i === labels.length - 1 ? ' last' : ''}`}>{i + 1}</div>
                <div className={cn(
                  'text-[10.5px] font-semibold text-center max-w-[76px] leading-tight',
                  i === labels.length - 1 ? 'text-brand-navy' : 'text-ink-faint',
                )}>
                  {label}
                </div>
                <div className={cn(
                  'text-[12px] font-bold',
                  i === labels.length - 1 ? 'text-brand-gold' : 'text-ink-muted',
                )}>
                  {counts[i]}
                </div>
              </div>
              {i < labels.length - 1 && <div className="pipeline-connector" aria-hidden="true" />}
            </div>
          ))}
        </div>
      </div>
    </Card>
  )
}
