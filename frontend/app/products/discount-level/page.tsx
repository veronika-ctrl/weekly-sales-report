'use client'

import { useEffect, useMemo, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { useDataCache } from '@/contexts/DataCacheContext'
import { useChartAnimations } from '@/contexts/ChartSettingsContext'
import { getDiscountsLevel, type DiscountLevelResponse } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ChartConfig, ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart'
import { CartesianGrid, LabelList, Line, LineChart, XAxis, YAxis } from '@/lib/recharts'

type MetricKey = 'discount_level_pct' | 'discounted_share_pct' | 'discount_amount'

const chartConfig = {
  value: { label: 'This year', color: '#4B5563' },
  lastYear: { label: 'Last year (same week)', color: '#F97316' },
} satisfies ChartConfig

function formatMetric(value: number, key: MetricKey) {
  if (key === 'discount_amount') {
    const th = Math.round((value || 0) / 1000)
    return th.toLocaleString('sv-SE')
  }
  return `${(value || 0).toFixed(1)}%`
}

export default function DiscountLevelPage() {
  const { baseWeek } = useDataCache()
  const isAnimationActive = useChartAnimations()
  const [data, setData] = useState<DiscountLevelResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [market, setMarket] = useState<string>('Total')

  useEffect(() => {
    if (!baseWeek) return
    let cancelled = false
    ;(async () => {
      setLoading(true)
      setError(null)
      try {
        const res = await getDiscountsLevel(baseWeek, 8)
        if (!cancelled) {
          setData(res)
          if (market !== 'Total' && !res.markets?.includes(market)) setMarket('Total')
        }
      } catch (e: any) {
        if (!cancelled) setError(e?.message || 'Failed to load discount level')
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [baseWeek])

  const markets = useMemo(() => ['Total', ...(data?.markets || [])], [data])

  const buildChartData = (key: MetricKey) =>
    (data?.weeks || []).map((w) => {
      const point = market === 'Total' ? w.total : w.markets?.[market]
      const ly = point?.last_year
      return {
        week: `W${String(w.week).split('-')[1]}`,
        value: Number(point?.[key] || 0),
        lastYear: Number(ly?.[key] || 0),
      }
    })

  const cards: Array<{ key: MetricKey; label: string; subtitle: string }> = [
    { key: 'discount_level_pct', label: 'Discount Level %', subtitle: 'Estimated markdown as % of gross before discount' },
    { key: 'discounted_share_pct', label: 'Discounted Sales Share %', subtitle: 'Discounted net sales / total net sales' },
    { key: 'discount_amount', label: 'Discount Amount (SEK \'000)', subtitle: 'Estimated markdown amount' },
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Discount Level</h2>
          <p className="text-sm text-muted-foreground">8-week trend with same-week last year comparison.</p>
        </div>
        <div className="flex items-center gap-2">
          <label htmlFor="market" className="text-sm text-gray-700">Market</label>
          <select
            id="market"
            value={market}
            onChange={(e) => setMarket(e.target.value)}
            className="rounded-md border bg-white px-3 py-2 text-sm"
          >
            {markets.map((m) => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>
        </div>
      </div>

      {loading && (
        <div className="flex items-center gap-3">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
          <p className="text-sm text-muted-foreground">Loading discount level metrics...</p>
        </div>
      )}
      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>
      )}
      {!loading && !error && data && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {cards.map(({ key, label, subtitle }) => {
            const chartData = buildChartData(key)
            return (
              <Card key={key}>
                <CardHeader>
                  <CardTitle className="text-sm font-medium">{label}</CardTitle>
                  <p className="text-xs text-muted-foreground">{subtitle}</p>
                </CardHeader>
                <CardContent className="overflow-visible">
                  <ChartContainer config={chartConfig} className="h-[260px] w-full min-w-0 overflow-visible">
                    <LineChart data={chartData} margin={{ top: 36, right: 12, left: 12, bottom: 8 }}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} />
                      <XAxis dataKey="week" tick={{ fontSize: 11 }} />
                      <YAxis tick={{ fontSize: 11 }} width={48} />
                      <ChartTooltip
                        content={
                          <ChartTooltipContent formatter={(v) => formatMetric(Number(v || 0), key)} />
                        }
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
                          formatter={(v: unknown) => formatMetric(Number(v ?? 0), key)}
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
            )
          })}
        </div>
      )}
    </div>
  )
}
