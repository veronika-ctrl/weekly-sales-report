import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { describe, it } from 'node:test'
import { fileURLToPath } from 'node:url'

import { bucketHasShipping, claimsPageNotes } from './claims-columns.ts'

const here = dirname(fileURLToPath(import.meta.url))

describe('bucketHasShipping', () => {
  it('is false when every shipping amount in the table is 0', () => {
    assert.equal(
      bucketHasShipping([
        { freight_sek: 0 },
        { freight_sek: 0 },
        { freight_sek: null },
      ]),
      false,
    )
  })

  it('is true when any row in that table has shipping', () => {
    assert.equal(
      bucketHasShipping([{ freight_sek: 0 }, { freight_sek: 275 }, { freight_sek: 0 }]),
      true,
    )
  })
})

describe('claimsPageNotes', () => {
  it('drops the extra-discount note and keeps shipping notes', () => {
    const notes = claimsPageNotes([
      'Shipping is the 2026 carrier price we pay.',
      'No extra discount is attached to these orders in this file.',
    ])
    assert.deepEqual(notes, ['Shipping is the 2026 carrier price we pay.'])
  })
})

describe('claims page columns', () => {
  it('hides empty replacement-product shipping and removes extra discount everywhere', () => {
    const page = readFileSync(join(here, '../app/claims/page.tsx'), 'utf8')
    assert.match(page, /showShipping=\{bucketHasShipping\(data\.categories\)\}/)
    assert.doesNotMatch(page, /Extra discount/i)
    assert.doesNotMatch(page, /discount_sek/)
    assert.match(page, /title="Shipping cost"/)
    assert.match(page, /title="Landed cost"/)

    const country = page.slice(page.indexOf('title="Destination country"'), page.indexOf('title="Destination country"') + 120)
    const method = page.slice(page.indexOf('title="Shipping method"'), page.indexOf('title="Shipping method"') + 160)
    assert.doesNotMatch(country, /showShipping/)
    assert.doesNotMatch(method, /bucketHasShipping|showShipping=\{false\}/)
    assert.match(page, /<th className="py-2 pr-3">Shipping<\/th>/)
    assert.match(page, /Shipping cost/)
  })
})
