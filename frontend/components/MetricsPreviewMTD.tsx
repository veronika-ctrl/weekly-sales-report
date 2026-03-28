'use client'

import type { ReactNode } from 'react'
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
  'Returning Customers',
  'New customers',
  'Marketing Spend',
  'Online Cost of Sale(3)',
  'aMER',
]

const METRIC_KEYS = [
  'online_gross_revenue',
  'returns',
  'return_rate_pct',
  'online_net_revenue',
  'returning_customers',
  'new_customers',
  'marketing_spend',
  'online_cost_of_sale_3',
  'emer',
]

const COL_COUNT = 5

export default function MetricsPreviewMTD({
  mtdData,
  baseWeek,
  isPdfMode = false,
}: MetricsPreviewMTDProps) {
  const calculateGrowthPercentage = (current: number, previous: number): number | null => {
    if (previous === 0) return null
    return ((current - previous) / previous) * 100
  }

  const formatGrowthPercentage = (value: number | null): string => {
    if (value === null) return '—'
    const absValue = Math.abs(value)
    const formatted = Math.round(absValue).toString()
    if (value < 0) return `(${formatted}%)`
    return `${formatted}%`
  }

  const formatValue = (value: number, metricKey: string): string => {
    if (metricKey === 'return_rate_pct' || metricKey === 'online_cost_of_sale_3') {
      return `${value.toFixed(1)}%`
    }
    if (metricKey === 'emer') {
      return value === 0 ? '0' : value.toFixed(1)
    }
    if (metricKey === 'returning_customers' || metricKey === 'new_customers') {
      return Math.round(value).toLocaleString('sv-SE')
    }
    if (value === 0) return '0'
    const thousandsValue = value / 1000
    const roundedThousands = Math.round(Math.abs(thousandsValue))
    const formattedThousands = roundedThousands.toLocaleString('sv-SE')
    if ((metricKey === 'returns' || metricKey === 'marketing_spend') && value < 0) {
      return `(${formattedThousands})`
    }
    return value < 0 ? `-${formattedThousands}` : formattedThousands
  }

  /** actual − budget: positive = ahead of budget, negative = shortfall. Same units as Actual (SEK raw → shown as '000); % metrics as pp. */
  const formatBudgetVariance = (actual: number, budget: number, metricKey: string): string => {
    const d = actual - budget
    if (metricKey === 'return_rate_pct' || metricKey === 'online_cost_of_sale_3') {
      if (d === 0) return '0'
      const a = Math.abs(d).toFixed(1)
      return d < 0 ? `(${a} pp)` : `+${a} pp`
    }
    if (metricKey === 'emer') {
      if (d === 0) return '0'
      const a = Math.abs(d).toFixed(1)
      return d < 0 ? `(${a})` : `+${a}`
    }
    if (metricKey === 'returning_customers' || metricKey === 'new_customers') {
      const r = Math.round(d)
      if (r === 0) return '0'
      const s = Math.abs(r).toLocaleString('sv-SE')
      return r < 0 ? `(${s})` : `+${s}`
    }
    if (d === 0) return '0'
    const thousandsValue = d / 1000
    const roundedThousands = Math.round(Math.abs(thousandsValue))
    const formattedThousands = roundedThousands.toLocaleString('sv-SE')
    if (d < 0) {
      return `(${formattedThousands})`
    }
    return `+${formattedThousands}`
  }

  /** Visible column label + optional tooltip (native title). */
  const th = (extra: string, label: ReactNode, tooltip?: string) => (
    <th
      title={tooltip}
      className={`${isPdfMode ? 'py-0.5 px-1' : 'py-1 px-2'} text-right font-medium text-gray-900 whitespace-nowrap ${isPdfMode ? 'tabular-nums' : ''} ${extra}`}
    >
      {label}
    </th>
  )

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
  const weekActualR = dateRanges.actual?.display || 'Week'
  const weekLyR = dateRanges.week_last_year?.display || 'Last year (same week)'
  const mtdAR = dateRanges.mtd_actual?.display || 'MTD'
  const mtdLyR = dateRanges.mtd_last_year?.display || 'MTD last year'
  const ytdAR = dateRanges.ytd_actual?.display || 'YTD'
  const ytdLyR = dateRanges.ytd_last_year?.display || 'YTD last year'

  const cell = (value: string, bg: string, semibold = false) => (
    <td
      className={`${isPdfMode ? 'py-0.5 px-1' : 'py-2 px-2'} text-right text-gray-700 ${isPdfMode ? 'tabular-nums' : ''} ${bg} ${semibold ? 'font-semibold' : ''}`}
    >
      {value}
    </td>
  )

  const fivePack = (
    metricKey: string,
    actual: number,
    lastYear: number,
    budget: number | null | undefined,
    weekClass: string
  ) => {
    const b = budget != null && !Number.isNaN(Number(budget)) ? Number(budget) : null
    const yoy = formatGrowthPercentage(calculateGrowthPercentage(actual, lastYear))
    const vsBud = b != null && b !== 0 ? formatBudgetVariance(actual, b, metricKey) : '—'
    return (
      <>
        {cell(formatValue(actual, metricKey), `${weekClass} font-semibold`)}
        {cell(formatValue(lastYear, metricKey), weekClass)}
        {cell(b != null ? formatValue(b, metricKey) : '—', `${weekClass} bg-green-50/80`)}
        {cell(yoy, weekClass)}
        {cell(vsBud, `${weekClass} bg-green-100/80 font-medium`)}
      </>
    )
  }

  return (
    <div className={`space-y-4 ${isPdfMode ? 'space-y-1' : ''}`}>
      {!isPdfMode && (
        <p className="text-sm text-muted-foreground">
          <strong>Week</strong> = latest ISO week vs same week last year; <strong>budget</strong> = share of the monthly
          budget for days of that week in the month (approximation). <strong>Month</strong> = month-to-date actuals vs
          last year and full-month budget. <strong>YTD</strong> budget is the fiscal-year sum from your budget file
          (through the current week; last month prorated). <strong>vs budget</strong> = actual minus budget in the same
          units as the row (SEK &apos;000 for money): positive means ahead of budget, negative means shortfall. Return
          rate and COS show the difference in <strong>pp</strong> (percentage points).
        </p>
      )}
      <div className={`bg-gray-50 rounded-lg overflow-hidden overflow-x-auto ${isPdfMode ? 'rounded-sm' : ''}`}>
        <table className={`w-full min-w-[1100px] ${isPdfMode ? 'text-[8pt]' : 'text-xs'} ${isPdfMode ? 'break-inside-avoid' : ''}`}>
          <thead>
            <tr className="bg-gray-200 border-b">
              <th
                className={`${isPdfMode ? 'py-0.5 px-1' : 'py-2 px-2'} text-left font-medium text-gray-900 border-r border-gray-300`}
                rowSpan={2}
              >
                (SEK &apos;000)
              </th>
              <th
                className={`${isPdfMode ? 'py-0.5 px-1' : 'py-2 px-2'} text-center font-medium text-gray-900 bg-slate-200 border-r border-gray-400`}
                colSpan={COL_COUNT}
                title={weekActualR}
              >
                Week
              </th>
              <th
                className={`${isPdfMode ? 'py-0.5 px-1' : 'py-2 px-2'} text-center font-medium text-gray-900 bg-gray-200 border-r border-gray-400`}
                colSpan={COL_COUNT}
                title={`${mtdAR} · ${mtdLyR}`}
              >
                Month
              </th>
              <th
                className={`${isPdfMode ? 'py-0.5 px-1' : 'py-2 px-2'} text-center font-medium text-gray-900 bg-blue-100`}
                colSpan={COL_COUNT}
                title={`${ytdAR} · ${ytdLyR}`}
              >
                YTD
              </th>
            </tr>
            <tr className="bg-gray-200 border-b">
              {th('bg-slate-200 border-l border-slate-300', 'Actual', weekActualR)}
              {th('bg-slate-200', 'Last year', weekLyR)}
              {th('bg-slate-200 bg-green-50/80', 'Budget', 'Share of monthly budget for this week (days in month)')}
              {th('bg-slate-200', 'Y/Y %', 'Actual vs last year')}
              {th(
                'bg-slate-200 bg-green-100/80 border-r border-gray-400',
                'vs budget',
                'Actual − budget (SEK ’000). + = ahead of budget, (−) = shortfall.',
              )}
              {th('bg-gray-200', 'Actual', mtdAR)}
              {th('bg-gray-200', 'Last year', mtdLyR)}
              {th('bg-gray-200 bg-green-50/80', 'Budget', 'Full month budget')}
              {th('bg-gray-200', 'Y/Y %', 'MTD actual vs MTD last year')}
              {th(
                'bg-gray-200 bg-green-100/80 border-r border-gray-400',
                'vs budget',
                'MTD actual − month budget (SEK ’000). + = ahead, (−) = shortfall.',
              )}
              {th('bg-blue-100', 'Actual', ytdAR)}
              {th('bg-blue-100', 'Last year', ytdLyR)}
              {th('bg-blue-100 bg-green-50/80', 'Budget', 'YTD budget when available')}
              {th('bg-blue-100', 'Y/Y %', 'YTD actual vs YTD last year')}
              {th(
                'bg-blue-100 bg-green-100/80',
                'vs budget',
                'YTD actual − cumulative YTD budget (SEK ’000). + = ahead of YTD budget, (−) = shortfall.',
              )}
            </tr>
          </thead>
          <tbody>
            {METRIC_LABELS.map((label, index) => {
              const metricKey = METRIC_KEYS[index]
              const wAct = periods.actual?.[metricKey] ?? 0
              const wLy = periods.week_last_year?.[metricKey] ?? 0
              const wBud = periods.week_budget?.[metricKey]

              const mAct = periods.mtd_actual?.[metricKey] ?? 0
              const mLy = periods.mtd_last_year?.[metricKey] ?? 0
              const mBud =
                periods.mtd_budget?.[metricKey] != null ? Number(periods.mtd_budget[metricKey]) : null

              const yAct = periods.ytd_actual?.[metricKey] ?? 0
              const yLy = periods.ytd_last_year?.[metricKey] ?? 0
              const yBud =
                periods.ytd_budget?.[metricKey] != null ? Number(periods.ytd_budget[metricKey]) : null

              return (
                <tr key={metricKey} className={`border-b border-gray-200 last:border-b-0 ${isPdfMode ? 'break-inside-avoid' : ''}`}>
                  <td
                    className={`${isPdfMode ? 'py-0.5 px-1' : 'py-2 px-2'} font-medium text-gray-900 border-r border-gray-200`}
                  >
                    {label}
                  </td>
                  {fivePack(metricKey, wAct, wLy, wBud, 'bg-slate-50')}
                  {fivePack(metricKey, mAct, mLy, mBud, 'bg-white')}
                  {fivePack(metricKey, yAct, yLy, yBud, 'bg-blue-50/60')}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {!isPdfMode && (
        <div className="text-sm text-gray-600">
          <p>
            Base week: <span className="font-medium">{baseWeek}</span>. Week budget is prorated from the same monthly
            budget used in the Month block.
          </p>
        </div>
      )}
    </div>
  )
}
