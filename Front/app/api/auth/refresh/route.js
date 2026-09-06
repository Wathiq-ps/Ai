import { NextResponse } from 'next/server'
import { cookies } from 'next/headers'
import { API_BASE_URL, apiPath, authCookieOptions } from '@/lib/api/server'
import { ACCESS_COOKIE, REFRESH_COOKIE } from '@/lib/auth/constants'

export async function POST() {
  if (!API_BASE_URL) return NextResponse.json({ message: 'Authentication API is not configured.' }, { status: 503 })
  const refresh = (await cookies()).get(REFRESH_COOKIE)?.value
  if (!refresh) return NextResponse.json({ message: 'No refresh session.' }, { status: 401 })
  try {
    const response = await fetch(`${API_BASE_URL}${apiPath('WATHIQ_AUTH_REFRESH_PATH', '/api/v1/auth/refresh')}`, { method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'application/json' }, body: JSON.stringify({ refresh_token: refresh }), cache: 'no-store' })
    const data = await response.json().catch(() => ({}))
    if (!response.ok) return NextResponse.json(data, { status: response.status })
    const access = data.access_token || data.accessToken
    const nextRefresh = data.refresh_token || data.refreshToken
    if (!access || !nextRefresh) return NextResponse.json({ message: 'Refresh succeeded but tokens were not returned.' }, { status: 502 })
    const result = NextResponse.json({ authenticated: true })
    result.cookies.set(ACCESS_COOKIE, access, authCookieOptions(Number(data.expires_in) || 900))
    result.cookies.set(REFRESH_COOKIE, nextRefresh, authCookieOptions(60 * 60 * 24 * 30))
    return result
  } catch { return NextResponse.json({ message: 'Unable to connect to the authentication service.' }, { status: 502 }) }
}
