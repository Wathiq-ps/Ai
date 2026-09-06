'use client'
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { Card }          from '@/components/ui/Card'
import { SectionHeader } from '@/components/ui/SectionHeader'

export function UserGrowthChart({ data, t, isRtl }) {
  return (
    <Card className="min-w-0">
      <SectionHeader title={t.userGrowth} linkLabel={t.last12Months} isRtl={isRtl} />
      <div style={{ width: '100%', height: 230 }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="gradNavy" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor="var(--color-brand-navy)" stopOpacity={0.20} />
                <stop offset="95%" stopColor="var(--color-brand-navy)" stopOpacity={0}    />
              </linearGradient>
              <linearGradient id="gradGold" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor="var(--color-brand-gold)" stopOpacity={0.38} />
                <stop offset="95%" stopColor="var(--color-brand-gold)" stopOpacity={0}    />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-brand-navy-light)" vertical={false} />
            <XAxis dataKey="m" tick={{ fontSize: 11, fill: 'var(--color-ink-faint)', fontFamily: 'var(--font-family-base)' }} tickLine={false} axisLine={false} interval={1} />
            <YAxis       tick={{ fontSize: 11, fill: 'var(--color-ink-faint)', fontFamily: 'var(--font-family-base)' }} tickLine={false} axisLine={false} width={42} />
            <Tooltip contentStyle={{ fontFamily: 'var(--font-family-base)', fontSize: 12, borderRadius: 10, border: '1px solid var(--color-border)', boxShadow: 'var(--shadow-chart-tooltip)' }} />
            <Legend wrapperStyle={{ fontSize: 12, fontFamily: 'var(--font-family-base)', paddingTop: 12 }} />
            <Area type="monotone" dataKey="verified" name={t.chartVerified} stroke="var(--color-brand-navy)" strokeWidth={2.5} fill="url(#gradNavy)" dot={false} activeDot={{ r: 5, fill: 'var(--color-brand-navy)', strokeWidth: 2, stroke: 'var(--color-white)' }} />
            <Area type="monotone" dataKey="newU"     name={t.chartNew}      stroke="var(--color-brand-gold)" strokeWidth={2.5} fill="url(#gradGold)" dot={false} activeDot={{ r: 5, fill: 'var(--color-brand-gold)', strokeWidth: 2, stroke: 'var(--color-white)' }} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </Card>
  )
}
