import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import {
  describeApiTarget,
  getApiStorageWarning,
  isVercelHostname,
} from './api-storage'

describe('isVercelHostname', () => {
  it('matches production and preview Vercel hosts', () => {
    assert.equal(isVercelHostname('weekly-sales-report-two.vercel.app'), true)
    assert.equal(isVercelHostname('weekly-sales-report-git-main-cdlps-projects-14314ed2.vercel.app'), true)
    assert.equal(isVercelHostname('localhost'), false)
  })
})

describe('describeApiTarget', () => {
  it('explains same-origin as the Next rewrite to loopback', () => {
    const t = describeApiTarget('', 'weekly-sales-report-two.vercel.app')
    assert.match(t, /weekly-sales-report-two\.vercel\.app\/api/)
    assert.match(t, /127\.0\.0\.1:8000/)
  })

  it('shows an explicit Render URL as-is', () => {
    assert.equal(
      describeApiTarget('https://weekly-sales-report.onrender.com/'),
      'https://weekly-sales-report.onrender.com'
    )
  })
})

describe('getApiStorageWarning', () => {
  it('warns when Vercel is same-origin / loopback', () => {
    for (const apiBaseUrl of ['', '/', 'same-origin', 'http://127.0.0.1:8000', 'http://localhost:8000']) {
      const w = getApiStorageWarning({
        apiBaseUrl,
        hostname: 'weekly-sales-report-two.vercel.app',
      })
      assert.ok(w, `expected warning for ${apiBaseUrl}`)
      assert.equal(w.level, 'danger')
      assert.match(w.body, /NEXT_PUBLIC_API_URL/)
      assert.match(w.body, /onrender\.com/)
    }
  })

  it('does not warn for local Next + local API', () => {
    assert.equal(
      getApiStorageWarning({ apiBaseUrl: 'http://127.0.0.1:8000', hostname: 'localhost' }),
      null
    )
  })

  it('warns that Render disk is ephemeral when the API URL is onrender.com', () => {
    const w = getApiStorageWarning({
      apiBaseUrl: 'https://weekly-sales-report.onrender.com',
      hostname: 'weekly-sales-report-two.vercel.app',
    })
    assert.ok(w)
    assert.equal(w.level, 'warning')
    assert.match(w.body, /ephemeral|persistent disk/i)
    assert.match(w.body, /Current Files/)
  })
})
