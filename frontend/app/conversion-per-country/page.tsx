'use client'

import { useConversionPerCountry } from '@/contexts/DataCacheContext'
import { useChartAnimations } from '@/contexts/ChartSettingsContext'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ChartConfig, ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart'
import { CartesianGrid, LabelList, Line, LineChart, XAxis } from '@/lib/recharts'
import { Skeleton } from '@/components/ui/skeleton'
import { Loader2 } from 'lucide-react'

export default function ConversionPerCountry() {
  const { conversion_per_country } = useConversionPerCountry()
  const isAnimationActive = useChartAnimations()

  // Define country order and labels
  const countryOrder = [
    { key: 'Total', label: 'Total' },
    { key: 'United States', label: 'USA' },
    { key: 'United Kingdom', label: 'UK' },
    { key: 'Sweden', label: 'Sverige' },
    { key: 'Germany', label: 'Tyskland' },
    { key: 'Australia', label: 'Australien' },
    { key: 'Canada', label: 'Kanada' },
    { key: 'France', label: 'Frankrike' },
    { key: 'ROW', label: 'ROW' }
  ]

  const formatValue = (value: number): string => {
    if (value === 0) return '0'
    return value.toFixed(1) + '%'
  }

  // Normalize conversion_per_country structure - handle both { conversion_per_country: [...] } and direct array
  let conversionData: any[] = []
  if (conversion_per_country) {
    if (Array.isArray(conversion_per_country)) {
      // Structure: direct array
      conversionData = conversion_per_country
    } else if (conversion_per_country.conversion_per_country && Array.isArray(conversion_per_country.conversion_per_country)) {
      // Structure: { conversion_per_country: [...] }
      conversionData = conversion_per_country.conversion_per_country
    } else if (typeof conversion_per_country === 'object') {
      // Structure: { conversion_per_country: {...} } - might be an object instead of array
      conversionData = Object.values(conversion_per_country.conversion_per_country || {}) as any[]
    }
  }

  if (!conversion_per_country || conversionData.length === 0) {
    return (
      <div className="space-y-8">
        <div className="flex items-center gap-3 mb-6">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Loading Conversion per Country</h2>
            <p className="text-sm text-gray-600">Processing conversion rate data by country...</p>
          </div>
        </div>
        
        <div className="grid grid-cols-3 gap-6">
          {countryOrder.map((_, index) => (
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
      <div className="grid grid-cols-3 gap-6">
        {countryOrder.map((country, index) => {
          const chartData = conversionData.map((week: any) => {
            const weekNum = week.week.split('-')[1]
            let currentValue = 0
            let lastYearValue = 0

            if (country.key === 'Total') {
              // Calculate total conversion rate across all countries
              if (week.countries && typeof week.countries === 'object') {
                const totalOrders = Object.values(week.countries).reduce((sum: number, val: any) => {
                  const orders = (val && typeof val === 'object' && val.orders) ? Number(val.orders) || 0 : 0
                  return sum + orders
                }, 0)
                const totalSessions = Object.values(week.countries).reduce((sum: number, val: any) => {
                  const sessions = (val && typeof val === 'object' && val.sessions) ? Number(val.sessions) || 0 : 0
                  return sum + sessions
                }, 0)
                currentValue = totalSessions > 0 ? (totalOrders / totalSessions) * 100 : 0
              }
              
              if (week.last_year && week.last_year.countries && typeof week.last_year.countries === 'object') {
                const totalOrdersLY = Object.values(week.last_year.countries).reduce((sum: number, val: any) => {
                  const orders = (val && typeof val === 'object' && val.orders) ? Number(val.orders) || 0 : 0
                  return sum + orders
                }, 0)
                const totalSessionsLY = Object.values(week.last_year.countries).reduce((sum: number, val: any) => {
                  const sessions = (val && typeof val === 'object' && val.sessions) ? Number(val.sessions) || 0 : 0
                  return sum + sessions
                }, 0)
                lastYearValue = totalSessionsLY > 0 ? (totalOrdersLY / totalSessionsLY) * 100 : 0
              }
            } else if (country.key === 'ROW') {
              // Calculate ROW (Rest of World) - all countries except the main ones
              const mainCountries = ['United States', 'United Kingdom', 'Sweden', 'Germany', 'Australia', 'Canada', 'France']
              let totalOrders = 0
              let totalSessions = 0
              
              if (week.countries && typeof week.countries === 'object') {
                Object.entries(week.countries).forEach(([countryName, data]: [string, any]) => {
                  if (!mainCountries.includes(countryName)) {
                    if (data && typeof data === 'object') {
                      totalOrders += Number(data.orders) || 0
                      totalSessions += Number(data.sessions) || 0
                    }
                  }
                })
              }
              currentValue = totalSessions > 0 ? (totalOrders / totalSessions) * 100 : 0
              
              if (week.last_year && week.last_year.countries && typeof week.last_year.countries === 'object') {
                let totalOrdersLY = 0
                let totalSessionsLY = 0
                Object.entries(week.last_year.countries).forEach(([countryName, data]: [string, any]) => {
                  if (!mainCountries.includes(countryName)) {
                    if (data && typeof data === 'object') {
                      totalOrdersLY += Number(data.orders) || 0
                      totalSessionsLY += Number(data.sessions) || 0
                    }
                  }
                })
                lastYearValue = totalSessionsLY > 0 ? (totalOrdersLY / totalSessionsLY) * 100 : 0
              }
            } else {
              // Specific country
              if (week.countries && week.countries[country.key]) {
                const countryData = week.countries[country.key]
                if (countryData && typeof countryData === 'object') {
                  currentValue = Number(countryData.conversion_rate) || 0
                }
              }
              
              if (week.last_year && week.last_year.countries && week.last_year.countries[country.key]) {
                const countryDataLY = week.last_year.countries[country.key]
                if (countryDataLY && typeof countryDataLY === 'object') {
                  lastYearValue = Number(countryDataLY.conversion_rate) || 0
                }
              }
            }
            
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
            <Card key={country.key}>
              <CardHeader>
                <CardTitle>{country.label}</CardTitle>
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
                        formatter={(label: unknown) => formatValue(Number(label ?? 0))}
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

