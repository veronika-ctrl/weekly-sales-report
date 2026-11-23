import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { reportingWeekUsesUkVatAdjustment, UK_VAT_NOTE } from './uk-vat-window'

describe('UK VAT window note', () => {
  it('uses the disclosure sentence', () => {
    assert.equal(
      UK_VAT_NOTE,
      'UK revenue adjusted for missing VAT (orders over £135, 29 Sep to 9 Nov 2026).',
    )
  })

  it('matches weeks that contain the missing-VAT window, and 2027 last year', () => {
    assert.equal(reportingWeekUsesUkVatAdjustment('2026-39'), false)
    assert.equal(reportingWeekUsesUkVatAdjustment('2026-40'), true)
    assert.equal(reportingWeekUsesUkVatAdjustment('2026-46'), true)
    assert.equal(reportingWeekUsesUkVatAdjustment('2026-52'), true)
    assert.equal(reportingWeekUsesUkVatAdjustment('2027-40'), true)
    assert.equal(reportingWeekUsesUkVatAdjustment('2027-10'), false)
  })
})
