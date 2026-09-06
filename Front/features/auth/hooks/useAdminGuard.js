'use client'
import { useEffect, useState } from 'react'
import { usePathname, useRouter } from 'next/navigation'
import { getSession } from '@/features/auth/services/authService'

function isAdminUser(user) {
  const role = String(user?.role || user?.user_role || '').toLowerCase()
  const roles = Array.isArray(user?.roles) ? user.roles.map(value => String(value?.name || value).toLowerCase()) : []
  const permissions = Array.isArray(user?.permissions) ? user.permissions.map(value => String(value?.name || value).toLowerCase()) : []
  return role === 'admin' || roles.includes('admin') || roles.includes('administrator') || permissions.includes('*') || permissions.some(value => value === 'admin' || value.startsWith('admin.'))
}

export function useAdminGuard() {
  const router = useRouter(); const pathname = usePathname(); const [checking, setChecking] = useState(true)
  useEffect(() => {
    let active = true
    getSession().then(session => {
      if (!active) return
      const user = session?.user || session?.data?.user || session?.data || null
      if (!user || !isAdminUser(user)) router.replace(`/login?next=${encodeURIComponent(pathname)}`)
      else setChecking(false)
    }).catch(() => router.replace(`/login?next=${encodeURIComponent(pathname)}`))
    return () => { active = false }
  }, [router, pathname])
  return checking
}
