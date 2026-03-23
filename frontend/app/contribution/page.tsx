'use client'

import { useContribution } from '@/contexts/DataCacheContext'
import { useChartAnimations } from '@/contexts/ChartSettingsContext'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ChartConfig, ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart'
import { CartesianGrid, LabelList, Line, LineChart, XAxis } from '@/lib/recharts'
import { Skeleton } from '@/components/ui/skeleton'
import { Loader2 } from 'lucide-react'

export default function Contribution() {
  const { contributions } = useContribution()
  const isAnimationActive = useChartAnimations()

  const contributionLabels = [
    { key: 'gross_revenue_new', label: 'Gross Revenue New Customer', format: (val: number) => Math.round(val / 1000).toString() },
    { key: 'gross_revenue_returning', label: 'Gross Revenue Returning Customer', format: (val: number) => Math.round(val / 1000).toString() },
    { key: 'contribution_new', label: 'Total New Customer Contribution', format: (val: number) => Math.round(val / 1000).toString() },
    { key: 'contribution_returning', label: 'Total Returning Customer Contribution', format: (val: number) => Math.round(val / 1000).toString() },
    { key: 'contribution_total', label: 'Total Customer Contribution', format: (val: number) => Math.round(val / 1000).toString() }
  ]

  // Reorder labels for custom layout
  // First row: Gross Revenue New Customer | Total New Customer Contribution | Total Customer Contribution
  // Second row: Gross Revenue Returning Customer | Total Returning Customer Contribution | (empty)
  const layoutOrder = [
    contributionLabels[0], // Gross Revenue New Customer
    contributionLabels[2], // Total New Customer Contribution
    contributionLabels[4], // Total Customer Contribution
    contributionLabels[1], // Gross Revenue Returning Customer
    contributionLabels[3], // Total Returning Customer Contribution
  ]

  // Normalize contributions structure - handle both { contributions: [...] } and direct array
  let contributionData: any[] = []
  if (contributions) {
    if (Array.isArray(contributions)) {
      // Structure: direct array
      contributionData = contributions
    } else if (contributions.contributions && Array.isArray(contributions.contributions)) {
      // Structure: { contributions: [...] }
      contributionData = contributions.contributions
    } else if (typeof contributions === 'object') {
      // Structure: { contributions: {...} } - might be an object instead of array
      contributionData = Object.values(contributions.contributions || {}) as any[]
    }
  }

  if (!contributions || contributionData.length === 0) {
    return (
      <div className="space-y-8">
        <div className="flex items-center gap-3 mb-6">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Loading Contribution Metrics</h2>
            <p className="text-sm text-gray-600">Processing data from Qlik, DEMA, and GM2...</p>
          </div>
        </div>
        
        <div className="grid grid-cols-3 gap-6">
          {contributionLabels.map((_, index) => (
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
      {/* First row: Top 3 graphs */}
      <div className="grid grid-cols-3 gap-6">
        {layoutOrder.slice(0, 3).map((label, index) => {
          const chartData = contributionData.map(k => {
            const weekNum = k.week.split('-')[1]
            const currentValue = k[label.key as keyof typeof k] as number
            const lastYearValue = k.last_year?.[label.key as keyof typeof k.last_year] as number || 0
            
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

      {/* Second row: Bottom 2 graphs, centered */}
      <div className="grid grid-cols-3 gap-6">
        {layoutOrder.slice(3).map((label, index) => {
          const chartData = contributionData.map(k => {
            const weekNum = k.week.split('-')[1]
            const currentValue = k[label.key as keyof typeof k] as number
            const lastYearValue = k.last_year?.[label.key as keyof typeof k.last_year] as number || 0
            
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

