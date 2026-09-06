'use client'
import { Badge }         from '@/components/ui/Badge'
import { Button }        from '@/components/ui/Button'
import { Card }          from '@/components/ui/Card'
import { SectionHeader } from '@/components/ui/SectionHeader'
import { cn }            from '@/lib/utils'

export function UsersTable({ users, t, isRtl }) {
  return (
    <Card>
      <div className={cn('flex justify-between items-start mb-5 flex-wrap gap-2.5', isRtl ? 'flex-row' : 'flex-row-reverse')}>
        <Button size="sm" className="gap-1.5">+ {t.addUser}</Button>
        <div className={isRtl ? 'text-right' : 'text-left'}>
          <h3 className="text-[16px] font-bold text-ink leading-tight">{t.usersTitle}</h3>
          <p className="text-[12.5px] text-ink-faint mt-1">{t.usersSubtitle}</p>
        </div>
      </div>

      <div className="flex gap-2 mb-4 flex-wrap">
        <input
          placeholder={t.searchUsers} aria-label={t.searchUsers}
          className={cn(
            'flex-1 min-w-[160px] border border-border rounded-xl px-3.5 py-2.5',
            'text-[13px] outline-none bg-surface placeholder:text-ink-faint',
            'focus:border-brand-navy focus:ring-2 focus:ring-brand-navy/10 transition-all',
            isRtl ? 'text-right' : 'text-left',
          )}
        />
        {[`${t.filterStatus}: ${t.filterAll}`, `${t.filterRole}: ${t.filterAll}`, t.advancedFilter].map(f => (
          <Button key={f} variant="outline" size="sm" className="whitespace-nowrap">{f} ▾</Button>
        ))}
      </div>

      {/* Desktop table */}
      <div className="users-table-header grid-cols-[2fr_1fr_1fr_1fr] gap-3 px-4 py-2.5 bg-surface rounded-xl mb-1">
        {[t.colUser, t.colRole, t.colStatus, t.colLastActive].map((h, idx) => (
          <div key={h} className={cn('text-xs font-bold text-ink-faint',
            isRtl ? (idx === 3 ? 'text-left' : 'text-right') : (idx === 3 ? 'text-right' : 'text-left'))}>
            {h}
          </div>
        ))}
      </div>

      {users.map((u, i) => (
        <div key={i} className="users-table-row grid-cols-[2fr_1fr_1fr_1fr] gap-3 px-4 py-3.5 border-b border-surface last:border-0 items-center hover:bg-surface transition-colors rounded-lg">
          <div className={cn('flex items-center gap-3', isRtl ? 'justify-end flex-row-reverse' : 'justify-end flex-row-reverse')}>
            <div className={isRtl ? 'text-right' : 'text-left'}>
              <div className="text-[13.5px] font-semibold text-ink">{u.name}</div>
              <div className="text-xs text-ink-faint">{u.email}</div>
            </div>
            <div className="w-9 h-9 rounded-full bg-surface text-brand-navy text-xs font-bold flex items-center justify-center shrink-0" aria-hidden="true">{u.init}</div>
          </div>
          <div className={cn('text-[13px] text-ink-muted', isRtl ? 'text-right' : 'text-left')}>{u.role}</div>
          <div className={isRtl ? 'text-right' : 'text-left'}><Badge variant={u.statusVariant}>{u.label}</Badge></div>
          <div className={cn('text-xs text-ink-faint', isRtl ? 'text-left' : 'text-right')}>{u.last}</div>
        </div>
      ))}

      {/* Mobile cards */}
      <div className="user-card-view">
        {users.map((u, i) => (
          <div key={i} className={cn('py-3.5', i < users.length - 1 && 'border-b border-surface')}>
            <div className={cn('flex items-center gap-3 mb-2', isRtl ? 'justify-end' : 'justify-start')}>
              <div className={cn('flex-1', isRtl ? 'text-right' : 'text-left')}>
                <div className="text-[13.5px] font-semibold text-ink">{u.name}</div>
                <div className="text-xs text-ink-faint">{u.email}</div>
              </div>
              <div className="w-10 h-10 rounded-full bg-surface text-brand-navy text-xs font-bold flex items-center justify-center shrink-0" aria-hidden="true">{u.init}</div>
            </div>
            <div className={cn('flex items-center gap-2 flex-wrap', isRtl ? 'justify-end' : 'justify-start')}>
              <span className="text-xs text-ink-faint">{u.last}</span>
              <Badge variant={u.statusVariant}>{u.label}</Badge>
              <span className="text-xs text-ink-muted">{u.role}</span>
            </div>
          </div>
        ))}
      </div>
      <div className="text-center pt-4"><Button variant="ghost" size="sm">{t.showAll} →</Button></div>
    </Card>
  )
}
