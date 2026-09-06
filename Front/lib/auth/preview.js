/**
 * Dashboard preview without backend authentication.
 *
 * Enabled only in local development or Vercel Preview.
 * Never enabled in Vercel Production.
 */

const isVercelPreview =
  process.env.VERCEL_ENV === 'preview'

const isLocalDevelopment =
  process.env.NODE_ENV === 'development'

export const isAuthPreviewEnabled =
  (isLocalDevelopment || isVercelPreview) &&
  process.env.WATHIQ_AUTH_BYPASS === 'true'