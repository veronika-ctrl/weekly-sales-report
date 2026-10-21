'use client'

import { useEffect, useMemo, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { useDataCache } from '@/contexts/DataCacheContext'
import { useChartAnimations } from '@/contexts/ChartSettingsContext'
import {
  getCommercialFullPrice,
  type CommercialFullPricePeriod,
  type CommercialFullPriceResponse,
} from '@/lib/api'
import { AMOUNTS_INCL_VAT_NOTE, hasLastYearTotal, lyOrNull, shareChartPoint } from '@/lib/full-price-presentation'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ChartConfig, ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart'
import { Bar, BarChart, CartesianGrid, LabelList, Legend, Line, LineChart, XAxis, YAxis } from '@/lib/recharts'

type Granularity = 'week' | 'month'
type Slide = 'charts' | 'table'

const shareConfig = {
  value: { label: 'This year', color: '#4B5563' },
  lastYear: { label: 'Last year', color: '#F97316' },
} satisfies ChartConfig

const splitConfig = {
  full_price: { label: 'Full price', color: '#4B5563' },
  discounted: { label: 'Discounted', color: '#F97316' },
} satisfies ChartConfig

const thousands = (value: number | null | undefined) =>
  Math.round((value || 0) / 1000).toLocaleString('sv-SE')

const pct = (value: number | null | undefined) => (value == null ? '–' : `${value.toFixed(1)}%`)

const signedPct = (value: number | null | undefined) =>
  value == null ? '–' : `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`

const signedPp = (value: number | null | undefined) =>
  value == null ? '–' : `${value >= 0 ? '+' : ''}${value.toFixed(1)}`

const weekLabel = (w: string) => `W${String(w).split('-')[1]}`
const monthLabel = (m: string) => {
  const [y, mo] = m.split('-')
  const d = new Date(Number(y), Number(mo) - 1, 1)
  return `${d.toLocaleString('en-US', { month: 'short' })} '${y.slice(2)}`
}

const periodLabel = (row: CommercialFullPricePeriod, granularity: Granularity) =>
  granularity === 'week' ? weekLabel(row.week || row.key) : monthLabel(row.month || row.key)

export default function CommercialFullPriceSlide({
  granularity,
  slide,
}: {
  granularity: Granularity
  slide: Slide
}) {
  const { baseWeek } = useDataCache()
  const isAnimationActive = useChartAnimations()
  const [data, setData] = useState<CommercialFullPriceResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

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
    getCommercialFullPrice(baseWeek, granularity)
      .then((payload) => {
        if (!cancelled) setData(payload)
      })
      .catch((e) => {
        if (!cancelled) {
          setData(null)
          setError(e instanceof Error ? e.message : 'Failed to load commercial full price')
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [baseWeek, granularity])

  const rows = useMemo(() => {
    const periods = data?.periods || []
    if (granularity === 'week') return periods
    return periods.filter((row) => (row.total || 0) > 0 || (row.last_year?.total || 0) > 0)
  }, [data, granularity])

  const shareData = useMemo(
    () =>
      rows.map((row) =>
        shareChartPoint({
          label: periodLabel(row, granularity),
          fullPricePct: row.full_price_pct,
          lastYear: row.last_year,
        }),
      ),
    [rows, granularity],
  )
  const splitData = useMemo(
    () =>
      rows.map((row) => ({
        label: periodLabel(row, granularity),
        full_price: row.full_price,
        discounted: row.discounted,
      })),
    [rows, granularity],
  )

  const periodWord = granularity === 'week' ? 'week' : 'month'
  const title =
    slide === 'charts'
      ? `Full price share vs discount · ${periodWord}`
      : `Full price table · ${periodWord}`
  const moved = data?.investor_net_moved || 0
  const empty = !loading && !error && rows.length === 0

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
        <p className="text-sm text-muted-foreground mt-1">
          {data?.note ||
            'Exchanges are excluded. Investors, team, PR & friends discounts are counted as full price. Klaviyo and Customer Care stay in the discount. The existing Full Price vs Sale slides are unchanged.'}
        </p>
        {data?.history_range && (
          <p className="text-xs text-muted-foreground mt-1">
            History: {data.history_range.start} → {data.history_range.end}
            {moved > 0 ? ` · team/investor net counted as full price in this window: ${thousands(moved)} SEK ’000` : ''}
          </p>
        )}
      </div>

      {loading && (
        <div className="flex items-center gap-3">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
          <p className="text-sm text-muted-foreground">Loading commercial full price…</p>
        </div>
      )}
      {error && <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>}
      {empty && (
        <div className="rounded-md border bg-muted/40 p-6 text-sm text-muted-foreground">
          No full-price history for this week yet. Upload the month-named Full Price vs Sale file in Settings. These
          slides use that file plus the discount-type export.
        </div>
      )}

      {!loading && !error && rows.length > 0 && slide === 'charts' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">Full price share % — by {periodWord}</CardTitle>
              <p className="text-xs text-muted-foreground">
                Full price ÷ total after exchanges are removed and team/investor discounts are counted as full price.
                Dashed line is the same {periodWord} last year.
              </p>
            </CardHeader>
            <CardContent className="overflow-visible">
              <ChartContainer config={shareConfig} className="h-[280px] w-full min-w-0 overflow-visible">
                <LineChart data={shareData} margin={{ top: 36, right: 12, left: 12, bottom: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} width={48} />
                  <ChartTooltip content={<ChartTooltipContent formatter={(v: unknown) => pct(v == null ? null : Number(v))} />} />
                  <Line
                    type="monotone"
                    dataKey="value"
                    stroke="#4B5563"
                    strokeWidth={2}
                    dot={{ r: 3 }}
                    connectNulls={false}
                    isAnimationActive={isAnimationActive}
                    name="This year"
                  >
                    <LabelList
                      position="top"
                      offset={10}
                      fontSize={12}
                      fontWeight={600}
                      fill="#1f2937"
                      formatter={(v: unknown) => pct(v == null ? null : Number(v))}
                    />
                  </Line>
                  <Line
                    type="monotone"
                    dataKey="lastYear"
                    stroke="#F97316"
                    strokeWidth={2}
                    strokeDasharray="4 4"
                    dot={{ r: 3 }}
                    connectNulls={false}
                    isAnimationActive={isAnimationActive}
                    name="Last year"
                  />
                </LineChart>
              </ChartContainer>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">Net sales split (SEK ’000) — by {periodWord}</CardTitle>
              <p className="text-xs text-muted-foreground">
                Full price (dark) plus the commercial discount that remains (orange). Team and investor sales sit in full
                price.
              </p>
            </CardHeader>
            <CardContent className="overflow-visible">
              <ChartContainer config={splitConfig} className="h-[280px] w-full min-w-0 overflow-visible">
                <BarChart data={splitData} margin={{ top: 16, right: 12, left: 12, bottom: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} width={48} tickFormatter={(v: number) => thousands(v)} />
                  <ChartTooltip content={<ChartTooltipContent formatter={(v: unknown) => thousands(Number(v ?? 0))} />} />
                  <Legend />
                  <Bar dataKey="full_price" stackId="a" fill="#4B5563" name="Full price" isAnimationActive={isAnimationActive} />
                  <Bar dataKey="discounted" stackId="a" fill="#F97316" name="Discounted" isAnimationActive={isAnimationActive} />
                </BarChart>
              </ChartContainer>
              <p className="text-[11px] text-muted-foreground mt-2">{AMOUNTS_INCL_VAT_NOTE}</p>
            </CardContent>
          </Card>
        </div>
      )}

      {!loading && !error && rows.length > 0 && slide === 'table' && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">
              {granularity === 'week' ? 'Weekly' : 'Monthly'} detail (SEK ’000)
            </CardTitle>
            <p className="text-xs text-muted-foreground">
              {granularity === 'week'
                ? 'Last 8 ISO weeks. Each row is that week only.'
                : 'Last 13 calendar months. The latest month runs through the selected week.'}{' '}
              LY is the same period last year. Δ pp is the full-price share change.
            </p>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-muted-foreground">
                  <th className="py-2 pr-4 font-medium">{granularity === 'week' ? 'Week' : 'Month'}</th>
                  <th className="py-2 px-4 font-medium text-right">Full price</th>
                  <th className="py-2 px-4 font-medium text-right">Discounted</th>
                  <th className="py-2 px-4 font-medium text-right">Total</th>
                  <th className="py-2 px-4 font-medium text-right">Full price %</th>
                  <th className="py-2 px-4 font-medium text-right">LY full price %</th>
                  <th className="py-2 px-4 font-medium text-right">Δ pp</th>
                  <th className="py-2 px-4 font-medium text-right">YoY total %</th>
                  <th className="py-2 px-4 font-medium text-right">YoY full price %</th>
                  <th className="py-2 px-4 font-medium text-right">Weighted disc %</th>
                  <th className="py-2 pl-4 font-medium text-right">LY weighted disc %</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => {
                  const lyOk = hasLastYearTotal(row.last_year)
                  return (
                    <tr key={row.key} className="border-b last:border-0">
                      <td className="py-2 pr-4 font-medium text-gray-900">{periodLabel(row, granularity)}</td>
                      <td className="py-2 px-4 text-right tabular-nums">{thousands(row.full_price)}</td>
                      <td className="py-2 px-4 text-right tabular-nums">{thousands(row.discounted)}</td>
                      <td className="py-2 px-4 text-right tabular-nums">{thousands(row.total)}</td>
                      <td className="py-2 px-4 text-right tabular-nums">{pct(row.full_price_pct)}</td>
                      <td className="py-2 px-4 text-right tabular-nums text-muted-foreground">
                        {pct(lyOrNull(row.last_year, row.last_year?.full_price_pct))}
                      </td>
                      <td className="py-2 px-4 text-right tabular-nums">{signedPp(lyOk ? row.full_price_pct_delta : null)}</td>
                      <td className="py-2 px-4 text-right tabular-nums">{signedPct(lyOk ? row.yoy_total_pct : null)}</td>
                      <td className="py-2 px-4 text-right tabular-nums">{signedPct(lyOk ? row.yoy_full_price_pct : null)}</td>
                      <td className="py-2 px-4 text-right tabular-nums">{pct(row.weighted_discount_pct)}</td>
                      <td className="py-2 pl-4 text-right tabular-nums text-muted-foreground">
                        {pct(lyOrNull(row.last_year, row.last_year?.weighted_discount_pct))}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            <p className="text-[11px] text-muted-foreground mt-3">{AMOUNTS_INCL_VAT_NOTE}</p>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
