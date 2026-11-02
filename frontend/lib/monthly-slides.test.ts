import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { describe, it } from 'node:test'
import { fileURLToPath } from 'node:url'
import { formatSekThousands, formatYoyPct } from './monthly-performance-format'

const here = dirname(fileURLToPath(import.meta.url))

describe('monthly performance format', () => {
  it('shows thousands SEK and YoY parentheses for declines', () => {
    assert.equal(formatSekThousands(1234000), '1 234')
    assert.equal(formatYoyPct(12.4), '12%')
    assert.equal(formatYoyPct(-8.2), '(8%)')
    assert.equal(formatYoyPct(null), '—')
  })
})

describe('monthly women and top-product slides', () => {
  it('women monthly page fetches /api/women-monthly itself', () => {
    const page = readFileSync(join(here, '../app/women-monthly/page.tsx'), 'utf8')
    const api = readFileSync(join(here, 'api.ts'), 'utf8')
    assert.match(page, /getWomenMonthly/)
    assert.match(page, /Women’s monthly/)
    assert.match(page, /onRetry/)
    assert.match(page, /do not need to re-upload/)
    assert.doesNotMatch(page, /loadAllData/)
    const start = api.indexOf('export async function getWomenMonthly')
    assert.ok(start >= 0)
    const body = api.slice(start, start + 500)
    assert.match(body, /\/api\/women-monthly/)
    assert.match(body, /fetchJsonWithHealthRetry/)
  })

  it('top products monthly page fetches /api/top-products-monthly itself', () => {
    const page = readFileSync(join(here, '../app/products-gender-monthly/page.tsx'), 'utf8')
    const api = readFileSync(join(here, 'api.ts'), 'utf8')
    assert.match(page, /getTopProductsMonthly/)
    assert.match(page, /Top selling products monthly/)
    assert.match(page, /onRetry/)
    assert.match(page, /do not need to re-upload/)
    assert.doesNotMatch(page, /loadAllData/)
    const start = api.indexOf('export async function getTopProductsMonthly')
    assert.ok(start >= 0)
    const body = api.slice(start, start + 700)
    assert.match(body, /\/api\/top-products-monthly/)
    assert.match(body, /fetchJsonWithHealthRetry/)
  })

  it('health-retry helper pings /api/health for 90s on Failed to fetch / 502', () => {
    const api = readFileSync(join(here, 'api.ts'), 'utf8')
    assert.match(api, /TRANSIENT_RETRY_WINDOW_MS = 90_000/)
    const start = api.indexOf('async function fetchJsonWithHealthRetry')
    assert.ok(start >= 0)
    const body = api.slice(start, start + 1200)
    assert.match(body, /isTransientApiError/)
    assert.match(body, /\/api\/health/)
    assert.match(body, /TRANSIENT_RETRY_WINDOW_MS/)
  })

  it('adds both slides to the weekly sales sidebar', () => {
    const src = readFileSync(join(here, '../components/SidebarLayout.tsx'), 'utf8')
    assert.match(src, /href="\/women-monthly"/)
    assert.match(src, /href="\/products-gender-monthly"/)
  })
})
