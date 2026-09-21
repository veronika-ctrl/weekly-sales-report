'use client'

import { useDataCache } from '@/contexts/DataCacheContext'
import { useChartAnimations } from '@/contexts/ChartSettingsContext'
import { getGenderSales, type GenderSalesData, type GenderSalesResponse } from '@/lib/api'
import { normalizeNamedSeries, useWeekSeriesLoad } from '@/lib/week-series-load'
import ReportLoadState from '@/components/ReportLoadState'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ChartConfig, ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart'
import { CartesianGrid, LabelList, Line, LineChart, XAxis } from '@/lib/recharts'
import { Skeleton } from '@/components/ui/skeleton'

export default function GenderSales() {
  const { baseWeek, gender_sales: cached } = useDataCache()
  const isAnimationActive = useChartAnimations()
  const { data, loading, error, retry } = useWeekSeriesLoad<GenderSalesResponse>({
    baseWeek,
    load: (week) => getGenderSales(week, 8),
    cached,
    hasRows: (payload) => normalizeNamedSeries<GenderSalesData>(payload, 'gender_sales').length > 0,
  })

  const genderLabels = [
    { key: 'men_unisex_sales', label: 'Gross Sales Men', format: (val: number) => Math.round(val / 1000).toString() },
    { key: 'women_sales', label: 'Gross Sales Womens', format: (val: number) => Math.round(val / 1000).toString() },
  ]

  const genderData = normalizeNamedSeries<GenderSalesData>(data, 'gender_sales')

  if (loading || error || genderData.length === 0) {
    return (
      <ReportLoadState
        loading={loading}
        error={error}
        empty={genderData.length === 0}
        onRetry={retry}
        loadingTitle="Loading Gender Sales"
        loadingHint="Reading Qlik sales by gender. Large exports can take a few minutes."
        emptyHint="Upload the Qlik export in Settings for this week, then open Gender Sales again."
        skeleton={
          <div className="grid grid-cols-2 gap-6">
            {genderLabels.map((_, index) => (
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
    <div className="space-y-8">
      <div className="grid grid-cols-2 gap-6">
        {genderLabels.map((label, index) => {
          const chartData = genderData.map((g) => {
            const weekNum = g.week.split('-')[1]
            const currentValue = g[label.key as keyof typeof g] as number
            const lastYearValue = g.last_year?.[label.key as keyof typeof g.last_year] as number || 0

            return {
              week: `W${weekNum}`,
              current: currentValue,
              lastYear: lastYearValue,
            }
          })

          const chartConfig = {
            current: {
              label: 'Current Year',
              color: '#4B5563',
            },
            lastYear: {
              label: 'Last Year',
              color: '#F97316',
            },
          } satisfies ChartConfig

          return (
            <Card key={index}>
              <CardHeader>
                <CardTitle>{label.label}</CardTitle>
              </CardHeader>
              <CardContent>
                <ChartContainer config={chartConfig}>
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
                        formatter={(val: unknown) => label.format(Number(val ?? 0))}
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
              </CardContent>
            </Card>
          )
        })}
      </div>
    </div>
  )
}
