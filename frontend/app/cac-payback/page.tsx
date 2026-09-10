'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { useDataCache } from '@/contexts/DataCacheContext'
import { useChartAnimations } from '@/contexts/ChartSettingsContext'
import {
  getCacPayback,
  hasBackend,
  type CacPaybackHorizonRow,
  type CacPaybackResponse,
  type CacPaybackSegmentRow,
} from '@/lib/api'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ChartConfig, ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart'
import { Bar, BarChart, CartesianGrid, Legend, ReferenceLine, XAxis, YAxis } from '@/lib/recharts'
import { Loader2 } from 'lucide-react'

const CHANNEL_LABELS: Record<string, string> = {
  social_ppc: 'Meta',
  sem: 'Search',
  affiliate: 'Affiliate',
}

const SEGMENT_LABELS: Record<string, string> = {
  all: 'All campaigns',
  prospecting: 'Prospecting',
  retargeting: 'Retargeting',
  branded: 'Branded',
  non_branded: 'Non-branded',
  editorial: 'Editorial',
  coupon: 'Coupon',
}

const CHANNEL_COLORS: Record<string, string> = {
  social_ppc: '#2563EB',
  sem: '#4B5563',
  affiliate: '#0D9488',
}

function channelLabel(name: string): string {
  return CHANNEL_LABELS[name] ?? name.replace(/_/g, ' ')
}

function segmentLabel(row: { segment: string; segment_label?: string }): string {
  return SEGMENT_LABELS[row.segment] ?? row.segment_label ?? row.segment.replace(/_/g, ' ')
}

function fmtMoney(v: number | null | undefined): string {
  if (v == null || Number.isNaN(Number(v))) return '—'
  return Number(v).toLocaleString('sv-SE', { maximumFractionDigits: 0 })
}

function fmtCount(v: number | null | undefined): string {
  if (v == null || Number.isNaN(Number(v))) return '—'
  return Number(v).toLocaleString('sv-SE')
}

function fmtPayback(v: number | null | undefined): string {
  if (v == null || Number.isNaN(Number(v)) || !Number.isFinite(Number(v))) return '—'
  return `${Number(v).toFixed(2)}×`
}

function fmtPct(v: number | null | undefined): string {
  if (v == null || Number.isNaN(Number(v)) || !Number.isFinite(Number(v))) return '—'
  return `${(Number(v) * 100).toFixed(1)}%`
}

function paybackClass(v: number | null | undefined): string {
  if (v == null || Number.isNaN(Number(v))) return ''
  return Number(v) >= 1 ? 'text-emerald-800 font-medium' : 'text-amber-800'
}

const BAR_MARGIN = { top: 16, right: 16, left: 8, bottom: 8 }
const horizonChartConfig: ChartConfig = {
  payback_180: { label: '180-day', color: '#4B5563' },
  payback_365: { label: '365-day', color: '#F97316' },
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

function SegmentGroup({
  channel,
  rows,
}: {
  channel: string
  rows: CacPaybackSegmentRow[]
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: CHANNEL_COLORS[channel] ?? '#9CA3AF' }} />
          {channelLabel(channel)}
        </CardTitle>
        <CardDescription>
          {channel === 'social_ppc'
            ? 'Prospecting vs retargeting'
            : channel === 'sem'
              ? 'Branded vs non-branded search'
              : 'Editorial vs coupon / cashback'}
        </CardDescription>
      </CardHeader>
      <CardContent className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-muted-foreground border-b">
              <th className="py-2 pr-3">Segment</th>
              <th className="py-2 pr-3 text-right">Customers</th>
              <th className="py-2 pr-3 text-right">CAC</th>
              <th className="py-2 pr-3 text-right">GP2 / cust (180d)</th>
              <th className="py-2 text-right">Payback</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={`${row.channel_group}-${row.segment}`} className="border-b last:border-0">
                <td className="py-2 pr-3">
                  <span className="inline-flex items-center gap-2">
                    {segmentLabel(row)}
                    {row.indicative ? (
                      <span className="text-[10px] font-semibold uppercase tracking-wide bg-amber-100 text-amber-900 px-1.5 py-0.5 rounded">
                        Indicative
                      </span>
                    ) : null}
                  </span>
                </td>
                <td className="py-2 pr-3 text-right">{fmtCount(row.new_customers)}</td>
                <td className="py-2 pr-3 text-right">{fmtMoney(row.cac)}</td>
                <td className="py-2 pr-3 text-right">{fmtMoney(row.gp2_per_customer)}</td>
                <td className={`py-2 text-right ${paybackClass(row.payback)}`}>{fmtPayback(row.payback)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  )
}

export default function CacPaybackPage() {
  const { baseWeek } = useDataCache()
  const weekToLoad = baseWeek || '2026-36'
  const chartAnimationsEnabled = useChartAnimations()
  const [data, setData] = useState<CacPaybackResponse | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    if (!hasBackend) return
    setLoading(true)
    setErr(null)
    try {
      setData(await getCacPayback(weekToLoad))
    } catch (e: unknown) {
      setData(null)
      setErr(e instanceof Error ? e.message : 'Failed to load CAC payback')
    } finally {
      setLoading(false)
    }
  }, [weekToLoad])

  useEffect(() => {
    void load()
  }, [load])

  const horizonTotals = useMemo(
    () => (data?.horizon ?? []).filter((row) => row.is_channel_total),
    [data]
  )
  const horizonChart = useMemo(
    () =>
      horizonTotals.map((row) => ({
        ...row,
        label: channelLabel(row.channel_group),
      })),
    [horizonTotals]
  )
  const segmentsByChannel = useMemo(() => {
    const groups: Array<{ channel: string; rows: CacPaybackSegmentRow[] }> = []
    for (const channel of ['social_ppc', 'sem', 'affiliate']) {
      const rows = (data?.segments ?? []).filter((r) => r.channel_group === channel)
      if (rows.length) groups.push({ channel, rows })
    }
    const extras = (data?.segments ?? []).filter(
      (r) => !['social_ppc', 'sem', 'affiliate'].includes(r.channel_group)
    )
    for (const channel of Array.from(new Set(extras.map((r) => r.channel_group)))) {
      groups.push({ channel, rows: extras.filter((r) => r.channel_group === channel) })
    }
    return groups
  }, [data])

  if (!hasBackend) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>CAC payback by channel</CardTitle>
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
          <h2 className="text-lg font-semibold text-gray-900">Loading CAC payback</h2>
          <p className="text-sm text-gray-600">Reading ChannelGroup, campaign-segment, and 180d vs 365d files…</p>
        </div>
      </div>
    )
  }

  const period =
    data?.period_min && data?.period_max ? `${data.period_min}–${data.period_max}` : null

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-lg font-semibold text-gray-900">CAC payback by channel</h2>
        <p className="text-sm text-muted-foreground mt-1 max-w-3xl">
          Sibling of{' '}
          <Link href="/retention-by-channel" className="underline font-medium">
            Retention by channel
          </Link>
          . Last-click ChannelGroup — not CFA — so these multiples are not comparable to Adjusted
          aMER headlines.
          {period ? ` Cohorts ${period}.` : null} Payback = 180-day net GP2 per customer ÷ CAC.
        </p>
      </div>

      <div className="text-sm text-amber-950 bg-amber-50 border border-amber-300 rounded p-3 space-y-2">
        <div className="font-semibold uppercase tracking-wide text-[11px] text-amber-800">
          Average returns, derived GP2 — read before the multiples
        </div>
        {(data?.caveats ?? []).map((c) => (
          <p key={c}>• {c}</p>
        ))}
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
            <CardTitle>No CAC payback files loaded</CardTitle>
            <CardDescription>
              {data.message ?? 'Upload the three CAC payback CSVs in Settings.'}{' '}
              <Link href="/settings" className="underline font-medium">
                Open Settings
              </Link>
            </CardDescription>
          </CardHeader>
        </Card>
      ) : null}

      {(data?.channels ?? []).length > 0 ? (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {data!.channels.map((row) => (
              <KpiCard
                key={row.channel_group}
                title={`${channelLabel(row.channel_group)} payback (180d)`}
                value={fmtPayback(row.payback_180d)}
                hint={`CAC ${fmtMoney(row.cac)} · GP2/cust ${fmtMoney(row.gp2_180d)}`}
              />
            ))}
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Headline by ChannelGroup</CardTitle>
              <CardDescription>
                Meta is social_ppc. CAC is full spend ÷ new customers. 180-day net GP2 per customer
                is margin-rate derived, not an official per-customer metric.
              </CardDescription>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-muted-foreground border-b">
                    <th className="py-2 pr-3">Channel group</th>
                    <th className="py-2 pr-3 text-right">New customers</th>
                    <th className="py-2 pr-3 text-right">CAC</th>
                    <th className="py-2 pr-3 text-right">Net GP2 / cust (180d)</th>
                    <th className="py-2 text-right">Payback multiple</th>
                  </tr>
                </thead>
                <tbody>
                  {data!.channels.map((row) => (
                    <tr key={row.channel_group} className="border-b last:border-0">
                      <td className="py-2 pr-3">
                        <span className="inline-flex items-center gap-2">
                          <span
                            className="h-2.5 w-2.5 rounded-full shrink-0"
                            style={{ background: CHANNEL_COLORS[row.channel_group] ?? '#9CA3AF' }}
                          />
                          {channelLabel(row.channel_group)}
                          <span className="text-xs text-muted-foreground">{row.channel_group}</span>
                        </span>
                      </td>
                      <td className="py-2 pr-3 text-right">{fmtCount(row.new_customers)}</td>
                      <td className="py-2 pr-3 text-right">{fmtMoney(row.cac)}</td>
                      <td className="py-2 pr-3 text-right">{fmtMoney(row.gp2_180d)}</td>
                      <td className={`py-2 text-right ${paybackClass(row.payback_180d)}`}>
                        {fmtPayback(row.payback_180d)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        </>
      ) : null}

      {segmentsByChannel.length > 0 ? (
        <div className="space-y-4">
          <div>
            <h3 className="text-base font-semibold text-gray-900">Campaign-segment breakdown</h3>
            <p className="text-sm text-muted-foreground mt-1 max-w-3xl">
              Each segment has its own CAC and 180-day payback. Affiliate splits are labelled
              indicative in the source export.
            </p>
          </div>
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
            {segmentsByChannel.map((g) => (
              <SegmentGroup key={g.channel} channel={g.channel} rows={g.rows} />
            ))}
          </div>
        </div>
      ) : null}

      {horizonChart.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>180-day vs 365-day payback</CardTitle>
            <CardDescription>
              Same ChannelGroups, longer observation. The 365-day cohort is smaller (customers with
              a full year of data). Dashed line is 1.0× (payback).
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ChartContainer config={horizonChartConfig} className="h-[320px] w-full max-w-3xl !aspect-auto">
              <BarChart data={horizonChart} margin={BAR_MARGIN} isAnimationActive={chartAnimationsEnabled}>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="label" tickLine={false} axisLine={false} tickMargin={8} />
                <YAxis
                  tickLine={false}
                  axisLine={false}
                  width={48}
                  tickFormatter={(v: number) => `${Number(v).toFixed(1)}×`}
                  domain={[0, 'auto']}
                />
                <ReferenceLine y={1} stroke="#9CA3AF" strokeDasharray="3 3" />
                <ChartTooltip
                  content={
                    <ChartTooltipContent
                      formatter={(value: unknown) => fmtPayback(Number(value ?? 0))}
                    />
                  }
                />
                <Legend />
                <Bar dataKey="payback_180" name="180-day" fill="#4B5563" radius={2} />
                <Bar dataKey="payback_365" name="365-day" fill="#F97316" radius={2} />
              </BarChart>
            </ChartContainer>
          </CardContent>
        </Card>
      ) : null}

      {(data?.horizon ?? []).length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Horizon detail</CardTitle>
            <CardDescription>
              Channel totals first, then branded / non-branded and Meta prospecting / retargeting
              where the export includes them.
            </CardDescription>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-muted-foreground border-b">
                  <th className="py-2 pr-3">Channel</th>
                  <th className="py-2 pr-3">Segment</th>
                  <th className="py-2 pr-3 text-right">Customers (180d)</th>
                  <th className="py-2 pr-3 text-right">GP2 180d</th>
                  <th className="py-2 pr-3 text-right">GP2 365d</th>
                  <th className="py-2 pr-3 text-right">Uplift</th>
                  <th className="py-2 pr-3 text-right">Payback 180d</th>
                  <th className="py-2 text-right">Payback 365d</th>
                </tr>
              </thead>
              <tbody>
                {(data!.horizon as CacPaybackHorizonRow[]).map((row) => (
                  <tr
                    key={`${row.channel_group}-${row.segment}`}
                    className={row.is_channel_total ? 'border-b font-medium' : 'border-b last:border-0 text-muted-foreground'}
                  >
                    <td className="py-2 pr-3">{channelLabel(row.channel_group)}</td>
                    <td className="py-2 pr-3">{segmentLabel(row)}</td>
                    <td className="py-2 pr-3 text-right">{fmtCount(row.new_customers_180)}</td>
                    <td className="py-2 pr-3 text-right">{fmtMoney(row.gp2_180)}</td>
                    <td className="py-2 pr-3 text-right">{fmtMoney(row.gp2_365)}</td>
                    <td className="py-2 pr-3 text-right">{fmtPct(row.gp2_uplift_pct)}</td>
                    <td className={`py-2 pr-3 text-right ${paybackClass(row.payback_180)}`}>
                      {fmtPayback(row.payback_180)}
                    </td>
                    <td className={`py-2 text-right ${paybackClass(row.payback_365)}`}>
                      {fmtPayback(row.payback_365)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      ) : null}

      {data?.footnotes?.length ? (
        <div className="text-xs text-muted-foreground space-y-1">
          {data.as_of ? <p>As of {new Date(data.as_of).toLocaleString('sv-SE')}.</p> : null}
          {data.footnotes.map((f) => (
            <p key={f}>• {f}</p>
          ))}
        </div>
      ) : null}
    </div>
  )
}
