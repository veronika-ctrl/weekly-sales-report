'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { useDataCache } from '@/contexts/DataCacheContext'
import { useChartAnimations } from '@/contexts/ChartSettingsContext'
import {
  getRetentionByChannel,
  hasBackend,
  type RetentionByChannelResponse,
  type RetentionChannelRow,
} from '@/lib/api'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ChartConfig, ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart'
import { Bar, BarChart, CartesianGrid, Cell, XAxis, YAxis } from '@/lib/recharts'
import { Loader2 } from 'lucide-react'

const CHANNEL_LABELS: Record<string, string> = {
  sem: 'SEM',
  social_ppc: 'Social PPC',
  affiliate: 'Affiliate',
  direct: 'Direct',
  organic: 'Organic',
  email: 'Email',
  referral: 'Referral',
  social_organic: 'Social organic',
  unknown: 'Unknown',
  backfilled: 'Backfilled',
  all: 'Total',
}

const PAID = new Set(['sem', 'social_ppc', 'affiliate'])
const ORGANIC = new Set(['direct', 'organic', 'email', 'referral', 'social_organic'])

function channelLabel(name: string): string {
  return CHANNEL_LABELS[name] ?? name.replace(/_/g, ' ')
}

function channelColor(name: string): string {
  if (name === 'backfilled') return '#0D9488'
  if (name === 'unknown') return '#6366F1'
  if (PAID.has(name)) return '#4B5563'
  if (ORGANIC.has(name)) return '#F97316'
  return '#9CA3AF'
}

function fmtPct(v: number | null | undefined): string {
  if (v == null || Number.isNaN(Number(v)) || !Number.isFinite(Number(v))) return '—'
  return `${(Number(v) * 100).toFixed(1)}%`
}

function fmtMoney(v: number | null | undefined): string {
  if (v == null || Number.isNaN(Number(v))) return '—'
  return Number(v).toLocaleString('sv-SE', { maximumFractionDigits: 0 })
}

function fmtDays(v: number | null | undefined): string {
  if (v == null || Number.isNaN(Number(v))) return '—'
  return Number(v).toLocaleString('sv-SE', { maximumFractionDigits: 0 })
}

function fmtCount(v: number | null | undefined): string {
  if (v == null || Number.isNaN(Number(v))) return '—'
  return Number(v).toLocaleString('sv-SE')
}

const BAR_MARGIN = { top: 16, right: 12, left: 8, bottom: 8 }

function tickProps(count: number) {
  const few = count <= 6
  return {
    tickLine: false as const,
    axisLine: false as const,
    tickMargin: few ? 10 : 8,
    interval: 0 as const,
    minTickGap: 0,
    angle: few ? 0 : -35,
    textAnchor: few ? ('middle' as const) : ('end' as const),
    height: few ? 36 : 64,
    tick: { fontSize: few ? 12 : 11 },
  }
}

function KpiCard({ title, value, hint }: { title: string; value: string; hint?: string }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-gray-700">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-semibold text-gray-900">{value}</div>
        {hint ? <p className="text-xs text-muted-foreground mt-1">{hint}</p> : null}
      </CardContent>
    </Card>
  )
}

type ChartPoint = RetentionChannelRow & { label: string; fill: string; chartValue: number | null }

function ChannelBarChart({
  title,
  description,
  points,
  valueKey,
  formatTooltip,
  tickFormatter,
}: {
  title: string
  description: string
  points: ChartPoint[]
  valueKey: 'repeat_rate_180d' | 'net_sales_per_customer_180d' | 'full_price_share_lifetime' | 'median_days_to_second_order'
  formatTooltip: (v: number | null) => string
  tickFormatter: (v: number) => string
}) {
  const chartAnimationsEnabled = useChartAnimations()
  const data = points.map((p) => ({
    ...p,
    chartValue: p[valueKey],
  }))
  const config: ChartConfig = { chartValue: { label: title, color: '#4B5563' } }
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>
        {data.length === 0 ? (
          <p className="text-sm text-muted-foreground">No eligible customers yet.</p>
        ) : (
          <ChartContainer config={config} className="h-[320px] w-full !aspect-auto">
            <BarChart data={data} margin={BAR_MARGIN} isAnimationActive={chartAnimationsEnabled}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="label" {...tickProps(data.length)} />
              <YAxis
                tickLine={false}
                axisLine={false}
                width={56}
                tickFormatter={tickFormatter}
                domain={[0, 'auto']}
              />
              <ChartTooltip
                content={
                  <ChartTooltipContent
                    formatter={(value: unknown) => formatTooltip(Number(value ?? 0))}
                  />
                }
              />
              <Bar dataKey="chartValue" radius={2}>
                {data.map((row) => (
                  <Cell key={row.channel_group} fill={row.fill} />
                ))}
              </Bar>
            </BarChart>
          </ChartContainer>
        )}
      </CardContent>
    </Card>
  )
}

export default function RetentionByChannelPage() {
  const { baseWeek } = useDataCache()
  const weekToLoad = baseWeek || '2026-36'
  const [data, setData] = useState<RetentionByChannelResponse | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    if (!hasBackend) return
    setLoading(true)
    setErr(null)
    try {
      setData(await getRetentionByChannel(weekToLoad))
    } catch (e: unknown) {
      setData(null)
      setErr(e instanceof Error ? e.message : 'Failed to load retention by channel')
    } finally {
      setLoading(false)
    }
  }, [weekToLoad])

  useEffect(() => {
    void load()
  }, [load])

  const points = useMemo<ChartPoint[]>(
    () =>
      (data?.channels ?? []).map((row) => ({
        ...row,
        label: channelLabel(row.channel_group),
        fill: channelColor(row.channel_group),
        chartValue: null,
      })),
    [data]
  )

  const tableRows = useMemo(() => {
    const rows = [...(data?.channels ?? [])]
    if (data?.total) rows.push(data.total)
    return rows
  }, [data])

  if (!hasBackend) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Retention by acquisition channel</CardTitle>
          <CardDescription>Configure the API URL to load this report.</CardDescription>
        </CardHeader>
      </Card>
    )
  }

  if (loading && !data) {
    return (
      <div className="flex items-center gap-3 py-12">
        <Loader2 className="h-6 w-6 animate-spin text-primary" />
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Loading retention by channel</h2>
          <p className="text-sm text-gray-600">Aggregating Eligible180d = 1 customers by last-click AcquisitionChannelGroup…</p>
        </div>
      </div>
    )
  }

  const total = data?.total ?? null
  const cohortRange =
    data?.cohort_min && data?.cohort_max ? `${data.cohort_min}–${data.cohort_max}` : null

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-lg font-semibold text-gray-900">Retention by acquisition channel</h2>
        <p className="text-sm text-muted-foreground mt-1 max-w-3xl">
          Separate from Adjusted aMER. Customer-level Dema export, last-click AcquisitionChannelGroup
          — not CFA. Do not compare these rates to the CFA-based headline aMER numbers.
          {cohortRange ? ` Eligible cohorts ${cohortRange}.` : null}
          {data?.eligible_count
            ? ` ${fmtCount(data.eligible_count)} customers with Eligible180d = 1` +
              (data.customer_count ? ` of ${fmtCount(data.customer_count)} in the file.` : '.')
            : null}
        </p>
      </div>

      <div className="text-sm text-amber-950 bg-amber-50 border border-amber-300 rounded p-3 space-y-1">
        <div className="font-semibold uppercase tracking-wide text-[11px] text-amber-800">
          Last-click attribution — not CFA
        </div>
        <p>
          These metrics use last-click AcquisitionChannelGroup because that is the only model
          available at individual-customer grain. Adjusted aMER headlines use CFA (and new-customer
          aMER uses MTA). The two reports are not directly comparable.
        </p>
        <p>
          Filtered to <span className="font-medium">Eligible180d = 1</span> only. Backfilled stays
          its own row and is never folded into organic, unknown, or unattributed.
        </p>
      </div>

      {err ? (
        <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded p-3">{err}</div>
      ) : null}

      {(data?.warnings ?? []).map((w) => (
        <div key={w.code} className="text-sm text-amber-900 bg-amber-50 border border-amber-200 rounded p-3">
          {w.message}{' '}
          <Link href="/settings" className="underline font-medium">
            Open Settings
          </Link>
        </div>
      ))}

      {data && !data.available ? (
        <Card>
          <CardHeader>
            <CardTitle>No retention file loaded</CardTitle>
            <CardDescription>
              {data.message ?? 'Upload Retention_customers_*.csv in Settings.'}{' '}
              <Link href="/settings" className="underline font-medium">
                Open Settings
              </Link>
            </CardDescription>
          </CardHeader>
        </Card>
      ) : null}

      {total ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
          <KpiCard
            title="180-day repeat rate"
            value={fmtPct(total.repeat_rate_180d)}
            hint="Site total · Eligible180d = 1 · last-click"
          />
          <KpiCard
            title="Net sales / customer (180d)"
            value={fmtMoney(total.net_sales_per_customer_180d)}
            hint="Mean of NetSalesTotal180d (acquisition + 180d)"
          />
          <KpiCard
            title="Full-price share (lifetime)"
            value={fmtPct(total.full_price_share_lifetime)}
            hint="Unweighted mean of FullPriceShareLifetime"
          />
          <KpiCard
            title="Median days to 2nd order"
            value={fmtDays(total.median_days_to_second_order)}
            hint="Among customers who repeated within 180 days"
          />
        </div>
      ) : null}

      {data?.available ? (
        <>
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            <ChannelBarChart
              title="180-day repeat rate"
              description="Share with Repeated180d = 1, by last-click AcquisitionChannelGroup."
              points={points}
              valueKey="repeat_rate_180d"
              formatTooltip={fmtPct}
              tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
            />
            <ChannelBarChart
              title="Net sales per customer (180d)"
              description="Mean NetSalesTotal180d (acquisition order plus 180-day sales)."
              points={points}
              valueKey="net_sales_per_customer_180d"
              formatTooltip={fmtMoney}
              tickFormatter={(v) => Number(v).toLocaleString('sv-SE', { maximumFractionDigits: 0 })}
            />
            <ChannelBarChart
              title="Full-price share (lifetime)"
              description="Unweighted mean of FullPriceShareLifetime. Backfilled is its own bar."
              points={points}
              valueKey="full_price_share_lifetime"
              formatTooltip={fmtPct}
              tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
            />
            <ChannelBarChart
              title="Median days to second order"
              description="Median DaysToSecondOrder among customers who repeated within 180 days."
              points={points}
              valueKey="median_days_to_second_order"
              formatTooltip={fmtDays}
              tickFormatter={(v) => Number(v).toLocaleString('sv-SE', { maximumFractionDigits: 0 })}
            />
          </div>

          <Card>
            <CardHeader>
              <CardTitle>By last-click AcquisitionChannelGroup</CardTitle>
              <CardDescription>
                Eligible180d = 1 only. Teal row is backfilled — kept separate, not folded into any other channel.
              </CardDescription>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-muted-foreground border-b">
                    <th className="py-2 pr-3">Channel group</th>
                    <th className="py-2 pr-3 text-right">Customers</th>
                    <th className="py-2 pr-3 text-right">180d repeat</th>
                    <th className="py-2 pr-3 text-right">NS / customer (180d)</th>
                    <th className="py-2 pr-3 text-right">Full-price share (LT)</th>
                    <th className="py-2 text-right">Median days to 2nd</th>
                  </tr>
                </thead>
                <tbody>
                  {tableRows.map((row) => {
                    const isTotal = row.is_total
                    const isBackfilled = row.is_backfilled
                    return (
                      <tr
                        key={row.channel_group}
                        className={
                          isTotal
                            ? 'border-t-2 font-semibold'
                            : isBackfilled
                              ? 'bg-teal-50 border-b last:border-0'
                              : 'border-b last:border-0'
                        }
                      >
                        <td className="py-2 pr-3">
                          <span className="inline-flex items-center gap-2">
                            {!isTotal ? (
                              <span
                                className="h-2.5 w-2.5 rounded-full shrink-0"
                                style={{ background: channelColor(row.channel_group) }}
                              />
                            ) : null}
                            {channelLabel(row.channel_group)}
                            {isBackfilled ? (
                              <span className="text-[10px] font-semibold uppercase tracking-wide bg-teal-100 text-teal-900 px-1.5 py-0.5 rounded">
                                Own row
                              </span>
                            ) : null}
                          </span>
                        </td>
                        <td className="py-2 pr-3 text-right">{fmtCount(row.customers)}</td>
                        <td className="py-2 pr-3 text-right">{fmtPct(row.repeat_rate_180d)}</td>
                        <td className="py-2 pr-3 text-right">{fmtMoney(row.net_sales_per_customer_180d)}</td>
                        <td className="py-2 pr-3 text-right">{fmtPct(row.full_price_share_lifetime)}</td>
                        <td className="py-2 text-right">{fmtDays(row.median_days_to_second_order)}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
              <div className="flex flex-wrap gap-4 text-xs text-muted-foreground mt-3">
                <span className="inline-flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full" style={{ background: '#4B5563' }} /> Paid
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full" style={{ background: '#F97316' }} /> Organic
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full" style={{ background: '#6366F1' }} /> Unknown
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full" style={{ background: '#0D9488' }} /> Backfilled
                </span>
              </div>
            </CardContent>
          </Card>
        </>
      ) : null}

      {data?.footnotes?.length ? (
        <div className="text-xs text-muted-foreground space-y-1">
          {data.as_of ? <p>As of {new Date(data.as_of).toLocaleString('sv-SE')}.</p> : null}
          {data.files?.length ? (
            <p>File{data.files.length > 1 ? 's' : ''}: {data.files.map((f) => f.filename).join(', ')}.</p>
          ) : null}
          {data.footnotes.map((f) => (
            <p key={f}>• {f}</p>
          ))}
        </div>
      ) : null}
    </div>
  )
}
