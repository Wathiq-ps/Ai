import { cookies } from 'next/headers'
import { ACCESS_COOKIE, REFRESH_COOKIE } from '@/lib/auth/constants'

export const API_BASE_URL = (process.env.WATHIQ_API_BASE_URL || '').replace(/\/$/, '')

export async function backendFetch(path, options = {}) {
  if (!API_BASE_URL) throw new Error('WATHIQ_API_BASE_URL is not configured')
  const cookieStore = await cookies()
  const access = cookieStore.get(ACCESS_COOKIE)?.value
  const headers = { Accept: 'application/json', ...(options.body ? { 'Content-Type': 'application/json' } : {}), ...(options.headers || {}) }
  if (access) headers.Authorization = `Bearer ${access}`
  return fetch(`${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`, { ...options, headers, cache: 'no-store' })
}

export function apiPath(name, fallback) { return process.env[name] || fallback }

export function authCookieOptions(maxAge) {
  return { httpOnly: true, secure: process.env.NODE_ENV === 'production', sameSite: 'lax', path: '/', maxAge }
}
