'use client'

import { useEffect, useMemo, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { useDataCache } from '@/contexts/DataCacheContext'
import { useChartAnimations } from '@/contexts/ChartSettingsContext'
import {
  getFullPriceVsSale,
  getFullPriceVsSaleMonthly,
  type FullPriceVsSaleResponse,
  type FullPriceVsSaleMonthlyResponse,
} from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ChartConfig, ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart'
import { Bar, BarChart, CartesianGrid, LabelList, Legend, Line, LineChart, XAxis, YAxis } from '@/lib/recharts'

type View = 'week' | 'month'

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

const pct = (value: number | null | undefined) =>
  value == null ? '–' : `${value.toFixed(1)}%`

const signedPct = (value: number | null | undefined) =>
  value == null ? '–' : `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`

const signedPp = (value: number | null | undefined) =>
  value == null ? '–' : `${value >= 0 ? '+' : ''}${value.toFixed(1)}`

const wdPpDelta = (
  current: number | null | undefined,
  lastYear: number | null | undefined,
) => (current == null || lastYear == null ? null : current - lastYear)

const weekLabel = (w: string) => `W${String(w).split('-')[1]}`
const monthLabel = (m: string) => {
  const [y, mo] = m.split('-')
  const d = new Date(Number(y), Number(mo) - 1, 1)
  return `${d.toLocaleString('en-US', { month: 'short' })} '${y.slice(2)}`
}

export default function FullPriceVsSalePage() {
  const { baseWeek } = useDataCache()
  const isAnimationActive = useChartAnimations()
  const [view, setView] = useState<View>('week')
  const [weekly, setWeekly] = useState<FullPriceVsSaleResponse | null>(null)
  const [monthly, setMonthly] = useState<FullPriceVsSaleMonthlyResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!baseWeek) return
    let cancelled = false
    ;(async () => {
      setLoading(true)
      setError(null)
      try {
        const [w, m] = await Promise.all([
          getFullPriceVsSale(baseWeek, 8),
          getFullPriceVsSaleMonthly(baseWeek, 13),
        ])
        if (!cancelled) {
          setWeekly(w)
          setMonthly(m)
        }
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

  // Weekly (ascending already)
  const weeklyShare = useMemo(
    () =>
      (weekly?.weeks || []).map((w) => ({
        label: weekLabel(w.week),
        value: w.full_price_pct ?? 0,
        lastYear: w.last_year?.full_price_pct ?? 0,
      })),
    [weekly]
  )
  const weeklySplit = useMemo(
    () =>
      (weekly?.weeks || []).map((w) => ({
        label: weekLabel(w.week),
        full_price: w.full_price,
        discounted: w.discounted,
      })),
    [weekly]
  )

  // Monthly comes newest-first from the API; display oldest→newest and drop
  // fully-empty months (gaps where nothing has been uploaded for either year).
  const monthsAsc = useMemo(
    () =>
      [...(monthly?.months_data || [])]
        .reverse()
        .filter((m) => (m.total || 0) > 0 || (m.last_year?.total || 0) > 0),
    [monthly]
  )
  const monthlyShare = useMemo(
    () =>
      monthsAsc.map((m) => ({
        label: monthLabel(m.month),
        value: m.full_price_pct ?? 0,
        lastYear: m.last_year?.full_price_pct ?? 0,
      })),
    [monthsAsc]
  )
  const monthlySplit = useMemo(
    () =>
      monthsAsc.map((m) => ({
        label: monthLabel(m.month),
        full_price: m.full_price,
        discounted: m.discounted,
      })),
    [monthsAsc]
  )

  const data = view === 'week' ? weekly : monthly
  const hasRows = view === 'week' ? (weekly?.weeks?.length || 0) > 0 : (monthly?.months_data?.length || 0) > 0
  const shareData = view === 'week' ? weeklyShare : monthlyShare
  const splitData = view === 'week' ? weeklySplit : monthlySplit
  const periodHeader = view === 'week' ? 'Week' : 'Month'
  const ytd = monthly?.ytd || null
  const ytdDateRange =
    ytd?.fy_start && ytd?.end ? `${ytd.fy_start} → ${ytd.end}` : null

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Full Price vs Sale</h2>
          <p className="text-sm text-muted-foreground">
            Net sales split into full price vs discounted, vs last year. All monetary values are shown in{' '}
            <strong>SEK</strong> (thousands) to match the rest of this app.
          </p>
          {data?.history_range && (
            <p className="text-xs text-muted-foreground mt-1">
              History: {data.history_range.start} → {data.history_range.end} · {data.files_used.length} file(s)
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-600">View:</span>
          <div className="inline-flex rounded-md border bg-white p-0.5">
            {(['week', 'month'] as View[]).map((v) => (
              <button
                key={v}
                onClick={() => setView(v)}
                className={`px-3 py-1 text-sm font-medium rounded ${
                  view === v ? 'bg-gray-900 text-white' : 'text-gray-600 hover:bg-gray-100'
                }`}
              >
                {v === 'week' ? 'Week' : 'Month'}
              </button>
            ))}
          </div>
        </div>
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

      {!loading && !error && data && !hasRows && (
        <div className="rounded-md border bg-muted/40 p-6 text-sm text-muted-foreground">
          No revenue-over-time data found yet. Upload the daily &quot;Full price vs Sale&quot; export in Settings.
        </div>
      )}

      {!loading && !error && data && hasRows && (
        <>
          {!data.has_last_year && (
            <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
              No last-year data in history yet, so year-over-year shows 0. Upload last year&apos;s export once and it
              will fill in automatically.
            </div>
          )}

          {data.fx?.applied ? (
            <div className="rounded-md border border-emerald-200 bg-emerald-50/70 p-4 text-sm text-emerald-950">
              <p className="font-medium">Currency (fixed)</p>
              <p className="text-xs mt-1 leading-relaxed">
                The Shopify app export is in <strong>{data.fx.source_currency ?? 'USD'}</strong> (shop money). This
                report converts every day to <strong>{data.fx.target_currency ?? 'SEK'}</strong> so it aligns with Qlik
                and the other weekly reports. We use the{' '}
                <strong>European Central Bank (ECB) daily {data.fx.source_currency ?? 'USD'}/{data.fx.target_currency ?? 'SEK'} rate</strong>{' '}
                for each calendar day (Frankfurter API); weekends and holidays use the last published ECB rate.
                {data.fx.sample_rate != null && (
                  <> Latest rate in history: ≈ {data.fx.sample_rate.toFixed(2)} SEK/USD.</>
                )}{' '}
                Percentages (full price share, weighted discount) are not affected by conversion.
              </p>
            </div>
          ) : data.currency === 'SEK' ? null : (
            <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
              Currency conversion to SEK was not applied
              {data.fx?.error ? ` (${data.fx.error})` : ''}. Amounts may still be in USD.
            </div>
          )}

          <div className="rounded-md border border-blue-100 bg-blue-50/60 p-4 text-sm text-blue-950 space-y-2">
            <p className="font-medium">How to read this page</p>
            <ul className="text-xs text-blue-900/90 space-y-1 list-disc pl-4">
              <li>
                <strong>Week / Month</strong> only changes the charts and table below. The three summary cards stay the
                same — they are always <strong>fiscal year-to-date (YTD)</strong>, not weekly or monthly totals.
              </li>
              <li>
                <strong>Week view</strong> — last 8 ISO weeks (Mon–Sun). Each row sums the daily Shopify export for that
                week. Good for operations.
              </li>
              <li>
                <strong>Month view</strong> — last 13 calendar months. The current month is month-to-date (cut off at your
                selected week&apos;s end date). Good for board / KPI reporting.
              </li>
              <li>
                <strong>LY</strong> = same period last year. <strong>Δ pp</strong> = percentage-point change vs LY.
                <strong> YoY total %</strong> = change in <strong>total net sales</strong> (full price + discounted).
                <strong> YoY full price %</strong> = change in <strong>absolute full-price revenue</strong> only.
              </li>
              <li>
                <strong>Weighted disc %</strong> = discount depth on discounted sales only. <strong>LY weighted disc
                %</strong> compares the same metric to last year.
              </li>
            </ul>
          </div>

          {/* Fiscal YTD summary — same on Week and Month tabs; only charts/table below switch */}
          {ytd && (
            <div className="space-y-2">
              <div>
                <h3 className="text-sm font-medium text-gray-900">Fiscal year-to-date summary</h3>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Fixed period: {ytdDateRange ?? ytd.label}. Sums every day in your Shopify export from 1 April through
                  your selected week&apos;s end date. Does not change when you switch Week / Month.
                </p>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-xs font-medium text-muted-foreground">
                      {ytd.label} · Full price share
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-semibold text-gray-900">{pct(ytd.full_price_pct)}</div>
                    <div className="text-xs text-muted-foreground mt-1">
                      LY {pct(ytd.last_year?.full_price_pct)} · {signedPp(ytd.full_price_pct_delta)} pp
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">
                      Full price sales {thousands(ytd.full_price)} · LY {thousands(ytd.last_year?.full_price)} ·{' '}
                      {signedPct(ytd.yoy_full_price_pct)}
                    </div>
                    <p className="text-[11px] text-muted-foreground mt-2 leading-snug">
                      Share = full price ÷ total. Second line = absolute full-price revenue YoY (SEK).
                    </p>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-xs font-medium text-muted-foreground">
                      {ytd.label} · Net sales (SEK &apos;000)
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-semibold text-gray-900">{thousands(ytd.total)}</div>
                    <div className="text-xs text-muted-foreground mt-1">
                      LY {thousands(ytd.last_year?.total)} · {signedPct(ytd.yoy_total_pct)}
                    </div>
                    <p className="text-[11px] text-muted-foreground mt-2 leading-snug">
                      Sum of daily &quot;Total&quot; column (all sale types). YoY % is total net sales growth, not
                      full-price-only growth.
                    </p>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-xs font-medium text-muted-foreground">
                      {ytd.label} · Discounted (SEK &apos;000)
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-semibold text-gray-900">{thousands(ytd.discounted)}</div>
                    <div className="text-xs text-muted-foreground mt-1">LY {thousands(ytd.last_year?.discounted)}</div>
                    {ytd.weighted_discount_pct != null && (
                      <div className="text-xs text-muted-foreground mt-1">
                        Weighted disc {pct(ytd.weighted_discount_pct)} · LY{' '}
                        {pct(ytd.last_year?.weighted_discount_pct)} ·{' '}
                        {signedPp(wdPpDelta(ytd.weighted_discount_pct, ytd.last_year?.weighted_discount_pct))} pp
                      </div>
                    )}
                    <p className="text-[11px] text-muted-foreground mt-2 leading-snug">
                      Total − full price. Weighted disc % = markdown depth on those discounted sales vs last year.
                    </p>
                  </CardContent>
                </Card>
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium">
                  Full price share % — by {view === 'week' ? 'week' : 'month'}
                </CardTitle>
                <p className="text-xs text-muted-foreground">
                  {view === 'week'
                    ? 'Last 8 weeks. Each point = that week’s full price ÷ total, vs the same ISO week last year.'
                    : 'Last 13 months. Each point = that month’s full price ÷ total; current month is month-to-date.'}
                </p>
              </CardHeader>
              <CardContent className="overflow-visible">
                <ChartContainer config={shareConfig} className="h-[280px] w-full min-w-0 overflow-visible">
                  <LineChart data={shareData} margin={{ top: 36, right: 12, left: 12, bottom: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} width={48} />
                    <ChartTooltip content={<ChartTooltipContent formatter={(v: unknown) => pct(Number(v ?? 0))} />} />
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
                      name="Last year"
                    />
                  </LineChart>
                </ChartContainer>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-sm font-medium">
                  Net sales split (SEK &apos;000) — by {view === 'week' ? 'week' : 'month'}
                </CardTitle>
                <p className="text-xs text-muted-foreground">
                  Stacked bars: full price (dark) + discounted (orange) per {view === 'week' ? 'week' : 'month'}.
                  Separate from the YTD cards above.
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
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">{periodHeader}ly detail (SEK &apos;000)</CardTitle>
              <p className="text-xs text-muted-foreground">
                {view === 'week'
                  ? 'One row per ISO week (last 8). Totals are that week only — not YTD.'
                  : 'One row per calendar month (last 13). Latest month is partial (through your selected week). Not YTD.'}
              </p>
              {!data.has_discount && (
                <p className="text-xs text-muted-foreground">
                  Weighted discount % stays blank until you upload the export with a &quot;Discount Amount&quot; column.
                </p>
              )}
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="py-2 pr-4 font-medium">{periodHeader}</th>
                    <th className="py-2 px-4 font-medium text-right">Full price</th>
                    <th className="py-2 px-4 font-medium text-right">Discounted</th>
                    <th className="py-2 px-4 font-medium text-right">Total</th>
                    <th className="py-2 px-4 font-medium text-right">Full price %</th>
                    <th className="py-2 px-4 font-medium text-right">LY full price %</th>
                    <th className="py-2 px-4 font-medium text-right">Δ pp</th>
                    <th className="py-2 px-4 font-medium text-right">YoY total %</th>
                    <th className="py-2 px-4 font-medium text-right">YoY full price %</th>
                    <th className="py-2 px-4 font-medium text-right">Weighted disc %</th>
                    <th className="py-2 px-4 font-medium text-right">LY weighted disc %</th>
                    <th className="py-2 pl-4 font-medium text-right">Δ wd pp</th>
                  </tr>
                </thead>
                <tbody>
                  {view === 'week'
                    ? (weekly?.weeks || []).map((w) => (
                        <tr key={w.week} className="border-b last:border-0">
                          <td className="py-2 pr-4 font-medium text-gray-900">{weekLabel(w.week)}</td>
                          <td className="py-2 px-4 text-right tabular-nums">{thousands(w.full_price)}</td>
                          <td className="py-2 px-4 text-right tabular-nums">{thousands(w.discounted)}</td>
                          <td className="py-2 px-4 text-right tabular-nums">{thousands(w.total)}</td>
                          <td className="py-2 px-4 text-right tabular-nums">{pct(w.full_price_pct)}</td>
                          <td className="py-2 px-4 text-right tabular-nums text-muted-foreground">{pct(w.last_year?.full_price_pct)}</td>
                          <td className="py-2 px-4 text-right tabular-nums">{signedPp(w.full_price_pct_delta)}</td>
                          <td className="py-2 px-4 text-right tabular-nums">{signedPct(w.yoy_total_pct)}</td>
                          <td className="py-2 px-4 text-right tabular-nums">{signedPct(w.yoy_full_price_pct)}</td>
                          <td className="py-2 px-4 text-right tabular-nums">{pct(w.weighted_discount_pct)}</td>
                          <td className="py-2 px-4 text-right tabular-nums text-muted-foreground">
                            {pct(w.last_year?.weighted_discount_pct)}
                          </td>
                          <td className="py-2 pl-4 text-right tabular-nums">
                            {signedPp(wdPpDelta(w.weighted_discount_pct, w.last_year?.weighted_discount_pct))}
                          </td>
                        </tr>
                      ))
                    : monthsAsc.map((m) => (
                        <tr key={m.month} className="border-b last:border-0">
                          <td className="py-2 pr-4 font-medium text-gray-900">{monthLabel(m.month)}</td>
                          <td className="py-2 px-4 text-right tabular-nums">{thousands(m.full_price)}</td>
                          <td className="py-2 px-4 text-right tabular-nums">{thousands(m.discounted)}</td>
                          <td className="py-2 px-4 text-right tabular-nums">{thousands(m.total)}</td>
                          <td className="py-2 px-4 text-right tabular-nums">{pct(m.full_price_pct)}</td>
                          <td className="py-2 px-4 text-right tabular-nums text-muted-foreground">{pct(m.last_year?.full_price_pct)}</td>
                          <td className="py-2 px-4 text-right tabular-nums">{signedPp(m.full_price_pct_delta)}</td>
                          <td className="py-2 px-4 text-right tabular-nums">{signedPct(m.yoy_total_pct)}</td>
                          <td className="py-2 px-4 text-right tabular-nums">{signedPct(m.yoy_full_price_pct)}</td>
                          <td className="py-2 px-4 text-right tabular-nums">{pct(m.weighted_discount_pct)}</td>
                          <td className="py-2 px-4 text-right tabular-nums text-muted-foreground">
                            {pct(m.last_year?.weighted_discount_pct)}
                          </td>
                          <td className="py-2 pl-4 text-right tabular-nums">
                            {signedPp(wdPpDelta(m.weighted_discount_pct, m.last_year?.weighted_discount_pct))}
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
