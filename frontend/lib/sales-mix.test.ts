import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import {
  buildSalesMixChartData,
  computeSalesMix,
  salesMixSumsTo100,
} from './sales-mix'

describe('computeSalesMix', () => {
  it('uses excl. Total + exchange gross as the 100% denominator', () => {
    // User example shape: 55 full price, 12 exchange gross, 33 promo net on 88 excl. total.
    const mix = computeSalesMix({ exclFull: 55, exclTotal: 88, exchangeGross: 12 })
    assert.equal(mix.denom, 100)
    assert.equal(mix.fullPricePct, 55)
    assert.equal(mix.exchangePct, 12)
    assert.equal(mix.promoPct, 33)
    assert.equal(salesMixSumsTo100(mix), true)
  })

  it('shows a non-zero exchange slice when gross > 0 even if exchange net is ~0', () => {
    // W37-style: AfterShip credit offsets gross so net ≈ 0, but the new order still sold.
    const exclFull = 848927
    const exclTotal = 1320856
    const exchangeGross = 27516
    const exchangeNet = 0
    assert.ok(Math.abs(exchangeNet) < 1)
    const mix = computeSalesMix({ exclFull, exclTotal, exchangeGross })
    assert.ok((mix.exchangePct || 0) > 0)
    assert.ok((mix.exchangePct || 0) > 1.9 && (mix.exchangePct || 0) < 2.2)
    assert.equal(salesMixSumsTo100(mix), true)
    // Net-only mix would be 0 for exchanges; this path must not use net.
    const netOnly = exchangeNet / (exclTotal + exchangeNet)
    assert.equal(netOnly, 0)
    assert.notEqual(mix.exchangePct, 0)
  })

  it('keeps last-8-weeks live W37 window shares summing to 100%', () => {
    const mix = computeSalesMix({
      exclFull: 8266779.914202999,
      exclTotal: 12959922.613242999,
      exchangeGross: 171195.480952,
    })
    assert.ok(Math.abs((mix.fullPricePct || 0) - 62.96) < 0.02)
    assert.ok(Math.abs((mix.exchangePct || 0) - 1.3) < 0.02)
    assert.ok(Math.abs((mix.promoPct || 0) - 35.74) < 0.02)
    assert.equal(salesMixSumsTo100(mix), true)
  })

  it('returns null shares when there is nothing to mix', () => {
    const mix = computeSalesMix({ exclFull: 0, exclTotal: 0, exchangeGross: 0 })
    assert.equal(mix.denom, null)
    assert.equal(mix.fullPricePct, null)
    assert.equal(mix.exchangePct, null)
    assert.equal(salesMixSumsTo100(mix), false)
  })
})

describe('buildSalesMixChartData', () => {
  it('maps each week independently and does not reuse the window mix', () => {
    const rows = buildSalesMixChartData([
      { label: 'W36', exclFull: 80, exclTotal: 100, exchangeGross: 0 },
      { label: 'W37', exclFull: 40, exclTotal: 100, exchangeGross: 20 },
    ])
    assert.deepEqual(
      rows.map((r) => r.label),
      ['W36', 'W37'],
    )
    assert.equal(rows[0].fullPrice, 80)
    assert.equal(rows[0].exchange, 0)
    assert.equal(rows[0].promo, 20)
    assert.ok(Math.abs((rows[1].fullPrice || 0) - 40 / 120 * 100) < 1e-9)
    assert.ok(Math.abs((rows[1].exchange || 0) - 20 / 120 * 100) < 1e-9)
    assert.ok((rows[1].exchange || 0) > 0)
    const sum = (rows[1].fullPrice || 0) + (rows[1].exchange || 0) + (rows[1].promo || 0)
    assert.ok(Math.abs(sum - 100) < 1e-9)
  })
})
