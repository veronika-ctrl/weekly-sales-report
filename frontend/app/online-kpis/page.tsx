'use client'

import { useDataCache } from '@/contexts/DataCacheContext'
import { useChartAnimations } from '@/contexts/ChartSettingsContext'
import { getOnlineKPIs, type OnlineKPIsResponse } from '@/lib/api'
import { normalizeNamedSeries, useWeekSeriesLoad } from '@/lib/week-series-load'
import ReportLoadState from '@/components/ReportLoadState'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ChartConfig, ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart'
import { CartesianGrid, LabelList, Line, LineChart, ResponsiveContainer, XAxis } from '@/lib/recharts'
import { Skeleton } from '@/components/ui/skeleton'

export default function OnlineKPIsPage() {
  const isPdfMode = false
  const { baseWeek, kpis: cachedKpis } = useDataCache()
  const chartAnimationsEnabled = useChartAnimations()
  const isAnimationActive = !isPdfMode && chartAnimationsEnabled
  const { data, loading, error, retry } = useWeekSeriesLoad<OnlineKPIsResponse>({
    baseWeek,
    load: (week) => getOnlineKPIs(week, 8),
    cached: cachedKpis,
    hasRows: (payload) => normalizeNamedSeries(payload, 'kpis').length > 0,
  })

  const kpiLabels = [
    { key: 'sessions', label: 'Sessions', format: (val: number) => (val / 1000).toFixed(1) },
    { key: 'aov_new_customer', label: 'AOV New Customer', format: (val: number) => Math.round(val).toString() },
    { key: 'aov_returning_customer', label: 'AOV Returning Customer', format: (val: number) => Math.round(val).toString() },
    { key: 'cos', label: 'Cost of Sales', format: (val: number) => val.toFixed(1) + '%' },
    { key: 'marketing_spend', label: 'Marketing Spend', format: (val: number) => Math.round(val / 1000).toString() + 'k' },
    { key: 'conversion_rate', label: 'Conversion Rate', format: (val: number) => val.toFixed(1) + '%' },
    { key: 'new_customers', label: 'New Customers', format: (val: number) => val.toLocaleString() },
    { key: 'returning_customers', label: 'Returning Customers', format: (val: number) => val.toLocaleString() },
    { key: 'new_customer_cac', label: 'New Customer CAC', format: (val: number) => Math.round(val).toString() }
  ]

  const kpis = normalizeNamedSeries<OnlineKPIsResponse['kpis'][number]>(data, 'kpis')

  if (loading || error || kpis.length === 0) {
    return (
      <ReportLoadState
        loading={loading}
        error={error}
        empty={kpis.length === 0}
        onRetry={retry}
        loadingTitle="Loading Online KPIs"
        loadingHint="Reading Qlik, DEMA, and Shopify. Large exports can take a few minutes."
        emptyHint="Upload Qlik and DEMA for this week in Settings, then open Online KPIs again."
        skeleton={
          <div className="grid grid-cols-3 gap-6">
            {kpiLabels.map((_, index) => (
              <Card key={index}>
                <CardHeader>
                  <Skeleton className="h-5 w-48" />
                </CardHeader>
                <CardContent>
                  <Skeleton className="h-48 w-full" />
                </CardContent>
              </Card>
            ))}
          </div>
        }
      />
    )
  }

  return (
    <div className={`${isPdfMode ? 'space-y-1' : 'space-y-8'}`}>
      <div className={`grid ${isPdfMode ? 'grid-cols-3 gap-2' : 'grid-cols-3 gap-6'}`}>
        {kpiLabels.map((kpi, index) => {
          // Data comes in correct order W35->W42 from backend
          const chartData = kpis.map(k => {
            const weekNum = k.week.split('-')[1]
            const currentValue = k[kpi.key as keyof typeof k] as number
            const lastYearValue = k.last_year?.[kpi.key as keyof typeof k.last_year] as number || 0
            
            return {
              week: `W${weekNum}`,
              current: currentValue,
              lastYear: lastYearValue
            }
          })

          const chartConfig = {
            current: {
              label: "Current Year",
              color: "#4B5563", // Dark gray
            },
            lastYear: {
              label: "Last Year",
              color: "#F97316", // Orange
            },
          } satisfies ChartConfig

          return (
            <Card key={index} className={isPdfMode ? 'shadow-none border break-inside-avoid' : ''}>
              <CardHeader className={isPdfMode ? 'p-2 pb-1' : ''}>
                <CardTitle className={isPdfMode ? 'text-xs' : ''}>{kpi.label}</CardTitle>
              </CardHeader>
              <CardContent className={isPdfMode ? 'p-2 pt-1' : ''}>
                {isPdfMode ? (
                  <div className="w-full h-[150px]">
                    <ChartContainer 
                      config={chartConfig}
                      className="w-full h-full"
                    >
                      <LineChart
                        width={600}
                        height={150}
                        data={chartData}
                        margin={{
                          top: 5,
                          left: 5,
                          right: 5,
                          bottom: 5,
                        }}
                        isAnimationActive={isAnimationActive}
                      >
                        <CartesianGrid vertical={false} />
                        <XAxis
                          dataKey="week"
                          tickLine={false}
                          axisLine={false}
                          tickMargin={8}
                          tickFormatter={(value) => value.replace('W', '')}
                        />
                        <ChartTooltip
                          cursor={false}
                          content={<ChartTooltipContent indicator="line" />}
                        />
                        <Line
                          dataKey="current"
                          type="natural"
                          stroke="#4B5563"
                          strokeWidth={2}
                          isAnimationActive={isAnimationActive}
                          animationDuration={isAnimationActive ? undefined : 0}
                        >
                          <LabelList
                            position="top"
                            offset={12}
                            fill="#4B5563"
                            fontSize={12}
                            formatter={(val: unknown) => kpi.format(Number(val ?? 0))}
                          />
                        </Line>
                        <Line
                          dataKey="lastYear"
                          type="natural"
                          stroke="#F97316"
                          strokeWidth={2}
                          strokeDasharray="5 5"
                          isAnimationActive={isAnimationActive}
                          animationDuration={isAnimationActive ? undefined : 0}
                        />
                      </LineChart>
                    </ChartContainer>
                  </div>
                ) : (
                  <ChartContainer 
                    config={chartConfig}
                  >
                    <LineChart
                      accessibilityLayer
                      data={chartData}
                      margin={{
                        top: 20,
                        left: 12,
                        right: 12,
                      }}
                      isAnimationActive={isAnimationActive}
                    >
                      <CartesianGrid vertical={false} />
                      <XAxis
                        dataKey="week"
                        tickLine={false}
                        axisLine={false}
                        tickMargin={8}
                        tickFormatter={(value) => value.replace('W', '')}
                      />
                      <ChartTooltip
                        cursor={false}
                        content={<ChartTooltipContent indicator="line" />}
                      />
                      <Line
                        dataKey="current"
                        type="natural"
                        stroke="#4B5563"
                        strokeWidth={2}
                        isAnimationActive={isAnimationActive}
                        animationDuration={isAnimationActive ? undefined : 0}
                      >
                        <LabelList
                          position="top"
                          offset={12}
                          fill="#4B5563"
                          fontSize={12}
                          formatter={(val: unknown) => kpi.format(Number(val ?? 0))}
                        />
                      </Line>
                      <Line
                        dataKey="lastYear"
                        type="natural"
                        stroke="#F97316"
                        strokeWidth={2}
                        strokeDasharray="5 5"
                        isAnimationActive={isAnimationActive}
                        animationDuration={isAnimationActive ? undefined : 0}
                      />
                    </LineChart>
                  </ChartContainer>
                )}
              </CardContent>
            </Card>
          )
        })}
      </div>
    </div>
  )
}
