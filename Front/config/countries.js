/**
 * Supported countries — extend as the platform grows.
 */
export const COUNTRIES = {
  SA: { code: 'SA', name: 'المملكة العربية السعودية', currency: 'SAR', locale: 'ar-SA', dir: 'rtl' },
  AE: { code: 'AE', name: 'الإمارات العربية المتحدة', currency: 'AED', locale: 'ar-AE', dir: 'rtl' },
  EG: { code: 'EG', name: 'مصر',                      currency: 'EGP', locale: 'ar-EG', dir: 'rtl' },
  JO: { code: 'JO', name: 'الأردن',                   currency: 'JOD', locale: 'ar-JO', dir: 'rtl' },
  MA: { code: 'MA', name: 'المغرب',                   currency: 'MAD', locale: 'ar-MA', dir: 'rtl' },
  KW: { code: 'KW', name: 'الكويت',                   currency: 'KWD', locale: 'ar-KW', dir: 'rtl' },
  QA: { code: 'QA', name: 'قطر',                      currency: 'QAR', locale: 'ar-QA', dir: 'rtl' },
}

export const DEFAULT_COUNTRY = COUNTRIES.SA
