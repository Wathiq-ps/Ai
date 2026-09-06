'use client'

import Link from 'next/link'
import { ArrowUpRight, Search, SlidersHorizontal } from 'lucide-react'

import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { useLang } from '@/context/LanguageContext'
import {
  getVerificationColumns,
  getVerificationConfig,
} from '@/features/verification/config/verification.config'
import { verificationRequests } from '@/features/verification/data/verificationMock'
import { renderVerificationCell } from '@/features/verification/utils/verification.formatters'

import { VerificationBreadcrumbs } from './VerificationBreadcrumbs'
import { VerificationTabs } from './VerificationTabs'

export function VerificationList({ type }) {
  const { locale, t } = useLang()
  const config = getVerificationConfig(type)
  const requests = [...(verificationRequests[config.key] ?? [])].sort(
    (a, b) => new Date(a.submittedAt) - new Date(b.submittedAt),
  )
  const activeColumns = getVerificationColumns(config.key)
  const context = { locale, t, requests }

  return (
    <div className="flex flex-col gap-5">
      <VerificationBreadcrumbs type={type} />

      <div>
        <h1 className="text-[26px] font-bold text-ink">
          {t.verificationCenter.title}
        </h1>
        <p className="mt-1.5 text-[13.5px] text-ink-faint">
          {t.verificationCenter.description}
        </p>
      </div>

      <VerificationTabs />

      <Card className="overflow-hidden p-0">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border px-6 py-5">
          <div>
            <h2 className="text-[17px] font-bold text-ink">
              {t[config.labelKey]}
            </h2>
            <p className="mt-1 text-[12px] text-ink-faint">
              {config.count} {t.verificationCenter.pendingRequests}
            </p>
          </div>

          <div className="flex items-center gap-2">
            <label className="relative">
              <Search
                size={15}
                className="absolute inset-inline-end-3 top-1/2 -translate-y-1/2 text-ink-faint"
                aria-hidden="true"
              />
              <input
                className="w-52 rounded-xl border border-border bg-surface py-2.5 pe-9 ps-3 text-[12px] outline-none focus:border-brand-navy"
                placeholder={t.verificationCenter.searchPlaceholder}
                aria-label={t.verificationCenter.searchPlaceholder}
              />
            </label>

            <Button variant="outline" size="sm">
              <SlidersHorizontal size={15} />
              {t.verificationCenter.filter}
            </Button>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px]">
            <thead className="bg-surface">
              <tr>
                {activeColumns.map((column) => (
                  <th
                    key={column}
                    className="px-5 py-3 text-start text-[11px] text-ink-faint"
                  >
                    {t.verificationCenter.columns[config.key][column]}
                  </th>
                ))}
                <th aria-label={t.verificationCenter.viewDetails} />
              </tr>
            </thead>

            <tbody>
              {requests.map((request) => (
                <tr
                  key={request.id}
                  className="border-t border-border transition-colors hover:bg-surface/60"
                >
                  {activeColumns.map((column) => (
                    <td
                      key={column}
                      className="px-5 py-4 text-[12px] text-ink-muted"
                    >
                      {renderVerificationCell(config.key, column, request, context)}
                    </td>
                  ))}
                  <td className="px-5 py-4 text-end">
                    <Link
                      href={`${config.listHref}/${request.id}`}
                      className="inline-flex items-center gap-1 text-[12px] font-semibold text-brand-navy hover:underline"
                    >
                      {t.verificationCenter.viewDetails}
                      <ArrowUpRight size={14} />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}