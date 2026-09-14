import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { describe, it } from 'node:test'
import { fileURLToPath } from 'node:url'
import {
  allOrdersSectionState,
  exclExchangesSectionState,
  hasExclExchangesPayload,
  settleLoad,
} from './full-price-vs-sale-load'

const exclWeekly = {
  period: { label: '2026-07-20 → 2026-09-13 (last 8 weeks)' },
  days: [{ date: '2026-09-07' }],
  weeks: [{ week: '2026-37' }],
  months_data: [],
}

describe('hasExclExchangesPayload', () => {
  it('is false for null (the Promise.all catch path)', () => {
    assert.equal(hasExclExchangesPayload(null), false)
    assert.equal(hasExclExchangesPayload(undefined), false)
  })

  it('is false for an API 200 with no period or rows', () => {
    assert.equal(
      hasExclExchangesPayload({ period: null, days: [], weeks: [], months_data: [] }),
      false,
    )
  })

  it('is true when period or any series is present', () => {
    assert.equal(hasExclExchangesPayload(exclWeekly), true)
    assert.equal(hasExclExchangesPayload({ period: null, days: [{ date: '2026-09-01' }] }), true)
    assert.equal(hasExclExchangesPayload({ weeks: [{ week: '2026-37' }] }), true)
  })
})

describe('exclExchangesSectionState', () => {
  it('does not show the upload empty-state when a fetch failed', () => {
    assert.equal(
      exclExchangesSectionState({
        view: 'week',
        weekly: null,
        monthly: null,
        loading: false,
        error: 'Failed to fetch',
      }),
      'error',
    )
  })

  it('keeps excl data when the all-orders (or monthly) sibling failed', () => {
    assert.equal(
      exclExchangesSectionState({
        view: 'week',
        weekly: exclWeekly,
        monthly: null,
        loading: false,
        error: 'Could not reach /api/discounts/full-price-vs-sale',
      }),
      'ready',
    )
  })

  it('shows empty only after a successful load with no payload', () => {
    assert.equal(
      exclExchangesSectionState({
        view: 'week',
        weekly: { period: null, days: [], weeks: [], months_data: [] },
        monthly: null,
        loading: false,
        error: null,
      }),
      'empty',
    )
  })

  it('stays on loading until the current view’s request finishes', () => {
    assert.equal(
      exclExchangesSectionState({
        view: 'week',
        weekly: null,
        monthly: null,
        loading: true,
        error: null,
      }),
      'loading',
    )
    assert.equal(
      exclExchangesSectionState({
        view: 'week',
        weekly: null,
        monthly: null,
        loading: false,
        error: null,
      }),
      'loading',
    )
  })

  it('shows month-view error without wiping week data', () => {
    assert.equal(
      exclExchangesSectionState({
        view: 'month',
        weekly: exclWeekly,
        monthly: null,
        loading: false,
        error: 'Request timed out after 180s (/api/discounts/full-price-vs-sale-excl-exchanges)',
      }),
      'error',
    )
    assert.equal(
      exclExchangesSectionState({
        view: 'week',
        weekly: exclWeekly,
        monthly: null,
        loading: false,
        error: null,
      }),
      'ready',
    )
  })
})

describe('allOrdersSectionState', () => {
  it('still shows charts when rows exist even if the other granularity failed', () => {
    assert.equal(
      allOrdersSectionState({
        hasRows: true,
        loading: false,
        error: 'monthly failed',
        data: { weeks: [{ week: '2026-37' }] },
      }),
      'ready',
    )
  })

  it('maps a fetch failure with no rows to error, not empty', () => {
    assert.equal(
      allOrdersSectionState({
        hasRows: false,
        loading: false,
        error: 'Failed to fetch',
        data: null,
      }),
      'error',
    )
  })

  it('treats an unloaded page as loading, not a missing-upload empty state', () => {
    assert.equal(
      allOrdersSectionState({
        hasRows: false,
        loading: false,
        error: null,
        data: null,
      }),
      'loading',
    )
  })
})

describe('settleLoad', () => {
  it('does not reject, so a sibling can still succeed', async () => {
    const failed = settleLoad(async () => {
      throw new TypeError('Failed to fetch')
    }, '/api/discounts/full-price-vs-sale')
    const ok = settleLoad(async () => exclWeekly, '/api/discounts/full-price-vs-sale-excl-exchanges')
    const [a, b] = await Promise.all([failed, ok])
    assert.equal(a.ok, false)
    if (!a.ok) {
      assert.match(a.error, /Could not reach/)
      assert.match(a.error, /full-price-vs-sale/)
      assert.doesNotMatch(a.error, /^Failed to fetch$/)
    }
    assert.equal(b.ok, true)
    if (b.ok) assert.equal(hasExclExchangesPayload(b.value), true)
  })
})

describe('full price API client', () => {
  const apiSrc = readFileSync(join(dirname(fileURLToPath(import.meta.url)), 'api.ts'), 'utf8')

  function exportedFnBody(name: string): string {
    const start = apiSrc.indexOf(`export async function ${name}`)
    assert.ok(start >= 0, `missing ${name}`)
    const rest = apiSrc.slice(start)
    const next = rest.slice(1).search(/\nexport (async )?function |\nexport interface |\ninterface /)
    return next < 0 ? rest : rest.slice(0, next + 1)
  }

  for (const name of [
    'getFullPriceVsSale',
    'getFullPriceVsSaleMonthly',
    'getFullPriceVsSaleExclExchanges',
    'getFullPriceVsSaleExclExchangesMonthly',
  ]) {
    it(`${name} uses fetchJsonWithTimeout (credentials + timeout)`, () => {
      const body = exportedFnBody(name)
      assert.match(body, /fetchJsonWithTimeout/)
      assert.doesNotMatch(body, /\bawait fetch\(/)
    })
  }
})
