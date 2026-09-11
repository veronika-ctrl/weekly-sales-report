/**
 * Shared-password HTTP Basic Auth for the Next.js app (Vercel production/preview).
 * Credentials come from env only — never hardcode a real password.
 */

export const DEFAULT_BASIC_AUTH_USER = 'ohjay'

export function getConfiguredUser(): string {
  const user = (process.env.SITE_BASIC_AUTH_USER || '').trim()
  return user || DEFAULT_BASIC_AUTH_USER
}

export function getConfiguredPassword(): string {
  return (
    process.env.SITE_BASIC_AUTH_PASSWORD ||
    process.env.SITE_PASSWORD ||
    ''
  ).trim()
}

/**
 * Local `next dev` stays open when no password is set.
 * Vercel production is always gated (fail closed) so revenue/spend data
 * is never world-readable if env vars were forgotten.
 * Preview/development on Vercel is gated only when a password is configured.
 */
export function shouldEnforceBasicAuth(): boolean {
  if (getConfiguredPassword()) return true
  return process.env.VERCEL_ENV === 'production'
}

export function timingSafeEqualString(a: string, b: string): boolean {
  const encoder = new TextEncoder()
  const bufA = encoder.encode(a)
  const bufB = encoder.encode(b)
  const len = Math.max(bufA.length, bufB.length)
  let mismatch = bufA.length === bufB.length ? 0 : 1
  for (let i = 0; i < len; i++) {
    mismatch |= (bufA[i] ?? 0) ^ (bufB[i] ?? 0)
  }
  return mismatch === 0
}

export function parseBasicAuthorization(
  header: string | null
): { user: string; password: string } | null {
  if (!header) return null
  const match = header.match(/^Basic\s+(.+)$/i)
  if (!match) return null
  try {
    const decoded = atob(match[1].trim())
    const idx = decoded.indexOf(':')
    if (idx === -1) return null
    return { user: decoded.slice(0, idx), password: decoded.slice(idx + 1) }
  } catch {
    return null
  }
}

export function isBasicAuthAuthorized(header: string | null): boolean {
  const expectedPassword = getConfiguredPassword()
  if (!expectedPassword) return false
  const parsed = parseBasicAuthorization(header)
  if (!parsed) return false
  const userOk = timingSafeEqualString(parsed.user, getConfiguredUser())
  const passOk = timingSafeEqualString(parsed.password, expectedPassword)
  return userOk && passOk
}

/**
 * Browser document navigations need WWW-Authenticate so the password dialog appears.
 * fetch() / XHR to /api with that header often becomes TypeError: Failed to fetch
 * instead of a readable 401 — those requests get a JSON 401 without the challenge.
 */
export function shouldUseWwwAuthenticateChallenge(args: {
  pathname: string
  secFetchDest?: string | null
  accept?: string | null
}): boolean {
  const pathname = args.pathname || ''
  if (pathname === '/api' || pathname.startsWith('/api/')) return false
  const dest = (args.secFetchDest || '').toLowerCase()
  if (dest === 'empty' || dest === 'cors') return false
  if (dest === 'document' || dest === 'iframe' || dest === 'frame') return true
  const accept = args.accept || ''
  return accept.includes('text/html')
}
