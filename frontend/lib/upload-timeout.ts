/**
 * Settings upload timeouts and error copy.
 *
 * Production: Vercel UI → FastAPI on Render (NEXT_PUBLIC_API_URL). Uploads are
 * sequential inside one card, but several cards can start at once. Render free
 * is one worker: a Qlik xlsx that pandas-scans after save blocks every other
 * request, so later files sit at 0 KB transferred until the 5-minute abort.
 */

export const SMALL_HOSTED_UPLOAD_TIMEOUT_MS = 90_000
export const DEFAULT_UPLOAD_TIMEOUT_MS = 5 * 60 * 1000
export const MAX_UPLOAD_TIMEOUT_MS = 15 * 60 * 1000

export function isRemoteApiUrl(apiBaseUrl: string): boolean {
  const base = (apiBaseUrl || '').trim()
  if (!base || base === '/' || base === 'same-origin') return false
  try {
    const host = new URL(base).hostname
    return host !== 'localhost' && host !== '127.0.0.1'
  } catch {
    return /onrender\.com|railway\.app/i.test(base)
  }
}

export function formatUploadFileSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return 'unknown size'
  if (bytes < 1024) return `${Math.round(bytes)} B`
  if (bytes < 100 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

/**
 * Small hosted files fail faster: waiting 5 minutes almost always means Render
 * is still busy (often Qlik Excel), not that this CSV is still transferring.
 * Large files keep a longer window for the actual upload.
 */
export function computeUploadTimeoutMs(
  fileSizeBytes: number,
  opts?: { remoteApi?: boolean }
): number {
  const mb = Math.max(0, fileSizeBytes) / (1024 * 1024)
  if (opts?.remoteApi && mb < 5) {
    return SMALL_HOSTED_UPLOAD_TIMEOUT_MS
  }
  const extraOver10Mb = Math.max(0, mb - 10) * 60 * 1000
  return Math.min(MAX_UPLOAD_TIMEOUT_MS, DEFAULT_UPLOAD_TIMEOUT_MS + extraOver10Mb)
}

export function formatUploadTimeoutError(opts: {
  fileName: string
  bytes: number
  timeoutMs: number
  remoteApi?: boolean
}): string {
  const size = formatUploadFileSize(opts.bytes)
  const seconds = Math.round(opts.timeoutMs / 1000)
  const minutes = Math.round(opts.timeoutMs / 60000)
  const waited =
    seconds < 120 ? `${seconds} seconds` : `${minutes} minute${minutes === 1 ? '' : 's'}`
  const hostedHint = opts.remoteApi
    ? ' Render may still be processing another file (often Qlik Excel) — try one file at a time, then wait until Current Files lists it.'
    : ' The API may still be processing the file.'
  return (
    `Upload timeout: "${opts.fileName}" (${size}) did not finish within ${waited}.` +
    hostedHint +
    ' Cancel/refresh Settings if the bar is stuck at 99%. A 0 B / tiny size in this message is the local file size, not proof the server received it.'
  )
}

export function formatSkippedAfterTimeoutError(fileName: string): string {
  return (
    `Skipped "${fileName}" because a previous file timed out or lost the API connection. ` +
    'Do not queue Qlik xlsx + many CSVs in one click. Upload one small file, wait until Current Files lists it, then the next.'
  )
}

export function formatOtherCardUploadingError(): string {
  return (
    'Another Settings card is already uploading. Wait until it finishes (or cancel it), ' +
    'then upload one file at a time. Parallel cards overload a single Render worker.'
  )
}

export function shouldAbortRemainingUploads(errorMessage: string): boolean {
  return /timeout|timed out|still processing|failed to fetch|network error|unreachable|gateway|aborted/i.test(
    errorMessage || ''
  )
}
