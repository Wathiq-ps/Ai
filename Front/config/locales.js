/**
 * Locale configuration for date/number formatting per country.
 */
export const DATE_FORMATS = {
  'ar-SA': { calendar: 'islamic', style: 'long' },
  'ar-AE': { calendar: 'gregory', style: 'long' },
  'ar-EG': { calendar: 'gregory', style: 'long' },
  default:  { calendar: 'gregory', style: 'long' },
}

function normalizeLocale(locale = 'ar') {
  return locale === 'ar' ? 'ar' : 'en'
}

export function formatDate(date, locale = 'ar-SA') {
  return new Intl.DateTimeFormat(locale, { dateStyle: 'medium' }).format(
    date instanceof Date ? date : new Date(date),
  )
}

export function formatDateTime(date, locale = 'ar') {
  return new Intl.DateTimeFormat(normalizeLocale(locale), {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date instanceof Date ? date : new Date(date))
}