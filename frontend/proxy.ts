import { NextResponse, type NextRequest } from 'next/server'
import {
  isBasicAuthAuthorized,
  shouldEnforceBasicAuth,
  shouldUseWwwAuthenticateChallenge,
} from '@/lib/site-basic-auth'

function unauthorized(request: NextRequest): NextResponse {
  const headers: Record<string, string> = { 'Cache-Control': 'no-store' }
  if (
    shouldUseWwwAuthenticateChallenge({
      pathname: request.nextUrl.pathname,
      secFetchDest: request.headers.get('sec-fetch-dest'),
      accept: request.headers.get('accept'),
    })
  ) {
    headers['WWW-Authenticate'] = 'Basic realm="Weekly Sales Report", charset="UTF-8"'
    return new NextResponse('Authentication required', { status: 401, headers })
  }
  // fetch() + WWW-Authenticate is often TypeError: Failed to fetch, not a 401 body.
  return NextResponse.json({ detail: 'Authentication required' }, { status: 401, headers })
}

export function proxy(request: NextRequest) {
  // Applies even when NEXT_PUBLIC_DISABLE_SUPABASE=true (that flag only
  // skips Supabase week-data login, not this gate).
  if (!shouldEnforceBasicAuth()) {
    return NextResponse.next()
  }

  if (isBasicAuthAuthorized(request.headers.get('authorization'))) {
    return NextResponse.next()
  }

  return unauthorized(request)
}

export const config = {
  matcher: [
    // Gate pages and /api (including proxied FastAPI). Skip static assets.
    '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)',
  ],
}
