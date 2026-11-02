import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { describe, it } from 'node:test'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))

describe('claims fetch retry', () => {
  it('retries Failed to fetch / 502 instead of telling the user to re-upload', () => {
    const api = readFileSync(join(here, 'api.ts'), 'utf8')
    assert.match(api, /fetchJsonWithHealthRetry/)
    assert.match(api, /TRANSIENT_RETRY_WINDOW_MS = 90_000/)
    assert.match(api, /\/api\/health/)
    const start = api.indexOf('export async function getClaims')
    assert.ok(start >= 0)
    const body = api.slice(start, start + 800)
    assert.match(body, /\/api\/claims/)
    assert.match(body, /fetchJsonWithHealthRetry/)
    assert.match(body, /20_000/)
    assert.doesNotMatch(body, /re-upload/)
  })

  it('shows a Retry button and never asks to re-upload Cin7 files on Failed to fetch', () => {
    const page = readFileSync(join(here, '../app/claims/page.tsx'), 'utf8')
    assert.match(page, /getClaims/)
    assert.match(page, /ReportLoadState/)
    assert.match(page, /onRetry/)
    assert.match(page, /do not need to re-upload/i)
    assert.match(page, /does not read Qlik/)
    assert.doesNotMatch(page, /Loader2/)
  })
})
