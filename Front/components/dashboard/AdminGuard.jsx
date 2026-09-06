'use client'
import { useAdminGuard } from '@/features/auth/hooks/useAdminGuard'
export function AdminGuard({ children }) {
  const checking = useAdminGuard()
  if (checking) return <div style={{ minHeight: '40vh' }} aria-busy="true" />
  return children
}
