'use client'

import { useParams } from 'next/navigation'
import { useEffect, useState } from 'react'
import { useDataCache } from '@/contexts/DataCacheContext'
import { useChartAnimations } from '@/contexts/ChartSettingsContext'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ChartConfig, ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart'
import { Line, LineChart, XAxis, YAxis, LabelList, CartesianGrid } from '@/lib/recharts'
import { Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import Link from 'next/link'
import { getAudienceMetricsPerCountry, type AudienceMetricsCountryData } from '@/lib/api'

const SLUG_TO_NAME: Record<string, string> = {
  sweden: 'Sweden',
  uk: 'United Kingdom',
  'united-kingdom': 'United Kingdom',
  usa: 'United States',
  'united-states': 'United States',
  germany: 'Germany',
  france: 'France',
  canada: 'Canada',
  australia: 'Australia',
  switzerland: 'Switzerland',
  uae: 'UAE',
  row: 'ROW',
}

function slugToMarketName(slug: string): string {
  const normalized = (slug || '').toLowerCase().replace(/\s+/g, '-')
  return SLUG_TO_NAME[normalized] ?? slug.replace(/-/g, ' ')
}

export default function AudienceMarketPage() {
  const params = useParams()
  const slug = typeof params?.market === 'string' ? params.market : ''
  const marketName = slugToMarketName(slug)
  const { baseWeek, loading, periods, loadAllData, isDataReady, error } = useDataCache()
  const chartAnimationsEnabled = useChartAnimations()
  const isAnimationActive = chartAnimationsEnabled

  const [audienceData, setAudienceData] = useState<
    Array<
      {
        week: string
        weekLabel: string
        last_year?: AudienceMetricsCountryData['last_year']
      } & AudienceMetricsCountryData
    > | null
  >(null)
  const [fetchError, setFetchError] = useState<string | null>(null)

  useEffect(() => {
    if (!baseWeek) return
    if (!periods && !loading) loadAllData(baseWeek, false)
  }, [baseWeek, loading, periods, loadAllData])

  useEffect(() => {
    if (!baseWeek || !marketName) return
    let cancelled = false
    getAudienceMetricsPerCountry(baseWeek, 8)
      .then((res) => {
        if (cancelled) return
        const byWeek = res.audience_metrics_per_country || []
        const firstWeek = byWeek[0]
        const countryKeys = firstWeek ? Object.keys(firstWeek.countries || {}) : []
        const nameMatch = countryKeys.find(
          (c) =>
            c.toLowerCase() === marketName.toLowerCase() ||
            c.toLowerCase().replace(/\s+/g, '-') === (slug || '').toLowerCase()
        )
        const countryKey = nameMatch || marketName

        const series = byWeek.map((w) => {
          const c = w.countries[countryKey] || w.countries[marketName]
          if (!c) return null
          return {
            week: w.week,
            weekLabel: `W${w.week.split('-')[1]}`,
            ...c,
            last_year: c.last_year ?? null,
          }
        }).filter(Boolean) as Array<
          {
            week: string
            weekLabel: string
            last_year?: AudienceMetricsCountryData['last_year']
          } & AudienceMetricsCountryData
        >
        setAudienceData(series.length ? series : null)
        setFetchError(series.length ? null : `No data for market "${marketName}"`)
      })
      .catch((e) => {
        if (!cancelled) {
          setFetchError(e?.message || 'Failed to load audience metrics')
          setAudienceData(null)
        }
      })
    return () => {
      cancelled = true
    }
  }, [baseWeek, marketName, slug])

  const noData = baseWeek && !loading && !error && (!periods || !isDataReady)
  const hasData = periods && isDataReady && audienceData && audienceData.length > 0

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
      {fetchError && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
          <p className="text-sm text-amber-800">{fetchError}</p>
          <Link href="/audience-total" className="text-sm text-amber-700 underline mt-2 inline-block">Back to Audience Total</Link>
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
      {!hasData && !noData && !fetchError && (
        <div className="flex items-center gap-3">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
          <p className="text-sm text-muted-foreground">Loading audience metrics for {marketName}...</p>
        </div>
      )}
      {hasData && (
        <>
          <h2 className="text-lg font-semibold text-gray-900">Audience — {marketName}</h2>
          <p className="text-sm text-muted-foreground mb-2">Total AOV, Total customers, Total orders, New customers, Returning customers, Return rate in market, COS, CAC. Comparison to last year uses the same ISO week (matching weekdays).</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {cards.map(({ key, label, format }) => {
              const chartData = audienceData!.map((m) => {
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
                      ? m.last_year != null
                        ? lyTotal > 0
                          ? (Number(m.last_year.new_customers) / lyTotal) * 100
                          : 0
                        : null
                      : key === 'returning_customer_share_pct'
                        ? m.last_year != null
                          ? lyTotal > 0
                            ? (Number(m.last_year.returning_customers) / lyTotal) * 100
                            : 0
                          : null
                        : m.last_year != null
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
          <Link href="/audience-total" className="text-sm text-muted-foreground hover:text-foreground">← Back to Audience Total</Link>
        </>
      )}
    </div>
  )
}
