'use client'

import { useEffect, useState, type ReactNode } from 'react'
import { getTopMarketsNetMtd, hasBackend, type TopMarketsNetMtdResponse } from '@/lib/api'
import { Loader2 } from 'lucide-react'

interface TopMarketsNetRevenueTableProps {
  baseWeek: string
  isPdfMode?: boolean
}

const COLS = 5

export default function TopMarketsNetRevenueTable({
  baseWeek,
  isPdfMode = false,
}: TopMarketsNetRevenueTableProps) {
  const [data, setData] = useState<TopMarketsNetMtdResponse | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!baseWeek || !hasBackend) {
      setLoading(false)
      setData(null)
      if (!hasBackend) setErr('Backend URL not configured.')
      return
    }
    let cancelled = false
    ;(async () => {
      setLoading(true)
      setErr(null)
      try {
        const res = await getTopMarketsNetMtd(baseWeek, 8)
        if (!cancelled) {
          setData(res)
        }
      } catch (e) {
        if (!cancelled) {
          setErr(e instanceof Error ? e.message : 'Failed to load markets net revenue')
          setData(null)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [baseWeek])

  const formatNetK = (value: number): string => {
    if (value === 0) return '0'
    const roundedThousands = Math.round(Math.abs(value / 1000)).toLocaleString('sv-SE')
    if (value < 0) return `(${roundedThousands})`
    return roundedThousands
  }

  const formatYoY = (pct: number | null): string => {
    if (pct === null) return '—'
    const absValue = Math.abs(pct)
    const formatted = Math.round(absValue).toString()
    if (pct < 0) return `(${formatted}%)`
    return `${formatted}%`
  }

  const formatVsBudget = (actual: number, budget: number | null | undefined): string => {
    if (budget == null || Number.isNaN(Number(budget))) return '—'
    const d = actual - budget
    if (d === 0) return '0'
    const roundedThousands = Math.round(Math.abs(d / 1000)).toLocaleString('sv-SE')
    if (d < 0) return `(${roundedThousands})`
    return `+${roundedThousands}`
  }

  const th = (extra: string, label: ReactNode, tooltip?: string) => (
    <th
      title={tooltip}
      className={`${isPdfMode ? 'py-0.5 px-1' : 'py-1 px-2'} text-right font-medium text-gray-900 whitespace-nowrap ${isPdfMode ? 'tabular-nums' : ''} ${extra}`}
    >
      {label}
    </th>
  )

  const cell = (value: string, bg: string, semibold = false) => (
    <td
      className={`${isPdfMode ? 'py-0.5 px-1' : 'py-2 px-2'} text-right text-gray-700 ${isPdfMode ? 'tabular-nums' : ''} ${bg} ${semibold ? 'font-semibold' : ''}`}
    >
      {value}
    </td>
  )

  if (!hasBackend) {
    return (
      <p className="text-sm text-muted-foreground">
        Configure <code className="text-xs">NEXT_PUBLIC_API_URL</code> to load net revenue by market.
      </p>
    )
  }

  if (loading) {
    return (
      <div className="flex items-center gap-3 py-6">
        <Loader2 className="h-6 w-6 animate-spin text-primary" />
        <span className="text-gray-600">Loading net revenue by market…</span>
      </div>
    )
  }

  if (err) {
    return <p className="text-sm text-red-700">{err}</p>
  }

  if (!data?.markets?.length) {
    return <p className="text-sm text-muted-foreground">No market data for this week.</p>
  }

  const dr = data.date_ranges || {}
  const weekTitle = dr.week_actual?.display || 'Week'
  const mtdTitle = dr.mtd_actual?.display || 'Month'
  const ytdTitle = dr.ytd_actual?.display || 'YTD'
  const weekLyTitle = `Last year (same week)`
  const mtdLyTitle = dr.mtd_last_year?.display ? `LY ${dr.mtd_last_year.display}` : 'MTD last year'
  const ytdLyTitle = dr.ytd_last_year?.display ? `LY ${dr.ytd_last_year.display}` : 'YTD last year'

  return (
    <div className={`space-y-2 ${isPdfMode ? 'break-inside-avoid' : ''}`}>
      {!isPdfMode && (
        <p className="text-sm text-muted-foreground">
          <strong>Online net revenue</strong> by country (same top markets as the 8-week view, ranked by average online
          gross).{' '}
          {data.budget_source === 'file_per_market' ? (
            <>
              <strong>Budget</strong> comes from your budget file per market (net revenue rows). The file{' '}
              <strong>ROW</strong> line is split: part goes to countries without a own line (by actual mix), and part
              stays for <strong>ROW</strong> in proportion to long-tail vs pool online net (last year if the week is
              quiet). <strong>ROW</strong> also gets any remainder so the group total matches.{' '}
            </>
          ) : (
            <>
              <strong>Budget</strong> is the group online net budget for the period, split by each market&apos;s share
              of actual net (budget file had no usable Market breakdown).{' '}
            </>
          )}
          <strong>Month</strong> actuals are MTD (1st → week end); <strong>Month budget</strong> is the same
          share of that month&apos;s plan. <strong>YTD budget</strong> is fiscal (Apr start) through the same
          end date as YTD actuals. <strong>vs budget</strong> = actual − budget (SEK &apos;000); + = ahead.
        </p>
      )}
      <div
        className={`rounded-lg overflow-hidden overflow-x-auto border border-slate-200/90 bg-slate-100 shadow-sm ${isPdfMode ? 'rounded-sm' : ''}`}
      >
        <table
          className={`w-full min-w-[1180px] bg-white ${isPdfMode ? 'text-[7pt]' : 'text-xs'} ${isPdfMode ? 'break-inside-avoid' : ''}`}
        >
          <thead>
            <tr className="bg-gray-200 border-b">
              <th
                rowSpan={2}
                className={`${isPdfMode ? 'py-0.5 px-1' : 'py-2 px-2'} text-left font-medium text-gray-900 border-r border-gray-300 align-bottom`}
              >
                Country
              </th>
              <th
                colSpan={COLS}
                className={`${isPdfMode ? 'py-0.5 px-1' : 'py-2 px-2'} text-center font-medium bg-sky-100 border-r border-gray-400`}
                title={weekTitle}
              >
                Week
              </th>
              <th
                colSpan={COLS}
                className={`${isPdfMode ? 'py-0.5 px-1' : 'py-2 px-2'} text-center font-medium bg-teal-100 border-r border-gray-400`}
                title={mtdTitle}
              >
                Month
              </th>
              <th
                colSpan={COLS}
                className={`${isPdfMode ? 'py-0.5 px-1' : 'py-2 px-2'} text-center font-medium bg-blue-100`}
                title={ytdTitle}
              >
                YTD
              </th>
            </tr>
            <tr className="bg-gray-200 border-b">
              {th('bg-sky-100 border-l border-sky-200', 'Actual', weekTitle)}
              {th('bg-sky-100', 'Last year', weekLyTitle)}
              {th(
                'bg-sky-100 bg-green-50/80',
                'Budget',
                "That month's budget × (ISO week days in that month ÷ days in month)",
              )}
              {th('bg-sky-100', 'Y/Y %', 'Actual vs last year (same week)')}
              {th('bg-sky-100 bg-green-100/80 border-r border-gray-400', 'vs budget', 'Actual − budget (SEK ’000)')}
              {th('bg-teal-100 border-l border-teal-200', 'Actual', mtdTitle)}
              {th('bg-teal-100', 'Last year', mtdLyTitle)}
              {th(
                'bg-teal-100 bg-green-50/80',
                'Budget',
                'MTD budget: full month plan × (week-end day ÷ days in month), same span as Month actual',
              )}
              {th('bg-teal-100', 'Y/Y %', 'MTD vs MTD LY')}
              {th('bg-teal-100 bg-green-100/80 border-r border-gray-400', 'vs budget', 'Actual − budget (SEK ’000)')}
              {th('bg-blue-100 border-l border-blue-200', 'Actual', ytdTitle)}
              {th('bg-blue-100', 'Last year', ytdLyTitle)}
              {th(
                'bg-blue-100 bg-green-50/80',
                'Budget',
                'Fiscal YTD budget (Apr–Mar) through week end, prorated in the current month',
              )}
              {th('bg-blue-100', 'Y/Y %', 'YTD vs YTD LY')}
              {th('bg-blue-100 bg-green-100/80', 'vs budget', 'Actual − budget (SEK ’000)')}
            </tr>
          </thead>
          <tbody>
            {data.markets.map((row) => {
              const isRow = row.country === 'ROW'
              const isTotal = row.country === 'Total'
              const bg = isRow ? 'bg-gray-100' : isTotal ? 'bg-gray-200 font-semibold' : ''
              const pack = (
                w: (typeof row)['week'],
                blockClass: string
              ) => (
                <>
                  {cell(formatNetK(w.actual), `${blockClass} font-semibold`)}
                  {cell(formatNetK(w.last_year), blockClass)}
                  {cell(w.budget != null ? formatNetK(w.budget) : '—', `${blockClass} bg-green-50/80`)}
                  {cell(formatYoY(w.yoy_pct), blockClass)}
                  {cell(formatVsBudget(w.actual, w.budget), `${blockClass} bg-green-100/80 font-medium`)}
                </>
              )
              return (
                <tr key={row.country} className={`border-b border-gray-200 last:border-b-0 ${bg}`}>
                  <td
                    className={`${isPdfMode ? 'py-0.5 px-1' : 'py-2 px-2'} font-medium text-gray-900 border-r border-gray-200 ${isTotal ? 'font-bold' : ''}`}
                  >
                    {row.country}
                  </td>
                  {pack(row.week, 'bg-sky-50/60')}
                  {pack(row.month, 'bg-teal-50/60')}
                  {pack(row.ytd, 'bg-blue-50/60')}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {data.budget_explanation && data.budget_explanation.length > 0 && (
        <div
          className={`rounded-md border border-gray-200 bg-gray-50/80 ${isPdfMode ? 'mt-1 px-2 py-1' : 'mt-2 px-3 py-2'}`}
        >
          <p
            className={`font-medium text-gray-800 ${isPdfMode ? 'text-[7pt] leading-tight' : 'text-xs'}`}
          >
            How Week, Month, and YTD budgets are calculated
          </p>
          <ul
            className={`list-disc pl-4 text-gray-600 space-y-0.5 ${isPdfMode ? 'text-[7pt] leading-tight mt-0.5' : 'text-xs mt-1'}`}
          >
            {data.budget_explanation.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
        </div>
      )}
      {!isPdfMode && data.period_info?.latest_dates && (
        <p className="text-xs text-gray-500">Latest week in ranking: {data.period_info.latest_dates}</p>
      )}
    </div>
  )
}
