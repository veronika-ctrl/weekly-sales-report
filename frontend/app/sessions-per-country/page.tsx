'use client'

import { useSessionsPerCountry } from '@/contexts/DataCacheContext'
import { useChartAnimations } from '@/contexts/ChartSettingsContext'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ChartConfig, ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart'
import { CartesianGrid, LabelList, Line, LineChart, XAxis } from '@/lib/recharts'
import { Skeleton } from '@/components/ui/skeleton'
import { Loader2 } from 'lucide-react'

export default function SessionsPerCountry() {
  const { sessions_per_country } = useSessionsPerCountry()
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
    return (value / 1000).toFixed(1)
  }

  // Normalize sessions_per_country structure - handle both { sessions_per_country: [...] } and direct array
  let sessionsData: any[] = []
  if (sessions_per_country) {
    if (Array.isArray(sessions_per_country)) {
      // Structure: direct array
      sessionsData = sessions_per_country
    } else if (sessions_per_country.sessions_per_country && Array.isArray(sessions_per_country.sessions_per_country)) {
      // Structure: { sessions_per_country: [...] }
      sessionsData = sessions_per_country.sessions_per_country
    } else if (typeof sessions_per_country === 'object') {
      // Structure: { sessions_per_country: {...} } - might be an object instead of array
      sessionsData = Object.values(sessions_per_country.sessions_per_country || {}) as any[]
    }
  }

  if (!sessions_per_country || sessionsData.length === 0) {
    return (
      <div className="space-y-8">
        <div className="flex items-center gap-3 mb-6">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Loading Sessions per Country</h2>
            <p className="text-sm text-gray-600">Processing sessions data by country...</p>
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
          const chartData = sessionsData.map((week: any) => {
            const weekNum = week.week.split('-')[1]
            let currentValue = 0
            let lastYearValue = 0

            if (country.key === 'Total') {
              // Calculate total sessions across all countries
              currentValue = (week.countries && typeof week.countries === 'object') 
                ? Object.values(week.countries).reduce((sum: number, val: any) => sum + (Number(val) || 0), 0)
                : 0
              if (week.last_year && week.last_year.countries && typeof week.last_year.countries === 'object') {
                lastYearValue = Object.values(week.last_year.countries).reduce((sum: number, val: any) => sum + (Number(val) || 0), 0)
              }
            } else if (country.key === 'ROW') {
              // Calculate ROW (Rest of World) - all countries except the main ones
              const mainCountries = ['United States', 'United Kingdom', 'Sweden', 'Germany', 'Australia', 'Canada', 'France']
              currentValue = (week.countries && typeof week.countries === 'object')
                ? Object.entries(week.countries).reduce((sum: number, [countryName, sessions]: [string, any]) => {
                    if (!mainCountries.includes(countryName)) {
                      return sum + (Number(sessions) || 0)
                    }
                    return sum
                  }, 0)
                : 0
              if (week.last_year && week.last_year.countries && typeof week.last_year.countries === 'object') {
                lastYearValue = Object.entries(week.last_year.countries).reduce((sum: number, [countryName, sessions]: [string, any]) => {
                  if (!mainCountries.includes(countryName)) {
                    return sum + (Number(sessions) || 0)
                  }
                  return sum
                }, 0)
              }
            } else {
              // Specific country
              currentValue = (week.countries && week.countries[country.key]) ? Number(week.countries[country.key]) || 0 : 0
              if (week.last_year && week.last_year.countries && week.last_year.countries[country.key]) {
                lastYearValue = Number(week.last_year.countries[country.key]) || 0
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
