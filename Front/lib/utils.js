import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'
import { CURRENCIES, DEFAULT_CURRENCY } from '@/config/currencies'

export function cn(...inputs) {
  return twMerge(clsx(inputs))
}

export function formatNumber(n) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return n.toLocaleString('ar-SA')
  return String(n)
}

/**
 * formatCurrency — centralised currency formatter.
 * Uses locale from config/currencies.js when uiLocale is not supplied.
 * @param {number} amount
 * @param {string} currency   ISO 4217, e.g. 'SAR' | 'AED' | 'EGP'
 * @param {string} uiLocale   BCP 47 UI language: 'ar' | 'en' (from LanguageContext)
 */
export function formatCurrency(amount, currency = DEFAULT_CURRENCY.code, uiLocale = 'ar') {
  const config = CURRENCIES[currency] || DEFAULT_CURRENCY
  // For English UI use en-US style (SAR 12,400), for Arabic use the native locale
  const intlLocale = uiLocale === 'en' ? 'en-US' : config.locale
  try {
    return new Intl.NumberFormat(intlLocale, {
      style: 'currency',
      currency: config.code,
      maximumFractionDigits: 0,
    }).format(amount)
  } catch {
    return `${amount.toLocaleString()} ${config.code}`
  }
}