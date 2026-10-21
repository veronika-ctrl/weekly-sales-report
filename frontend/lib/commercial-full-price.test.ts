import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { describe, it } from 'node:test'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))

describe('commercial full price slides', () => {
  it('adds four sales-report tabs before Top Markets and keeps the existing slide', () => {
    const src = readFileSync(join(here, '../components/SidebarLayout.tsx'), 'utf8')
    const topMarkets = src.indexOf('href="/top-markets"')
    const links = [
      'href="/full-price-commercial/week-charts"',
      'href="/full-price-commercial/week-table"',
      'href="/full-price-commercial/month-charts"',
      'href="/full-price-commercial/month-table"',
    ]
    for (const link of links) {
      const at = src.indexOf(link)
      assert.ok(at >= 0, link)
      assert.ok(at < topMarkets, `${link} should sit before Top Markets`)
    }
    assert.match(src, /href="\/products\/full-price-vs-sale"/)
  })

  it('loads /api/discounts/commercial-full-price and does not replace the old page', () => {
    const slide = readFileSync(join(here, '../components/CommercialFullPriceSlide.tsx'), 'utf8')
    const api = readFileSync(join(here, 'api.ts'), 'utf8')
    const oldPage = readFileSync(join(here, '../app/products/full-price-vs-sale/page.tsx'), 'utf8')
    assert.match(slide, /getCommercialFullPrice/)
    assert.match(slide, /Full price share vs discount/)
    assert.doesNotMatch(slide, /loadAllData/)
    const start = api.indexOf('export async function getCommercialFullPrice')
    assert.ok(start >= 0)
    assert.match(api.slice(start, start + 700), /\/api\/discounts\/commercial-full-price/)
    assert.match(oldPage, /getFullPriceVsSale/)
    assert.doesNotMatch(oldPage, /getCommercialFullPrice/)
  })
})
