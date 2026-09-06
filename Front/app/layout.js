import './globals.css'

export const metadata = {
  title:       'وثيق - لوحة التحكم',
  description: 'تحكم كامل. رؤية واضحة. إدارة احترافية.',
}

/**
 * Root layout — lang/dir are set dynamically by LanguageProvider inside each route group.
 * We default to Arabic RTL at the html level; the LanguageProvider wraps its children
 * in a <div dir> that overrides the effective direction without full page reloads.
 */
export default function RootLayout({ children }) {
  return (
    <html lang="ar" dir="rtl">
      <body>{children}</body>
    </html>
  )
}
