/**
 * Supported currencies — add new ones here without touching UI components.
 * All currency formatting goes through lib/utils.js formatCurrency().
 */
export const CURRENCIES = {
  SAR: { code: 'SAR', locale: 'ar-SA', name: 'ريال سعودي'  },
  AED: { code: 'AED', locale: 'ar-AE', name: 'درهم إماراتي' },
  EGP: { code: 'EGP', locale: 'ar-EG', name: 'جنيه مصري'   },
  JOD: { code: 'JOD', locale: 'ar-JO', name: 'دينار أردني'  },
  ILS: { code: 'ILS', locale: 'ar',    name: 'شيقل'          },
  MAD: { code: 'MAD', locale: 'ar-MA', name: 'درهم مغربي'   },
  TND: { code: 'TND', locale: 'ar-TN', name: 'دينار تونسي'  },
  DZD: { code: 'DZD', locale: 'ar-DZ', name: 'دينار جزائري' },
  KWD: { code: 'KWD', locale: 'ar-KW', name: 'دينار كويتي'  },
  QAR: { code: 'QAR', locale: 'ar-QA', name: 'ريال قطري'    },
  BHD: { code: 'BHD', locale: 'ar-BH', name: 'دينار بحريني' },
  OMR: { code: 'OMR', locale: 'ar-OM', name: 'ريال عماني'   },
}

/** Default for mock data — change here only */
export const DEFAULT_CURRENCY = CURRENCIES.SAR
