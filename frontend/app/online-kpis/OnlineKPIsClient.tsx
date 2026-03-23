'use client'

import { useKPIs } from '@/contexts/DataCacheContext'
import { useChartAnimations } from '@/contexts/ChartSettingsContext'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ChartConfig, ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart'
import { CartesianGrid, LabelList, Line, LineChart, XAxis } from '@/lib/recharts'
import { Loader2 } from 'lucide-react'
import type { OnlineKPIsResponse } from '@/lib/api'
import { Skeleton } from '@/components/ui/skeleton'

export interface OnlineKPIsClientProps {
  isPdfMode?: boolean
  dataOverride?: OnlineKPIsResponse | null
}

export default function OnlineKPIsClient({ isPdfMode = false, dataOverride }: OnlineKPIsClientProps) {
  const { kpis: contextKpis } = useKPIs()
  const kpisData = dataOverride ?? contextKpis
  const chartAnimationsEnabled = useChartAnimations()
  // Disable animations in PDF mode
  const isAnimationActive = !isPdfMode && chartAnimationsEnabled

  const kpiLabels = [
    { key: 'sessions', label: 'Sessions', format: (val: number) => (val / 1000).toFixed(1) },
    { key: 'aov_new_customer', label: 'AOV New Customer', format: (val: number) => Math.round(val).toString() },
    { key: 'aov_returning_customer', label: 'AOV Returning Customer', format: (val: number) => Math.round(val).toString() },
    { key: 'cos', label: 'Cost of Sales', format: (val: number) => val.toFixed(1) + '%' },
    { key: 'marketing_spend', label: 'Marketing Spend', format: (val: number) => Math.round(val / 1000).toString() + 'k' },
    { key: 'conversion_rate', label: 'Conversion Rate', format: (val: number) => val.toFixed(1) + '%' },
    { key: 'new_customers', label: 'New Customers', format: (val: number) => val.toLocaleString() },
    { key: 'returning_customers', label: 'Returning Customers', format: (val: number) => val.toLocaleString() },
    { key: 'new_customer_cac', label: 'New Customer CAC', format: (val: number) => Math.round(val).toString() },
  ]

  // Normalize kpis structure - handle both { kpis: [...] } and direct array
  let kpis: any[] = []
  if (kpisData) {
    if (Array.isArray(kpisData)) {
      // Structure: direct array
      kpis = kpisData
    } else if (kpisData && typeof kpisData === 'object' && 'kpis' in kpisData) {
      // Structure: { kpis: [...] } - this is the expected OnlineKPIsResponse structure
      if (Array.isArray((kpisData as any).kpis)) {
        kpis = (kpisData as any).kpis
      } else if (typeof (kpisData as any).kpis === 'object' && (kpisData as any).kpis !== null) {
        // Structure: { kpis: {...} } - might be an object instead of array
        kpis = Object.values((kpisData as any).kpis) as any[]
      }
    }
  }

  // Debug logging (remove in production)
  if (typeof window !== 'undefined' && process.env.NODE_ENV === 'development') {
    // eslint-disable-next-line no-console
    console.log('[OnlineKPIs] kpisData:', kpisData)
    // eslint-disable-next-line no-console
    console.log('[OnlineKPIs] kpisData type:', typeof kpisData)
    // eslint-disable-next-line no-console
    console.log('[OnlineKPIs] kpisData is array:', Array.isArray(kpisData))
    // eslint-disable-next-line no-console
    console.log('[OnlineKPIs] kpisData.kpis:', kpisData && typeof kpisData === 'object' ? (kpisData as any).kpis : 'N/A')
    // eslint-disable-next-line no-console
    console.log('[OnlineKPIs] normalized kpis:', kpis)
    // eslint-disable-next-line no-console
    console.log('[OnlineKPIs] kpis length:', kpis.length)
  }

  if (!kpisData || kpis.length === 0) {
    return (
      <div className="space-y-8">
        <div className="flex items-center gap-3 mb-6">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Loading Online KPIs</h2>
            <p className="text-sm text-gray-600">Processing data from Qlik, DEMA, and Shopify...</p>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-6">
          {kpiLabels.map((kpi, index) => (
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
    <div className={`${isPdfMode ? 'space-y-1' : 'space-y-8'}`}>
      <div className={`grid ${isPdfMode ? 'grid-cols-3 gap-2' : 'grid-cols-3 gap-6'}`}>
        {kpiLabels.map((kpi, index) => {
          // Data comes in correct order W35->W42 from backend
          const chartData = kpis
            .filter((k) => k && k.week) // Filter out null/undefined entries
            .map((k) => {
              const weekNum = k.week.split('-')[1]
              const currentValue = k[kpi.key as keyof typeof k] as number
              const lastYearValue = (k.last_year?.[kpi.key as keyof typeof k.last_year] as number) || 0

              return {
                week: `W${weekNum}`,
                current: currentValue,
                lastYear: lastYearValue,
              }
            })

          const chartConfig = {
            current: {
              label: 'Current Year',
              color: '#4B5563', // Dark gray
            },
            lastYear: {
              label: 'Last Year',
              color: '#F97316', // Orange
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
                    <ChartContainer config={chartConfig} className="w-full h-full">
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
                      >
                        <CartesianGrid vertical={false} />
                        <XAxis
                          dataKey="week"
                          tickLine={false}
                          axisLine={false}
                          tickMargin={8}
                          tickFormatter={(value) => value.replace('W', '')}
                        />
                        <ChartTooltip cursor={false} content={<ChartTooltipContent indicator="line" />} />
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
                  <ChartContainer config={chartConfig}>
                    <LineChart
                      accessibilityLayer
                      data={chartData}
                      margin={{
                        top: 20,
                        left: 12,
                        right: 12,
                      }}
                    >
                      <CartesianGrid vertical={false} />
                      <XAxis
                        dataKey="week"
                        tickLine={false}
                        axisLine={false}
                        tickMargin={8}
                        tickFormatter={(value) => value.replace('W', '')}
                      />
                      <ChartTooltip cursor={false} content={<ChartTooltipContent indicator="line" />} />
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


