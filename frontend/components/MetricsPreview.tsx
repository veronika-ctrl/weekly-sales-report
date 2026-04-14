'use client'

import { useEffect } from 'react'
import { useMetrics, useDataCache } from '@/contexts/DataCacheContext'
import { type PeriodsResponse } from '@/lib/api'

interface MetricsPreviewProps {
  periods: PeriodsResponse
  baseWeek: string
  onMetricsChange: (metrics: any) => void
  isPdfMode?: boolean
}

const METRIC_LABELS = [
  'Online Gross Revenue',
  'Returns',
  'Return Rate %',
  'Online Net Revenue',
  'Retail Concept Store',
  'Retail Pop-ups, Outlets',
  'Retail Net Revenue',
  'Wholesale Net Revenue',
  'Total Net Revenue'
]

const METRIC_KEYS = [
  'online_gross_revenue',
  'returns',
  'return_rate_pct',
  'online_net_revenue',
  'retail_concept_store',
  'retail_popups_outlets',
  'retail_net_revenue',
  'wholesale_net_revenue',
  'total_net_revenue'
]

export default function MetricsPreview({ 
  periods, 
  baseWeek, 
  onMetricsChange,
  isPdfMode = false
}: MetricsPreviewProps) {
  const { metrics } = useMetrics()
  const { refreshData, clearCache } = useDataCache()

  // Notify parent when metrics change
  useEffect(() => {
    onMetricsChange(metrics)
  }, [metrics, onMetricsChange])

  const calculateGrowthPercentage = (current: number, previous: number): number | null => {
    if (previous === 0) return null
    return ((current - previous) / previous) * 100
  }

  const isLowerBetterMetric = (metricKey: string): boolean =>
    metricKey === 'returns' || metricKey === 'return_rate_pct'

  const calculateDirectionalGrowth = (metricKey: string, current: number, previous: number): number | null => {
    const growth = calculateGrowthPercentage(current, previous)
    if (growth === null) return null
    return isLowerBetterMetric(metricKey) ? -growth : growth
  }

  /** Match markets table: YoY as integer %, negative in parentheses. */
  const formatGrowthPercentage = (value: number | null): string => {
    if (value === null) return '-'
    const absValue = Math.abs(value)
    const formatted = Math.round(absValue).toString()
    if (value < 0) {
      return `(${formatted}%)`
    }
    return `${formatted}%`
  }

  const formatValue = (value: number, metricKey: string): string => {
    if (metricKey === 'return_rate_pct' || metricKey === 'online_cost_of_sale_3') {
      return `${value.toFixed(1)}%`
    }
    if (metricKey === 'emer') {
      return value === 0 ? '0' : value.toFixed(1)
    }
    
    // Customer counts should NOT be formatted in thousands
    if (metricKey === 'returning_customers' || metricKey === 'new_customers') {
      return Math.round(value).toLocaleString('sv-SE')
    }
    
    if (value === 0) {
      return '0'
    }
    
    // Convert to thousands and round to nearest integer
    const thousandsValue = value / 1000
    const roundedThousands = Math.round(thousandsValue)
    
    return roundedThousands.toLocaleString('sv-SE')
  }

  const getPeriodDateRange = (periodKey: string): string => {
    if (!periods?.date_ranges) {
      return 'N/A'
    }
    const dateRange = periods.date_ranges[periodKey]
    return dateRange?.display || 'N/A'
  }

  if (!metrics) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        <span className="ml-3 text-gray-600">Loading metrics...</span>
      </div>
    )
  }

  // Normalize metrics structure - handle both { periods: { actual: {...} } } and { actual: {...} }
  let metricsData: Record<string, Record<string, number>> | null = null
  if (metrics.periods && typeof metrics.periods === 'object') {
    // Structure: { periods: { actual: {...}, last_week: {...}, ... } }
    metricsData = metrics.periods as Record<string, Record<string, number>>
  } else if ((metrics as unknown as Record<string, unknown>).actual || (metrics as unknown as Record<string, unknown>).last_week) {
    // Structure: { actual: {...}, last_week: {...}, ... } (legacy shape)
    metricsData = metrics as unknown as Record<string, Record<string, number>>
  }
  
  if (!metricsData || typeof metricsData !== 'object') {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="text-gray-600">No metrics data available. Please refresh data.</div>
      </div>
    )
  }

  const lastYearDateRange = getPeriodDateRange('last_year')
  const actualDateRange = getPeriodDateRange('actual')

  return (
    <div className={`space-y-4 ${isPdfMode ? 'space-y-1' : ''}`}>
      {!isPdfMode && (
        <p className="text-sm text-muted-foreground">
          Comparison to last year uses the <strong>same ISO week</strong> (matching weekdays). Latest week: {actualDateRange}. Last year same week: {lastYearDateRange}.
        </p>
      )}
      {/* Metrics table */}
      <div className={`bg-gray-50 rounded-lg overflow-hidden overflow-x-auto ${isPdfMode ? 'rounded-sm' : ''}`}>
        <table className={`w-full table-fixed ${isPdfMode ? 'text-[8pt]' : 'text-xs'} ${isPdfMode ? 'break-inside-avoid' : ''}`}>
          <thead>
            <tr className="bg-gray-200 border-b">
              <th className={`${isPdfMode ? 'py-0.5 px-1' : 'py-2 px-2'} w-[30%] text-left font-medium text-gray-900`} rowSpan={2}>(SEK '000)</th>
              <th className={`${isPdfMode ? 'py-0.5 px-1' : 'py-2 px-2'} w-[20%] text-center font-medium text-gray-900 bg-gray-200`} colSpan={1}>
                Latest Week: {actualDateRange}
              </th>
              <th className={`${isPdfMode ? 'py-0.5 px-1' : 'py-2 px-2'} w-[25%] text-center font-medium text-gray-900 bg-gray-200`} colSpan={2}>
                Last year (same week) — YoY
              </th>
              <th className={`${isPdfMode ? 'py-0.5 px-1' : 'py-2 px-2'} w-[25%] text-center font-medium text-gray-900 bg-blue-100`} colSpan={3}>
                Year-to-date
              </th>
            </tr>
            <tr className="bg-gray-200 border-b">
              <th className={`${isPdfMode ? 'py-0.5 px-1' : 'py-1 px-2'} text-right font-medium text-gray-900 bg-gray-400 ${isPdfMode ? 'tabular-nums' : ''}`}>Actual</th>
              <th className={`${isPdfMode ? 'py-0.5 px-1' : 'py-1 px-2'} text-right font-medium text-gray-900 bg-gray-100 ${isPdfMode ? 'tabular-nums' : ''}`} title={`Same week last year: ${lastYearDateRange}`}>
                Last Year
              </th>
              <th className={`${isPdfMode ? 'py-0.5 px-1' : 'py-1 px-2'} text-right font-medium text-gray-900 bg-gray-100 ${isPdfMode ? 'tabular-nums' : ''}`} title="Year-over-year: vs same week last year">
                Y/Y %
              </th>
              <th className={`${isPdfMode ? 'py-0.5 px-1' : 'py-1 px-2'} text-right font-medium text-gray-900 bg-blue-200 ${isPdfMode ? 'tabular-nums' : ''}`}>YTD Actual</th>
              <th className={`${isPdfMode ? 'py-0.5 px-1' : 'py-1 px-2'} text-right font-medium text-gray-900 bg-blue-50 ${isPdfMode ? 'tabular-nums' : ''}`}>YTD Last Year</th>
              <th className={`${isPdfMode ? 'py-0.5 px-1' : 'py-1 px-2'} text-right font-medium text-gray-900 bg-blue-50 ${isPdfMode ? 'tabular-nums' : ''}`}>YTD vs Last Year</th>
            </tr>
          </thead>
          <tbody>
            {METRIC_LABELS.map((label, index) => {
              const metricKey = METRIC_KEYS[index]
              return (
                <tr key={metricKey} className={`border-b border-gray-200 last:border-b-0 ${isPdfMode ? 'break-inside-avoid' : ''}`}>
                  <td className={`${isPdfMode ? 'py-0.5 px-1' : 'py-1 px-2'} font-medium text-gray-900`}>{label}</td>
                  <td className={`${isPdfMode ? 'py-0.5 px-1' : 'py-1 px-2'} text-right text-gray-700 bg-gray-200 font-semibold ${isPdfMode ? 'tabular-nums' : ''}`}>
                    {formatValue(metricsData?.actual?.[metricKey] || 0, metricKey)}
                  </td>
                  <td className={`${isPdfMode ? 'py-0.5 px-1' : 'py-1 px-2'} text-right text-gray-700 bg-gray-100 ${isPdfMode ? 'tabular-nums' : ''}`}>
                    {formatValue(metricsData?.last_year?.[metricKey] || 0, metricKey)}
                  </td>
                  <td className={`${isPdfMode ? 'py-0.5 px-1' : 'py-1 px-2'} text-right text-gray-700 bg-gray-100 ${isPdfMode ? 'tabular-nums' : ''}`}>
                    {formatGrowthPercentage(calculateDirectionalGrowth(
                      metricKey,
                      metricsData?.actual?.[metricKey] || 0,
                      metricsData?.last_year?.[metricKey] || 0
                    ))}
                  </td>
                  <td className={`${isPdfMode ? 'py-0.5 px-1' : 'py-1 px-2'} text-right text-gray-700 bg-blue-100 font-semibold ${isPdfMode ? 'tabular-nums' : ''}`}>
                    {formatValue(metricsData?.ytd_actual?.[metricKey] || 0, metricKey)}
                  </td>
                  <td className={`${isPdfMode ? 'py-0.5 px-1' : 'py-1 px-2'} text-right text-gray-700 bg-blue-50 ${isPdfMode ? 'tabular-nums' : ''}`}>
                    {formatValue(metricsData?.ytd_last_year?.[metricKey] || 0, metricKey)}
                  </td>
                  <td className={`${isPdfMode ? 'py-0.5 px-1' : 'py-1 px-2'} text-right text-gray-700 bg-blue-50 ${isPdfMode ? 'tabular-nums' : ''}`}>
                    {formatGrowthPercentage(calculateDirectionalGrowth(
                      metricKey,
                      metricsData?.ytd_actual?.[metricKey] || 0, 
                      metricsData?.ytd_last_year?.[metricKey] || 0
                    ))}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Summary info - hide in PDF mode */}
      {!isPdfMode && (
        <div className="text-sm text-gray-600">
          <p>Showing metrics for base week: <span className="font-medium">{baseWeek}</span>. Last year column = same ISO week previous year (matching weekdays).</p>
          <p>Data loaded for {Object.keys(metricsData || {}).length} periods</p>
        </div>
      )}
    </div>
  )
}
