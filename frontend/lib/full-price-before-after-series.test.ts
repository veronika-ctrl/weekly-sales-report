import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import type { FullPriceExclExchangesResponse } from './api'
import {
  buildBeforeAfterSeries,
  buildDiscountShareChartData,
  mixIsEssentiallyFlat,
  monthLabel,
  periodVsLatest,
  weekLabel,
} from './full-price-before-after-series'

const comparison = (over: {
  inclShare: number
  exclShare: number
  fullIncl: number
  fullExcl: number
  totalIncl: number
  totalExcl: number
  discountIncl: number
  discountExcl: number
  exchDiscShare: number
}) => ({
  full_price_share_incl_pct: over.inclShare,
  full_price_share_excl_pct: over.exclShare,
  full_price_share_pp_diff: over.exclShare - over.inclShare,
  full_incl: over.fullIncl,
  full_excl: over.fullExcl,
  discounted_incl: over.totalIncl - over.fullIncl,
  discounted_excl: over.totalExcl - over.fullExcl,
  total_incl: over.totalIncl,
  total_excl: over.totalExcl,
  discount_incl: over.discountIncl,
  discount_excl: over.discountExcl,
  exchange_gross_share_pct: 1,
  exchange_discount_share_pct: over.exchDiscShare,
  non_exchange_gross_est: over.totalExcl + over.discountExcl,
  gross_context: over.totalExcl + over.discountExcl,
})

const metrics = (
  weekOrMonth: { week?: string; month?: string },
  over: Parameters<typeof comparison>[0] & { orders?: number; net?: number; gross?: number },
) => ({
  full_price: over.fullExcl,
  compare_at_price_sale: 0,
  discount_code_auto: 0,
  both: 0,
  price_drop_sale: 0,
  total: over.totalExcl,
  discount_amount: over.discountExcl,
  full_price_share_pct: over.exclShare,
  exchange_orders: over.orders ?? 0,
  exchange_gross_value: over.gross ?? 0,
  exchange_discount: over.discountIncl - over.discountExcl,
  exchange_net_revenue: over.net ?? 0,
  comparison: comparison(over),
  ...weekOrMonth,
})

const weeklyPayload: FullPriceExclExchangesResponse = {
  base_week: '2026-37',
  num_weeks: 2,
  months: 13,
  granularity: 'week',
  source: 'full_price_vs_sale_excl_exchanges',
  files_used: ['excl.csv'],
  days: [],
  weeks: [
    metrics(
      { week: '2026-36' },
      {
        inclShare: 80,
        exclShare: 80,
        fullIncl: 80,
        fullExcl: 80,
        totalIncl: 100,
        totalExcl: 100,
        discountIncl: 10,
        discountExcl: 5,
        exchDiscShare: 50,
      },
    ),
    metrics(
      { week: '2026-37' },
      {
        inclShare: 64.27,
        exclShare: 64.27,
        fullIncl: 848927,
        fullExcl: 848927,
        totalIncl: 1320856,
        totalExcl: 1320856,
        discountIncl: 47040,
        discountExcl: 19524,
        exchDiscShare: 58.5,
        gross: 27516,
        net: 0,
      },
    ),
  ],
  months_data: [],
  period: {
    ...metrics(
      {},
      {
        inclShare: 63.79,
        exclShare: 63.79,
        fullIncl: 8267654,
        fullExcl: 8266779,
        totalIncl: 12961228,
        totalExcl: 12959922,
        discountIncl: 1323477,
        discountExcl: 1153587,
        exchDiscShare: 12.84,
        orders: 46,
        net: 1306,
        gross: 171195,
      },
    ),
    label: '2026-07-20 → 2026-09-13 (last 8 weeks)',
    start: '2026-07-20',
    end: '2026-09-13',
  },
}

describe('buildBeforeAfterSeries', () => {
  it('maps weekly incl/excl shares without hardcoding 64.3 / 63.8', () => {
    const series = buildBeforeAfterSeries(weeklyPayload, 'week')
    assert.deepEqual(
      series.map((p) => p.label),
      ['W36', 'W37'],
    )
    assert.equal(series[1].before, weeklyPayload.weeks[1].comparison.full_price_share_incl_pct)
    assert.equal(series[1].after, weeklyPayload.weeks[1].comparison.full_price_share_excl_pct)
    assert.equal(series[1].fullIncl, 848927)
    assert.equal(series[1].discIncl, 1320856 - 848927)
    assert.notEqual(series[1].before, weeklyPayload.period?.comparison.full_price_share_incl_pct)
  })

  it('reverses monthly rows oldest → newest', () => {
    const monthly: FullPriceExclExchangesResponse = {
      ...weeklyPayload,
      granularity: 'month',
      weeks: [],
      months_data: [
        {
          ...metrics(
            { month: '2026-09' },
            {
              inclShare: 65.5,
              exclShare: 65.5,
              fullIncl: 1600,
              fullExcl: 1600,
              totalIncl: 2443,
              totalExcl: 2443,
              discountIncl: 80,
              discountExcl: 44,
              exchDiscShare: 45,
            },
          ),
          start: '2026-09-01',
          end: '2026-09-13',
        },
        {
          ...metrics(
            { month: '2026-08' },
            {
              inclShare: 66.8,
              exclShare: 66.8,
              fullIncl: 5100,
              fullExcl: 5100,
              totalIncl: 7663,
              totalExcl: 7663,
              discountIncl: 400,
              discountExcl: 353,
              exchDiscShare: 11.8,
            },
          ),
          start: '2026-08-01',
          end: '2026-08-31',
        },
      ],
    }
    const series = buildBeforeAfterSeries(monthly, 'month')
    assert.deepEqual(
      series.map((p) => p.label),
      [monthLabel('2026-08'), monthLabel('2026-09')],
    )
    assert.equal(series[0].before, 66.8)
    assert.equal(series[1].before, 65.5)
  })
})

describe('periodVsLatest', () => {
  it('flags that the window mix is not the latest week', () => {
    const note = periodVsLatest(weeklyPayload, 'week')
    assert.ok(note)
    assert.equal(note.latestLabel, 'W37')
    assert.equal(note.latestBefore, 64.27)
    assert.equal(note.periodBefore, 63.79)
    assert.equal(note.latestDiffersFromPeriod, true)
    assert.equal(note.mixUnchanged, true)
    assert.ok(Math.abs((note.exchangeDiscountSharePct || 0) - 12.84) < 0.01)
  })
})

describe('mixIsEssentiallyFlat', () => {
  it('is true when every week’s before and after shares match', () => {
    assert.equal(mixIsEssentiallyFlat(buildBeforeAfterSeries(weeklyPayload, 'week')), true)
  })

  it('is false when after mix actually rises', () => {
    const points = buildBeforeAfterSeries(weeklyPayload, 'week').map((p, i) =>
      i === 1 ? { ...p, after: (p.before || 0) + 3 } : p,
    )
    assert.equal(mixIsEssentiallyFlat(points), false)
  })
})

describe('labels', () => {
  it('formats ISO weeks and months', () => {
    assert.equal(weekLabel('2026-37'), 'W37')
    assert.match(monthLabel('2026-09'), /Sep/)
  })
})

describe('buildDiscountShareChartData', () => {
  it('maps each week’s exchange-credit share of recorded discount, not the window 12.8%', () => {
    const rows = buildDiscountShareChartData(buildBeforeAfterSeries(weeklyPayload, 'week'))
    assert.deepEqual(
      rows.map((r) => r.label),
      ['W36', 'W37'],
    )
    assert.equal(rows[0].exchange, 50)
    assert.equal(rows[0].promotional, 50)
    assert.ok(Math.abs((rows[1].exchange || 0) - 58.5) < 0.02)
    assert.ok(Math.abs((rows[1].promotional || 0) - 41.5) < 0.02)
    assert.notEqual(rows[1].exchange, weeklyPayload.period?.comparison.exchange_discount_share_pct)
  })

  it('keeps the period total as the 8-week mix (≈12.8%), separate from W37', () => {
    const note = periodVsLatest(weeklyPayload, 'week')
    assert.ok(note)
    assert.ok(Math.abs((note.exchangeDiscountSharePct || 0) - 12.84) < 0.01)
    assert.ok(Math.abs((note.promotionalDiscountSharePct || 0) - (100 - 12.84)) < 0.01)
    assert.ok(note.discountShare)
    assert.deepEqual(
      note.discountShare.slices.map((s) => s.id),
      ['exchange', 'promotional'],
    )
    const latest = buildDiscountShareChartData(buildBeforeAfterSeries(weeklyPayload, 'week')).at(-1)
    assert.ok(Math.abs((latest?.exchange || 0) - 58.5) < 0.02)
    assert.notEqual(latest?.exchange, note.exchangeDiscountSharePct)
  })

  it('reverses monthly discount-share rows oldest → newest', () => {
    const monthly: FullPriceExclExchangesResponse = {
      ...weeklyPayload,
      granularity: 'month',
      weeks: [],
      months_data: [
        {
          ...metrics(
            { month: '2026-09' },
            {
              inclShare: 65.5,
              exclShare: 65.5,
              fullIncl: 1600,
              fullExcl: 1600,
              totalIncl: 2443,
              totalExcl: 2443,
              discountIncl: 80,
              discountExcl: 44,
              exchDiscShare: 45,
            },
          ),
          start: '2026-09-01',
          end: '2026-09-13',
        },
        {
          ...metrics(
            { month: '2026-08' },
            {
              inclShare: 66.8,
              exclShare: 66.8,
              fullIncl: 5100,
              fullExcl: 5100,
              totalIncl: 7663,
              totalExcl: 7663,
              discountIncl: 400,
              discountExcl: 353,
              exchDiscShare: 11.8,
            },
          ),
          start: '2026-08-01',
          end: '2026-08-31',
        },
      ],
    }
    const rows = buildDiscountShareChartData(buildBeforeAfterSeries(monthly, 'month'))
    assert.deepEqual(
      rows.map((r) => r.label),
      [monthLabel('2026-08'), monthLabel('2026-09')],
    )
    assert.ok(Math.abs((rows[0].exchange || 0) - 11.75) < 0.01)
    assert.equal(rows[1].exchange, 45)
    assert.ok(Math.abs((rows[0].promotional || 0) - 88.25) < 0.01)
  })

  it('fills promotional share as 100 − exchange when the API omits it', () => {
    const points = buildBeforeAfterSeries(weeklyPayload, 'week').map((p) => ({
      ...p,
      promotionalDiscountSharePct: null,
    }))
    const rows = buildDiscountShareChartData(points)
    assert.equal(rows[0].promotional, 50)
    assert.ok(Math.abs((rows[1].promotional || 0) - 41.5) < 0.01)
  })
})

describe('sales mix on period vs latest', () => {
  it('attaches a 100% sales mix even when exchange net is ~0', () => {
    const note = periodVsLatest(weeklyPayload, 'week')
    assert.ok(note?.salesMix)
    assert.equal(note.exchangeNet, 1306)
    assert.ok((note.salesMix.exchangePct || 0) > 0)
    assert.ok(
      Math.abs(
        (note.salesMix.fullPricePct || 0) +
          (note.salesMix.exchangePct || 0) +
          (note.salesMix.promoPct || 0) -
          100,
      ) < 0.05,
    )
    const w37 = buildBeforeAfterSeries(weeklyPayload, 'week')[1]
    assert.equal(w37.exchangeGross, 27516)
    assert.ok(Math.abs((w37.exchangeDiscountSharePct || 0) - 58.5) < 0.02)
  })

  it('does not treat exchange credits ÷ discount as the sales mix', () => {
    const w37 = buildBeforeAfterSeries(weeklyPayload, 'week')[1]
    assert.ok(Math.abs((w37.exchangeDiscountSharePct || 0) - 58.5) < 0.02)
    const mixShare = (w37.exchangeGross / (w37.totalExcl + w37.exchangeGross)) * 100
    assert.ok(mixShare > 0)
    assert.ok(mixShare < 5)
    assert.notEqual(Math.round(mixShare), Math.round(w37.exchangeDiscountSharePct || 0))
  })
})

