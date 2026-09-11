import { NextResponse, type NextRequest } from 'next/server'
import {
  isBasicAuthAuthorized,
  shouldEnforceBasicAuth,
} from '@/lib/site-basic-auth'

function unauthorized(): NextResponse {
  return new NextResponse('Authentication required', {
    status: 401,
    headers: {
      'WWW-Authenticate': 'Basic realm="Weekly Sales Report", charset="UTF-8"',
      'Cache-Control': 'no-store',
    },
  })
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

  return unauthorized()
}

export const config = {
  matcher: [
    // Gate pages and /api (including proxied FastAPI). Skip static assets.
    '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)',
  ],
}
