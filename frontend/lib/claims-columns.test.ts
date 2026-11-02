import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { describe, it } from 'node:test'
import { fileURLToPath } from 'node:url'

import { hasNonZeroAmount, visibleClaimsTableColumns } from './claims-columns.ts'

const here = dirname(fileURLToPath(import.meta.url))

const replacementProduct = [
  { freight_sek: 0, discount_sek: 0, product_cost_sek: 6380 },
  { freight_sek: 0, discount_sek: 0, product_cost_sek: 5976 },
  { freight_sek: 0, discount_sek: 0, product_cost_sek: 1496 },
  { freight_sek: 0, discount_sek: 0, product_cost_sek: 791 },
  { freight_sek: 0, discount_sek: 0, product_cost_sek: 778 },
  { freight_sek: 0, discount_sek: 0, product_cost_sek: 0 },
]

const destinationCountry = [
  { freight_sek: 1812, discount_sek: 0, product_cost_sek: 4828 },
  { freight_sek: 1448, discount_sek: 0, product_cost_sek: 2480 },
  { freight_sek: 275, discount_sek: 0, product_cost_sek: 2224 },
  { freight_sek: 0, discount_sek: 0, product_cost_sek: 81 },
]

describe('visibleClaimsTableColumns', () => {
  it('omits Extra discount and product-type shipping when every row is 0', () => {
    assert.deepEqual(
      visibleClaimsTableColumns(replacementProduct).map((column) => column.header),
      ['Claims', 'Units', 'Landed cost'],
    )
    assert.equal(
      visibleClaimsTableColumns(replacementProduct).some((column) => column.id === 'freight_sek'),
      false,
    )
    assert.equal(
      visibleClaimsTableColumns(replacementProduct).some((column) => column.id === 'discount_sek'),
      false,
    )
  })

  it('keeps Shipping on destination country when that table has real amounts, and still hides all-zero Extra discount', () => {
    const headers = visibleClaimsTableColumns(destinationCountry).map((column) => column.header)
    assert.deepEqual(headers, ['Claims', 'Units', 'Landed cost', 'Shipping'])
    assert.equal(headers.includes('Extra discount'), false)
  })

  it('shows Extra discount again when any row has a discount amount', () => {
    const headers = visibleClaimsTableColumns([
      { freight_sek: 80, discount_sek: 0 },
      { freight_sek: 0, discount_sek: 40 },
    ]).map((column) => column.header)
    assert.deepEqual(headers, ['Claims', 'Units', 'Landed cost', 'Shipping', 'Extra discount'])
  })
})

describe('hasNonZeroAmount', () => {
  it('hides the Extra discounts KPI and the orders Discount column when every value is 0', () => {
    assert.equal(hasNonZeroAmount([{ discount_sek: 0 }, { discount_sek: 0 }], 'discount_sek'), false)
    assert.equal(hasNonZeroAmount([{ discount_sek: 0 }, { discount_sek: 15 }], 'discount_sek'), true)
    assert.equal(hasNonZeroAmount([{ freight_sek: 9423.22 }], 'freight_sek'), true)
    assert.equal(hasNonZeroAmount([{ freight_sek: 0 }, { freight_sek: null }], 'freight_sek'), false)
  })
})

describe('claims page column wiring', () => {
  it('renders tables from visibleClaimsTableColumns and omits all-zero Extra discount / shipping KPIs', () => {
    const page = readFileSync(join(here, '../app/claims/page.tsx'), 'utf8')
    assert.match(page, /visibleClaimsTableColumns\(rows\)/)
    assert.match(page, /hasNonZeroAmount\(\[totals\], 'discount_sek'\)/)
    assert.match(page, /hasNonZeroAmount\(\[totals\], 'freight_sek'\)/)
    assert.match(page, /hasNonZeroAmount\(data\?\.orders \?\? \[\], 'discount_sek'\)/)
    assert.match(page, /hasNonZeroAmount\(data\?\.orders \?\? \[\], 'freight_sek'\)/)
    assert.match(page, /showDiscountKpi/)
    assert.match(page, /showOrderDiscount/)
    assert.match(page, /showOrderShipping/)
    assert.match(page, /title="Extra discounts"/)
    assert.match(page, /title="Shipping cost"/)
    assert.doesNotMatch(page, /claimsPageNotes/)
  })
})
