'use client'

import Link from 'next/link'
import { ChevronLeft } from 'lucide-react'

import { useLang } from '@/context/LanguageContext'
import { getVerificationConfig } from '@/features/verification/config/verification.config'

export function VerificationBreadcrumbs({ type }) {
  const { t } = useLang()
  const config = type ? getVerificationConfig(type) : null

  return (
    <nav
      aria-label={t.verificationCenter.breadcrumb}
      className="flex items-center gap-2 text-[12px] text-ink-faint"
    >
      <Link
        href="/dashboard"
        className="transition-colors hover:text-brand-navy"
      >
        {t.home}
      </Link>

      <ChevronLeft size={14} aria-hidden="true" />

      <Link
        href="/dashboard/verification"
        className="transition-colors hover:text-brand-navy"
      >
        {t.verificationCenter.title}
      </Link>

      {config && (
        <>
          <ChevronLeft size={14} aria-hidden="true" />

          <span className="text-ink-muted">
            {t[config.labelKey]}
          </span>
        </>
      )}
    </nav>
  )
}