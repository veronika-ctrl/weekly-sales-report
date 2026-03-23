'use client'

import { useWomenCategorySales } from '@/contexts/DataCacheContext'
import { useChartAnimations } from '@/contexts/ChartSettingsContext'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ChartConfig, ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart'
import { CartesianGrid, LabelList, Line, LineChart, XAxis } from '@/lib/recharts'
import { Skeleton } from '@/components/ui/skeleton'
import { Loader2 } from 'lucide-react'

export default function WomenCategorySales() {
  const { women_category_sales } = useWomenCategorySales()
  const isAnimationActive = useChartAnimations()

  // Normalize women_category_sales structure - handle both { women_category_sales: [...] } and direct array
  let categoryData: any[] = []
  if (women_category_sales) {
    if (Array.isArray(women_category_sales)) {
      // Structure: direct array
      categoryData = women_category_sales
    } else if (women_category_sales.women_category_sales && Array.isArray(women_category_sales.women_category_sales)) {
      // Structure: { women_category_sales: [...] }
      categoryData = women_category_sales.women_category_sales
    } else if (typeof women_category_sales === 'object') {
      // Structure: { women_category_sales: {...} } - might be an object instead of array
      categoryData = Object.values(women_category_sales.women_category_sales || {}) as any[]
    }
  }

  if (!women_category_sales || categoryData.length === 0) {
    return (
      <div className="space-y-8">
        <div className="flex items-center gap-3 mb-6">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Loading Women Category Sales</h2>
            <p className="text-sm text-gray-600">Processing sales data by product category...</p>
          </div>
        </div>
        
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
      </div>
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

  // Sort by total sales descending
  const sortedCategories = categoryTotals.sort((a, b) => b.total - a.total).map(item => item.category)

  return (
    <div className="space-y-8">
      <div className="grid grid-cols-3 gap-6">
        {sortedCategories.map((category, index) => {
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
                        formatter={(label: unknown) => Math.round(Number(label ?? 0) / 1000).toString()}
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

