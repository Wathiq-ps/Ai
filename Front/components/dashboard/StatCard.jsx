import { TrendingUp, TrendingDown } from 'lucide-react'
import { cn }             from '@/lib/utils'
import { formatCurrency } from '@/lib/utils'
import { DEFAULT_CURRENCY } from '@/config/currencies'

export function StatCard({ title, value, change, icon: Icon, iconBg, isCurrency = false, currency = DEFAULT_CURRENCY.code, locale = 'ar' }) {
  const up      = change >= 0
  const display = isCurrency ? formatCurrency(value, currency, locale) : value
  const isRtl   = locale === 'ar'

  return (
    <div className="bg-white border border-border rounded-[18px] p-6 flex flex-col gap-4 shadow-card hover:shadow-md transition-shadow duration-200">
      <div className={cn('flex items-start justify-between', isRtl ? 'flex-row' : 'flex-row-reverse')}>
        {/* Icon */}
        <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0" style={{ background: iconBg ?? 'var(--color-brand-navy-light)' }}>
          <Icon size={18} color="var(--color-brand-navy)" aria-hidden="true" />
        </div>
        {/* Change badge */}
        <span className={cn(
          'inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11.5px] font-bold shrink-0',
          up ? 'bg-success-bg text-success' : 'bg-danger-bg text-danger',
        )}>
          {up ? <TrendingUp size={11} aria-hidden="true" /> : <TrendingDown size={11} aria-hidden="true" />}
          {Math.abs(change)}%
        </span>
      </div>
      <div className={isRtl ? 'text-right' : 'text-left'}>
        <div className="text-[26px] font-bold text-ink leading-none tracking-tight">{display}</div>
        <div className="text-[13px] font-medium text-ink-faint mt-1.5">{title}</div>
      </div>
    </div>
  )
}
