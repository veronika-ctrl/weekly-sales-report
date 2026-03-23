'use client'

import { 
  useSessionsPerCountry, 
  useConversionPerCountry,
  useNewCustomersPerCountry,
  useReturningCustomersPerCountry,
  useAOVNewCustomersPerCountry,
  useAOVReturningCustomersPerCountry,
  useMarketingSpendPerCountry,
  useNCACPerCountry,
  useDataCache
} from '@/contexts/DataCacheContext'
import { useChartAnimations } from '@/contexts/ChartSettingsContext'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ChartConfig, ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart'
import { CartesianGrid, LabelList, Line, LineChart, XAxis } from '@/lib/recharts'
import { Skeleton } from '@/components/ui/skeleton'
import { Loader2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { getOnlineKPIs, getSessionsPerCountry, getConversionPerCountry, getNewCustomersPerCountry, getReturningCustomersPerCountry, getAOVNewCustomersPerCountry, getAOVReturningCustomersPerCountry, getMarketingSpendPerCountry, getNCACPerCountry, type OnlineKPIsResponse } from '@/lib/api'

export default function UKSessions() {
  const { sessions_per_country } = useSessionsPerCountry()
  const { conversion_per_country } = useConversionPerCountry()
  const { new_customers_per_country } = useNewCustomersPerCountry()
  const { returning_customers_per_country } = useReturningCustomersPerCountry()
  const { aov_new_customers_per_country } = useAOVNewCustomersPerCountry()
  const { aov_returning_customers_per_country } = useAOVReturningCustomersPerCountry()
  const { marketing_spend_per_country } = useMarketingSpendPerCountry()
  const { ncac_per_country } = useNCACPerCountry()
  const { baseWeek, loadAllData } = useDataCache()
  const isAnimationActive = useChartAnimations()
  const [ukKPIs, setUkKPIs] = useState<OnlineKPIsResponse | null>(null)
  const [loadingKPIs, setLoadingKPIs] = useState(false)
  const [bootstrapped, setBootstrapped] = useState(false)
  const [kpiError, setKpiError] = useState<string | null>(null)
  const [localSessions, setLocalSessions] = useState<any[] | null>(null)
  const [localConversion, setLocalConversion] = useState<any[] | null>(null)
  const [localNewCust, setLocalNewCust] = useState<any[] | null>(null)
  const [localRetCust, setLocalRetCust] = useState<any[] | null>(null)
  const [localAovNew, setLocalAovNew] = useState<any[] | null>(null)
  const [localAovRet, setLocalAovRet] = useState<any[] | null>(null)
  const [localMarketing, setLocalMarketing] = useState<any[] | null>(null)
  const [localNcac, setLocalNcac] = useState<any[] | null>(null)

  // Format functions
  const formatSessionsValue = (value: number): string => {
    if (value === 0) return '0'
    return (value / 1000).toFixed(1)
  }

  const formatConversionValue = (value: number): string => {
    if (value === 0) return '0'
    return value.toFixed(1) + '%'
  }

  const formatNumberValue = (value: number): string => {
    if (value === 0) return '0'
    return Math.round(value).toString()
  }

  const formatMarketingValue = (value: number): string => {
    if (value === 0) return '0'
    return Math.round(value / 1000).toString() + 'k'
  }

  const formatPercentValue = (value: number): string => {
    if (value === 0) return '0'
    return value.toFixed(1) + '%'
  }

  // Helper function to normalize data structure
  const normalizeData = (data: any, key: string): any[] => {
    if (!data) return []
    if (Array.isArray(data)) return data
    if (data[key] && Array.isArray(data[key])) return data[key]
    if (typeof data === 'object' && data[key]) {
      return Object.values(data[key]) as any[]
    }
    return []
  }

  // Normalize all data sources
  const sessionsData = normalizeData(localSessions ?? sessions_per_country, 'sessions_per_country')
  const conversionData = normalizeData(localConversion ?? conversion_per_country, 'conversion_per_country')
  const newCustomersData = normalizeData(localNewCust ?? new_customers_per_country, 'new_customers_per_country')
  const returningCustomersData = normalizeData(localRetCust ?? returning_customers_per_country, 'returning_customers_per_country')
  const aovNewData = normalizeData(localAovNew ?? aov_new_customers_per_country, 'aov_new_customers_per_country')
  const aovReturningData = normalizeData(localAovRet ?? aov_returning_customers_per_country, 'aov_returning_customers_per_country')
  const marketingData = normalizeData(localMarketing ?? marketing_spend_per_country, 'marketing_spend_per_country')
  const ncacData = normalizeData(localNcac ?? ncac_per_country, 'ncac_per_country')

  // Ensure core datasets are loaded so page doesn't hang
  useEffect(() => {
    if (bootstrapped) return
    const targetWeek = baseWeek || '2026-02'
    loadAllData(targetWeek, false)
    setBootstrapped(true)
  }, [bootstrapped, baseWeek, loadAllData])

  // Fallback: fetch per-country datasets directly if context is empty
  useEffect(() => {
    const targetWeek = baseWeek || '2026-02'
    const needsSessions = sessionsData.length === 0
    const needsConv = conversionData.length === 0
    const needsNew = newCustomersData.length === 0
    const needsRet = returningCustomersData.length === 0
    const needsAovNew = aovNewData.length === 0
    const needsAovRet = aovReturningData.length === 0
    const needsMkt = marketingData.length === 0
    const needsNcac = ncacData.length === 0
    if (!(needsSessions || needsConv || needsNew || needsRet || needsAovNew || needsAovRet || needsMkt || needsNcac)) return
    let cancelled = false
    ;(async () => {
      try {
        if (needsSessions) {
          const fresh = await getSessionsPerCountry(targetWeek, 8)
          if (!cancelled) setLocalSessions((fresh as any).sessions_per_country ?? fresh)
        }
        if (needsConv) {
          const fresh = await getConversionPerCountry(targetWeek, 8)
          if (!cancelled) setLocalConversion((fresh as any).conversion_per_country ?? fresh)
        }
        if (needsNew) {
          const fresh = await getNewCustomersPerCountry(targetWeek, 8)
          if (!cancelled) setLocalNewCust((fresh as any).new_customers_per_country ?? fresh)
        }
        if (needsRet) {
          const fresh = await getReturningCustomersPerCountry(targetWeek, 8)
          if (!cancelled) setLocalRetCust((fresh as any).returning_customers_per_country ?? fresh)
        }
        if (needsAovNew) {
          const fresh = await getAOVNewCustomersPerCountry(targetWeek, 8)
          if (!cancelled) setLocalAovNew((fresh as any).aov_new_customers_per_country ?? fresh)
        }
        if (needsAovRet) {
          const fresh = await getAOVReturningCustomersPerCountry(targetWeek, 8)
          if (!cancelled) setLocalAovRet((fresh as any).aov_returning_customers_per_country ?? fresh)
        }
        if (needsMkt) {
          const fresh = await getMarketingSpendPerCountry(targetWeek, 8)
          if (!cancelled) setLocalMarketing((fresh as any).marketing_spend_per_country ?? fresh)
        }
        if (needsNcac) {
          const fresh = await getNCACPerCountry(targetWeek, 8)
          if (!cancelled) setLocalNcac((fresh as any).ncac_per_country ?? fresh)
        }
      } catch (e) {
        // swallow; UI will show loaders until context or local fills
      }
    })()
    return () => {
      cancelled = true
    }
  }, [baseWeek, sessionsData.length, conversionData.length, newCustomersData.length, returningCustomersData.length, aovNewData.length, aovReturningData.length, marketingData.length, ncacData.length])

  // Fetch UK-specific KPIs for COS
  useEffect(() => {
    const targetWeek = baseWeek || '2026-02'
    
    let cancelled = false
    async function fetchUKKPIs() {
      setLoadingKPIs(true)
      setKpiError(null)
      try {
        const attempt = async () => getOnlineKPIs(targetWeek, 8, 'United Kingdom')
        let data: any = null
        try {
          data = await attempt()
        } catch (err: any) {
          if (err?.message?.toLowerCase().includes('failed to fetch')) {
            await new Promise((res) => setTimeout(res, 800))
            data = await attempt()
          } else {
            throw err
          }
        }
        if (!cancelled) setUkKPIs(data)
      } catch (err: any) {
        console.error('Failed to fetch UK KPIs:', err)
        if (!cancelled) setKpiError(err?.message || 'Failed to fetch UK KPIs')
      } finally {
        if (!cancelled) {
          setLoadingKPIs(false)
        }
      }
    }
    fetchUKKPIs()
    return () => {
      cancelled = true
    }
  }, [baseWeek])

  // Normalize KPIs data for COS
  let kpisData: any[] = []
  if (ukKPIs) {
    if (Array.isArray(ukKPIs)) {
      kpisData = ukKPIs
    } else if (ukKPIs.kpis && Array.isArray(ukKPIs.kpis)) {
      kpisData = ukKPIs.kpis
    } else if (typeof ukKPIs === 'object' && ukKPIs !== null && 'kpis' in ukKPIs) {
      kpisData = Object.values((ukKPIs as any).kpis || {}) as any[]
    }
  }

  // Check if all data is loaded
  const isLoading = 
    sessionsData.length === 0 || 
    conversionData.length === 0 || 
    newCustomersData.length === 0 || 
    returningCustomersData.length === 0 || 
    aovNewData.length === 0 || 
    aovReturningData.length === 0 || 
    marketingData.length === 0 || 
    ncacData.length === 0 ||
    kpisData.length === 0 ||
    loadingKPIs

  if (isLoading) {
    return (
      <div className="space-y-8">
        <div className="flex items-center gap-3 mb-6">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Loading UK Data</h2>
            <p className="text-sm text-gray-600">Processing all metrics for UK...</p>
          </div>
        </div>
        
        <div className="grid grid-cols-3 gap-6">
          {Array.from({ length: 9 }).map((_, index) => (
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

  // Helper function to extract UK data from country-based data
  const extractUKData = (data: any[], countryKey: string = 'United Kingdom') => {
    return data.map((week: any) => {
      const weekNum = week.week.split('-')[1]
      let currentValue = 0
      let lastYearValue = 0

      if (week.countries && week.countries[countryKey]) {
        currentValue = Number(week.countries[countryKey]) || 0
      }
      if (week.last_year && week.last_year.countries && week.last_year.countries[countryKey]) {
        lastYearValue = Number(week.last_year.countries[countryKey]) || 0
      }

      return {
        week: `W${weekNum}`,
        current: currentValue,
        lastYear: lastYearValue
      }
    })
  }

  // Helper function to extract UK conversion data (special structure)
  const extractUKConversionData = (data: any[]) => {
    return data.map((week: any) => {
      const weekNum = week.week.split('-')[1]
      let currentValue = 0
      let lastYearValue = 0

      if (week.countries && week.countries['United Kingdom']) {
        const countryData = week.countries['United Kingdom']
        if (countryData && typeof countryData === 'object') {
          currentValue = Number(countryData.conversion_rate) || 0
        }
      }
      if (week.last_year && week.last_year.countries && week.last_year.countries['United Kingdom']) {
        const countryDataLY = week.last_year.countries['United Kingdom']
        if (countryDataLY && typeof countryDataLY === 'object') {
          lastYearValue = Number(countryDataLY.conversion_rate) || 0
        }
      }

      return {
        week: `W${weekNum}`,
        current: currentValue,
        lastYear: lastYearValue
      }
    })
  }

  // Extract UK data for all metrics
  const sessionsChartData = extractUKData(sessionsData)
  const conversionChartData = extractUKConversionData(conversionData)
  const newCustomersChartData = extractUKData(newCustomersData)
  const returningCustomersChartData = extractUKData(returningCustomersData)
  const aovNewChartData = extractUKData(aovNewData)
  const aovReturningChartData = extractUKData(aovReturningData)
  const marketingChartData = extractUKData(marketingData)
  const ncacChartData = extractUKData(ncacData)

  // Extract COS data from KPIs (filtered for UK)
  const cosChartData = kpisData.map((k: any) => {
    const weekNum = k.week.split('-')[1]
    const currentValue = k.cos || 0
    const lastYearValue = k.last_year?.cos || 0
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

  // Chart component helper
  const renderChart = (
    title: string,
    data: any[],
    formatter: (val: number) => string
  ) => (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <ChartContainer config={chartConfig}>
          <LineChart
            accessibilityLayer
            data={data}
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
                formatter={(label: unknown) => formatter(Number(label ?? 0))}
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

  return (
    <div className="space-y-8">
      <div className="grid grid-cols-3 gap-6">
        {renderChart('UK - Sessions', sessionsChartData, formatSessionsValue)}
        {renderChart('UK - Conversion', conversionChartData, formatConversionValue)}
        {renderChart('UK - New Customers', newCustomersChartData, formatNumberValue)}
        {renderChart('UK - Returning Customers', returningCustomersChartData, formatNumberValue)}
        {renderChart('UK - AOV New Customers', aovNewChartData, formatNumberValue)}
        {renderChart('UK - AOV Returning Customers', aovReturningChartData, formatNumberValue)}
        {renderChart('UK - Marketing Spend', marketingChartData, formatMarketingValue)}
        {renderChart('UK - nCAC', ncacChartData, formatNumberValue)}
        {renderChart('UK - Cost of Sale', cosChartData, formatPercentValue)}
      </div>
    </div>
  )
}









