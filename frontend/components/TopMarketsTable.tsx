'use client'

import { useMarkets } from '@/contexts/DataCacheContext'
import { Skeleton } from '@/components/ui/skeleton'
import { Loader2 } from 'lucide-react'

interface TopMarketsTableProps {
  baseWeek: string
  isPdfMode?: boolean
}

export default function TopMarketsTable({ baseWeek, isPdfMode = false }: TopMarketsTableProps) {
  const { markets: marketsData } = useMarkets()

  const formatValue = (value: number): string => {
    if (value === 0) return '0'
    const thousandsValue = value / 1000
    const roundedThousands = Math.round(thousandsValue)
    return roundedThousands.toLocaleString('sv-SE')
  }

  const calculateYoY = (current: number, previous: number): number | null => {
    if (previous === 0) return null
    return ((current - previous) / previous) * 100
  }

  /** Y/Y = same ISO week previous year. "-" when baseline missing or 0 (no division by zero). */
  const formatYoY = (value: number | null): string => {
    if (value === null) return '-'
    const absValue = Math.abs(value)
    const formatted = Math.round(absValue).toString()
    if (value < 0) {
      return `(${formatted}%)`
    } else {
      return `${formatted}%`
    }
  }

  const calculateSoB = (marketValue: number, totalValue: number): number | null => {
    if (totalValue === 0) return null
    return (marketValue / totalValue) * 100
  }

  const formatSoB = (value: number | null): string => {
    if (value === null) return '-'
    return `${Math.round(value)}%`
  }

  const getWeekNumber = (weekStr: string): string => {
    const parts = weekStr.split('-')
    return `W${parts[1]}`
  }

  /** ISO week helpers to mirror backend logic (markets.py). */
  const getIsoWeek = (date: Date): { year: number; week: number } => {
    const d = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()))
    const day = d.getUTCDay() || 7
    d.setUTCDate(d.getUTCDate() + 4 - day)
    const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1))
    const week = Math.ceil((((d.getTime() - yearStart.getTime()) / 86400000) + 1) / 7)
    return { year: d.getUTCFullYear(), week }
  }

  const has53Weeks = (year: number): boolean => {
    const dec28 = new Date(Date.UTC(year, 11, 28))
    return getIsoWeek(dec28).week === 53
  }

  /** Build last numWeeks in chronological order, matching backend week logic. */
  const getChronologicalWeeksFromBase = (base: string, numWeeks: number): string[] => {
    const [yStr, wStr] = base.split('-')
    const year = Number(yStr)
    const week = Number(wStr)
    const weeks: string[] = []
    let i = 0
    while (weeks.length < numWeeks) {
      let weekNum = week - i
      let yearForWeek = year
      if (weekNum < 1) {
        const prevYear = year - 1
        weekNum = (has53Weeks(prevYear) ? 53 : 52) + weekNum
        if (weekNum === 53) {
          weekNum = 52
          i += 1
          continue
        }
        yearForWeek = prevYear
      }
      const key = `${yearForWeek}-${String(weekNum).padStart(2, '0')}`
      if (!weeks.includes(key)) weeks.push(key)
      i += 1
    }
    weeks.sort((a, b) => {
      const [yA, wA] = a.split('-').map(Number)
      const [yB, wB] = b.split('-').map(Number)
      if (yA !== yB) return yA - yB
      return wA - wB
    })
    return weeks
  }

  // Normalize markets structure - handle both { markets: [...] } and direct array
  let markets: any[] = []
  let period_info: any = null
  
  if (marketsData) {
    if (Array.isArray(marketsData)) {
      // Structure: direct array
      markets = marketsData
    } else if (marketsData.markets && Array.isArray(marketsData.markets)) {
      // Structure: { markets: [...], period_info: {...} }
      markets = marketsData.markets
      period_info = marketsData.period_info
    } else if (marketsData.markets && typeof marketsData.markets === 'object') {
      // Structure: { markets: {...} } - might be an object instead of array
      markets = Object.values(marketsData.markets) as any[]
      period_info = marketsData.period_info
    }
  }

  if (!markets || markets.length === 0) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <Loader2 className="h-5 w-5 animate-spin text-primary" />
          <span className="text-gray-600">Loading markets data...</span>
        </div>
        <div className="space-y-2">
          <Skeleton className="h-12 w-full" />
          {[...Array(15)].map((_, i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </div>
      </div>
    )
  }
  // Define desired weeks from baseWeek in chronological order (previous year first, then current year) – same as Category Sales/backend
  const numWeeks = 8
  const weekKeys = getChronologicalWeeksFromBase(baseWeek, numWeeks)
  
  const getLastYearWeek = (weekStr: string): string => {
    const [yearStr, weekStrNum] = weekStr.split('-')
    const year = Number(yearStr)
    let weekNum = Number(weekStrNum)
    const prevYear = year - 1
    if (weekNum === 53 && !has53Weeks(prevYear)) {
      weekNum = 52
    }
    return `${prevYear}-${String(weekNum).padStart(2, '0')}`
  }

  // Last year weeks for Y/Y (same ISO week numbers, previous year)
  const lastYearWeeks = weekKeys.map(getLastYearWeek)

  return (
    <div className={`bg-gray-50 rounded-lg overflow-hidden overflow-x-auto ${isPdfMode ? 'rounded-sm' : ''} ${isPdfMode ? 'break-inside-avoid' : ''}`}>
      {/* Markets table */}
      <table className={`w-full ${isPdfMode ? 'text-[6pt]' : 'text-xs'} ${isPdfMode ? 'break-inside-avoid' : ''}`}>
        <thead>
          <tr className="bg-gray-200 border-b">
            <th className={`${isPdfMode ? 'py-0 px-0.5' : 'py-2 px-2'} text-left font-medium text-gray-900`} rowSpan={3}>Country</th>
            <th className={`${isPdfMode ? 'py-0 px-0.5' : 'py-2 px-2'} text-center font-medium text-gray-900 bg-gray-200`} colSpan={9}>
              Latest Week: {period_info?.latest_dates || 'N/A'}
            </th>
            <th className={`${isPdfMode ? 'py-0 px-0.5' : 'py-2 px-2'} text-center font-medium text-gray-900 bg-yellow-100`} colSpan={9}>
              Y/Y GROWTH%
            </th>
            <th className={`${isPdfMode ? 'py-0 px-0.5' : 'py-2 px-2'} text-center font-medium text-gray-900 bg-green-100`} colSpan={9}>
              SoB
            </th>
          </tr>
          <tr className="bg-gray-200 border-b">
            {weekKeys.map((week) => (
              <th key={week} className={`${isPdfMode ? 'py-0 px-0.5' : 'py-1 px-2'} text-right font-medium text-gray-900`} rowSpan={2}>
                {getWeekNumber(week)}
              </th>
            ))}
            <th className={`${isPdfMode ? 'py-0 px-0.5' : 'py-1 px-2'} text-right font-medium text-gray-900 bg-blue-100`} rowSpan={2}>Avg</th>
            {weekKeys.map((week) => (
              <th key={`yoy-${week}`} className={`${isPdfMode ? 'py-0 px-0.5' : 'py-1 px-2'} text-right font-medium text-gray-900 bg-yellow-50`} rowSpan={2}>
                {getWeekNumber(week)}
              </th>
            ))}
            <th className={`${isPdfMode ? 'py-0 px-0.5' : 'py-1 px-2'} text-right font-medium text-gray-900 bg-yellow-50`} rowSpan={2}>Avg</th>
            {weekKeys.map((week) => (
              <th key={`sob-${week}`} className={`${isPdfMode ? 'py-0 px-0.5' : 'py-1 px-2'} text-right font-medium text-gray-900 bg-green-50`} rowSpan={2}>
                {getWeekNumber(week)}
              </th>
            ))}
            <th className={`${isPdfMode ? 'py-0 px-0.5' : 'py-1 px-2'} text-right font-medium text-gray-900 bg-green-50`} rowSpan={2}>Avg</th>
          </tr>
        </thead>
        <tbody>
          {markets.map((market, index) => {
            const isRow = market.country === 'ROW'
            const isTotal = market.country === 'Total'
            const bgClass = isRow ? 'bg-gray-100' : isTotal ? 'bg-gray-200 font-semibold' : ''
            
            return (
              <tr key={index} className={`border-b border-gray-200 last:border-b-0 ${bgClass}`}>
                <td className={`${isPdfMode ? 'py-0 px-0.5' : 'py-2 px-2'} font-medium text-gray-900 ${isTotal ? 'font-bold' : ''}`}>
                  {market.country}
                </td>
                {weekKeys.map((week) => (
                  <td key={week} className={`${isPdfMode ? 'py-0 px-0.5' : 'py-2 px-2'} text-right text-gray-700 ${isPdfMode ? 'tabular-nums' : ''}`}>
                    {formatValue(market.weeks[week] || 0)}
                  </td>
                ))}
                <td className={`${isPdfMode ? 'py-0 px-0.5' : 'py-2 px-2'} text-right text-gray-700 bg-blue-50 font-medium ${isPdfMode ? 'tabular-nums' : ''}`}>
                  {formatValue(market.average)}
                </td>
                {weekKeys.map((week, weekIndex) => {
                  const lastYearWeek = lastYearWeeks[weekIndex]
                  const currentValue = market.weeks[week] || 0
                  const lastYearValue = market.weeks[lastYearWeek] || 0
                  const yoY = calculateYoY(currentValue, lastYearValue)
                  
                  return (
                    <td key={`yoy-${week}`} className={`${isPdfMode ? 'py-0 px-0.5' : 'py-2 px-2'} text-right text-gray-700 bg-yellow-50 ${isPdfMode ? 'tabular-nums' : ''}`}>
                      {formatYoY(yoY)}
                    </td>
                  )
                })}
                <td className={`${isPdfMode ? 'py-0 px-0.5' : 'py-2 px-2'} text-right text-gray-700 bg-yellow-50 font-medium ${isPdfMode ? 'tabular-nums' : ''}`}>
                  {(() => {
                    let totalYoY = 0
                    let validWeeks = 0
                    weekKeys.forEach((week, weekIndex) => {
                      const lastYearWeek = lastYearWeeks[weekIndex]
                      const currentValue = market.weeks[week] || 0
                      const lastYearValue = market.weeks[lastYearWeek] || 0
                      const yoY = calculateYoY(currentValue, lastYearValue)
                      if (yoY !== null) {
                        totalYoY += yoY
                        validWeeks++
                      }
                    })
                    const avgYoY = validWeeks > 0 ? totalYoY / validWeeks : null
                    return formatYoY(avgYoY)
                  })()}
                </td>
                {weekKeys.map((week) => {
                  const totalRow = markets.find(m => m.country === 'Total')
                  const totalValue = totalRow?.weeks[week] || 0
                  const marketValue = market.weeks[week] || 0
                  const sob = isTotal ? 100 : calculateSoB(marketValue, totalValue)

                  return (
                    <td key={`sob-${week}`} className={`${isPdfMode ? 'py-0 px-0.5' : 'py-2 px-2'} text-right text-gray-700 bg-green-50 ${isPdfMode ? 'tabular-nums' : ''}`}>
                      {formatSoB(sob)}
                    </td>
                  )
                })}
                <td className={`${isPdfMode ? 'py-0 px-0.5' : 'py-2 px-2'} text-right text-gray-700 bg-green-50 font-medium ${isPdfMode ? 'tabular-nums' : ''}`}>
                  {(() => {
                    if (isTotal) {
                      return formatSoB(100)
                    }
                    
                    const totalRow = markets.find(m => m.country === 'Total')
                    let totalMarketValue = 0
                    let totalTotalValue = 0
                    
                    weekKeys.forEach(week => {
                      const totalValue = totalRow?.weeks[week] || 0
                      const marketValue = market.weeks[week] || 0
                      totalMarketValue += marketValue
                      totalTotalValue += totalValue
                    })
                    
                    const avgSoB = totalTotalValue > 0 ? (totalMarketValue / totalTotalValue) * 100 : null
                    return formatSoB(avgSoB)
                  })()}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

