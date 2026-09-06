'use client'
import { Search, Bell, Globe, Menu } from 'lucide-react'
import { useLang }    from '@/context/LanguageContext'
import { useSidebar } from '@/context/SidebarContext'

export function TopBar() {
  const { t, locale, toggleLanguage } = useLang()
  const { toggleMobile } = useSidebar()
  const isRtl = t.dir === 'rtl'

  return (
    <header className="topbar" role="banner">

      {/* Hamburger — mobile only */}
      <button
        className="topbar-hamburger items-center justify-center"
        onClick={toggleMobile}
        aria-label={t.common.openMenu}
        style={{ width: 38, height: 38, borderRadius: 10, color: 'var(--color-ink-muted)', border: 'none', background: 'transparent', cursor: 'pointer', display: 'none', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}
      >
        <Menu size={22} aria-hidden="true" />
      </button>

      {/* User */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0 }}>
        <div style={{ width: 38, height: 38, borderRadius: '50%', background: 'var(--color-brand-navy)', color: 'var(--color-white)', fontSize: 14, fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'var(--font-family-base)', boxShadow: '0 2px 8px rgba(0,35,102,.2)' }} aria-hidden="true">
          {t.common.userInitial}
        </div>
        <div className="hidden sm:block" style={{ lineHeight: 1.3 }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--color-ink)', fontFamily: 'var(--font-family-base)' }}>{t.common.userName}</div>
          <div style={{ fontSize: 12, color: 'var(--color-ink-faint)', fontFamily: 'var(--font-family-base)' }}>{t.common.userRole}</div>
        </div>
      </div>

      {/* Separator */}
      <div className="hidden sm:block" style={{ width: 1, height: 28, background: 'var(--color-border)', flexShrink: 0 }} aria-hidden="true" />

      {/* Search */}
      <div className="topbar-search" role="search" style={{ flex: 1, position: 'relative', maxWidth: 420 }}>
        <Search size={15} style={{ position: 'absolute', insetInlineEnd: 14, top: '50%', transform: 'translateY(-50%)', color: 'var(--color-ink-faint)', pointerEvents: 'none' }} aria-hidden="true" />
        <input
          type="search"
          placeholder={t.searchPh}
          aria-label={t.searchPh}
          style={{
            width: '100%', border: '1.5px solid var(--color-border)', borderRadius: 12,
            padding: '10px 44px 10px 16px',
            fontSize: 13, color: 'var(--color-ink)', background: 'var(--color-surface)',
            fontFamily: 'var(--font-family-base)', outline: 'none',
          }}
          className="placeholder:text-ink-placeholder focus:border-brand-navy focus:bg-white focus:ring-2 focus:ring-brand-navy/10 transition-all"
        />
      </div>

      <div style={{ flex: 1 }} aria-hidden="true" />

      {/* Language */}
      <button
        onClick={toggleLanguage}
        aria-label={locale === 'ar' ? t.common.switchToEnglish : t.common.switchToArabic}
        style={{ display: 'flex', alignItems: 'center', gap: 6, border: '1.5px solid var(--color-border)', borderRadius: 10, padding: '8px 14px', fontSize: 13, fontWeight: 600, color: 'var(--color-ink-muted)', background: 'var(--color-white)', cursor: 'pointer', fontFamily: 'var(--font-family-base)', flexShrink: 0, transition: 'all 150ms' }}
        onMouseEnter={e => e.currentTarget.style.background = 'var(--color-surface)'}
        onMouseLeave={e => e.currentTarget.style.background = 'var(--color-white)'}
      >
        <Globe size={14} aria-hidden="true" />
        {locale === 'ar' ? 'EN' : 'ع'}
      </button>

      {/* Notifications */}
      <button
        aria-label={t.common.notifications}
        style={{ position: 'relative', width: 38, height: 38, display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 10, color: 'var(--color-ink-muted)', background: 'transparent', border: 'none', cursor: 'pointer', flexShrink: 0, transition: 'all 150ms' }}
        onMouseEnter={e => e.currentTarget.style.background = 'var(--color-surface)'}
        onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
      >
        <Bell size={19} aria-hidden="true" />
        <span style={{ position: 'absolute', top: 7, insetInlineEnd: 7, width: 8, height: 8, borderRadius: '50%', background: 'var(--color-brand-gold)', border: '2px solid var(--color-white)' }} aria-hidden="true" />
      </button>

    </header>
  )
}