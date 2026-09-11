/**
 * Production upload/storage warnings. Vercel Next cannot keep CSVs;
 * Settings uploads go to whatever host NEXT_PUBLIC_API_URL points at.
 */

export type ApiStorageWarning = {
  level: 'danger' | 'warning'
  title: string
  body: string
}

function looksLikeLoopbackApi(apiBaseUrl: string): boolean {
  const base = (apiBaseUrl || '').trim()
  if (!base || base === '/' || base === 'same-origin') return true
  try {
    const u = new URL(base)
    return u.hostname === 'localhost' || u.hostname === '127.0.0.1'
  } catch {
    return /localhost|127\.0\.0\.1/.test(base)
  }
}

export function isVercelHostname(hostname: string): boolean {
  const host = (hostname || '').toLowerCase()
  return host === 'vercel.app' || host.endsWith('.vercel.app')
}

/** Human-readable API target for Settings (never includes secrets). */
export function describeApiTarget(apiBaseUrl: string, hostname?: string): string {
  const base = (apiBaseUrl || '').trim()
  if (!base || base === '/' || base === 'same-origin') {
    const host = hostname ? `https://${hostname}` : 'this site'
    return `${host}/api (Next rewrite → 127.0.0.1:8000)`
  }
  return base.replace(/\/$/, '')
}

/**
 * Return a Settings banner when uploads cannot persist, or persist only on
 * an ephemeral host. Pure function so tests do not need a browser.
 */
export function getApiStorageWarning(opts: {
  apiBaseUrl: string
  hostname?: string
}): ApiStorageWarning | null {
  const hostname = opts.hostname || ''
  const onVercel = isVercelHostname(hostname)
  const base = (opts.apiBaseUrl || '').trim()

  if (onVercel && looksLikeLoopbackApi(base)) {
    return {
      level: 'danger',
      title: 'Uploads are not persisted on this Vercel app',
      body:
        'Settings uploads POST to /api on this site, and Next rewrites that to 127.0.0.1:8000. ' +
        'There is no FastAPI process on Vercel, so files never land on a durable disk. ' +
        'Set NEXT_PUBLIC_API_URL in Vercel to the persistent FastAPI URL (Render/Railway), ' +
        'for example https://weekly-sales-report.onrender.com, then Redeploy. ' +
        'Upload only after that API is the one this page calls.',
    }
  }

  if (/onrender\.com/i.test(base)) {
    return {
      level: 'warning',
      title: 'Files live on the Render API disk, not on Vercel',
      body:
        'This site’s reports read CSVs from the FastAPI host in NEXT_PUBLIC_API_URL. ' +
        'Render’s default disk is ephemeral: a deploy, restart, or free-tier spin-up wipes every upload. ' +
        'Attach a persistent disk at DATA_ROOT (e.g. ./data) on Render, keep that service awake while you upload, ' +
        'and confirm Current Files lists the CSVs for this week before opening reports.',
    }
  }

  if (/railway\.app/i.test(base) || /up\.railway\.app/i.test(base)) {
    return {
      level: 'warning',
      title: 'Files live on the Railway API disk, not on Vercel',
      body:
        'Uploads are stored on the FastAPI service, not in the Vercel deployment. ' +
        'Use a volume for DATA_ROOT if you need CSVs to survive redeploys.',
    }
  }

  return null
}
