'use client'

import { useEffect, useState } from 'react'
import { useDataCache } from '@/contexts/DataCacheContext'
import { getWomenMonthly, type WomenMonthlyResponse } from '@/lib/api'
import ReportLoadState from '@/components/ReportLoadState'
import MonthlySalesTrend from '@/components/MonthlySalesTrend'
import MonthlyTopProductsTable from '@/components/MonthlyTopProductsTable'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatSekThousands, formatSharePct, formatYoyPct, yoyTone } from '@/lib/monthly-performance-format'

export default function WomenMonthlyPage() {
  const { baseWeek } = useDataCache()
  const [data, setData] = useState<WomenMonthlyResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [reloadToken, setReloadToken] = useState(0)

  useEffect(() => {
    if (!baseWeek) {
      setData(null)
      setError(null)
      setLoading(false)
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    getWomenMonthly(baseWeek)
      .then((payload) => {
        if (!cancelled) setData(payload)
      })
      .catch((e) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : 'Failed to load women’s monthly overview')
          setData(null)
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [baseWeek, reloadToken])

  const empty = !loading && !error && (!data || (data.headline.gross_revenue === 0 && data.categories.length === 0))

  if (loading || error || empty) {
    return (
      <ReportLoadState
        loading={loading}
        error={error}
        empty={empty}
        onRetry={() => setReloadToken((n) => n + 1)}
        loadingTitle="Loading women’s monthly overview"
        loadingHint="Reading Qlik online women’s sales for the last completed month vs last year."
        emptyHint="Upload the Qlik export in Settings for this week, then open Women’s monthly again."
      />
    )
  }

  if (!data) return null
  const h = data.headline

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-gray-900">Women’s monthly · {data.focus_label}</h2>
        <p className="text-sm text-muted-foreground mt-1">{data.note}</p>
        <p className="text-xs text-muted-foreground mt-1">
          {data.focus_start} → {data.focus_end}. Values in SEK ’000. Online only.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Women’s gross</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold tabular-nums">{formatSekThousands(h.gross_revenue)}</p>
            <p className="text-xs text-muted-foreground mt-1">LY {formatSekThousands(h.last_year_gross_revenue)}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">vs last year</CardTitle>
          </CardHeader>
          <CardContent>
            <p className={`text-2xl font-semibold tabular-nums ${yoyTone(h.yoy_pct)}`}>{formatYoyPct(h.yoy_pct)}</p>
            <p className="text-xs text-muted-foreground mt-1">Qty {h.sales_qty.toLocaleString('sv-SE')} · LY {h.last_year_sales_qty.toLocaleString('sv-SE')}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Share of online</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold tabular-nums">{formatSharePct(h.online_share_pct)}</p>
            <p className="text-xs text-muted-foreground mt-1">of {formatSekThousands(h.online_gross_revenue)} online gross</p>
          </CardContent>
        </Card>
      </div>

      <MonthlySalesTrend title="How it sells · 13 months" trend={data.trend} />

      <Card>
        <CardHeader>
          <CardTitle className="text-base">What is selling · categories</CardTitle>
          <p className="text-xs text-muted-foreground">Completed month vs the same month last year</p>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full text-sm min-w-[640px]">
            <thead>
              <tr className="border-b text-left text-muted-foreground">
                <th className="py-2 pr-3 font-medium">Category</th>
                <th className="py-2 px-3 font-medium text-right">Gross</th>
                <th className="py-2 px-3 font-medium text-right">LY gross</th>
                <th className="py-2 px-3 font-medium text-right">YoY</th>
                <th className="py-2 px-3 font-medium text-right">Qty</th>
                <th className="py-2 pl-3 font-medium text-right">Share</th>
              </tr>
            </thead>
            <tbody>
              {data.categories.map((row) => (
                <tr key={row.category} className="border-b last:border-0">
                  <td className="py-2 pr-3 font-medium">{row.category}</td>
                  <td className="py-2 px-3 text-right tabular-nums">{formatSekThousands(row.gross_revenue)}</td>
                  <td className="py-2 px-3 text-right tabular-nums text-muted-foreground">{formatSekThousands(row.last_year_gross_revenue)}</td>
                  <td className={`py-2 px-3 text-right tabular-nums ${yoyTone(row.yoy_pct)}`}>{formatYoyPct(row.yoy_pct)}</td>
                  <td className="py-2 px-3 text-right tabular-nums">{row.sales_qty.toLocaleString('sv-SE')}</td>
                  <td className="py-2 pl-3 text-right tabular-nums">{formatSharePct(row.share_pct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>

      <div>
        <h3 className="text-base font-semibold text-gray-900 mb-2">Top women’s products</h3>
        <MonthlyTopProductsTable
          products={data.top_products}
          topTotal={data.top_total}
          grandTotal={data.grand_total}
          genderFilter="women"
        />
      </div>
    </div>
  )
}
