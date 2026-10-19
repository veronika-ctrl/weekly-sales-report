import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { describe, it } from 'node:test'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))

describe('online summary new/returning net rows', () => {
  it('shows new and returning net revenue after customer counts', () => {
    const src = readFileSync(join(here, '../components/MetricsPreviewMTD.tsx'), 'utf8')
    assert.match(src, /'Returning Net Revenue'/)
    assert.match(src, /'New Net Revenue'/)
    assert.match(src, /'returning_customers_net_revenue'/)
    assert.match(src, /'new_customers_net_revenue'/)
    const returningCount = src.indexOf("'returning_customers'")
    const returningNet = src.indexOf("'returning_customers_net_revenue'")
    const newCount = src.indexOf("'new_customers'")
    const newNet = src.indexOf("'new_customers_net_revenue'")
    assert.ok(returningCount >= 0 && returningNet > returningCount)
    assert.ok(newCount > returningNet && newNet > newCount)
  })
})
