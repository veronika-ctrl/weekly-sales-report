/**
 * Shared fetch options and error mapping for the Python API.
 *
 * HTTP Basic Auth (Vercel proxy.ts) is stored by the browser after the login
 * dialog. Document navigations send Authorization automatically; fetch() does
 * not unless credentials are included — Chrome/Safari then surface that as
 * TypeError: Failed to fetch when the 401 still carries WWW-Authenticate.
 */

export const API_FETCH_CREDENTIALS: RequestCredentials = 'include'

export function withApiCredentials(init?: RequestInit): RequestInit {
  return { credentials: API_FETCH_CREDENTIALS, ...init }
}

export function isNetworkFetchErrorMessage(message: string): boolean {
  return /failed to fetch|networkerror|network request failed|load failed|err_aborted|err_network/i.test(
    message
  )
}

export function describeHttpError(status: number, body: string): string {
  const trimmed = (body || '')
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 280)

  if (status === 401) {
    return (
      'Authentication required (401). Refresh the page, enter the site password if prompted, ' +
      'then open this report again. API calls must send the same login as the page.'
    )
  }
  if (status === 502 || status === 503 || status === 504) {
    return (
      `The API returned ${status} (gateway timeout or unavailable). ` +
      'A large Shopify customer file can drop this connection. ' +
      'Headline Adjusted aMER comes from the Dema agent trio and does not need a re-upload — retry in a minute.'
    )
  }
  if (trimmed) return trimmed
  return `Request failed (${status})`
}

export function describeApiFetchFailure(
  err: unknown,
  opts?: { endpoint?: string; timeoutMs?: number }
): string {
  if (err instanceof Error && err.name === 'AbortError') {
    const sec = opts?.timeoutMs != null ? `${opts.timeoutMs / 1000}s` : 'the limit'
    const where = opts?.endpoint ? ` (${opts.endpoint})` : ''
    return `Request timed out after ${sec}${where}. The API may still be working on a large file.`
  }
  const msg = err instanceof Error ? err.message : String(err ?? '')
  if (/request timed out/i.test(msg)) return msg
  if (isNetworkFetchErrorMessage(msg)) {
    const where = opts?.endpoint ? ` ${opts.endpoint}` : ' the API'
    return (
      `Could not reach${where} (Failed to fetch). ` +
      'This is a network, CORS, or site-password problem — not missing Dema files. ' +
      'Hard-refresh, re-enter the site password if prompted, and retry. ' +
      'If it continues, the API connection was dropped (timeout or restart). Uploaded files stay on the server; you do not need to re-upload them.'
    )
  }
  return msg || 'Failed to load'
}
