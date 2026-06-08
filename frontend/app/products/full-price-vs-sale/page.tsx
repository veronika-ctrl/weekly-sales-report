'use client'

import { useEffect, useMemo, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { useDataCache } from '@/contexts/DataCacheContext'
import { useChartAnimations } from '@/contexts/ChartSettingsContext'
import { getFullPriceVsSale, type FullPriceVsSaleResponse } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ChartConfig, ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart'
import { Bar, BarChart, CartesianGrid, LabelList, Legend, Line, LineChart, XAxis, YAxis } from '@/lib/recharts'

const shareConfig = {
  value: { label: 'This year', color: '#4B5563' },
  lastYear: { label: 'Last year (same week)', color: '#F97316' },
} satisfies ChartConfig

const splitConfig = {
  full_price: { label: 'Full price', color: '#4B5563' },
  discounted: { label: 'Discounted', color: '#F97316' },
} satisfies ChartConfig

const thousands = (value: number | null | undefined) =>
  Math.round((value || 0) / 1000).toLocaleString('sv-SE')

const pct = (value: number | null | undefined) =>
  value == null ? '–' : `${value.toFixed(1)}%`

const weekLabel = (w: string) => `W${String(w).split('-')[1]}`

export default function FullPriceVsSalePage() {
  const { baseWeek } = useDataCache()
  const isAnimationActive = useChartAnimations()
  const [data, setData] = useState<FullPriceVsSaleResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!baseWeek) return
    let cancelled = false
    ;(async () => {
      setLoading(true)
      setError(null)
      try {
        const res = await getFullPriceVsSale(baseWeek, 8)
        if (!cancelled) setData(res)
      } catch (e: any) {
        if (!cancelled) setError(e?.message || 'Failed to load full price vs sale')
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [baseWeek])

  const shareData = useMemo(
    () =>
      (data?.weeks || []).map((w) => ({
        week: weekLabel(w.week),
        value: w.full_price_pct ?? 0,
        lastYear: w.last_year?.full_price_pct ?? 0,
      })),
    [data]
  )

  const splitData = useMemo(
    () =>
      (data?.weeks || []).map((w) => ({
        week: weekLabel(w.week),
        full_price: w.full_price,
        discounted: w.discounted,
      })),
    [data]
  )

  const hasWeeks = (data?.weeks?.length || 0) > 0

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-gray-900">Full Price vs Sale</h2>
        <p className="text-sm text-muted-foreground">
          Weekly net sales split into full price vs discounted, with the same week last year. Built from the
          accumulated daily revenue-over-time export.
        </p>
        {data?.history_range && (
          <p className="text-xs text-muted-foreground mt-1">
            History: {data.history_range.start} → {data.history_range.end} · {data.files_used.length} file(s)
          </p>
        )}
      </div>

      {loading && (
        <div className="flex items-center gap-3">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
          <p className="text-sm text-muted-foreground">Loading full price vs sale...</p>
        </div>
      )}
      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>
      )}

      {!loading && !error && data && !hasWeeks && (
        <div className="rounded-md border bg-muted/40 p-6 text-sm text-muted-foreground">
          No revenue-over-time data found yet. Upload the daily &quot;Full price vs Sale&quot; export in Settings (the
          Shopify order-lines / discounts slot).
        </div>
      )}

      {!loading && !error && data && hasWeeks && (
        <>
          {!data.has_last_year && (
            <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
              No last-year data in history yet, so year-over-year shows 0. Upload last year&apos;s export once (any
              short ranges) and it will fill in automatically.
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium">Full price share %</CardTitle>
                <p className="text-xs text-muted-foreground">Full price net sales / total, this year vs last year</p>
              </CardHeader>
              <CardContent className="overflow-visible">
                <ChartContainer config={shareConfig} className="h-[280px] w-full min-w-0 overflow-visible">
                  <LineChart data={shareData} margin={{ top: 36, right: 12, left: 12, bottom: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="week" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} width={48} />
                    <ChartTooltip
                      content={<ChartTooltipContent formatter={(v: unknown) => pct(Number(v ?? 0))} />}
                    />
                    <Line
                      type="monotone"
                      dataKey="value"
                      stroke="#4B5563"
                      strokeWidth={2}
                      dot={{ r: 3 }}
                      isAnimationActive={isAnimationActive}
                      name="This year"
                    >
                      <LabelList
                        position="top"
                        offset={10}
                        fontSize={12}
                        fontWeight={600}
                        fill="#1f2937"
                        formatter={(v: unknown) => pct(Number(v ?? 0))}
                      />
                    </Line>
                    <Line
                      type="monotone"
                      dataKey="lastYear"
                      stroke="#F97316"
                      strokeWidth={2}
                      strokeDasharray="4 4"
                      dot={{ r: 3 }}
                      isAnimationActive={isAnimationActive}
                      name="Last year (same week)"
                    />
                  </LineChart>
                </ChartContainer>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium">Net sales split (SEK &apos;000)</CardTitle>
                <p className="text-xs text-muted-foreground">Full price vs discounted, this year</p>
              </CardHeader>
              <CardContent className="overflow-visible">
                <ChartContainer config={splitConfig} className="h-[280px] w-full min-w-0 overflow-visible">
                  <BarChart data={splitData} margin={{ top: 16, right: 12, left: 12, bottom: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="week" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} width={48} tickFormatter={(v: number) => thousands(v)} />
                    <ChartTooltip content={<ChartTooltipContent formatter={(v: unknown) => thousands(Number(v ?? 0))} />} />
                    <Legend />
                    <Bar dataKey="full_price" stackId="a" fill="#4B5563" name="Full price" isAnimationActive={isAnimationActive} />
                    <Bar dataKey="discounted" stackId="a" fill="#F97316" name="Discounted" isAnimationActive={isAnimationActive} />
                  </BarChart>
                </ChartContainer>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">Weekly detail (SEK &apos;000)</CardTitle>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="py-2 pr-4 font-medium">Week</th>
                    <th className="py-2 px-4 font-medium text-right">Full price</th>
                    <th className="py-2 px-4 font-medium text-right">Discounted</th>
                    <th className="py-2 px-4 font-medium text-right">Total</th>
                    <th className="py-2 px-4 font-medium text-right">Full price %</th>
                    <th className="py-2 px-4 font-medium text-right">LY full price %</th>
                    <th className="py-2 px-4 font-medium text-right">Δ pp</th>
                    <th className="py-2 pl-4 font-medium text-right">YoY total %</th>
                  </tr>
                </thead>
                <tbody>
                  {data.weeks.map((w) => (
                    <tr key={w.week} className="border-b last:border-0">
                      <td className="py-2 pr-4 font-medium text-gray-900">{weekLabel(w.week)}</td>
                      <td className="py-2 px-4 text-right tabular-nums">{thousands(w.full_price)}</td>
                      <td className="py-2 px-4 text-right tabular-nums">{thousands(w.discounted)}</td>
                      <td className="py-2 px-4 text-right tabular-nums">{thousands(w.total)}</td>
                      <td className="py-2 px-4 text-right tabular-nums">{pct(w.full_price_pct)}</td>
                      <td className="py-2 px-4 text-right tabular-nums text-muted-foreground">
                        {pct(w.last_year?.full_price_pct)}
                      </td>
                      <td className="py-2 px-4 text-right tabular-nums">
                        {w.full_price_pct_delta == null
                          ? '–'
                          : `${w.full_price_pct_delta >= 0 ? '+' : ''}${w.full_price_pct_delta.toFixed(1)}`}
                      </td>
                      <td className="py-2 pl-4 text-right tabular-nums">
                        {w.yoy_total_pct == null
                          ? '–'
                          : `${w.yoy_total_pct >= 0 ? '+' : ''}${w.yoy_total_pct.toFixed(1)}%`}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}
