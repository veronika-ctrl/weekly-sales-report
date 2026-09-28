'use client'

import { useDataCache } from '@/contexts/DataCacheContext'
import { useChartAnimations } from '@/contexts/ChartSettingsContext'
import { getMenCategorySales, type MenCategorySalesData, type MenCategorySalesResponse } from '@/lib/api'
import { normalizeNamedSeries, useWeekSeriesLoad } from '@/lib/week-series-load'
import ReportLoadState from '@/components/ReportLoadState'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ChartConfig, ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart'
import { CartesianGrid, LabelList, Line, LineChart, XAxis } from '@/lib/recharts'
import { Skeleton } from '@/components/ui/skeleton'

export default function MenCategorySales() {
  const { baseWeek, men_category_sales: cached } = useDataCache()
  const isAnimationActive = useChartAnimations()
  const { data, loading, error, retry } = useWeekSeriesLoad<MenCategorySalesResponse>({
    baseWeek,
    load: (week) => getMenCategorySales(week, 8),
    cached,
    hasRows: (payload) => normalizeNamedSeries<MenCategorySalesData>(payload, 'men_category_sales').length > 0,
  })

  const categoryData = normalizeNamedSeries<MenCategorySalesData>(data, 'men_category_sales')

  if (loading || error || categoryData.length === 0) {
    return (
      <ReportLoadState
        loading={loading}
        error={error}
        empty={categoryData.length === 0}
        onRetry={retry}
        loadingTitle="Loading Men Category Sales"
        loadingHint="Reading Qlik sales by product category. Large exports can take a few minutes."
        emptyHint="Upload the Qlik export in Settings for this week, then open Men's Category Sales again."
        skeleton={
          <div className="grid grid-cols-3 gap-6">
            {[1, 2, 3, 4, 5, 6, 7].map((index) => (
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

  // Get all unique categories across all weeks
  const allCategories = new Set<string>()
  categoryData.forEach(week => {
    if (week.categories && typeof week.categories === 'object') {
      Object.keys(week.categories).forEach(cat => allCategories.add(cat))
    }
  })

  // Calculate total sales for each category and sort by highest to lowest
  const categoryTotals = Array.from(allCategories).map(category => {
    const total = categoryData.reduce((sum, week) => {
      return sum + ((week.categories && week.categories[category]) || 0)
    }, 0)
    return { category, total }
  })

  // Sort by total sales descending, then swap RESORT and ACCESSORIES.
  const sortedCategories = categoryTotals.sort((a, b) => b.total - a.total).map(item => item.category)
  const resortIndex = sortedCategories.findIndex((name) => name.toUpperCase() === 'RESORT')
  const accessoriesIndex = sortedCategories.findIndex((name) => name.toUpperCase() === 'ACCESSORIES')
  if (resortIndex !== -1 && accessoriesIndex !== -1 && resortIndex !== accessoriesIndex) {
    const resort = sortedCategories[resortIndex]
    sortedCategories[resortIndex] = sortedCategories[accessoriesIndex]
    sortedCategories[accessoriesIndex] = resort
  }

  return (
    <div className="space-y-8">
      <p className="text-sm text-muted-foreground">Values shown as sales amount in SEK &apos;000.</p>
      <div className="grid grid-cols-3 gap-6">
        {sortedCategories.map((category, index) => {
          const labelFormatter = (label: unknown) => {
            const value = Number(label ?? 0)
            if (category === 'MATERIAL') {
              const kValue = value / 1000
              if (Math.abs(kValue) < 0.05) return '0'
              return kValue.toFixed(1)
            }
            return Math.round(value / 1000).toString()
          }
          const chartData = categoryData.map(g => {
            const weekNum = g.week.split('-')[1]
            const currentValue = (g.categories && g.categories[category]) || 0
            const lastYearValue = (g.last_year?.categories && g.last_year.categories[category]) || 0
            
            return {
              week: `W${weekNum}`,
              current: currentValue,
              lastYear: lastYearValue
            }
          })

          const chartConfig = {
            current: {
              label: "Current Year",
              color: "#4B5563",
            },
            lastYear: {
              label: "Last Year",
              color: "#F97316",
            },
          } satisfies ChartConfig

          return (
            <Card key={category}>
              <CardHeader>
                <CardTitle>{category}</CardTitle>
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
                        formatter={labelFormatter}
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

