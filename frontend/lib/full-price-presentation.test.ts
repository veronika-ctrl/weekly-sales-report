import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { describe, it } from 'node:test'
import { fileURLToPath } from 'node:url'
import {
  AMOUNTS_INCL_VAT_NOTE,
  SHOPIFY_GROSS_EXCL_VAT_NOTE,
  formatMixAxisTick,
  hasLastYearTotal,
  lastYearShareForChart,
  lyOrNull,
  monthlyTypesLayout,
  shareChartPoint,
} from './full-price-presentation'

const here = dirname(fileURLToPath(import.meta.url))

describe('last-year missing vs zero (display only)', () => {
  it('treats last_year total of 0 as missing', () => {
    assert.equal(hasLastYearTotal({ total: 0, full_price_pct: 0 }), false)
    assert.equal(hasLastYearTotal({ total: 0, full_price_pct: null }), false)
    assert.equal(hasLastYearTotal(null), false)
    assert.equal(hasLastYearTotal(undefined), false)
    assert.equal(hasLastYearTotal({ total: 1500, full_price_pct: 0 }), true)
  })

  it('nulls the LY share-chart point so Recharts skips Oct–Dec with no prior year', () => {
    assert.equal(lastYearShareForChart({ total: 0, full_price_pct: 0 }), null)
    assert.equal(lastYearShareForChart({ total: 0, full_price_pct: 12.3 }), null)
    assert.equal(lastYearShareForChart(undefined), null)
    assert.equal(lastYearShareForChart({ total: 80_000, full_price_pct: 61.2 }), 61.2)
    assert.equal(lastYearShareForChart({ total: 80_000, full_price_pct: null }), null)
  })

  it('hides LY table metrics when last-year total is 0, including 0.0% API leftovers', () => {
    const missing = { total: 0, full_price_pct: 0, weighted_discount_pct: 0 }
    assert.equal(lyOrNull(missing, 0), null)
    assert.equal(lyOrNull(missing, -12.5), null)
    assert.equal(lyOrNull({ total: 10_000 }, 4.2), 4.2)
  })

  it('builds share points with lastYear null rather than 0', () => {
    const point = shareChartPoint({
      label: "Oct '25",
      fullPricePct: 58.1,
      lastYear: { total: 0, full_price_pct: 0 },
    })
    assert.equal(point.value, 58.1)
    assert.equal(point.lastYear, null)
    const withLy = shareChartPoint({
      label: "Sep '26",
      fullPricePct: 62,
      lastYear: { total: 1, full_price_pct: 55 },
    })
    assert.equal(withLy.lastYear, 55)
  })
})

describe('formatMixAxisTick', () => {
  it('prints integer percent ticks including 100%', () => {
    assert.equal(formatMixAxisTick(0), '0%')
    assert.equal(formatMixAxisTick(25), '25%')
    assert.equal(formatMixAxisTick(50), '50%')
    assert.equal(formatMixAxisTick(75), '75%')
    assert.equal(formatMixAxisTick(100), '100%')
  })

  it('does not emit scientific / padded ticks like 0000001%', () => {
    assert.equal(formatMixAxisTick(100.0000001), '100%')
    assert.equal(formatMixAxisTick(1e-7), '0%')
    assert.equal(formatMixAxisTick('100'), '100%')
    assert.doesNotMatch(formatMixAxisTick(100), /0000001/)
    assert.doesNotMatch(formatMixAxisTick(1), /0000001/)
  })
})

describe('monthlyTypesLayout', () => {
  it('puts last full month first and current MTD below (Oct 2026 as of 2026-10-13)', () => {
    const { primary, mtd, periodsAsc } = monthlyTypesLayout([
      { key: '2026-10', month: '2026-10', end: '2026-10-12' },
      { key: '2026-09', month: '2026-09', end: '2026-09-30' },
      { key: '2026-08', month: '2026-08', end: '2026-08-31' },
    ])
    assert.equal(periodsAsc.map((p) => p.key).join(','), '2026-08,2026-09,2026-10')
    assert.equal(primary?.key, '2026-09')
    assert.equal(mtd?.key, '2026-10')
  })

  it('has no MTD block when the latest month is complete', () => {
    const { primary, mtd } = monthlyTypesLayout([
      { key: '2026-09', month: '2026-09', end: '2026-09-30' },
      { key: '2026-08', month: '2026-08', end: '2026-08-31' },
    ])
    assert.equal(primary?.key, '2026-09')
    assert.equal(mtd, undefined)
  })
})

describe('footnote and title wiring', () => {
  it('keeps VAT footnote on Full Price vs Sale slides and Shopify excl. VAT on discount-type slides', () => {
    const page = readFileSync(join(here, '../app/products/full-price-vs-sale/page.tsx'), 'utf8')
    const types = readFileSync(join(here, '../components/DiscountTypesSection.tsx'), 'utf8')
    const excl = readFileSync(join(here, '../components/FullPriceExclExchangesSection.tsx'), 'utf8')
    assert.match(page, new RegExp(AMOUNTS_INCL_VAT_NOTE.replace(/\./g, '\\.')))
    assert.match(excl, new RegExp(AMOUNTS_INCL_VAT_NOTE.replace(/\./g, '\\.')))
    assert.doesNotMatch(page, /Shopify gross sales and discounts, excl\. VAT\./)
    assert.match(types, /SHOPIFY_GROSS_EXCL_VAT_NOTE|Shopify gross sales and discounts, excl\. VAT\./)
    assert.doesNotMatch(types, new RegExp(AMOUNTS_INCL_VAT_NOTE.replace(/\./g, '\\.')))
  })

  it('titles discount-type slides Discount Types – Monthly / Weekly, not Full Price vs Sale detail', () => {
    const types = readFileSync(join(here, '../components/DiscountTypesSection.tsx'), 'utf8')
    const page = readFileSync(join(here, '../app/products/full-price-vs-sale/page.tsx'), 'utf8')
    assert.match(types, /Discount Types – Monthly/)
    assert.match(types, /Discount Types – Weekly/)
    assert.match(types, /Discount amount \(SEK\)/)
    assert.doesNotMatch(types, /SEK [’']000/)
    assert.doesNotMatch(types, /Full Price vs Sale – Monthly detail/)
    assert.match(page, /\{periodHeader\}ly detail/)
  })

  it('wires mix-chart y-axis to integer 0–100 ticks', () => {
    const mix = readFileSync(join(here, '../components/SalesMixChart.tsx'), 'utf8')
    const share = readFileSync(join(here, '../components/ExchangeDiscountShareChart.tsx'), 'utf8')
    for (const src of [mix, share]) {
      assert.match(src, /MIX_AXIS_DOMAIN/)
      assert.match(src, /MIX_AXIS_TICKS/)
      assert.match(src, /formatMixAxisTick/)
    }
  })

  it('nulls the LY share line and does not connect across missing months', () => {
    const page = readFileSync(join(here, '../app/products/full-price-vs-sale/page.tsx'), 'utf8')
    assert.match(page, /shareChartPoint/)
    assert.match(page, /connectNulls=\{false\}/)
    assert.match(page, /hasLastYearTotal|lyOrNull/)
  })
})
