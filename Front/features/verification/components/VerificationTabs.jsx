'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'

import { useLang } from '@/context/LanguageContext'
import {
  getVerificationConfig,
  VERIFICATION_ORDER,
} from '@/features/verification/config/verification.config'

export function VerificationTabs() {
  const pathname = usePathname()
  const { t } = useLang()

  return (
    <div
      className="flex items-center gap-2 overflow-x-auto border-b border-border"
      role="tablist"
      aria-label={t.verificationCenter.types}
    >
      {VERIFICATION_ORDER.map((type) => {
        const config = getVerificationConfig(type)
        const active =
          pathname === config.listHref ||
          pathname.startsWith(`${config.listHref}/`)

        return (
          <Link
            key={type}
            href={config.listHref}
            role="tab"
            aria-selected={active}
            className={`shrink-0 border-b-2 px-4 py-3 text-[13px] font-semibold transition-colors ${
              active
                ? 'border-brand-gold text-brand-navy'
                : 'border-transparent text-ink-muted hover:text-brand-navy'
            }`}
          >
            {t[config.labelKey]}

            <span className="ms-1 text-[11px] opacity-70">
              ({config.count})
            </span>
          </Link>
        )
      })}
    </div>
  )
}