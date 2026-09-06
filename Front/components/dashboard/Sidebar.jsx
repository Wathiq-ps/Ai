'use client'
import { logout } from '@/features/auth/services/authService'
import Link            from 'next/link'
import { useSidebar }  from '@/context/SidebarContext'
import { useLang }     from '@/context/LanguageContext'
import { usePathname } from 'next/navigation'
import { WathiqLogo }  from '@/components/ui/WathiqLogo'
import { cn }          from '@/lib/utils'
import { getTotalVerificationCount } from '@/features/verification/config/verification.config'

/* ── Nav groups matching the reference image ── */
const NAV_GROUPS = [
  {
    groupKey: null,
    items: [{ key: 'home', href: '/dashboard', icon: 'dashboard' }],
  },
  {
    groupKey: 'verification',
    items: [{ key: 'verifyCenter', href: '/dashboard/verification', icon: 'shield', badge: getTotalVerificationCount() }],
  },
  {
    groupKey: 'management',
    items: [
      { key: 'users',      href: '/dashboard/users',      icon: 'users'     },
      { key: 'properties', href: '/dashboard/properties', icon: 'building'  },
      { key: 'contracts',  href: '/dashboard/contracts',  icon: 'contracts' },
      { key: 'lawyers',    href: '/dashboard/lawyers',    icon: 'gavel'     },
      { key: 'financial',  href: '/dashboard/financial',  icon: 'financial' },
    ],
  },
  {
    groupKey: 'knowledge',
    items: [{ key: 'activities', href: '/dashboard/activities', icon: 'clock' }],
  },
  {
    groupKey: 'system',
    items: [{ key: 'settings', href: '/dashboard/settings', icon: 'settings' }],
  },
]

/* ── SVG Icons ── */
function Icon({ type, active }) {
  const c = active ? 'var(--color-white)' : 'var(--color-sidebar-text)'
  const p = { width: 18, height: 18, viewBox: '0 0 24 24', fill: 'none', stroke: c, strokeWidth: 1.8, strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': true, style: { flexShrink: 0 } }
  if (type === 'dashboard') return <svg {...p}><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/></svg>
  if (type === 'shield')    return <svg {...p}><path d="M12 2L3 7v5c0 5.25 3.75 10.15 9 11.25C17.25 22.15 21 17.25 21 12V7z"/><polyline points="9 12 11 14 15 10"/></svg>
  if (type === 'users')     return <svg {...p}><circle cx="9" cy="7" r="4"/><path d="M3 21v-2a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v2"/><path d="M16 3.13a4 4 0 0 1 0 7.75M21 21v-2a4 4 0 0 0-3-3.87"/></svg>
  if (type === 'building')  return <svg {...p}><rect x="2" y="7" width="20" height="14" rx="1.5"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></svg>
  if (type === 'contracts') return <svg {...p}><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
  if (type === 'gavel')     return <svg {...p}><path d="M14.5 9.5l-5-5-7 7 5 5z"/><path d="M9.5 4.5l5 5"/><line x1="14" y1="16" x2="21" y2="22"/></svg>
  if (type === 'financial') return <svg {...p}><rect x="1" y="4" width="22" height="16" rx="2"/><line x1="1" y1="10" x2="23" y2="10"/></svg>
  if (type === 'clock')     return <svg {...p}><circle cx="12" cy="12" r="9"/><polyline points="12 7 12 12 15.5 15.5"/></svg>
  if (type === 'settings')  return <svg {...p}><circle cx="12" cy="12" r="3"/><path d="M12 2v2m0 16v2M4.22 4.22l1.42 1.42m12.72 12.72l1.42 1.42M2 12h2m16 0h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>
  if (type === 'logout')    return <svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="var(--color-sidebar-text)" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden style={{ flexShrink: 0 }}><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
  return null
}

/* ── Nav item (inline styles for guaranteed spacing) ── */
function NavItem({ item, pathname, t, isRtl }) {
  const active = pathname === item.href || (item.href !== '/dashboard' && pathname.startsWith(item.href))

  return (
    <div style={{ position: 'relative', margin: '1px 10px' }}>
      {/* Active bar */}
      {active && (
        <span style={{
          position: 'absolute', top: '50%', transform: 'translateY(-50%)',
          [isRtl ? 'right' : 'left']: 0,
          width: 3, height: 28, borderRadius: 99, background: 'var(--color-brand-gold)',
        }} aria-hidden="true" />
      )}
      <Link
        href={item.href}
        aria-label={t[item.key]}
        style={{
          display: 'flex', alignItems: 'center',
          flexDirection: isRtl ? 'row' : 'row-reverse',
          gap: 10, padding: '9px 14px',
          borderRadius: 12, textDecoration: 'none',
          fontSize: 13.5, fontWeight: active ? 700 : 500,
          fontFamily: 'var(--font-family-base)',
          color: active ? 'var(--color-white)' : 'var(--color-sidebar-text)',
          background: active ? 'var(--color-sidebar-active)' : 'transparent',
          transition: 'all 150ms',
        }}
        onMouseEnter={e => { if (!active) { e.currentTarget.style.background = 'var(--color-sidebar-hover)'; e.currentTarget.style.color = 'var(--color-white)' } }}
        onMouseLeave={e => { if (!active) { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--color-sidebar-text)' } }}
      >
        <Icon type={item.icon} active={active} />
        <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', textAlign: isRtl ? 'right' : 'left' }}>
          {t[item.key]}
        </span>
        {item.badge != null && (
          <span style={{
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            minWidth: 24, height: 24, padding: '0 6px', borderRadius: 99,
            background: 'var(--color-brand-gold)', color: 'var(--color-brand-navy)',
            fontSize: 11, fontWeight: 800, fontFamily: 'var(--font-family-base)', flexShrink: 0,
          }}>
            {item.badge}
          </span>
        )}
      </Link>
    </div>
  )
}

/* ── Main Sidebar ── */
export function Sidebar() {
  const { mobileOpen, closeMobile } = useSidebar()
  const { t }    = useLang()
  const pathname = usePathname()
  const isRtl    = t.dir === 'rtl'

  return (
    <>
      {/* Overlay */}
      <div
        className={cn('sidebar-backdrop', mobileOpen && 'visible')}
        onClick={closeMobile}
        aria-hidden="true"
      />

      <aside
        className={cn('sidebar', mobileOpen && 'mobile-open')}
        aria-label={t.common.sidebarNavigation}
      >
        {/* ── Logo ── */}
        <div style={{ height: 76, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '0 20px', borderBottom: '1px solid var(--color-sidebar-border)', flexShrink: 0 }}>
          <span className="logo-full">
            <WathiqLogo variant="full" size="md" />
          </span>
          <span className="logo-icon" style={{ display: 'none' }}>
            <WathiqLogo variant="icon" size="md" />
          </span>
        </div>

        {/* ── Nav ── */}
        <nav
          style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden', padding: '8px 0' }}
          aria-label={t.common.navigation}
        >
          {NAV_GROUPS.map((group, gi) => (
            <div key={gi} style={{ marginBottom: 4 }}>
              {/* Group label */}
              {group.groupKey && (
                <div style={{
                  padding: '16px 22px 6px',
                  fontSize: 10.5, fontWeight: 700,
                  letterSpacing: '0.08em',
                  textTransform: 'uppercase',
                  color: 'var(--color-sidebar-muted)',
                  fontFamily: 'var(--font-family-base)',
                  textAlign: isRtl ? 'right' : 'left',
                  userSelect: 'none',
                }}>
                  {t[group.groupKey]}
                </div>
              )}
              {/* Items */}
              {group.items.map(item => (
                <NavItem key={item.key} item={item} pathname={pathname} t={t} isRtl={isRtl} />
              ))}
            </div>
          ))}
        </nav>

        {/* ── Divider ── */}
        <div style={{ height: 1, background: 'var(--color-sidebar-border)', margin: '0 16px' }} />

        {/* ── Logout ── */}
        <div style={{ padding: '10px 10px 16px' }}>
          <button
            type="button"
            aria-label={t.common.signOut}
            onClick={async () => { await logout(); window.location.assign('/login') }}
            style={{
              display: 'flex', alignItems: 'center',
              flexDirection: isRtl ? 'row' : 'row-reverse',
              gap: 10, width: '100%', padding: '9px 14px', borderRadius: 12,
              fontSize: 13.5, fontWeight: 500, color: 'var(--color-sidebar-text)',
              fontFamily: 'var(--font-family-base)',
              background: 'transparent', border: 'none', cursor: 'pointer',
              transition: 'all 150ms',
            }}
            onMouseEnter={e => { e.currentTarget.style.background = 'var(--color-sidebar-hover)'; e.currentTarget.style.color = 'var(--color-white)' }}
            onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--color-sidebar-text)' }}
          >
            <Icon type="logout" active={false} />
            <span>{t.common.signOut}</span>
          </button>
        </div>
      </aside>
    </>
  )
}