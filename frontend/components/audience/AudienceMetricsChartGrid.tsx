'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ChartConfig, ChartContainer, ChartTooltip } from '@/components/ui/chart'
import {
  CartesianGrid,
  LabelList,
  Line,
  LineChart,
  XAxis,
  YAxis,
} from '@/lib/recharts'

/** One weekly row from Audience Total (derived KPIs) or per-country API — same chart keys. */
export interface AudienceSeriesRow {
  weekLabel: string
  new_customers?: number
  returning_customers?: number
  total_customers?: number
  total_orders?: number
  total_aov?: number
  /** Net ÷ unique customers in segment (Online KPIs definition). */
  aov_new_customer?: number
  aov_returning_customer?: number
  cos_pct?: number
  cac?: number
  return_rate_pct?: number
  return_rate_new_pct?: number
  return_rate_returning_pct?: number
  /** aMER = online new-customer net / DEMA marketing spend (same as summary slide / Table 1 eMER). */
  amer?: number
  last_year?: Record<string, number> | null
  /** Monthly budget (budget-general) mapped to the same keys as actuals for this week’s month. */
  budget?: Record<string, number> | null
}

function formatAmerRatio(v: number): string {
  const x = Math.round(v * 100) / 100
  return x.toLocaleString('sv-SE', { minimumFractionDigits: 1, maximumFractionDigits: 2 })
}

const chartConfig = {
  value: { label: 'This year', color: '#4B5563' },
  lastYear: { label: 'Last year (same week)', color: '#F97316' },
} satisfies ChartConfig

function AudienceLineTooltip({
  active,
  payload,
  label,
  format,
}: {
  active?: boolean
  payload?: Array<{
    payload?: {
      value?: number
      lastYear?: number | null
    }
  }>
  label?: string | number
  format: (v: number) => string
}) {
  if (!active || !payload?.length) return null
  const row = payload[0]?.payload as
    | {
        value?: number
        lastYear?: number | null
      }
    | undefined
  if (!row) return null
  const fmt = (n: number | null | undefined) =>
    n != null && Number.isFinite(Number(n)) ? format(Number(n)) : '—'
  return (
    <div className="border-border/50 bg-background grid min-w-[10rem] gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs shadow-xl">
      <div className="font-medium">{label}</div>
      <div className="flex justify-between gap-4">
        <span className="text-muted-foreground">This year</span>
        <span className="font-medium tabular-nums">{fmt(row.value)}</span>
      </div>
      <div className="flex justify-between gap-4">
        <span className="text-muted-foreground">Last year</span>
        <span className="font-medium tabular-nums">{fmt(row.lastYear ?? null)}</span>
      </div>
    </div>
  )
}

export type AudienceCardDef = {
  key: string
  label: string
  format: (v: number) => string
  /** Optional native tooltip on the chart card title. */
  title?: string
}

/** Core volume, return rate by customer type, COS & aMER — top section on all audience views. */
export const AUDIENCE_PRIMARY_CARDS: AudienceCardDef[] = [
  { key: 'total_customers', label: 'Total Customers', format: (v: number) => v.toLocaleString() },
  { key: 'total_orders', label: 'Total Orders', format: (v: number) => v.toLocaleString() },
  { key: 'total_aov', label: 'Total AOV', format: (v: number) => `${Math.round(v)}` },
  { key: 'returning_customers', label: 'Returning Customers', format: (v: number) => v.toLocaleString() },
  {
    key: 'return_rate_returning_pct',
    label: 'Return Rate (Returning)',
    format: (v: number) => `${v.toFixed(1)}%`,
  },
  { key: 'new_customers', label: 'New Customers', format: (v: number) => v.toLocaleString() },
  { key: 'return_rate_new_pct', label: 'Return Rate (New)', format: (v: number) => `${v.toFixed(1)}%` },
  { key: 'cos_pct', label: 'COS', format: (v: number) => `${v.toFixed(1)}%` },
  {
    key: 'amer',
    label: 'aMER',
    format: (v: number) => formatAmerRatio(v),
    title:
      'aMER = online new-customer net revenue (Qlik) ÷ total marketing spend (DEMA). Same definition as summary slide 1 (Table 1 eMER).',
  },
]

/** Customer mix, blended return rate & CAC — bottom section. */
export const AUDIENCE_SECONDARY_CARDS: AudienceCardDef[] = [
  {
    key: 'aov_returning_customer',
    label: 'Returning AOV',
    format: (v: number) => `${Math.round(v)}`,
    title: 'Online net revenue for returning customers ÷ unique returning customers (same as Online KPIs).',
  },
  {
    key: 'aov_new_customer',
    label: 'New AOV',
    format: (v: number) => `${Math.round(v)}`,
    title: 'Online net revenue for new customers ÷ unique new customers (same as Online KPIs).',
  },
  { key: 'new_customer_share_pct', label: 'New Customer Share', format: (v: number) => `${v.toFixed(1)}%` },
  {
    key: 'returning_customer_share_pct',
    label: 'Returning Customer Share',
    format: (v: number) => `${v.toFixed(1)}%`,
  },
  { key: 'return_rate_pct', label: 'Return Rate', format: (v: number) => `${v.toFixed(1)}%` },
  { key: 'cac', label: 'CAC', format: (v: number) => `${Math.round(v)}` },
]

function chartPointsForKey(m: AudienceSeriesRow, key: string) {
  const currentTotal = Number(m.total_customers) || 0
  const lyTotal = Number(m.last_year?.total_customers) || 0
  const value =
    key === 'new_customer_share_pct'
      ? currentTotal > 0
        ? (Number(m.new_customers) / currentTotal) * 100
        : 0
      : key === 'returning_customer_share_pct'
        ? currentTotal > 0
          ? (Number(m.returning_customers) / currentTotal) * 100
          : 0
        : Number((m as unknown as Record<string, unknown>)[key]) || 0

  const lastYear =
    key === 'new_customer_share_pct'
      ? m.last_year
        ? lyTotal > 0
          ? (Number(m.last_year.new_customers) / lyTotal) * 100
          : 0
        : null
      : key === 'returning_customer_share_pct'
        ? m.last_year
          ? lyTotal > 0
            ? (Number(m.last_year.returning_customers) / lyTotal) * 100
            : 0
          : null
        : m.last_year
          ? Number((m.last_year as unknown as Record<string, unknown>)[key])
          : null

  const numValue = Number(value) || 0

  return {
    week: m.weekLabel,
    value: numValue,
    lastYear: lastYear == null ? null : Number(lastYear),
  }
}

function AudienceChartCard({
  card,
  series,
  isAnimationActive,
}: {
  card: AudienceCardDef
  series: AudienceSeriesRow[]
  isAnimationActive: boolean
}) {
  const { key, label, format, title: titleAttr } = card
  const chartData = series.map((m) => chartPointsForKey(m, key))

  return (
    <Card key={key}>
      <CardHeader>
        <CardTitle className="text-sm font-medium" title={titleAttr}>
          {label}
        </CardTitle>
      </CardHeader>
      <CardContent className="overflow-visible">
        <ChartContainer config={chartConfig} className="h-[260px] w-full min-w-0 overflow-visible">
          <LineChart
            data={chartData}
            margin={{ top: 44, right: 12, left: 12, bottom: 22 }}
          >
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="week"
              type="category"
              interval={0}
              tick={{ fontSize: 9, fill: '#6b7280' }}
              tickMargin={6}
              height={34}
              tickLine={false}
              axisLine={{ stroke: '#e5e7eb' }}
            />
            <YAxis
              yAxisId="left"
              tick={{ fontSize: 11 }}
              width={40}
              tickFormatter={(v) =>
                (key === 'total_customers' ||
                  key === 'total_orders' ||
                  key === 'new_customers' ||
                  key === 'returning_customers' ||
                  key === 'cac' ||
                  key === 'total_aov' ||
                  key === 'aov_new_customer' ||
                  key === 'aov_returning_customer') &&
                Math.abs(v) >= 1000
                  ? `${v / 1000}k`
                  : String(v)
              }
            />
            <ChartTooltip
              content={
                <AudienceLineTooltip
                  format={(v) => format(v)}
                />
              }
            />
            <Line
              yAxisId="left"
              type="monotone"
              dataKey="value"
              stroke="var(--color-value)"
              strokeWidth={2}
              dot={{ r: 3 }}
              isAnimationActive={isAnimationActive}
              name="This year"
            >
              <LabelList
                position="top"
                offset={8}
                fill="#374151"
                fontSize={9}
                formatter={(val: unknown) => format(Number(val ?? 0))}
              />
            </Line>
            <Line
              yAxisId="left"
              type="monotone"
              dataKey="lastYear"
              stroke="var(--color-lastYear)"
              strokeWidth={2}
              strokeDasharray="4 4"
              dot={{ r: 3 }}
              connectNulls
              isAnimationActive={isAnimationActive}
              name="Last year (same week)"
            />
          </LineChart>
        </ChartContainer>
      </CardContent>
    </Card>
  )
}

export function AudienceMetricsChartGrid({
  series,
  isAnimationActive,
}: {
  series: AudienceSeriesRow[]
  isAnimationActive: boolean
}) {
  return (
    <div className="space-y-10">
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {AUDIENCE_PRIMARY_CARDS.map((card) => (
          <AudienceChartCard key={card.key} card={card} series={series} isAnimationActive={isAnimationActive} />
        ))}
      </div>

      <div className="border-t border-gray-200 pt-10">
        <h3 className="mb-4 text-base font-semibold text-gray-900">AOV by customer type, mix, return rate &amp; CAC</h3>
        <p className="mb-6 text-sm text-muted-foreground">
          Returning and new AOV use the same net-revenue-per-unique-customer definition as Online KPIs. Below that:
          new vs returning share of customers, blended return rate (all customers), and new-customer CAC. Main KPIs
          and segment return rates are in the section above.
        </p>
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {AUDIENCE_SECONDARY_CARDS.map((card) => (
            <AudienceChartCard key={card.key} card={card} series={series} isAnimationActive={isAnimationActive} />
          ))}
        </div>
      </div>
    </div>
  )
}
