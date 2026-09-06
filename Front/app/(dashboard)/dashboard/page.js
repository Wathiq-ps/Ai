'use client'

import {
  Home, AlertTriangle, CheckCircle2, Users,
  AlertCircle, Sparkles, DollarSign, Activity,
} from 'lucide-react'

import { StatCard }          from '@/components/dashboard/StatCard'
import { VerifyRequests }    from '@/components/dashboard/sections/VerifyRequests'
import { ContractPipeline }  from '@/components/dashboard/sections/ContractPipeline'
import { UserGrowthChart }   from '@/components/dashboard/sections/UserGrowthChart'
import { RevenueTrendChart } from '@/components/dashboard/sections/RevenueTrendChart'
import { AiMonitor }         from '@/components/dashboard/sections/AiMonitor'
import { ContractDonut }     from '@/components/dashboard/sections/ContractDonut'
import { PaymentsList }      from '@/components/dashboard/sections/PaymentsList'
import { SystemAlerts }      from '@/components/dashboard/sections/SystemAlerts'
import { AuditLog }          from '@/components/dashboard/sections/AuditLog'
import { UsersTable }        from '@/components/dashboard/sections/UsersTable'
import { RiskContracts }     from '@/components/dashboard/sections/RiskContracts'

import { useLang }           from '@/context/LanguageContext'
import { formatCurrency }    from '@/lib/utils'
import { DEFAULT_CURRENCY }  from '@/config/currencies'

import {
  STATS_ROW1, STATS_ROW2, PIPELINE_COUNTS,
  getVerifyRequests, PAYMENTS, SYSTEM_ALERTS,
  AUDIT_LOGS, USERS_LIST, RISK_CONTRACTS, AI_STATS,
  makeLineData, makeBarData,
} from '@/features/dashboard/data/dashboardMock'

const ICON_MAP = {
  Home, AlertTriangle, CheckCircle2, Users,
  AlertCircle, Sparkles, DollarSign, Activity,
}

const DONUT_COLORS = ['var(--color-brand-navy)', 'var(--color-brand-periwinkle)', 'var(--color-border-strong)', 'var(--color-brand-gold)']

export default function DashboardPage() {
  const { t, locale } = useLang()
  const isRtl = t.dir === 'rtl'

  const payments = PAYMENTS.map(p => ({
    ...p,
    ref:    p.type === 'fee' ? t.paymentFee : p.type === 'sub' ? t.paymentSub : t.paymentFail,
    amount: p.ok ? formatCurrency(p.amount, p.currency, locale) : '—',
    time:   isRtl ? p.timeAr : p.timeEn,
  }))

  const alerts = SYSTEM_ALERTS.map(a => ({
    ...a, text: t[a.key], time: isRtl ? a.timeAr : a.timeEn,
  }))

  const auditLogs = AUDIT_LOGS.map(a => ({
    ...a, user: isRtl ? a.userAr : a.userEn, action: t[a.actionKey], time: isRtl ? a.timeAr : a.timeEn,
  }))

  const users = USERS_LIST.map(u => ({
    ...u, init: isRtl ? u.init : u.initEn, name: isRtl ? u.nameAr : u.nameEn,
    role: t[u.roleKey], label: t[u.statusKey], last: isRtl ? u.lastAr : u.lastEn,
  }))

  const risks = RISK_CONTRACTS.map(c => ({
    ...c, lawyer: isRtl ? c.lawyerAr : c.lawyerEn, label: t[c.statusKey],
  }))

  const donut = [
    { name: t.donutActive,  value: 42, color: DONUT_COLORS[0] },
    { name: t.donutLegal,   value: 18, color: DONUT_COLORS[1] },
    { name: t.donutPending, value: 14, color: DONUT_COLORS[2] },
    { name: t.donutDone,    value: 26, color: DONUT_COLORS[3] },
  ]

  const aiStats = AI_STATS.map(s => ({ value: s.value, label: t[s.key] }))

  return (
    <div className="flex flex-col gap-7">

      {/* ── Welcome bar ── */}
      <div className={`flex items-center justify-between flex-wrap gap-3 ${isRtl ? 'flex-row' : 'flex-row-reverse'}`}>
        <div className={isRtl ? 'text-right' : 'text-left'}>
          <h1 className="text-[22px] font-bold text-ink font-sans leading-tight">
            {t.welcomeUser}
          </h1>
          <p className="text-[13.5px] text-ink-faint mt-1 font-sans">
            {t.welcomeDate}
          </p>
        </div>
      </div>

      {/* ── Stats row 1 ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {STATS_ROW1.map(s => (
          <StatCard
            key={s.key}
            title={t[s.key]}
            value={s.value}
            change={s.change}
            icon={ICON_MAP[s.iconKey]}
            iconBg={s.iconBg}
            locale={locale}
          />
        ))}
      </div>

      {/* ── Stats row 2 ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {STATS_ROW2.map(s => (
          <StatCard
            key={s.key}
            title={t[s.key]}
            value={s.value}
            change={s.change}
            icon={ICON_MAP[s.iconKey]}
            iconBg={s.iconBg}
            isCurrency={!!s.isCurrency}
            currency={DEFAULT_CURRENCY.code}
            locale={locale}
          />
        ))}
      </div>

      {/* ── Priority banner ── */}
      <div className={`flex items-center justify-between flex-wrap gap-5 bg-brand-navy rounded-2xl px-7 py-5 text-white shadow-lg ${isRtl ? 'flex-row' : 'flex-row-reverse'}`}>
        <div className={`flex gap-8 flex-wrap ${isRtl ? '' : 'flex-row-reverse'}`}>
          {[
            { val: '2.4h', label: t.avgReviewTime },
            { val: '6',    label: t.highPriority },
            { val: '47',   label: t.totalPending },
          ].map((s, i) => (
            <div key={i} className={isRtl ? 'text-right' : 'text-left'}>
              <div className="text-[28px] font-bold font-sans leading-none">{s.val}</div>
              <div className="text-[12px] text-white/60 mt-1.5 font-sans">{s.label}</div>
            </div>
          ))}
        </div>
        <div className={isRtl ? 'text-right' : 'text-left'}>
          <div className="text-[16px] font-bold font-sans">{t.priorityCenter}</div>
          <div className="text-[12.5px] text-white/60 mt-1 font-sans">{t.prioritySub}</div>
        </div>
      </div>

      <VerifyRequests requests={getVerifyRequests()} t={t} isRtl={isRtl} />
      <ContractPipeline labels={t.pipeline ?? []} counts={PIPELINE_COUNTS} t={t} isRtl={isRtl} />

      {/* ── Charts row ── */}
      <div className="grid grid-cols-1 lg:grid-cols-[2fr_1fr] gap-4">
        <UserGrowthChart   data={makeLineData(t)} t={t} isRtl={isRtl} />
        <RevenueTrendChart data={makeBarData(t)}  t={t} isRtl={isRtl} locale={locale} />
      </div>

      {/* ── AI Monitor + Donut ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <AiMonitor stats={aiStats} kbHealth={96} t={t} isRtl={isRtl} />
        <ContractDonut data={donut} t={t} isRtl={isRtl} />
      </div>

      {/* ── 3-col widgets ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <PaymentsList payments={payments} t={t} isRtl={isRtl} />
        <SystemAlerts alerts={alerts}    t={t} isRtl={isRtl} />
        <AuditLog     logs={auditLogs}   t={t} isRtl={isRtl} />
      </div>

      <UsersTable    users={users}     t={t} isRtl={isRtl} />
      <RiskContracts contracts={risks} t={t} isRtl={isRtl} />
    </div>
  )
}
