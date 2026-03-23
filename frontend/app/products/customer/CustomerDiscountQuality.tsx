'use client'

import { useEffect, useMemo, useState } from 'react'
import { Info, Loader2 } from 'lucide-react'
import { CartesianGrid, Line, LineChart, ReferenceArea, ReferenceLine, XAxis, YAxis } from '@/lib/recharts'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart'
import {
  getCustomerQualityDiscountDepth,
  getCustomerQualityPathways,
  getCustomerQualityScorecard,
  getCustomerQualitySegments,
  type CustomerQualityDiscountDepthResponse,
  type CustomerQualityPathwaysResponse,
  type CustomerQualityScorecardResponse,
  type CustomerQualitySegmentsResponse,
} from '@/lib/api'

interface CustomerDiscountQualityProps {
  baseWeek: string
}

const COHORT_WINDOWS = [90, 180, 365]
const BASELINE_OPTIONS = [24, 36]

const SCORECARD_METRICS = [
  {
    key: 'net_sales_per_customer',
    label: 'Net sales / customer',
    tip: 'Net sales within the window divided by acquired customers in the cohort.',
    format: 'currency',
  },
  {
    key: 'repeat_rate',
    label: 'Repeat rate',
    tip: 'Share of customers with 2+ orders within the window.',
    format: 'percent',
  },
  {
    key: 'full_price_revenue_share',
    label: 'Full-price revenue share',
    tip: 'Share of net sales coming from full-price orders within the window.',
    format: 'percent',
  },
  {
    key: 'discount_cost_rate',
    label: 'Discount cost rate',
    tip: 'Discount cost (codes/auto + markdown) divided by gross sales within the window.',
    format: 'percent',
  },
]

export default function CustomerDiscountQuality({ baseWeek }: CustomerDiscountQualityProps) {
  const [cohortWindowDays, setCohortWindowDays] = useState(180)
  const [thresholdLow, setThresholdLow] = useState(0.2)
  const [thresholdHigh, setThresholdHigh] = useState(0.8)
  const [asOfDate, setAsOfDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [baselineMonths, setBaselineMonths] = useState(24)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [scorecard, setScorecard] = useState<CustomerQualityScorecardResponse | null>(null)
  const [discountDepth, setDiscountDepth] = useState<CustomerQualityDiscountDepthResponse | null>(null)
  const [segments, setSegments] = useState<CustomerQualitySegmentsResponse | null>(null)
  const [pathways, setPathways] = useState<CustomerQualityPathwaysResponse | null>(null)

  const thresholdError = thresholdLow > thresholdHigh

  useEffect(() => {
    if (!baseWeek || thresholdError) return
    let cancelled = false
    ;(async () => {
      setLoading(true)
      setError(null)
      try {
        const [scorecardRes, depthRes, segmentsRes, pathwaysRes] = await Promise.all([
          getCustomerQualityScorecard(baseWeek, cohortWindowDays, asOfDate, baselineMonths),
          getCustomerQualityDiscountDepth(baseWeek, cohortWindowDays, asOfDate),
          getCustomerQualitySegments(baseWeek, cohortWindowDays, asOfDate, thresholdLow, thresholdHigh),
          getCustomerQualityPathways(baseWeek, cohortWindowDays, asOfDate, thresholdLow, thresholdHigh, baselineMonths),
        ])
        if (!cancelled) {
          setScorecard(scorecardRes)
          setDiscountDepth(depthRes)
          setSegments(segmentsRes)
          setPathways(pathwaysRes)
        }
      } catch (e: any) {
        if (!cancelled) setError(e?.message || 'Failed to load customer quality data')
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [asOfDate, baselineMonths, baseWeek, cohortWindowDays, thresholdHigh, thresholdLow, thresholdError])

  const currency = scorecard?.meta?.currency || 'SEK'
  const fmtPct = (v?: number | null) => (Number.isFinite(v) ? `${Number(v).toFixed(1)}%` : '—')
  const fmtNumber = (v?: number | null) => (Number.isFinite(v) ? Math.round(Number(v)).toLocaleString('sv-SE') : '—')
  const fmtMoney = useMemo(() => {
    return (v?: number | null) =>
      Number.isFinite(v)
        ? new Intl.NumberFormat('sv-SE', { style: 'currency', currency, maximumFractionDigits: 0 }).format(Number(v))
        : '—'
  }, [currency])

  const metaWarning = scorecard?.meta?.currency_warning
  const diagnostics = scorecard?.diagnostics
  const isDev = process.env.NODE_ENV !== 'production'

  const scorecardMetrics = useMemo(() => {
    const metrics = [...SCORECARD_METRICS]
    const hasGrossProfit =
      scorecard?.latest?.metrics?.gross_profit_per_customer !== null &&
      scorecard?.latest?.metrics?.gross_profit_per_customer !== undefined
    const baselineGrossProfit = scorecard?.baseline?.gross_profit_per_customer?.mean
    if (hasGrossProfit || Number.isFinite(baselineGrossProfit)) {
      metrics.push({
        key: 'gross_profit_per_customer',
        label: 'Gross profit / customer',
        tip: 'Gross profit within the window divided by acquired customers (if COGS is available).',
        format: 'currency',
      })
    }
    return metrics
  }, [scorecard])

  const trendData = useMemo(() => {
    return (scorecard?.trend || []).map((c) => ({
      cohort: c.cohort,
      ...c.metrics,
    }))
  }, [scorecard])

  if (loading && !scorecard && !discountDepth && !segments) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <Loader2 className="h-5 w-5 animate-spin text-primary" />
          <span className="text-gray-600">Loading customer quality…</span>
        </div>
        <div className="space-y-2">
          <Skeleton className="h-12 w-full" />
          {[...Array(6)].map((_, i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center gap-4">
        <div className="text-sm font-medium text-gray-700">Cohort window</div>
        {COHORT_WINDOWS.map((d) => (
          <Button key={d} size="sm" variant={cohortWindowDays === d ? 'default' : 'outline'} onClick={() => setCohortWindowDays(d)}>
            {d}d
          </Button>
        ))}
        <div className="ml-2 flex items-center gap-2 text-sm text-gray-700">
          <span>As of</span>
          <input
            type="date"
            value={asOfDate}
            onChange={(e) => setAsOfDate(e.target.value)}
            className="rounded-md border px-2 py-1 text-xs"
          />
        </div>
        <div className="flex items-center gap-2 text-sm text-gray-700">
          <span>Baseline</span>
          <select
            value={baselineMonths}
            onChange={(e) => setBaselineMonths(Number(e.target.value))}
            className="rounded-md border px-2 py-1 text-xs"
          >
            {BASELINE_OPTIONS.map((m) => (
              <option key={m} value={m}>
                {m} mo
              </option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-2 text-sm text-gray-700">
          <span>Thresholds</span>
          <input
            type="number"
            step="0.05"
            min="0"
            max="1"
            value={thresholdLow}
            onChange={(e) => setThresholdLow(Number(e.target.value))}
            className="w-16 rounded-md border px-2 py-1 text-xs"
          />
          <span>–</span>
          <input
            type="number"
            step="0.05"
            min="0"
            max="1"
            value={thresholdHigh}
            onChange={(e) => setThresholdHigh(Number(e.target.value))}
            className="w-16 rounded-md border px-2 py-1 text-xs"
          />
        </div>
        {thresholdError && <div className="text-xs text-red-700">Low threshold must be ≤ high threshold.</div>}
      </div>

      {metaWarning && <div className="text-xs text-amber-700">{metaWarning}</div>}
      {error && <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}

      {isDev && diagnostics && (
        <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
          <div className="font-semibold">Diagnostics (dev-only)</div>
          <div className="mt-1 flex flex-wrap gap-4">
            <span>Code/auto discounted: {fmtPct(diagnostics.pct_code_or_auto_discounted_orders)}</span>
            <span>Markdown discounted: {fmtPct(diagnostics.pct_markdown_discounted_orders)}</span>
            <span>Any discounted: {fmtPct(diagnostics.pct_any_discounted_orders)}</span>
          </div>
        </div>
      )}

      <div className="space-y-3">
        <div className="text-sm font-semibold text-gray-900">Customer Quality Scorecard</div>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {scorecardMetrics.map((metric) => {
            const latestMetrics = (scorecard?.latest?.metrics || {}) as Record<string, number | null | undefined>
            const latestValue = latestMetrics[metric.key]
            const baseline = scorecard?.baseline?.[metric.key]
            const baselineMean = baseline?.mean ?? null
            const delta = Number.isFinite(latestValue) && Number.isFinite(baselineMean) ? Number(latestValue) - Number(baselineMean) : null
            const formatter = metric.format === 'currency' ? fmtMoney : fmtPct
            return (
              <Card key={metric.key}>
                <CardHeader>
                  <CardTitle className="text-xs font-medium text-gray-600">
                    <MetricLabel label={metric.label} tip={metric.tip} />
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-1">
                  <div className="text-lg font-semibold">{formatter(latestValue)}</div>
                  <div className="text-xs text-gray-500">
                    Baseline: {formatter(baselineMean)} {delta !== null && <span>({delta > 0 ? '+' : ''}{formatter(delta)})</span>}
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          {scorecardMetrics.map((metric) => {
            const baseline = scorecard?.baseline?.[metric.key]
            const formatter = metric.format === 'currency' ? fmtMoney : fmtPct
            return (
              <Card key={`trend-${metric.key}`}>
                <CardHeader>
                  <CardTitle className="text-sm font-semibold text-gray-900">{metric.label}</CardTitle>
                </CardHeader>
                <CardContent>
                  <MetricTrendChart data={trendData} dataKey={metric.key} baseline={baseline} formatter={formatter} />
                </CardContent>
              </Card>
            )
          })}
        </div>
      </div>

      <div className="space-y-3">
        <div className="text-sm font-semibold text-gray-900">Discount Depth × Outcome</div>
        <div className="bg-gray-50 rounded-lg overflow-hidden overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="bg-gray-200 border-b">
                <th className="text-left py-2 px-2 font-medium text-gray-900">
                  <MetricLabel label="First order discount depth" tip="Discount depth buckets from the first order (code/auto + markdown)." />
                </th>
                <th className="text-right py-2 px-2 font-medium text-gray-900">
                  <MetricLabel label="Customers" tip="Eligible customers in the bucket." />
                </th>
                <th className="text-right py-2 px-2 font-medium text-gray-900">
                  <MetricLabel label="Repeat rate" tip="Share of customers with 2+ orders in the window." />
                </th>
                <th className="text-right py-2 px-2 font-medium text-gray-900">
                  <MetricLabel label="Net sales / customer" tip="Net sales per acquired customer in the bucket." />
                </th>
                <th className="text-right py-2 px-2 font-medium text-gray-900">
                  <MetricLabel label="FP revenue share" tip="Full-price net sales share within the window." />
                </th>
                <th className="text-right py-2 px-2 font-medium text-gray-900">
                  <MetricLabel label="Discount cost rate" tip="Discount cost divided by gross sales in the window." />
                </th>
              </tr>
            </thead>
            <tbody>
              {(discountDepth?.buckets || []).map((row) => (
                <tr key={row.bucket} className="border-b border-gray-200 last:border-b-0">
                  <td className="py-2 px-2 text-gray-900">{row.bucket}</td>
                  <td className="py-2 px-2 text-right text-gray-700 tabular-nums">{fmtNumber(row.customers)}</td>
                  <td className="py-2 px-2 text-right text-gray-700 tabular-nums">{fmtPct(row.repeat_rate)}</td>
                  <td className="py-2 px-2 text-right text-gray-700 tabular-nums">{fmtMoney(row.net_sales_per_customer)}</td>
                  <td className="py-2 px-2 text-right text-gray-700 tabular-nums">{fmtPct(row.full_price_revenue_share)}</td>
                  <td className="py-2 px-2 text-right text-gray-700 tabular-nums">{fmtPct(row.discount_cost_rate)}</td>
                </tr>
              ))}
              {(discountDepth?.buckets || []).length === 0 && (
                <tr>
                  <td className="px-3 py-3 text-gray-600" colSpan={6}>
                    No eligible cohorts for this window.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="space-y-3">
        <div className="text-sm font-semibold text-gray-900">Behavioral Pathways</div>
        <div className="grid gap-4 md:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-semibold text-gray-900">Promo-acquired pathways</CardTitle>
            </CardHeader>
            <CardContent>
              <PathwaysChart
                data={pathways?.trend || []}
                lines={[
                  { key: 'promo_full_price_share', label: 'Promo → Full-price', color: '#111827' },
                  { key: 'promo_promo_share', label: 'Promo → Promo', color: '#F97316' },
                  { key: 'promo_one_and_done_share', label: 'Promo → One-and-done', color: '#9CA3AF' },
                ]}
              />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-semibold text-gray-900">Full-price pathways</CardTitle>
            </CardHeader>
            <CardContent>
              <PathwaysChart
                data={pathways?.trend || []}
                lines={[
                  { key: 'fp_fp_share', label: 'FP → FP', color: '#111827' },
                  { key: 'fp_drift_share', label: 'FP → Drift', color: '#EF4444' },
                ]}
              />
            </CardContent>
          </Card>
        </div>
        {pathways?.baseline && (
          <div className="bg-gray-50 rounded-lg overflow-hidden overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-gray-200 border-b">
                  <th className="text-left py-2 px-2 font-medium text-gray-900">Pathway</th>
                  <th className="text-right py-2 px-2 font-medium text-gray-900">Baseline mean</th>
                  <th className="text-right py-2 px-2 font-medium text-gray-900">P25–P75</th>
                </tr>
              </thead>
              <tbody>
                {[
                  ['Promo → Full-price', pathways.baseline.promo_full_price_share],
                  ['Promo → Promo', pathways.baseline.promo_promo_share],
                  ['Promo → One-and-done', pathways.baseline.promo_one_and_done_share],
                  ['FP → FP', pathways.baseline.fp_fp_share],
                  ['FP → Drift', pathways.baseline.fp_drift_share],
                ].map(([label, stats]) => (
                  <tr key={label} className="border-b border-gray-200 last:border-b-0">
                    <td className="py-2 px-2 text-gray-900">{label}</td>
                    <td className="py-2 px-2 text-right text-gray-700 tabular-nums">{fmtPct(stats?.mean)}</td>
                    <td className="py-2 px-2 text-right text-gray-700 tabular-nums">
                      {fmtPct(stats?.p25)} – {fmtPct(stats?.p75)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="space-y-3">
        <div className="text-sm font-semibold text-gray-900">Segment Value Table</div>
        <div className="bg-gray-50 rounded-lg overflow-hidden overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="bg-gray-200 border-b">
                <th className="text-left py-2 px-2 font-medium text-gray-900">Segment</th>
                <th className="text-right py-2 px-2 font-medium text-gray-900">Customers</th>
                <th className="text-right py-2 px-2 font-medium text-gray-900">Customer share</th>
                <th className="text-right py-2 px-2 font-medium text-gray-900">Net sales / customer</th>
                <th className="text-right py-2 px-2 font-medium text-gray-900">Repeat rate</th>
                <th className="text-right py-2 px-2 font-medium text-gray-900">FP revenue share</th>
                <th className="text-right py-2 px-2 font-medium text-gray-900">Discount cost / customer</th>
                <th className="text-right py-2 px-2 font-medium text-gray-900">Value share</th>
              </tr>
            </thead>
            <tbody>
              {(segments?.segments || []).map((row) => (
                <tr key={row.segment} className="border-b border-gray-200 last:border-b-0">
                  <td className="py-2 px-2 text-gray-900">{row.segment}</td>
                  <td className="py-2 px-2 text-right text-gray-700 tabular-nums">{fmtNumber(row.customers)}</td>
                  <td className="py-2 px-2 text-right text-gray-700 tabular-nums">{fmtPct(row.customer_share)}</td>
                  <td className="py-2 px-2 text-right text-gray-700 tabular-nums">{fmtMoney(row.net_sales_per_customer)}</td>
                  <td className="py-2 px-2 text-right text-gray-700 tabular-nums">{fmtPct(row.repeat_rate)}</td>
                  <td className="py-2 px-2 text-right text-gray-700 tabular-nums">{fmtPct(row.full_price_revenue_share)}</td>
                  <td className="py-2 px-2 text-right text-gray-700 tabular-nums">{fmtMoney(row.discount_cost_per_customer)}</td>
                  <td className="py-2 px-2 text-right text-gray-700 tabular-nums">{fmtPct(row.value_share)}</td>
                </tr>
              ))}
              {(segments?.segments || []).length === 0 && (
                <tr>
                  <td className="px-3 py-3 text-gray-600" colSpan={8}>
                    No eligible cohorts for this window.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

function MetricLabel({ label, tip }: { label: string; tip: string }) {
  return (
    <span className="inline-flex items-center gap-1">
      <span>{label}</span>
      <Tooltip>
        <TooltipTrigger asChild>
          <Info className="h-3.5 w-3.5 text-gray-400 cursor-help hover:text-gray-600" />
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-xs">
          {tip}
        </TooltipContent>
      </Tooltip>
    </span>
  )
}

function MetricTrendChart({
  data,
  dataKey,
  baseline,
  formatter,
}: {
  data: Array<Record<string, any>>
  dataKey: string
  baseline?: { mean: number | null; p25: number | null; p75: number | null }
  formatter: (value?: number | null) => string
}) {
  const hasBand = Number.isFinite(baseline?.p25) && Number.isFinite(baseline?.p75)
  const hasMean = Number.isFinite(baseline?.mean)
  const chartConfig = {
    value: {
      label: dataKey,
      color: '#111827',
    },
  }
  return (
    <ChartContainer config={chartConfig} className="h-56 w-full">
      <LineChart data={data} margin={{ top: 16, left: 12, right: 12 }}>
        <CartesianGrid vertical={false} />
        <XAxis dataKey="cohort" tickLine={false} axisLine={false} tickMargin={8} />
        <YAxis tickLine={false} axisLine={false} tickMargin={8} tickFormatter={(v) => formatter(v)} />
        <ChartTooltip content={<ChartTooltipContent />} />
        {hasBand && <ReferenceArea y1={baseline?.p25 as number} y2={baseline?.p75 as number} fill="#E5E7EB" fillOpacity={0.6} />}
        {hasMean && <ReferenceLine y={baseline?.mean as number} stroke="#6B7280" strokeDasharray="3 3" />}
        <Line dataKey={dataKey} type="monotone" stroke="#111827" strokeWidth={2} />
      </LineChart>
    </ChartContainer>
  )
}

function PathwaysChart({
  data,
  lines,
}: {
  data: CustomerQualityPathwaysResponse['trend']
  lines: Array<{ key: keyof CustomerQualityPathwaysResponse['trend'][number]; label: string; color: string }>
}) {
  const chartConfig = lines.reduce<Record<string, { label: string; color: string }>>(
    (acc, line) => ({
      ...acc,
      [line.key]: { label: line.label, color: line.color },
    }),
    {}
  )
  return (
    <ChartContainer config={chartConfig} className="h-56 w-full">
      <LineChart data={data} margin={{ top: 16, left: 12, right: 12 }}>
        <CartesianGrid vertical={false} />
        <XAxis dataKey="cohort" tickLine={false} axisLine={false} tickMargin={8} />
        <YAxis tickLine={false} axisLine={false} tickMargin={8} tickFormatter={(v) => `${Number(v).toFixed(0)}%`} />
        <ChartTooltip content={<ChartTooltipContent />} />
        {lines.map((line) => (
          <Line
            key={String(line.key)}
            dataKey={line.key}
            type="monotone"
            stroke={line.color}
            strokeWidth={2}
            connectNulls
          />
        ))}
      </LineChart>
    </ChartContainer>
  )
}


