import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import {
  DISCOUNT_AMOUNT_FORMULA,
  DISCOUNT_AMOUNT_SLICES,
  DISCOUNTED_NET_SLICES,
  buildDiscountShareChartData,
  buildDiscountedNetTypeChartData,
  computeDiscountedNetByType,
  computeRecordedDiscountShare,
  discountShareSumsTo100,
  discountedNetTypeSumsTo100,
} from './discount-share'

describe('computeRecordedDiscountShare', () => {
  it('uses excl. Discount Amount + Exchange Discount as the 100% denominator', () => {
    const share = computeRecordedDiscountShare({
      exchangeDiscount: 12,
      promotionalDiscount: 88,
    })
    assert.equal(share.denom, 100)
    assert.ok(Math.abs((share.exchangePct || 0) - 12) < 1e-9)
    assert.ok(Math.abs((share.promotionalPct || 0) - 88) < 1e-9)
    assert.equal(discountShareSumsTo100(share), true)
    assert.deepEqual(
      share.slices.map((s) => s.id),
      ['exchange', 'promotional'],
    )
  })

  it('matches live W37: AfterShip is ~58.5% of that week’s recorded discount', () => {
    const excl = 19524.282138
    const exch = 27516.033
    const incl = 47040.315138
    assert.ok(Math.abs(excl + exch - incl) < 1e-6)
    const share = computeRecordedDiscountShare({
      exchangeDiscount: exch,
      promotionalDiscount: excl,
    })
    assert.ok(Math.abs((share.exchangePct || 0) - 58.494576) < 0.01)
    assert.ok(Math.abs((share.promotionalPct || 0) - 41.505424) < 0.01)
    assert.equal(discountShareSumsTo100(share), true)
    assert.ok((share.exchangePct || 0) > 50)
  })

  it('matches live last-8-weeks window (~12.8% exchanges) and is not W37’s 58.5%', () => {
    const excl = 1153587.615884
    const exch = 169889.7959
    const incl = 1323477.411784
    assert.ok(Math.abs(excl + exch - incl) < 1e-4)
    const share = computeRecordedDiscountShare({
      exchangeDiscount: exch,
      promotionalDiscount: excl,
    })
    assert.ok(Math.abs((share.exchangePct || 0) - 12.836622) < 0.01)
    assert.ok(Math.abs((share.promotionalPct || 0) - 87.163378) < 0.01)
    assert.equal(discountShareSumsTo100(share), true)
    assert.ok((share.exchangePct || 0) < 20)
    assert.ok((share.exchangePct || 0) < 50)
  })

  it('carves extra discount-$ types out of the promotional remainder', () => {
    const share = computeRecordedDiscountShare({
      exchangeDiscount: 10,
      promotionalDiscount: 90,
      others: [{ id: 'staff', label: 'Staff discount', color: '#A855F7', amount: 15 }],
    })
    assert.equal(share.denom, 100)
    assert.ok(Math.abs((share.exchangePct || 0) - 10) < 1e-9)
    assert.ok(Math.abs((share.promotionalPct || 0) - 90) < 1e-9)
    assert.deepEqual(
      share.slices.map((s) => [s.id, s.pct]),
      [
        ['exchange', 10],
        ['staff', 15],
        ['promotional', 75],
      ],
    )
    const stacked = share.slices.reduce((sum, s) => sum + (s.pct || 0), 0)
    assert.ok(Math.abs(stacked - 100) < 1e-9)
  })

  it('returns null shares when there is no recorded discount', () => {
    const share = computeRecordedDiscountShare({
      exchangeDiscount: 0,
      promotionalDiscount: 0,
    })
    assert.equal(share.denom, null)
    assert.equal(share.exchangePct, null)
    assert.equal(discountShareSumsTo100(share), false)
  })
})

describe('buildDiscountShareChartData', () => {
  it('maps each week independently and does not reuse the window 12.8%', () => {
    const rows = buildDiscountShareChartData([
      { label: 'W36', exchangeDiscount: 3536.941, promotionalDiscount: 33930.167852 },
      { label: 'W37', exchangeDiscount: 27516.033, promotionalDiscount: 19524.282138 },
    ])
    assert.deepEqual(
      rows.map((r) => r.label),
      ['W36', 'W37'],
    )
    assert.ok(Math.abs((rows[0].exchange || 0) - 9.440123) < 0.01)
    assert.ok(Math.abs((rows[1].exchange || 0) - 58.494576) < 0.01)
    assert.notEqual(Math.round(rows[1].exchange || 0), 13)
    const sum = (rows[1].exchange || 0) + (rows[1].promotional || 0)
    assert.ok(Math.abs(sum - 100) < 1e-9)
  })
})

describe('computeDiscountedNetByType', () => {
  it('is 100% of discounted net by pricing type, not discount $', () => {
    // Live W37 excl net types: code + price drop = discounted net; compare-at/both = 0.
    const compareAt = 0
    const discountCode = 138011.009412
    const both = 0
    const priceDrop = 333917.673096
    const discountedNet = 471928.682508
    assert.ok(Math.abs(compareAt + discountCode + both + priceDrop - discountedNet) < 1e-4)
    const share = computeDiscountedNetByType({ compareAt, discountCode, both, priceDrop })
    assert.equal(discountedNetTypeSumsTo100(share), true)
    const drop = share.slices.find((s) => s.id === 'priceDrop')
    const code = share.slices.find((s) => s.id === 'discountCode')
    assert.ok((drop?.pct || 0) > 70)
    assert.ok((code?.pct || 0) > 25)
    assert.match(DISCOUNT_AMOUNT_FORMULA, /not discount \$/)
    assert.equal(
      DISCOUNTED_NET_SLICES.every((s) => s.kind === 'discounted_net'),
      true,
    )
  })

  it('keeps a stable slice id list so more types can be added later', () => {
    assert.deepEqual(
      DISCOUNT_AMOUNT_SLICES.map((s) => s.id),
      ['exchange', 'promotional'],
    )
    assert.deepEqual(
      DISCOUNTED_NET_SLICES.map((s) => s.id),
      ['compareAt', 'discountCode', 'both', 'priceDrop'],
    )
  })
})

describe('buildDiscountedNetTypeChartData', () => {
  it('maps each week’s pricing-type mix independently', () => {
    const rows = buildDiscountedNetTypeChartData([
      { label: 'W36', compareAt: 0, discountCode: 50, both: 0, priceDrop: 50 },
      { label: 'W37', compareAt: 0, discountCode: 25, both: 0, priceDrop: 75 },
    ])
    assert.equal(rows[0].discountCode, 50)
    assert.equal(rows[0].priceDrop, 50)
    assert.equal(rows[1].discountCode, 25)
    assert.equal(rows[1].priceDrop, 75)
  })
})
