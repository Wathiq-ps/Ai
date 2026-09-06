'use client'
import { Globe, ChevronDown } from 'lucide-react'
import { useLang }    from '@/context/LanguageContext'
import { WathiqLogo } from '@/components/ui/WathiqLogo'

function BrandPanel() {
  const { t, locale, toggleLanguage } = useLang()
  const isRtl = t.dir === 'rtl'

  return (
    <div className="auth-navy-panel">
      {/* Language toggle */}
      <div style={{ display: 'flex', justifyContent: isRtl ? 'flex-start' : 'flex-end', position: 'relative', zIndex: 10 }}>
        <button
          onClick={toggleLanguage}
          style={{
            display: 'flex', alignItems: 'center', gap: 6,
            color: 'rgba(255,255,255,.85)',
            background: 'rgba(255,255,255,.12)',
            border: '1px solid rgba(255,255,255,.2)',
            borderRadius: 99, padding: '8px 16px',
            fontSize: 13, fontWeight: 600, cursor: 'pointer',
            fontFamily: 'Alexandria, sans-serif',
            transition: 'all 150ms',
          }}
          onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,.22)'}
          onMouseLeave={e => e.currentTarget.style.background = 'rgba(255,255,255,.12)'}
          aria-label={locale === 'ar' ? 'Switch to English' : 'التبديل إلى العربية'}
        >
          <Globe size={14} aria-hidden="true" />
          <span>{locale === 'ar' ? 'English' : 'العربية'}</span>
          <ChevronDown size={12} aria-hidden="true" />
        </button>
      </div>

      {/* Center */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 40, textAlign: 'center', position: 'relative', zIndex: 10 }}>
        {/* Logo box */}
        <div style={{
          background: 'rgba(255,255,255,.12)',
          border: '1px solid rgba(255,255,255,.18)',
          borderRadius: 28, padding: '28px 36px',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <WathiqLogo responsive size="lg" />
        </div>

        {/* Brand text */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <h1 style={{ color: 'var(--color-white)', fontSize: 30, fontWeight: 800, lineHeight: 1.2, fontFamily: 'Alexandria, sans-serif', margin: 0 }}>
            {t.dashboardTitle}
          </h1>
          <p style={{ color: 'rgba(255,255,255,.62)', fontSize: 15, lineHeight: 1.7, fontFamily: 'Alexandria, sans-serif', margin: 0, maxWidth: 260, marginInline: 'auto' }}>
            {t.dashboardSub}
          </p>
        </div>
      </div>

      {/* Bottom dot */}
      <div style={{ display: 'flex', justifyContent: 'center', position: 'relative', zIndex: 10 }}>
        <div style={{ width: 10, height: 10, borderRadius: '50%', background: 'var(--color-brand-gold)' }} aria-hidden="true" />
      </div>
    </div>
  )
}

export function AuthLayout({ children }) {
  const { t } = useLang()
  return (
    <div className="auth-root">
      <div className={`auth-card ${t.dir === 'ltr' ? 'ltr' : ''}`}>
        <BrandPanel />
        <div className="auth-form-panel">
          <div className="auth-form-inner">{children}</div>
        </div>
      </div>
    </div>
  )
}
