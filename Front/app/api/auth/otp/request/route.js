import { NextResponse } from 'next/server'
import { API_BASE_URL, apiPath } from '@/lib/api/server'

export async function POST(request) {
  if (!API_BASE_URL) return NextResponse.json({ message: 'Authentication API is not configured.' }, { status: 503 })
  const body = await request.json().catch(() => null)
  if (!body?.email) return NextResponse.json({ message: 'Email is required.' }, { status: 400 })
  try {
    const response = await fetch(`${API_BASE_URL}${apiPath('WATHIQ_OTP_REQUEST_PATH', '/api/v1/auth/otp/request')}`, { method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'application/json' }, body: JSON.stringify({ email: body.email }), cache: 'no-store' })
    const data = await response.json().catch(() => ({}))
    return NextResponse.json(data, { status: response.status })
  } catch { return NextResponse.json({ message: 'Unable to connect to the authentication service.' }, { status: 502 }) }
}
