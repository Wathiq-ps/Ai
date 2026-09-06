import { NextResponse } from 'next/server'
import { backendFetch, apiPath } from '@/lib/api/server'
import { isAuthPreviewEnabled } from '@/lib/auth/preview'

export async function GET() {
  // Never exposed outside a development build. This lets the UI be reviewed
  // before the real Backend is available without creating a fake JWT/session.
  if (isAuthPreviewEnabled) {
    return NextResponse.json({
      user: {
        id: 'preview-admin',
        name: 'WATHIQ Admin Preview',
        email: 'admin.preview@wathiq.local',
        role: 'admin',
      },
      preview: true,
    })
  }

  try {
    const response = await backendFetch(apiPath('WATHIQ_AUTH_ME_PATH', '/api/v1/auth/me'))
    const data = await response.json().catch(() => ({}))
    return NextResponse.json(data, { status: response.status })
  } catch {
    return NextResponse.json({ message: 'Authentication API is not configured.' }, { status: 503 })
  }
}
