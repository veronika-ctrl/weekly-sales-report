'use client'

import { type MetricsMtdResponse } from '@/lib/api'

interface MetricsPreviewMTDProps {
  mtdData: MetricsMtdResponse | null
  baseWeek: string
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
  'Total Net Revenue',
  'Returning Customers',
  'New customers',
  'Marketing Spend',
  'Online Cost of Sale(3)',
  'aMER'
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
  'total_net_revenue',
  'returning_customers',
  'new_customers',
  'marketing_spend',
  'online_cost_of_sale_3',
  'emer'
]

export default function MetricsPreviewMTD({
  mtdData,
  baseWeek,
  isPdfMode = false
}: MetricsPreviewMTDProps) {
  const calculateGrowthPercentage = (current: number, previous: number): number | null => {
    if (previous === 0) return null
    return ((current - previous) / previous) * 100
  }

  const formatGrowthPercentage = (value: number | null): string => {
    if (value === null) return '-'
    const absValue = Math.abs(value)
    const formatted = Math.round(absValue).toString()
    if (value < 0) return `(${formatted}%)`
    return `${formatted}%`
  }

  const formatValue = (value: number, metricKey: string): string => {
    if (metricKey === 'return_rate_pct' || metricKey === 'online_cost_of_sale_3') {
      return `${value.toFixed(1)}%`
    }
    if (metricKey === 'emer') { // aMER: same key, display label is "aMER"
      return value === 0 ? '0' : value.toFixed(1)
    }
    if (metricKey === 'returning_customers' || metricKey === 'new_customers') {
      return Math.round(value).toLocaleString('sv-SE')
    }
    if (value === 0) return '0'
    const thousandsValue = value / 1000
    const roundedThousands = Math.round(thousandsValue)
    return roundedThousands.toLocaleString('sv-SE')
  }

  if (!mtdData) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        <span className="ml-3 text-gray-600">Loading MTD metrics...</span>
      </div>
    )
  }

  const periods = mtdData.periods
  const dateRanges = mtdData.date_ranges || {}
  const actualWeekDisplay = dateRanges.actual?.display || 'Latest week'
  const mtdActualDisplay = dateRanges.mtd_actual?.display || 'Month-to-date'
  const mtdLastYearDisplay = dateRanges.mtd_last_year?.display || 'Last year (same period)'
  const mtdLastMonthDisplay = dateRanges.mtd_last_month?.display || 'Last month to date'

  return (
    <div className={`space-y-4 ${isPdfMode ? 'space-y-1' : ''}`}>
      {!isPdfMode && (
        <p className="text-sm text-muted-foreground">
          Actual = latest week. Month-to-date = from 1st of month to end of week. Budget = full month budget (from Settings). MTD vs Budget = how month-to-date actual compares to budget (e.g. 10% = 10% ahead, (5%) = 5% behind).
        </p>
      )}
      <div className={`bg-gray-50 rounded-lg overflow-hidden overflow-x-auto ${isPdfMode ? 'rounded-sm' : ''}`}>
        <table className={`w-full ${isPdfMode ? 'text-[8pt]' : 'text-xs'} ${isPdfMode ? 'break-inside-avoid' : ''}`}>
          <thead>
            <tr className="bg-gray-200 border-b">
              <th className={`${isPdfMode ? 'py-0.5 px-1' : 'py-2 px-2'} text-left font-medium text-gray-900`} rowSpan={2}>(SEK &apos;000)</th>
              <th className={`${isPdfMode ? 'py-0.5 px-1' : 'py-2 px-2'} text-center font-medium text-gray-900 bg-gray-200`} colSpan={5}>
                Latest week: {actualWeekDisplay} · MTD: {mtdActualDisplay} · Budget (month)
              </th>
              <th className={`${isPdfMode ? 'py-0.5 px-1' : 'py-2 px-2'} text-center font-medium text-gray-900 bg-yellow-100`} colSpan={2}>
                Last year (same period)
              </th>
              <th className={`${isPdfMode ? 'py-0.5 px-1' : 'py-2 px-2'} text-center font-medium text-gray-900 bg-blue-100`} colSpan={3}>
                Year-to-date
              </th>
            </tr>
            <tr className="bg-gray-200 border-b">
              <th className={`${isPdfMode ? 'py-0.5 px-1' : 'py-1 px-2'} text-right font-medium text-gray-900 bg-gray-400 ${isPdfMode ? 'tabular-nums' : ''}`} title={actualWeekDisplay}>Actual (week)</th>
              <th className={`${isPdfMode ? 'py-0.5 px-1' : 'py-1 px-2'} text-right font-medium text-gray-900 ${isPdfMode ? 'tabular-nums' : ''}`} title={mtdActualDisplay}>Month-to-date</th>
              <th className={`${isPdfMode ? 'py-0.5 px-1' : 'py-1 px-2'} text-right font-medium text-gray-900 bg-green-50 ${isPdfMode ? 'tabular-nums' : ''}`}>Budget (month)</th>
              <th className={`${isPdfMode ? 'py-0.5 px-1' : 'py-1 px-2'} text-right font-medium text-gray-900 bg-green-100 ${isPdfMode ? 'tabular-nums' : ''}`} title="Month-to-date vs Budget (variance %)">MTD vs Budget</th>
              <th className={`${isPdfMode ? 'py-0.5 px-1' : 'py-1 px-2'} text-right font-medium text-gray-900 ${isPdfMode ? 'tabular-nums' : ''}`} title={mtdLastMonthDisplay}>vs last month to date</th>
              <th className={`${isPdfMode ? 'py-0.5 px-1' : 'py-1 px-2'} text-right font-medium text-gray-900 bg-yellow-50 ${isPdfMode ? 'tabular-nums' : ''}`} title={mtdLastYearDisplay}>Last year</th>
              <th className={`${isPdfMode ? 'py-0.5 px-1' : 'py-1 px-2'} text-right font-medium text-gray-900 bg-yellow-50 ${isPdfMode ? 'tabular-nums' : ''}`}>Y/Y %</th>
              <th className={`${isPdfMode ? 'py-0.5 px-1' : 'py-1 px-2'} text-right font-medium text-gray-900 bg-blue-200 ${isPdfMode ? 'tabular-nums' : ''}`}>YTD Actual</th>
              <th className={`${isPdfMode ? 'py-0.5 px-1' : 'py-1 px-2'} text-right font-medium text-gray-900 bg-blue-50 ${isPdfMode ? 'tabular-nums' : ''}`}>YTD Last Year</th>
              <th className={`${isPdfMode ? 'py-0.5 px-1' : 'py-1 px-2'} text-right font-medium text-gray-900 bg-blue-50 ${isPdfMode ? 'tabular-nums' : ''}`}>YTD vs Last Year</th>
            </tr>
          </thead>
          <tbody>
            {METRIC_LABELS.map((label, index) => {
              const metricKey = METRIC_KEYS[index]
              const actualWeek = periods.actual?.[metricKey] ?? 0
              const mtdActual = periods.mtd_actual?.[metricKey] ?? 0
              const mtdLastYear = periods.mtd_last_year?.[metricKey] ?? 0
              const mtdLastMonth = periods.mtd_last_month?.[metricKey] ?? 0
              const ytdActual = periods.ytd_actual?.[metricKey] ?? 0
              const ytdLastYear = periods.ytd_last_year?.[metricKey] ?? 0
              return (
                <tr key={metricKey} className={`border-b border-gray-200 last:border-b-0 ${isPdfMode ? 'break-inside-avoid' : ''}`}>
                  <td className={`${isPdfMode ? 'py-0.5 px-1' : 'py-2 px-2'} font-medium text-gray-900`}>{label}</td>
                  <td className={`${isPdfMode ? 'py-0.5 px-1' : 'py-2 px-2'} text-right text-gray-700 bg-gray-200 font-semibold ${isPdfMode ? 'tabular-nums' : ''}`}>
                    {formatValue(actualWeek, metricKey)}
                  </td>
                  <td className={`${isPdfMode ? 'py-0.5 px-1' : 'py-2 px-2'} text-right text-gray-700 ${isPdfMode ? 'tabular-nums' : ''}`}>
                    {formatValue(mtdActual, metricKey)}
                  </td>
                  <td className={`${isPdfMode ? 'py-0.5 px-1' : 'py-2 px-2'} text-right text-gray-700 bg-green-50 ${isPdfMode ? 'tabular-nums' : ''}`}>
                    {periods.mtd_budget?.[metricKey] != null
                      ? formatValue(Number(periods.mtd_budget[metricKey]), metricKey)
                      : '—'}
                  </td>
                  <td className={`${isPdfMode ? 'py-0.5 px-1' : 'py-2 px-2'} text-right text-gray-700 bg-green-100 font-medium ${isPdfMode ? 'tabular-nums' : ''}`}>
                    {periods.mtd_budget?.[metricKey] != null && Number(periods.mtd_budget[metricKey]) !== 0
                      ? formatGrowthPercentage(calculateGrowthPercentage(mtdActual, Number(periods.mtd_budget[metricKey])))
                      : '—'}
                  </td>
                  <td className={`${isPdfMode ? 'py-0.5 px-1' : 'py-2 px-2'} text-right text-gray-700 ${isPdfMode ? 'tabular-nums' : ''}`}>
                    {formatGrowthPercentage(calculateGrowthPercentage(mtdActual, mtdLastMonth))}
                  </td>
                  <td className={`${isPdfMode ? 'py-0.5 px-1' : 'py-2 px-2'} text-right text-gray-700 bg-yellow-50 ${isPdfMode ? 'tabular-nums' : ''}`}>
                    {formatValue(mtdLastYear, metricKey)}
                  </td>
                  <td className={`${isPdfMode ? 'py-0.5 px-1' : 'py-2 px-2'} text-right text-gray-700 bg-yellow-50 ${isPdfMode ? 'tabular-nums' : ''}`}>
                    {formatGrowthPercentage(calculateGrowthPercentage(mtdActual, mtdLastYear))}
                  </td>
                  <td className={`${isPdfMode ? 'py-0.5 px-1' : 'py-2 px-2'} text-right text-gray-700 bg-blue-100 font-semibold ${isPdfMode ? 'tabular-nums' : ''}`}>
                    {formatValue(ytdActual, metricKey)}
                  </td>
                  <td className={`${isPdfMode ? 'py-0.5 px-1' : 'py-2 px-2'} text-right text-gray-700 bg-blue-50 ${isPdfMode ? 'tabular-nums' : ''}`}>
                    {formatValue(ytdLastYear, metricKey)}
                  </td>
                  <td className={`${isPdfMode ? 'py-0.5 px-1' : 'py-2 px-2'} text-right text-gray-700 bg-blue-50 ${isPdfMode ? 'tabular-nums' : ''}`}>
                    {formatGrowthPercentage(calculateGrowthPercentage(ytdActual, ytdLastYear))}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {!isPdfMode && (
        <div className="text-sm text-gray-600">
          <p>Showing metrics for base week: <span className="font-medium">{baseWeek}</span>. MTD = from 1st of month to end of week. Budget = full month. MTD vs Budget = variance % (positive = ahead of budget). YTD = fiscal year to date.</p>
        </div>
      )}
    </div>
  )
}
