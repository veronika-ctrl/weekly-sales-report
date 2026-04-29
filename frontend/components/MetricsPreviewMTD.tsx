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

/** Week column uses MTD-derived plan for aMER (monthly eMER convention). */
const STATIC_MONTH_BUDGET_KEYS = new Set<string>(['emer'])

/** Body cell styles per time block: Actual highlighted, Last year vs Y/Y differ, Budget + vs budget share one green. */
type PeriodBlock = 'week' | 'month' | 'ytd'

const PERIOD_BODY: Record<
  PeriodBlock,
  { actual: string; lastYear: string; yoy: string; budget: string; vsBudget: string }
> = {
  week: {
    actual:
      'bg-amber-50 text-gray-900 font-semibold border-l border-amber-200/80 shadow-[inset_0_0_0_1px_rgba(251,191,36,0.15)]',
    lastYear: 'bg-slate-100 text-gray-700',
    yoy: 'bg-violet-50 text-gray-700',
    budget: 'bg-emerald-50 text-gray-800',
    vsBudget: 'bg-emerald-50 text-gray-800 font-medium border-r border-slate-300/80',
  },
  month: {
    actual:
      'bg-amber-50 text-gray-900 font-semibold border-l border-amber-200/80 shadow-[inset_0_0_0_1px_rgba(251,191,36,0.15)]',
    lastYear: 'bg-slate-100 text-gray-700',
    yoy: 'bg-violet-50 text-gray-700',
    budget: 'bg-emerald-50 text-gray-800',
    vsBudget: 'bg-emerald-50 text-gray-800 font-medium border-r border-slate-300/80',
  },
  ytd: {
    actual:
      'bg-amber-50 text-gray-900 font-semibold border-l border-amber-200/80 shadow-[inset_0_0_0_1px_rgba(251,191,36,0.15)]',
    lastYear: 'bg-slate-100 text-gray-700',
    yoy: 'bg-violet-50 text-gray-700',
    budget: 'bg-emerald-50 text-gray-800',
    vsBudget: 'bg-emerald-50 text-gray-800 font-medium',
  },
}

/** Header row 2 — aligned with body bands (Week / Month / YTD). */
const PERIOD_HEAD: Record<PeriodBlock, { group: string; actual: string; lastYear: string; yoy: string; budget: string; vsBudget: string }> = {
  week: {
    group: 'bg-slate-300/95 border-slate-400',
    actual: 'bg-amber-100 border-l border-amber-300',
    lastYear: 'bg-slate-100',
    yoy: 'bg-violet-100',
    budget: 'bg-emerald-100/90',
    vsBudget: 'bg-emerald-100/90 border-r border-slate-400/70',
  },
  month: {
    group: 'bg-amber-200/95 border-amber-300',
    actual: 'bg-amber-100 border-l border-amber-300',
    lastYear: 'bg-slate-100',
    yoy: 'bg-violet-100',
    budget: 'bg-emerald-100/90',
    vsBudget: 'bg-emerald-100/90 border-r border-slate-400/70',
  },
  ytd: {
    group: 'bg-sky-200/90 border-sky-300',
    actual: 'bg-amber-100 border-l border-amber-300',
    lastYear: 'bg-slate-100',
    yoy: 'bg-violet-100',
    budget: 'bg-emerald-100/90',
    vsBudget: 'bg-emerald-100/90',
  },
}

export default function MetricsPreviewMTD({
  mtdData,
  baseWeek,
  isPdfMode = false,
}: MetricsPreviewMTDProps) {
  const calculateGrowthPercentage = (current: number, previous: number): number | null => {
    if (previous === 0) return null
    return ((current - previous) / previous) * 100
  }

  const isPercentMetric = (metricKey: string): boolean =>
    metricKey === 'return_rate_pct' || metricKey === 'online_cost_of_sale_3'

  const isSignedCostMetric = (metricKey: string): boolean =>
    metricKey === 'returns' || metricKey === 'marketing_spend'

  const isLowerBetterMetric = (metricKey: string): boolean =>
    metricKey === 'returns' ||
    metricKey === 'marketing_spend' ||
    metricKey === 'return_rate_pct' ||
    metricKey === 'online_cost_of_sale_3'

  const formatYoYForMetric = (metricKey: string, actual: number, lastYear: number): string => {
    if (isPercentMetric(metricKey)) {
      const diff = actual - lastYear
      const directionalDiff = isLowerBetterMetric(metricKey) ? -diff : diff
      return formatPpDifference(directionalDiff)
    }
    const growth = calculateGrowthPercentage(actual, lastYear)
    if (growth === null) return '—'
    const directionalGrowth = isLowerBetterMetric(metricKey) ? -growth : growth
    return formatGrowthPercentage(directionalGrowth)
  }

  const formatGrowthPercentage = (value: number | null): string => {
    if (value === null) return '—'
    const absValue = Math.abs(value)
    const formatted = Math.round(absValue).toString()
    if (value < 0) return `(${formatted}%)`
    return `${formatted}%`
  }

  const formatPpDifference = (value: number | null): string => {
    if (value === null) return '—'
    if (value === 0) return '0 pp'
    const absValue = Math.abs(value).toFixed(1)
    return value < 0 ? `(${absValue} pp)` : `+${absValue} pp`
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

  /**
   * vs budget for % KPIs where lower is better (return rate, COS).
   * Uses (budget − actual) in pp: **positive** = below plan (favorable); **negative** = above plan (unfavorable).
   */
  const formatVsBudgetPercentPp = (actual: number, budget: number): string => {
    const b = Math.abs(budget)
    const diff = b - actual
    if (diff === 0) return '0 pp'
    const absV = Math.abs(diff).toFixed(1)
    if (diff < 0) return `-${absV} pp`
    return `+${absV} pp`
  }

  const formatVsBudget = (actual: number, budget: number, metricKey: string): string => {
    if (isPercentMetric(metricKey)) {
      return formatVsBudgetPercentPp(actual, budget)
    }
    if (metricKey === 'emer') {
      const a = Math.abs(actual)
      const b = Math.abs(budget)
      if (b === 0) return '—'
      const pct = ((a - b) / b) * 100
      if (!Number.isFinite(pct)) return '—'
      const rounded = Math.round(Math.abs(pct))
      if (rounded === 0) return '0%'
      return pct < 0 ? `(${rounded}%)` : `${rounded}%`
    }
    const a = isSignedCostMetric(metricKey) ? Math.abs(actual) : actual
    const b = isSignedCostMetric(metricKey) ? Math.abs(budget) : Math.abs(budget)
    if (b === 0) return '—'
    const rawPct = ((a - b) / b) * 100
    const pct = isLowerBetterMetric(metricKey) ? -rawPct : rawPct
    if (!Number.isFinite(pct)) return '—'
    const rounded = Math.round(Math.abs(pct))
    if (rounded === 0) return '0%'
    return pct < 0 ? `(${rounded}%)` : `${rounded}%`
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

  const cell = (value: string, bg: string) => (
    <td className={`${isPdfMode ? 'py-0.5 px-1' : 'py-2 px-2'} text-right ${isPdfMode ? 'tabular-nums' : ''} ${bg}`}>
      {value}
    </td>
  )

  const fivePack = (
    metricKey: string,
    actual: number,
    lastYear: number,
    budget: number | null | undefined,
    block: PeriodBlock,
  ) => {
    const s = PERIOD_BODY[block]
    const rawBudget = budget != null && !Number.isNaN(Number(budget)) ? Number(budget) : null
    const b = rawBudget != null ? Math.abs(rawBudget) : null
    const yoy = formatYoYForMetric(metricKey, actual, lastYear)
    const vsBud =
      rawBudget != null && !Number.isNaN(Number(rawBudget))
        ? formatVsBudget(actual, Number(rawBudget), metricKey)
        : '—'
    return (
      <>
        {cell(formatValue(actual, metricKey), s.actual)}
        {cell(formatValue(lastYear, metricKey), s.lastYear)}
        {cell(b != null ? formatValue(b, metricKey) : '—', s.budget)}
        {cell(yoy, s.yoy)}
        {cell(vsBud, s.vsBudget)}
      </>
    )
  }

  return (
    <div className={`space-y-4 ${isPdfMode ? 'space-y-1' : ''}`}>
      {!isPdfMode && (
        <p className="text-sm text-muted-foreground">
          <strong>Week</strong> = latest ISO week vs same week last year; <strong>budget</strong> = sum of daily plan
          amounts for that Mon–Sun (monthly plan spread evenly per calendar day, or exact daily rows if your budget file
          has Date + Metric + Value). <strong>Month</strong> = month-to-date actuals vs last year; month budget = plan
          for the same calendar dates (1st through end of the selected week). <strong>YTD</strong> budget = plan for the
          same fiscal YTD dates as actuals (Apr 1 through week end). <strong>vs budget</strong> = percent variance
          for value rows. <strong>Return rate</strong> and <strong>COS</strong>: pp = budget minus actual;{' '}
          <strong>+</strong> (e.g. +1.3 pp) = below plan (favorable); <strong>−</strong> (e.g. −2.5 pp) = above plan
          (unfavorable).
        </p>
      )}
      <div className={`bg-gray-50 rounded-lg overflow-hidden overflow-x-auto ${isPdfMode ? 'rounded-sm' : ''}`}>
        <table className={`w-full min-w-[1100px] ${isPdfMode ? 'text-[8pt]' : 'text-xs'} ${isPdfMode ? 'break-inside-avoid' : ''}`}>
          <thead>
            <tr className="border-b border-gray-300">
              <th
                className={`${isPdfMode ? 'py-0.5 px-1' : 'py-2 px-2'} text-left font-medium text-gray-900 border-r border-gray-300 bg-gray-100`}
                rowSpan={2}
              >
                (SEK &apos;000)
              </th>
              <th
                className={`${isPdfMode ? 'py-0.5 px-1' : 'py-2 px-2'} text-center font-semibold text-gray-900 border-r border-slate-400/80 ${PERIOD_HEAD.week.group}`}
                colSpan={COL_COUNT}
                title={weekActualR}
              >
                Week
              </th>
              <th
                className={`${isPdfMode ? 'py-0.5 px-1' : 'py-2 px-2'} text-center font-semibold text-gray-900 border-r border-stone-400/80 ${PERIOD_HEAD.month.group}`}
                colSpan={COL_COUNT}
                title={`${mtdAR} · ${mtdLyR}`}
              >
                Month
              </th>
              <th
                className={`${isPdfMode ? 'py-0.5 px-1' : 'py-2 px-2'} text-center font-semibold text-gray-900 ${PERIOD_HEAD.ytd.group}`}
                colSpan={COL_COUNT}
                title={`${ytdAR} · ${ytdLyR}`}
              >
                YTD
              </th>
            </tr>
            <tr className="border-b border-gray-300">
              {th(PERIOD_HEAD.week.actual, 'Actual', weekActualR)}
              {th(PERIOD_HEAD.week.lastYear, 'Last year', weekLyR)}
              {th(PERIOD_HEAD.week.budget, 'Budget', 'Daily plan summed for this ISO week (7 days)')}
              {th(PERIOD_HEAD.week.yoy, 'Y/Y %', 'Actual vs last year')}
              {th(
                PERIOD_HEAD.week.vsBudget,
                'vs budget',
                'Week: % variance for value rows. Return rate &amp; COS vs budget: pp = budget−actual; + = below plan, − = above plan.',
              )}
              {th(PERIOD_HEAD.month.actual, 'Actual', mtdAR)}
              {th(PERIOD_HEAD.month.lastYear, 'Last year', mtdLyR)}
              {th(
                PERIOD_HEAD.month.budget,
                'Budget',
                'Daily plan summed for MTD (1st through week end — same dates as Actual)',
              )}
              {th(PERIOD_HEAD.month.yoy, 'Y/Y %', 'MTD actual vs MTD last year')}
              {th(
                PERIOD_HEAD.month.vsBudget,
                'vs budget',
                'MTD: % variance for value rows. Return rate &amp; COS: pp = budget−actual; + below plan, − above plan.',
              )}
              {th(PERIOD_HEAD.ytd.actual, 'Actual', ytdAR)}
              {th(PERIOD_HEAD.ytd.lastYear, 'Last year', ytdLyR)}
              {th(PERIOD_HEAD.ytd.budget, 'Budget', 'Daily plan summed fiscal YTD (same dates as Actual)')}
              {th(PERIOD_HEAD.ytd.yoy, 'Y/Y %', 'YTD actual vs YTD last year')}
              {th(
                PERIOD_HEAD.ytd.vsBudget,
                'vs budget',
                'YTD: % variance for value rows. Return rate &amp; COS: pp = budget−actual; + below plan, − above plan.',
              )}
            </tr>
          </thead>
          <tbody>
            {METRIC_LABELS.map((label, index) => {
              const metricKey = METRIC_KEYS[index]
              const yBud =
                periods.ytd_budget?.[metricKey] != null ? Number(periods.ytd_budget[metricKey]) : null

              const wAct = periods.actual?.[metricKey] ?? 0
              const wLy = periods.week_last_year?.[metricKey] ?? 0
              const wBud = STATIC_MONTH_BUDGET_KEYS.has(metricKey)
                ? periods.mtd_budget?.[metricKey]
                : periods.week_budget?.[metricKey]

              const mAct = periods.mtd_actual?.[metricKey] ?? 0
              const mLy = periods.mtd_last_year?.[metricKey] ?? 0
              const mBud =
                periods.mtd_budget?.[metricKey] != null ? Number(periods.mtd_budget[metricKey]) : null

              const yAct = periods.ytd_actual?.[metricKey] ?? 0
              const yLy = periods.ytd_last_year?.[metricKey] ?? 0

              return (
                <tr key={metricKey} className={`border-b border-gray-200/80 last:border-b-0 ${isPdfMode ? 'break-inside-avoid' : ''}`}>
                  <td
                    className={`${isPdfMode ? 'py-0.5 px-1' : 'py-2 px-2'} font-medium text-gray-900 border-r border-gray-300 bg-gray-50/90 ${isPdfMode ? '' : 'sticky left-0 z-[1] shadow-[2px_0_6px_-2px_rgba(0,0,0,0.08)]'}`}
                  >
                    {label}
                  </td>
                  {fivePack(metricKey, wAct, wLy, wBud, 'week')}
                  {fivePack(metricKey, mAct, mLy, mBud, 'month')}
                  {fivePack(metricKey, yAct, yLy, yBud ?? null, 'ytd')}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {!isPdfMode && (
        <div className="text-sm text-gray-600">
          <p>
            Base week: <span className="font-medium">{baseWeek}</span>. Budgets are built from daily amounts (even
            spread of each monthly plan when no daily rows are present).
          </p>
        </div>
      )}
    </div>
  )
}
