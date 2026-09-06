import { NextResponse } from 'next/server'
import { ACCESS_COOKIE, PROTECTED_PREFIXES } from '@/lib/auth/constants'
import { isAuthPreviewEnabled } from '@/lib/auth/preview'

export function proxy(request) {
  const { pathname } = request.nextUrl
  const protectedRoute = PROTECTED_PREFIXES.some(prefix => pathname === prefix || pathname.startsWith(`${prefix}/`))
  if (!protectedRoute) return NextResponse.next()

  // Development-only UI preview. Production always requires an access token.
  if (isAuthPreviewEnabled) return NextResponse.next()

  if (request.cookies.get(ACCESS_COOKIE)?.value) return NextResponse.next()

  const loginUrl = new URL('/login', request.url)
  loginUrl.searchParams.set('next', pathname)
  return NextResponse.redirect(loginUrl)
}

export const config = { matcher: ['/((?!api|_next/static|_next/image|favicon.ico).*)'] }
