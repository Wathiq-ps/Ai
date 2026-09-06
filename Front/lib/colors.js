/**
 * WATHIQ — Design Token bridge for JavaScript-only libraries.
 *
 * The canonical values live in app/globals.css (@theme).
 * Use these CSS custom-property references when a library (e.g. Recharts)
 * requires a color value from JavaScript. Do not add raw brand hex values here.
 */
export const colors = Object.freeze({
  navy: 'var(--color-brand-navy)',
  navyHover: 'var(--color-brand-navy-hover)',
  navyDark: 'var(--color-brand-navy-dark)',
  navyLight: 'var(--color-brand-navy-light)',
  periwinkle: 'var(--color-brand-periwinkle)',
  gold: 'var(--color-brand-gold)',
  goldHover: 'var(--color-brand-gold-hover)',
  goldLight: 'var(--color-brand-gold-light)',
  white: 'var(--color-white)',
  pageBg: 'var(--color-page-bg)',
  cardBg: 'var(--color-card-bg)',
  border: 'var(--color-border)',
  borderStrong: 'var(--color-border-strong)',
  textPrimary: 'var(--color-ink)',
  textSecond: 'var(--color-ink-muted)',
  textMuted: 'var(--color-ink-faint)',
  textSubtle: 'var(--color-ink-subtle)',
  placeholder: 'var(--color-ink-placeholder)',
  success: 'var(--color-success)',
  successBg: 'var(--color-success-bg)',
  warning: 'var(--color-warning)',
  warningBg: 'var(--color-warning-bg)',
  danger: 'var(--color-danger)',
  dangerBg: 'var(--color-danger-bg)',
  info: 'var(--color-info)',
  infoBg: 'var(--color-info-bg)',
  sidebarText: 'var(--color-sidebar-text)',
})
