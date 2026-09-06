'use client'
import { BarChart, Bar, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { Card }          from '@/components/ui/Card'
import { SectionHeader } from '@/components/ui/SectionHeader'
import { formatCurrency } from '@/lib/utils'
import { DEFAULT_CURRENCY } from '@/config/currencies'

export function RevenueTrendChart({ data, t, isRtl, locale }) {
  return (
    <Card className="min-w-0">
      <SectionHeader title={t.revenueTitle} linkLabel={t.last6Months} isRtl={isRtl} />
      <div style={{ width: '100%', height: 230 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} barSize={16} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-brand-navy-light)" vertical={false} />
            <XAxis dataKey="m" tick={{ fontSize: 11, fill: 'var(--color-ink-faint)', fontFamily: 'var(--font-family-base)' }} tickLine={false} axisLine={false} interval={1} />
            <YAxis       tick={{ fontSize: 11, fill: 'var(--color-ink-faint)', fontFamily: 'var(--font-family-base)' }} tickLine={false} axisLine={false} width={34} />
            <Tooltip
              formatter={v => [formatCurrency(v * 1_000_000, DEFAULT_CURRENCY.code, locale), t.chartRevenue]}
              contentStyle={{ fontFamily: 'var(--font-family-base)', fontSize: 12, borderRadius: 10, border: '1px solid var(--color-border)', boxShadow: 'var(--shadow-chart-tooltip)' }}
            />
            <Bar dataKey="r" name={t.chartRevenue} radius={[5, 5, 0, 0]}>
              {data.map((_, i) => <Cell key={i} fill={i === data.length - 1 ? 'var(--color-brand-gold)' : 'var(--color-brand-periwinkle)'} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  )
}
