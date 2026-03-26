'use client'

import { useEffect } from 'react'
import { useDataCache } from '@/contexts/DataCacheContext'
import { useChartAnimations } from '@/contexts/ChartSettingsContext'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ChartConfig, ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart'
import { Line, LineChart, XAxis, YAxis, LabelList, CartesianGrid } from '@/lib/recharts'
import { Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import Link from 'next/link'

function deriveMetrics(k: {
  new_customers?: number
  returning_customers?: number
  total_orders?: number
  aov_new_customer?: number
  aov_returning_customer?: number
  cos?: number
  new_customer_cac?: number
  return_rate_pct?: number
  return_rate_new_pct?: number
  return_rate_returning_pct?: number
}) {
  const newC = Number(k.new_customers) || 0
  const retC = Number(k.returning_customers) || 0
  const totalC = newC + retC
  const totalAov = totalC > 0
    ? (newC * (Number(k.aov_new_customer) || 0) + retC * (Number(k.aov_returning_customer) || 0)) / totalC
    : 0
  // Return rate % = (Gross − Net) / Gross from API (~5–6%). Do not use returning-customer share (that would be ~55%).
  const returnRatePct =
    typeof k.return_rate_pct === 'number' && Number.isFinite(k.return_rate_pct)
      ? k.return_rate_pct
      : 0
  const returnRateNewPct =
    typeof k.return_rate_new_pct === 'number' && Number.isFinite(k.return_rate_new_pct)
      ? k.return_rate_new_pct
      : 0
  const returnRateReturningPct =
    typeof k.return_rate_returning_pct === 'number' && Number.isFinite(k.return_rate_returning_pct)
      ? k.return_rate_returning_pct
      : 0
  const newCustomerSharePct = totalC > 0 ? (newC / totalC) * 100 : 0
  const returningCustomerSharePct = totalC > 0 ? (retC / totalC) * 100 : 0
  return {
    total_aov: Math.round(totalAov),
    total_customers: totalC,
    total_orders: Math.round(Number(k.total_orders) || 0),
    new_customers: newC,
    returning_customers: retC,
    new_customer_share_pct: Math.round(newCustomerSharePct * 10) / 10,
    returning_customer_share_pct: Math.round(returningCustomerSharePct * 10) / 10,
    return_rate_pct: Math.round(returnRatePct * 10) / 10,
    return_rate_new_pct: Math.round(returnRateNewPct * 10) / 10,
    return_rate_returning_pct: Math.round(returnRateReturningPct * 10) / 10,
    cos_pct: Number(k.cos) ?? 0,
    cac: Math.round(Number(k.new_customer_cac) ?? 0),
  }
}

export default function AudienceTotalPage() {
  const { baseWeek, loading, error, loadAllData, kpis: kpisData, periods, isDataReady } = useDataCache()
  const chartAnimationsEnabled = useChartAnimations()
  const isAnimationActive = chartAnimationsEnabled

  useEffect(() => {
    if (!baseWeek) return
    if (!periods && !loading) loadAllData(baseWeek, false)
  }, [baseWeek, loading, periods, loadAllData])

  let kpis: Array<{
    week: string
    new_customers?: number
    returning_customers?: number
    total_orders?: number
    aov_new_customer?: number
    aov_returning_customer?: number
    cos?: number
    new_customer_cac?: number
    last_year?: Record<string, number>
  }> = []
  if (kpisData) {
    if (Array.isArray(kpisData)) kpis = kpisData as any[]
    else if (kpisData?.kpis && Array.isArray(kpisData.kpis)) kpis = kpisData.kpis as any[]
    else if (typeof kpisData === 'object' && (kpisData as any).kpis)
      kpis = Object.values((kpisData as any).kpis) as any[]
  }


  const metrics = kpis.map((k) => {
    const current = deriveMetrics(k)
    const ly = k.last_year ? deriveMetrics(k.last_year as any) : null
    return {
      week: k.week,
      weekLabel: `W${k.week.split('-')[1]}`,
      ...current,
      last_year: ly,
    }
  })

  const noData = baseWeek && !loading && !error && (!periods || !isDataReady)
  const hasData = periods && isDataReady && metrics.length > 0
  const noAudienceData = baseWeek && !loading && !error && periods && isDataReady && metrics.length === 0

  const chartConfig = {
    value: { label: 'This year', color: '#4B5563' },
    lastYear: { label: 'Last year (same week)', color: '#F97316' },
  } satisfies ChartConfig

  const cards = [
    { key: 'total_aov', label: 'Total AOV', format: (v: number) => `${Math.round(v)}` },
    { key: 'total_customers', label: 'Total Customers', format: (v: number) => v.toLocaleString() },
    { key: 'total_orders', label: 'Total Orders', format: (v: number) => v.toLocaleString() },
    { key: 'new_customers', label: 'New Customers', format: (v: number) => v.toLocaleString() },
    { key: 'returning_customers', label: 'Returning Customers', format: (v: number) => v.toLocaleString() },
    { key: 'new_customer_share_pct', label: 'New Customer Share', format: (v: number) => `${v.toFixed(1)}%` },
    { key: 'returning_customer_share_pct', label: 'Returning Customer Share', format: (v: number) => `${v.toFixed(1)}%` },
    { key: 'return_rate_new_pct', label: 'Return Rate (New)', format: (v: number) => `${v.toFixed(1)}%` },
    { key: 'return_rate_returning_pct', label: 'Return Rate (Returning)', format: (v: number) => `${v.toFixed(1)}%` },
    { key: 'return_rate_pct', label: 'Return Rate', format: (v: number) => `${v.toFixed(1)}%` },
    { key: 'cos_pct', label: 'COS', format: (v: number) => `${v.toFixed(1)}%` },
    { key: 'cac', label: 'CAC', format: (v: number) => `${Math.round(v)}` },
  ]

  return (
    <div className="space-y-8">
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-sm text-red-800 mb-2">{error}</p>
          <Button onClick={() => baseWeek && loadAllData(baseWeek, true)} variant="outline" size="sm">
            Retry
          </Button>
        </div>
      )}
      {noData && (
        <div className="rounded-lg border bg-muted/40 p-6 text-center">
          <p className="text-sm text-muted-foreground mb-4">No data for this week. Choose another week above or sync data in Settings.</p>
          <Link href="/settings" className="inline-flex rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground">
            Go to Settings
          </Link>
        </div>
      )}
      {noAudienceData && (
        <div className="rounded-lg border bg-amber-50 border-amber-200 p-6 text-center">
          <p className="text-sm font-medium text-amber-900 mb-2">No audience data for this week</p>
          <p className="text-sm text-amber-800 mb-4">
            Audience metrics (Total AOV, customers, Return rate, COS, CAC) use the same data as the Summary and Online KPIs: <strong>Qlik</strong> (with Sales Channel, Country, New/Returning Customer) and <strong>DEMA</strong> (for COS and CAC). Upload or sync data for this week in Settings and ensure the files contain online sales by country.
          </p>
          <Link href="/settings" className="inline-flex rounded-md bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-700">
            Go to Settings
          </Link>
        </div>
      )}
      {!hasData && !noData && !noAudienceData && (
        <div className="flex items-center gap-3">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
          <p className="text-sm text-muted-foreground">Loading audience metrics...</p>
        </div>
      )}
      {hasData && (
        <>
          <h2 className="text-lg font-semibold text-gray-900">Audience Total</h2>
          <p className="text-sm text-muted-foreground mb-2">Total AOV, Total customers, Total orders, New customers, Returning customers, Return rate, COS, CAC. Comparison to last year uses the same ISO week (matching weekdays).</p>
          <p className="text-xs text-muted-foreground mb-4">
            By market:{' '}
            {['sweden', 'uk', 'usa', 'germany', 'france', 'canada', 'australia', 'row'].map((m) => (
              <Link key={m} href={`/audience/${m}`} className="text-primary hover:underline mr-2">
                {m === 'uk' ? 'UK' : m === 'usa' ? 'USA' : m === 'row' ? 'ROW' : m.charAt(0).toUpperCase() + m.slice(1)}
              </Link>
            ))}
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {cards.map(({ key, label, format }) => {
              const chartData = metrics.map((m) => {
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
                      : (m as any)[key]
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
                          ? (m.last_year as any)[key]
                          : null
                return {
                  week: m.weekLabel,
                  value: Number(value) || 0,
                  lastYear: lastYear == null ? null : Number(lastYear),
                }
              })
              return (
                <Card key={key}>
                  <CardHeader>
                    <CardTitle className="text-sm font-medium">{label}</CardTitle>
                  </CardHeader>
                  <CardContent className="overflow-visible">
                    <ChartContainer config={chartConfig} className="h-[260px] w-full min-w-0 overflow-visible">
                      <LineChart data={chartData} margin={{ top: 36, right: 12, left: 12, bottom: 8 }}>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} />
                        <XAxis dataKey="week" tick={{ fontSize: 11 }} />
                        <YAxis
                          tick={{ fontSize: 11 }}
                          width={40}
                          tickFormatter={(v) => (
                            (key === 'total_customers' || key === 'total_orders' || key === 'new_customers' || key === 'returning_customers') && v >= 1000
                              ? `${v / 1000}k`
                              : String(v)
                          )}
                        />
                        <ChartTooltip content={<ChartTooltipContent formatter={(v: unknown) => format(Number(v))} />} />
                        <Line
                          type="monotone"
                          dataKey="value"
                          stroke="#4B5563"
                          strokeWidth={2}
                          dot={{ r: 3 }}
                          isAnimationActive={isAnimationActive}
                          name="This year"
                        >
                          <LabelList position="top" offset={10} fontSize={12} fontWeight={600} fill="#1f2937" formatter={(v: unknown) => format(Number(v ?? 0))} />
                        </Line>
                        <Line
                          type="monotone"
                          dataKey="lastYear"
                          stroke="#F97316"
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
            })}
          </div>
        </>
      )}
    </div>
  )
}
