import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { describe, it } from 'node:test'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))

describe('online summary MTD load', () => {
  it('uses fetchJsonWithTimeout instead of a bare fetch (Failed to fetch)', () => {
    const api = readFileSync(join(here, 'api.ts'), 'utf8')
    const start = api.indexOf('export async function getTable1Mtd')
    assert.ok(start >= 0)
    const body = api.slice(start, start + 700)
    assert.match(body, /fetchJsonWithTimeout/)
    assert.match(body, /\/api\/metrics\/table1-mtd/)
    assert.match(body, /HEAVY_METRICS_TIMEOUT_MS/)
    assert.doesNotMatch(body, /\bawait fetch\(/)
  })

  it('does not kick off Summary table1 in parallel with MTD', () => {
    const page = readFileSync(join(here, '../app/summary-mtd/page.tsx'), 'utf8')
    assert.match(page, /getTable1Mtd/)
    assert.doesNotMatch(page, /loadAllData/)
    assert.match(page, /30–90 seconds|30-90 seconds/)
    assert.match(page, /Do not re-upload/)
  })
})
