'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { useDataCache } from '@/contexts/DataCacheContext'
import { useChartAnimations } from '@/contexts/ChartSettingsContext'
import {
  getAdjustedAmer,
  getAdjustedAmerRecruited,
  hasBackend,
  type AdjustedAmerChannelMonth,
  type AdjustedAmerGroupMonth,
  type AdjustedAmerHeadline,
  type AdjustedAmerReconciliation,
  type AdjustedAmerResponse,
} from '@/lib/api'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ChartConfig, ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart'
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  XAxis,
  YAxis,
} from '@/lib/recharts'
import { Loader2 } from 'lucide-react'

function fmtRatio(v: number | null | undefined): string {
  if (v == null || Number.isNaN(Number(v)) || !Number.isFinite(Number(v))) return '—'
  return Number(v).toFixed(2)
}

function fmtPct(v: number | null | undefined): string {
  if (v == null || Number.isNaN(Number(v)) || !Number.isFinite(Number(v))) return '—'
  return `${(Number(v) * 100).toFixed(1)}%`
}

function fmtMoney(v: number | null | undefined): string {
  if (v == null || Number.isNaN(Number(v))) return '—'
  return Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })
}

const EMPTY_MONTHS: string[] = []
const LINE_CHART_MARGIN = { top: 16, right: 28, left: 12, bottom: 8 }

function demaChartClass(count: number): string {
  const width = count <= 4 ? 'max-w-xl' : count <= 12 ? 'max-w-3xl' : 'max-w-full'
  return `h-[320px] w-full ${width} !aspect-auto`
}

function loadedMonthsCaption(months: string[]): string {
  if (!months.length) return 'No Dema months loaded yet.'
  if (months.length >= 24) return 'Last 24 calendar months with Dema files.'
  if (months.length === 1) {
    return `Showing ${months[0]} (1 of last 24 months with a Dema file). Upload more calendar-month trios in Settings to extend.`
  }
  return `Showing ${months[0]}–${months[months.length - 1]} (${months.length} of last 24 months with Dema files). Upload more calendar-month trios in Settings to extend.`
}

function monthTickProps(count: number) {
  const few = count <= 8
  return {
    tickLine: false as const,
    axisLine: false as const,
    tickMargin: few ? 10 : 8,
    interval: 0 as const,
    minTickGap: few ? 8 : 0,
    angle: few ? 0 : -35,
    textAnchor: few ? ('middle' as const) : ('end' as const),
    height: few ? 36 : 56,
    tick: { fontSize: few ? 12 : 11 },
    padding: few ? { left: 48, right: 48 } : { left: 12, right: 12 },
  }
}

function trendDotRadius(count: number): number {
  return count <= 6 ? 5 : count <= 12 ? 3 : 2
}

function monthsWithData(rows: Array<{ year_month?: string }>, window: string[]): string[] {
  const allowed = new Set(window)
  const seen = new Set<string>()
  for (const row of rows) {
    const ym = row.year_month
    if (!ym) continue
    if (window.length && !allowed.has(ym)) continue
    seen.add(ym)
  }
  return Array.from(seen).sort()
}

function pivotGroupTrend(
  rows: AdjustedAmerGroupMonth[],
  valueKey: 'adjustedAMER' | 'newCustomerAdjustedAMER',
  window: string[]
): { months: string[]; groups: string[]; data: Array<Record<string, string | number | null>> } {
  const groups = Array.from(new Set(rows.filter((r) => r.bucket === 'paid').map((r) => r.channel_group))).sort()
  const axis = monthsWithData(rows.filter((r) => r.bucket === 'paid'), window)
  const data = axis.map((ym) => {
    const point: Record<string, string | number | null> = { year_month: ym }
    for (const g of groups) {
      const hit = rows.find((r) => r.year_month === ym && r.channel_group === g)
      point[g] = hit ? hit[valueKey] : null
    }
    return point
  })
  return { months: axis, groups, data }
}

function inWindow<T extends { year_month: string }>(rows: T[], months: string[]): T[] {
  if (!months.length) return rows
  const allowed = new Set(months)
  return rows.filter((r) => allowed.has(r.year_month))
}

const SHARE_COLORS = {
  paid: '#4B5563',
  organic: '#F97316',
  unattributed: '#6366F1',
  other: '#9CA3AF',
}

const CHANNEL_LINE_COLORS = ['#4B5563', '#F97316', '#2563EB', '#16A34A', '#DC2626', '#7C3AED', '#0891B2']

function fmtSek(v: number | null | undefined): string {
  if (v == null || Number.isNaN(Number(v))) return '—'
  return `${Number(v).toLocaleString('sv-SE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} SEK`
}

function KpiCard({
  title,
  value,
  hint,
  provisional,
}: {
  title: string
  value: string
  hint?: string
  provisional?: boolean
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-gray-700 flex items-center gap-2">
          {title}
          {provisional ? (
            <span className="text-[10px] font-semibold uppercase tracking-wide bg-amber-100 text-amber-800 px-1.5 py-0.5 rounded">
              Provisional
            </span>
          ) : null}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-semibold text-gray-900">{value}</div>
        {hint ? <p className="text-xs text-muted-foreground mt-1">{hint}</p> : null}
      </CardContent>
    </Card>
  )
}

function ShareBar({ week }: { week: AdjustedAmerHeadline }) {
  const slices = [
    { key: 'paid', label: 'Paid', value: week.paidRevenue, color: SHARE_COLORS.paid },
    { key: 'organic', label: 'Organic', value: week.organicRevenue, color: SHARE_COLORS.organic },
    { key: 'unattributed', label: 'Unattributed', value: week.unattributedRevenue, color: SHARE_COLORS.unattributed },
    { key: 'other', label: 'Other', value: week.otherRevenue, color: SHARE_COLORS.other },
  ]
  const total = slices.reduce((s, x) => s + x.value, 0)
  return (
    <div className="space-y-3">
      <div className="h-3 w-full rounded-full overflow-hidden flex bg-gray-100">
        {slices.map((s) => {
          const pct = total > 0 ? (s.value / total) * 100 : 0
          if (pct <= 0) return null
          return <div key={s.key} style={{ width: `${pct}%`, background: s.color }} title={`${s.label} ${pct.toFixed(1)}%`} />
        })}
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
        {slices.map((s) => (
          <div key={s.key} className="flex items-start gap-2">
            <span className="mt-1 h-2.5 w-2.5 rounded-full shrink-0" style={{ background: s.color }} />
            <div>
              <div className="font-medium text-gray-800">{s.label}</div>
              <div className="text-muted-foreground">
                {fmtMoney(s.value)} · {s.key === 'other' ? fmtPct(week.otherRevShare) : fmtPct(
                  s.key === 'paid' ? week.paidRevShare : s.key === 'organic' ? week.organicRevShare : week.unattributedShare
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
      <p className="text-xs text-muted-foreground">
        Paid / organic / unattributed shares are vs totalRevenue (paid + organic + unattributed). Other is shown
        separately and is not folded into organic.
      </p>
    </div>
  )
}

export default function AdjustedAmerPage() {
  const { baseWeek } = useDataCache()
  const weekToLoad = baseWeek || '2026-36'
  const chartAnimationsEnabled = useChartAnimations()
  const [data, setData] = useState<AdjustedAmerResponse | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [rvdLoading, setRvdLoading] = useState(false)

  const load = useCallback(async () => {
    if (!hasBackend) return
    setLoading(true)
    setErr(null)
    setRvdLoading(false)
    try {
      // Dema headline first so a huge Shopify customer CSV cannot blank the page.
      const headline = await getAdjustedAmer(weekToLoad, { includeCustomers: false })
      setData(headline)
      setLoading(false)
      setRvdLoading(true)
      try {
        const recruited = await getAdjustedAmerRecruited(weekToLoad)
        setData((prev) => (prev ? { ...prev, recruited_vs_dropped: recruited } : prev))
      } catch (rvdErr: unknown) {
        const message =
          rvdErr instanceof Error
            ? rvdErr.message
            : 'Shopify recruited vs dropped could not be loaded.'
        setData((prev) =>
          prev
            ? {
                ...prev,
                recruited_vs_dropped: {
                  available: false,
                  message,
                  months: [],
                },
              }
            : prev
        )
      } finally {
        setRvdLoading(false)
      }
    } catch (e: unknown) {
      setData(null)
      setErr(e instanceof Error ? e.message : 'Failed to load Adjusted aMER')
      setLoading(false)
      setRvdLoading(false)
    }
  }, [weekToLoad])

  useEffect(() => {
    void load()
  }, [load])

  const trendMonths = data?.trend_months ?? EMPTY_MONTHS
  const amerTrend = useMemo(
    () => pivotGroupTrend(data?.monthly_by_group ?? [], 'adjustedAMER', trendMonths),
    [data, trendMonths]
  )
  const newTrend = useMemo(
    () => pivotGroupTrend(data?.monthly_by_group ?? [], 'newCustomerAdjustedAMER', trendMonths),
    [data, trendMonths]
  )
  const headlineTrend = useMemo(() => {
    const rows = inWindow(
      (data?.monthly ?? []).filter((row) => Boolean(row.year_month)) as Array<
        AdjustedAmerHeadline & { year_month: string }
      >,
      trendMonths
    )
    return rows
      .slice()
      .sort((a, b) => a.year_month.localeCompare(b.year_month))
      .map((row) => ({
        year_month: row.year_month,
        adjustedAMER: row.adjustedAMER ?? null,
        blendedMER: row.blendedMER ?? null,
        newCustomerAdjustedAMER: row.newCustomerAdjustedAMER ?? null,
        netGM2: row.netGM2 ?? null,
        gp3: row.gp3 ?? null,
      }))
  }, [data, trendMonths])
  const demaMonthCaption = loadedMonthsCaption(headlineTrend.map((row) => row.year_month))
  const headlineTableRows = useMemo(
    () => inWindow((data?.monthly ?? []).filter((row) => Boolean(row.year_month)) as Array<AdjustedAmerHeadline & { year_month: string }>, trendMonths),
    [data, trendMonths]
  )
  const groupRows = useMemo(
    () => inWindow(data?.monthly_by_group ?? [], trendMonths),
    [data, trendMonths]
  )
  const channelRows = useMemo(
    () => inWindow(data?.monthly_by_channel ?? [], trendMonths),
    [data, trendMonths]
  )
  const churnMonths = useMemo(() => {
    const rows = data?.recruited_vs_dropped?.months ?? []
    if (!trendMonths.length) return rows
    const by = new Map(rows.map((r) => [r.year_month, r]))
    return trendMonths.map(
      (ym) => by.get(ym) ?? { year_month: ym, recruited: 0, dropped: 0, net: 0 }
    )
  }, [data, trendMonths])

  const amerChartConfig = useMemo(() => {
    const cfg: ChartConfig = {}
    amerTrend.groups.forEach((g, i) => {
      cfg[g] = { label: g, color: CHANNEL_LINE_COLORS[i % CHANNEL_LINE_COLORS.length] }
    })
    return cfg
  }, [amerTrend.groups])

  if (!hasBackend) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Adjusted aMER</CardTitle>
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
          <h2 className="text-lg font-semibold text-gray-900">Loading Adjusted aMER</h2>
          <p className="text-sm text-gray-600">Joining Dema agent revenue, spend, and Net GM2 files…</p>
        </div>
      </div>
    )
  }

  const week = data?.week ?? null
  const rvd = data?.recruited_vs_dropped

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-lg font-semibold text-gray-900">Adjusted aMER</h2>
        <p className="text-sm text-muted-foreground mt-1 max-w-3xl">
          Separate from weekly Dema/Shopify/Qlik reports. Upload the scheduled Dema agent trio
          (Revenue by channel, Marketing spend, Net GM2) in Settings. Headline uses Revenue_CFA;
          new-customer Adjusted aMER uses Revenue_New_MTA (MTA). Ratios are
          ChannelGroup grain only (sem / social_ppc / affiliate) — never per Channel.
          {data?.week_range?.display ? ` Week ${data.base_week}: ${data.week_range.display}.` : null}
        </p>
      </div>

      {err ? (
        <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded p-3">{err}</div>
      ) : null}

      {(data?.warnings ?? []).map((w) => (
        <div key={w.code} className="text-sm text-amber-900 bg-amber-50 border border-amber-200 rounded p-3">
          <div className="font-medium mb-0.5">
            {w.code === 'reconciliation_mismatch' ? 'Reconciliation' : 'Missing file / agent check'}
          </div>
          {w.message}{' '}
          <Link href="/settings" className="underline font-medium">
            Open Settings
          </Link>
        </div>
      ))}

      {(data?.reconciliation?.length ?? 0) > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Dema file reconciliation</CardTitle>
            <CardDescription>
              Source-file Net sales and Marketing spend vs the validated W36 and August 2026 totals.
            </CardDescription>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-muted-foreground border-b">
                  <th className="py-2 pr-3">Period</th>
                  <th className="py-2 pr-3 text-right">Net sales</th>
                  <th className="py-2 pr-3 text-right">Expected sales</th>
                  <th className="py-2 pr-3 text-right">Spend</th>
                  <th className="py-2 pr-3 text-right">Expected spend</th>
                  <th className="py-2">Match</th>
                </tr>
              </thead>
              <tbody>
                {data!.reconciliation!.map((row: AdjustedAmerReconciliation) => (
                  <tr key={`${row.kind}-${row.key}`} className="border-b last:border-0">
                    <td className="py-2 pr-3">{row.label}</td>
                    <td className="py-2 pr-3 text-right">{fmtSek(row.net_sales)}</td>
                    <td className="py-2 pr-3 text-right">{fmtSek(row.expected_net_sales)}</td>
                    <td className="py-2 pr-3 text-right">{fmtSek(row.marketing_spend)}</td>
                    <td className="py-2 pr-3 text-right">{fmtSek(row.expected_marketing_spend)}</td>
                    <td className="py-2">
                      <span className={row.match ? 'text-green-700 font-medium' : 'text-amber-800 font-medium'}>
                        {row.match ? 'Match' : 'Not matched'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      ) : null}

      {week ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-4">
          <KpiCard
            title="Adjusted aMER"
            value={fmtRatio(week.adjustedAMER)}
            hint="Paid Revenue_CFA ÷ paid spend (ChannelGroup)"
            provisional={week.provisional}
          />
          <KpiCard
            title="New-customer Adjusted aMER"
            value={fmtRatio(week.newCustomerAdjustedAMER)}
            hint="MTA-based — paid Revenue_New_MTA ÷ paid spend (ChannelGroup)"
            provisional={week.provisional}
          />
          <KpiCard title="Blended MER" value={fmtRatio(week.blendedMER)} hint="(Paid + organic + unattributed) CFA ÷ paid spend (ChannelGroup)" />
          <KpiCard title="Net GM2" value={fmtPct(week.netGM2)} hint="sum(Net gross profit 2) ÷ sum(Net sales)" />
          <KpiCard title="GP3" value={fmtMoney(week.gp3)} hint="Net gross profit 2 − Marketing spend (KR)" />
        </div>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>This week&apos;s headline</CardTitle>
            <CardDescription>
              No complete Dema agent trio for the selected week, so headline ratios are not shown.
              Stale files from other weeks are not substituted.
            </CardDescription>
          </CardHeader>
        </Card>
      )}

      {week ? (
        <Card>
          <CardHeader>
            <CardTitle>Paid / organic / unattributed revenue share</CardTitle>
            <CardDescription>Revenue_CFA. Unattributed is not folded into organic. Other ChannelGroups stay visible.</CardDescription>
          </CardHeader>
          <CardContent>
            <ShareBar week={week} />
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Monthly Adjusted aMER</CardTitle>
          <CardDescription>
            Company headline: paid Revenue_CFA ÷ paid spend. {demaMonthCaption}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {headlineTrend.length === 0 ? (
            <p className="text-sm text-muted-foreground">No monthly series yet — upload the Dema agent files for this week.</p>
          ) : (
            <ChartContainer config={{ adjustedAMER: { label: 'Adjusted aMER', color: '#111827' } }} className={demaChartClass(headlineTrend.length)}>
              <LineChart data={headlineTrend} margin={LINE_CHART_MARGIN} isAnimationActive={chartAnimationsEnabled}>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="year_month" {...monthTickProps(headlineTrend.length)} />
                <YAxis tickLine={false} axisLine={false} domain={['auto', 'auto']} width={48} />
                <ChartTooltip content={<ChartTooltipContent />} />
                <Legend />
                <Line
                  dataKey="adjustedAMER"
                  name="Adjusted aMER"
                  type="monotone"
                  stroke="#111827"
                  strokeWidth={2.5}
                  dot={{ r: trendDotRadius(headlineTrend.length) }}
                  activeDot={{ r: trendDotRadius(headlineTrend.length) + 2 }}
                  connectNulls={false}
                  isAnimationActive={chartAnimationsEnabled}
                />
              </LineChart>
            </ChartContainer>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Monthly Adjusted aMER by ChannelGroup</CardTitle>
          <CardDescription>
            Calendar month of Day. Ratios are sem / social_ppc / affiliate (never Channel).
            Meta spend is on facebook; CFA splits across facebook + instagram.
            {data?.monthly?.some((m) => m.provisional) ? ' Periods younger than ~6 weeks are flagged provisional. ' : ' '}
            {demaMonthCaption}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {amerTrend.groups.length === 0 ? (
            <p className="text-sm text-muted-foreground">No monthly series yet — upload the Dema agent files for this week.</p>
          ) : (
            <ChartContainer config={amerChartConfig} className={demaChartClass(amerTrend.data.length)}>
              <LineChart data={amerTrend.data} margin={LINE_CHART_MARGIN} isAnimationActive={chartAnimationsEnabled}>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="year_month" {...monthTickProps(amerTrend.data.length)} />
                <YAxis tickLine={false} axisLine={false} domain={['auto', 'auto']} width={48} />
                <ChartTooltip content={<ChartTooltipContent />} />
                <Legend />
                {amerTrend.groups.map((g, i) => (
                  <Line
                    key={g}
                    dataKey={g}
                    type="monotone"
                    stroke={CHANNEL_LINE_COLORS[i % CHANNEL_LINE_COLORS.length]}
                    strokeWidth={2.5}
                    dot={{ r: trendDotRadius(amerTrend.data.length) }}
                    activeDot={{ r: trendDotRadius(amerTrend.data.length) + 2 }}
                    connectNulls={false}
                    isAnimationActive={chartAnimationsEnabled}
                  />
                ))}
              </LineChart>
            </ChartContainer>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Monthly new-customer Adjusted aMER by ChannelGroup (MTA-based)</CardTitle>
          <CardDescription>
            Paid Revenue_New_MTA ÷ ChannelGroup spend. Not the same methodology as headline Adjusted aMER (CFA). {demaMonthCaption}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {newTrend.groups.length === 0 ? (
            <p className="text-sm text-muted-foreground">No monthly series yet.</p>
          ) : (
            <ChartContainer config={amerChartConfig} className={demaChartClass(newTrend.data.length)}>
              <LineChart data={newTrend.data} margin={LINE_CHART_MARGIN} isAnimationActive={chartAnimationsEnabled}>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="year_month" {...monthTickProps(newTrend.data.length)} />
                <YAxis tickLine={false} axisLine={false} domain={['auto', 'auto']} width={48} />
                <ChartTooltip content={<ChartTooltipContent />} />
                <Legend />
                {newTrend.groups.map((g, i) => (
                  <Line
                    key={g}
                    dataKey={g}
                    type="monotone"
                    stroke={CHANNEL_LINE_COLORS[i % CHANNEL_LINE_COLORS.length]}
                    strokeWidth={2.5}
                    dot={{ r: trendDotRadius(newTrend.data.length) }}
                    activeDot={{ r: trendDotRadius(newTrend.data.length) + 2 }}
                    connectNulls={false}
                    isAnimationActive={chartAnimationsEnabled}
                  />
                ))}
              </LineChart>
            </ChartContainer>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Monthly Net GM2 and GP3</CardTitle>
          <CardDescription>
            Net GM2 = sum(Net gross profit 2) ÷ sum(Net sales). GP3 = Net gross profit 2 − Marketing spend (KR). {demaMonthCaption}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {headlineTrend.length === 0 ? (
            <p className="text-sm text-muted-foreground">No monthly series yet.</p>
          ) : (
            <ChartContainer
              config={{ netGM2: { label: 'Net GM2', color: '#7C3AED' }, gp3: { label: 'GP3', color: '#0891B2' } }}
              className={demaChartClass(headlineTrend.length)}
            >
              <ComposedChart data={headlineTrend} margin={LINE_CHART_MARGIN} isAnimationActive={chartAnimationsEnabled}>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="year_month" {...monthTickProps(headlineTrend.length)} />
                <YAxis
                  yAxisId="gm2"
                  tickLine={false}
                  axisLine={false}
                  width={48}
                  tickFormatter={(v: number) => `${(Number(v) * 100).toFixed(0)}%`}
                />
                <YAxis yAxisId="gp3" orientation="right" width={64} tickLine={false} axisLine={false} tickFormatter={(v: number) => fmtMoney(v)} />
                <ChartTooltip content={<ChartTooltipContent />} />
                <Legend />
                <Line
                  yAxisId="gm2"
                  dataKey="netGM2"
                  name="Net GM2"
                  type="monotone"
                  stroke="#7C3AED"
                  strokeWidth={2.5}
                  dot={{ r: trendDotRadius(headlineTrend.length) }}
                  activeDot={{ r: trendDotRadius(headlineTrend.length) + 2 }}
                  connectNulls={false}
                  isAnimationActive={chartAnimationsEnabled}
                />
                <Line
                  yAxisId="gp3"
                  dataKey="gp3"
                  name="GP3"
                  type="monotone"
                  stroke="#0891B2"
                  strokeWidth={2.5}
                  dot={{ r: trendDotRadius(headlineTrend.length) }}
                  activeDot={{ r: trendDotRadius(headlineTrend.length) + 2 }}
                  connectNulls={false}
                  isAnimationActive={chartAnimationsEnabled}
                />
              </ComposedChart>
            </ChartContainer>
          )}
        </CardContent>
      </Card>

      {headlineTableRows.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Monthly headline table</CardTitle>
            <CardDescription>
              Company-level ratios plus Net GM2 and GP3 for months with a Dema agent file. {demaMonthCaption}
            </CardDescription>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-muted-foreground border-b">
                  <th className="py-2 pr-3">Month</th>
                  <th className="py-2 pr-3 text-right">Adj. aMER</th>
                  <th className="py-2 pr-3 text-right">NC adj. aMER (MTA)</th>
                  <th className="py-2 pr-3 text-right">Blended MER</th>
                  <th className="py-2 pr-3 text-right">Net GM2</th>
                  <th className="py-2 text-right">GP3</th>
                </tr>
              </thead>
              <tbody>
                {headlineTableRows.map((row) => (
                  <tr key={row.year_month} className="border-b last:border-0">
                    <td className="py-2 pr-3">{row.year_month}</td>
                    <td className="py-2 pr-3 text-right">{fmtRatio(row.adjustedAMER)}</td>
                    <td className="py-2 pr-3 text-right">{fmtRatio(row.newCustomerAdjustedAMER)}</td>
                    <td className="py-2 pr-3 text-right">{fmtRatio(row.blendedMER)}</td>
                    <td className="py-2 pr-3 text-right">{fmtPct(row.netGM2)}</td>
                    <td className="py-2 text-right">{fmtMoney(row.gp3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      ) : null}

      {groupRows.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Monthly ChannelGroup table (last 24 months)</CardTitle>
            <CardDescription>
              Adjusted aMER and new-customer aMER at ChannelGroup grain. Net GM2 and GP3 sit next to them.
              Channel rows below are revenue only.
            </CardDescription>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-muted-foreground border-b">
                  <th className="py-2 pr-3">Month</th>
                  <th className="py-2 pr-3">Group</th>
                  <th className="py-2 pr-3">Bucket</th>
                  <th className="py-2 pr-3">Channels</th>
                  <th className="py-2 pr-3 text-right">Adj. aMER</th>
                  <th className="py-2 pr-3 text-right">NC adj. aMER (MTA)</th>
                  <th className="py-2 pr-3 text-right">Net GM2</th>
                  <th className="py-2 pr-3 text-right">GP3</th>
                  <th className="py-2 pr-3 text-right">CFA</th>
                  <th className="py-2 text-right">Spend</th>
                </tr>
              </thead>
              <tbody>
                {groupRows.map((row) => (
                  <tr key={`${row.year_month}-${row.channel_group}`} className="border-b last:border-0">
                    <td className="py-2 pr-3">
                      {row.year_month}
                      {row.provisional ? (
                        <span className="ml-2 text-[10px] uppercase bg-amber-100 text-amber-800 px-1 rounded">prov.</span>
                      ) : null}
                    </td>
                    <td className="py-2 pr-3">{row.channel_group}</td>
                    <td className="py-2 pr-3">{row.bucket}</td>
                    <td className="py-2 pr-3 text-muted-foreground">{row.channels.join(', ')}</td>
                    <td className="py-2 pr-3 text-right">{fmtRatio(row.adjustedAMER)}</td>
                    <td className="py-2 pr-3 text-right">{fmtRatio(row.newCustomerAdjustedAMER)}</td>
                    <td className="py-2 pr-3 text-right">{fmtPct(row.netGM2)}</td>
                    <td className="py-2 pr-3 text-right">{fmtMoney(row.gp3)}</td>
                    <td className="py-2 pr-3 text-right">{fmtMoney(row.revenue_cfa)}</td>
                    <td className="py-2 text-right">{fmtMoney(row.paidSpend)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      ) : null}

      {channelRows.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Monthly channel revenue (no ratios, last 24 months)</CardTitle>
            <CardDescription>
              Individual channels are shown for CFA and spend totals only. Instagram can have CFA with zero spend.
            </CardDescription>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-muted-foreground border-b">
                  <th className="py-2 pr-3">Month</th>
                  <th className="py-2 pr-3">Channel</th>
                  <th className="py-2 pr-3">Group</th>
                  <th className="py-2 pr-3">Bucket</th>
                  <th className="py-2 pr-3 text-right">CFA</th>
                  <th className="py-2 text-right">Spend</th>
                </tr>
              </thead>
              <tbody>
                {channelRows.map((row: AdjustedAmerChannelMonth) => (
                  <tr key={`${row.year_month}-${row.channel}-${row.channel_group}`} className="border-b last:border-0">
                    <td className="py-2 pr-3">{row.year_month}</td>
                    <td className="py-2 pr-3">{row.channel}</td>
                    <td className="py-2 pr-3">{row.channel_group}</td>
                    <td className="py-2 pr-3">{row.bucket}</td>
                    <td className="py-2 pr-3 text-right">{fmtMoney(row.revenue_cfa)}</td>
                    <td className="py-2 text-right">{fmtMoney(row.paidSpend)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Recruited vs dropped (Shopify customer orders, last 24 months)</CardTitle>
          <CardDescription>
            Recruited = earliest order since 2022-01-01 in the month. Dropped = last order exactly 12 months earlier,
            with no order since. The net line is recruited − dropped each month.
            Native Shopify reports: Customer ID + Second, filtered to Orders = 1
            (Orders = 0 is a later return/refund/edit). Dema / Sessions / Qlik are not used.
            {rvd?.available && rvd.as_of
              ? ` ${Number(rvd.customer_count ?? 0).toLocaleString()} customers · ${Number(rvd.order_count ?? 0).toLocaleString()} order-days through ${rvd.as_of}. The last month is month-to-date.`
              : null}{' '}
            Last 24 calendar months.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {!rvd?.available && rvdLoading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading recruited vs dropped from Shopify customer orders…
            </div>
          ) : !rvd?.available ? (
            <div className="rounded-md border border-dashed bg-muted/30 p-6 text-sm text-muted-foreground">
              {rvd?.message ?? 'Upload Shopify customer orders in Settings to compute recruited vs dropped.'}{' '}
              <Link href="/settings" className="underline font-medium text-foreground">
                Upload in Settings
              </Link>
            </div>
          ) : (
            <ChartContainer
              config={{
                recruited: { label: 'Recruited', color: '#16A34A' },
                dropped: { label: 'Dropped', color: '#DC2626' },
                net: { label: 'Net', color: '#1D4ED8' },
              }}
              className="h-[320px] w-full"
            >
              <ComposedChart data={churnMonths} isAnimationActive={chartAnimationsEnabled}>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="year_month" {...monthTickProps(churnMonths.length)} />
                <YAxis tickLine={false} axisLine={false} />
                <ReferenceLine y={0} stroke="#9CA3AF" strokeDasharray="3 3" />
                <ChartTooltip content={<ChartTooltipContent />} />
                <Legend />
                <Bar dataKey="recruited" name="Recruited" fill="#16A34A" radius={2} />
                <Bar dataKey="dropped" name="Dropped" fill="#DC2626" radius={2} />
                <Line
                  dataKey="net"
                  name="Net"
                  type="monotone"
                  stroke="#1D4ED8"
                  strokeWidth={2}
                  dot={{ r: 2 }}
                  isAnimationActive={chartAnimationsEnabled}
                />
              </ComposedChart>
            </ChartContainer>
          )}
        </CardContent>
      </Card>

      {data?.taxonomy ? (
        <Card>
          <CardHeader>
            <CardTitle>ChannelGroup taxonomy</CardTitle>
            <CardDescription>{data.taxonomy.notes}</CardDescription>
          </CardHeader>
          <CardContent className="text-sm space-y-2">
            {(data.taxonomy.observed_groups ?? []).length === 0 ? (
              <p className="text-muted-foreground">No ChannelGroups observed yet.</p>
            ) : (
              <ul className="grid md:grid-cols-2 gap-2">
                {data.taxonomy.observed_groups.map((g) => (
                  <li key={`${g.bucket}-${g.group}`} className="rounded border bg-muted/20 px-3 py-2">
                    <span className="font-medium">{g.group}</span>
                    <span className="text-muted-foreground"> → {g.bucket}</span>
                    <div className="text-xs text-muted-foreground">{g.channels.join(', ')}</div>
                  </li>
                ))}
              </ul>
            )}
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
