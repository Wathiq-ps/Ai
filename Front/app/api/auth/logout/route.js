import { NextResponse } from 'next/server'
import { cookies } from 'next/headers'
import { API_BASE_URL, apiPath, authCookieOptions } from '@/lib/api/server'
import { ACCESS_COOKIE, REFRESH_COOKIE } from '@/lib/auth/constants'
export async function POST() {
  const store = await cookies(); const access = store.get(ACCESS_COOKIE)?.value; const refresh = store.get(REFRESH_COOKIE)?.value
  if (API_BASE_URL && (access || refresh)) {
    await fetch(`${API_BASE_URL}${apiPath('WATHIQ_AUTH_LOGOUT_PATH', '/api/v1/auth/logout')}`, { method: 'POST', headers: { Accept: 'application/json', ...(access ? { Authorization: `Bearer ${access}` } : {}), 'Content-Type': 'application/json' }, body: JSON.stringify({ refresh_token: refresh }), cache: 'no-store' }).catch(() => null)
  }
  const response = NextResponse.json({ ok: true })
  response.cookies.set(ACCESS_COOKIE, '', authCookieOptions(0))
  response.cookies.set(REFRESH_COOKIE, '', authCookieOptions(0))
  return response
}
