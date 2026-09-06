'use client'
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts'
import { Card }          from '@/components/ui/Card'
import { SectionHeader } from '@/components/ui/SectionHeader'
import { cn }            from '@/lib/utils'

export function ContractDonut({ data, t, isRtl }) {
  return (
    <Card>
      <SectionHeader title={t.contractDist} isRtl={isRtl} />
      <div className={cn('flex items-center gap-6 flex-wrap', isRtl ? 'flex-row' : 'flex-row-reverse')}>
        <div className="shrink-0 mx-auto sm:mx-0">
          <ResponsiveContainer width={130} height={130}>
            <PieChart>
              <Pie data={data} innerRadius={42} outerRadius={60} paddingAngle={3} dataKey="value" startAngle={90} endAngle={-270}>
                {data.map((d, i) => <Cell key={i} fill={d.color} />)}
              </Pie>
              <Tooltip
                formatter={(v, name) => [`${v}%`, name]}
                contentStyle={{ fontFamily: 'var(--font-family-base)', fontSize: 12, borderRadius: 10, border: '1px solid var(--color-border)' }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <ul className="flex-1 flex flex-col gap-2.5 min-w-[110px] list-none">
          {data.map((d, i) => (
            <li key={i} className={cn('flex items-center gap-2.5', isRtl ? 'justify-end' : 'justify-start')}>
              <span className="w-3 h-3 rounded-sm shrink-0" style={{ background: d.color }} aria-hidden="true" />
              <span className="text-[12.5px] text-ink flex-1 leading-tight">{d.name}</span>
              <span className="text-[12.5px] font-bold text-ink-muted">{d.value}%</span>
            </li>
          ))}
        </ul>
      </div>
    </Card>
  )
}
