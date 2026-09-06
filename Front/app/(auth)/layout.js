'use client'

import { LanguageProvider } from '@/context/LanguageContext'

export default function AuthGroupLayout({ children }) {
  return <LanguageProvider>{children}</LanguageProvider>
}
