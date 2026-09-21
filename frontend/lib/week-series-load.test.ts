import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { describe, it } from 'node:test'
import { fileURLToPath } from 'node:url'
import { normalizeNamedSeries } from './week-series'

const here = dirname(fileURLToPath(import.meta.url))

describe('normalizeNamedSeries', () => {
  it('reads a keyed array payload', () => {
    assert.deepEqual(
      normalizeNamedSeries({ gender_sales: [{ week: '2026-38' }] }, 'gender_sales'),
      [{ week: '2026-38' }],
    )
  })

  it('reads a bare array', () => {
    assert.deepEqual(normalizeNamedSeries([{ week: '2026-37' }], 'gender_sales'), [{ week: '2026-37' }])
  })

  it('treats null, missing key, and empty array as no rows', () => {
    assert.deepEqual(normalizeNamedSeries(null, 'gender_sales'), [])
    assert.deepEqual(normalizeNamedSeries({}, 'gender_sales'), [])
    assert.deepEqual(normalizeNamedSeries({ gender_sales: [] }, 'gender_sales'), [])
  })
})

describe('gender sales self-load wiring', () => {
  it('fetches /api/gender-sales itself instead of waiting on the summary cache', () => {
    const page = readFileSync(join(here, '../app/gender-sales/page.tsx'), 'utf8')
    const api = readFileSync(join(here, 'api.ts'), 'utf8')
    const start = api.indexOf('export async function getGenderSales')
    assert.ok(start >= 0)
    const body = api.slice(start, start + 500)
    assert.match(page, /getGenderSales/)
    assert.match(page, /useWeekSeriesLoad/)
    assert.match(page, /ReportLoadState/)
    assert.match(page, /Upload the Qlik export in Settings/)
    assert.doesNotMatch(page, /useGenderSales/)
    assert.match(body, /fetchJsonWithTimeout/)
    assert.match(body, /\/api\/gender-sales/)
    assert.doesNotMatch(body, /\bawait fetch\(/)
  })

  it('stops the loading spinner for contribution and category pages too', () => {
    for (const [file, fn] of [
      ['../app/contribution/page.tsx', 'getContribution'],
      ['../app/men-category-sales/page.tsx', 'getMenCategorySales'],
      ['../app/women-category-sales/page.tsx', 'getWomenCategorySales'],
    ] as const) {
      const src = readFileSync(join(here, file), 'utf8')
      assert.match(src, new RegExp(fn))
      assert.match(src, /useWeekSeriesLoad/)
      assert.match(src, /ReportLoadState/)
      assert.doesNotMatch(src, /if \(!.*\|\| .*\.length === 0\)/)
    }
  })
})
