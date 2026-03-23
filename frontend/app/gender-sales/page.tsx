'use client'

import { useGenderSales } from '@/contexts/DataCacheContext'
import { useChartAnimations } from '@/contexts/ChartSettingsContext'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ChartConfig, ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart'
import { CartesianGrid, LabelList, Line, LineChart, XAxis } from '@/lib/recharts'
import { Skeleton } from '@/components/ui/skeleton'
import { Loader2 } from 'lucide-react'

export default function GenderSales() {
  const { gender_sales } = useGenderSales()
  const isAnimationActive = useChartAnimations()

  const genderLabels = [
    { key: 'men_unisex_sales', label: 'Gross Sales Men', format: (val: number) => Math.round(val / 1000).toString() },
    { key: 'women_sales', label: 'Gross Sales Womens', format: (val: number) => Math.round(val / 1000).toString() },
  ]

  // Normalize gender_sales structure - handle both { gender_sales: [...] } and direct array
  let genderData: any[] = []
  if (gender_sales) {
    if (Array.isArray(gender_sales)) {
      // Structure: direct array
      genderData = gender_sales
    } else if (gender_sales.gender_sales && Array.isArray(gender_sales.gender_sales)) {
      // Structure: { gender_sales: [...] }
      genderData = gender_sales.gender_sales
    } else if (typeof gender_sales === 'object') {
      // Structure: { gender_sales: {...} } - might be an object instead of array
      genderData = Object.values(gender_sales.gender_sales || {}) as any[]
    }
  }

  if (!gender_sales || genderData.length === 0) {
    return (
      <div className="space-y-8">
        <div className="flex items-center gap-3 mb-6">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Loading Gender Sales</h2>
            <p className="text-sm text-gray-600">Processing sales data by gender...</p>
          </div>
        </div>
        
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
      </div>
    )
  }

  return (
    <div className="space-y-8">
      <div className="grid grid-cols-2 gap-6">
        {genderLabels.map((label, index) => {
          const chartData = genderData.map(g => {
            const weekNum = g.week.split('-')[1]
            const currentValue = g[label.key as keyof typeof g] as number
            const lastYearValue = g.last_year?.[label.key as keyof typeof g.last_year] as number || 0
            
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

