'use client'

import { useEffect, useMemo, useState } from 'react'
import { getDiscountsMonthlyMetrics, type DiscountsMonthlyResponse, type PeriodsResponse } from '@/lib/api'

interface ProductsSummaryMonthPreviewProps {
  periods: PeriodsResponse
  baseWeek: string
}

const METRICS: Array<{ label: string; key: string; indent?: boolean }> = [
  { label: 'Net Revenue Overall', key: 'net_revenue_overall' },
  { label: 'Net Revenue Full Price', key: 'net_revenue_full_price' },
  { label: 'Net Revenue Sale', key: 'net_revenue_sale' },
  ...[10, 20, 30, 40, 50, 60, 70].map((b) => ({ label: `${b}%`, key: `net_revenue_sale_${b}`, indent: true })),
]

export default function ProductsSummaryMonthPreview({ periods, baseWeek }: ProductsSummaryMonthPreviewProps) {
  const [monthly, setMonthly] = useState<DiscountsMonthlyResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setLoading(true)
      setError(null)
      try {
        const res = await getDiscountsMonthlyMetrics(baseWeek, 12)
        if (!cancelled) setMonthly(res)
      } catch (e: any) {
        if (!cancelled) setError(e?.message || 'Failed to load products month summary')
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [baseWeek])

  const months = monthly?.months || []
  const current = monthly?.current || null
  const lastYear = monthly?.last_year || null

  const weekEnd = useMemo(() => {
    const end = periods?.date_ranges?.actual?.end
    return end ? new Date(end) : null
  }, [periods])

  const monthsLabel = useMemo(() => {
    if (!weekEnd) return 'Last 12 months (by month)'
    const end = weekEnd
    const start = new Date(end.getFullYear(), end.getMonth(), 1)
    start.setMonth(start.getMonth() - 11)
    const fmt = (d: Date) => d.toISOString().slice(0, 10)
    return `Last 12 months (${fmt(start)} → ${fmt(end)})`
  }, [weekEnd])

  const formatUsdThousands = (value: number) => {
    const v = Number.isFinite(value) ? value : 0
    if (v === 0) return '0'
    return Math.round(v / 1000).toLocaleString('sv-SE')
  }

  const growthPct = (current: number, previous: number): number | null => {
    if (!previous) return null
    return ((current - previous) / previous) * 100
  }

  const fmtPct = (value: number | null) => {
    if (value === null) return '—'
    const abs = Math.abs(value).toFixed(1)
    return value < 0 ? `(${abs}%)` : `${abs}%`
  }

  const fmtMonth = (ym: string) => {
    // ym = YYYY-MM
    const parts = ym.split('-').map(Number)
    const y = parts[0]
    const m = parts[1]
    if (!y || !m) return ym
    const dt = new Date(Date.UTC(y, m - 1, 1))
    return new Intl.DateTimeFormat('en-US', { month: 'short', year: 'numeric' }).format(dt)
  }

  const fmtMonthHeader = (ym: string, idx: number) => {
    // Latest month is month-to-date (clamped to base week end)
    const base = fmtMonth(ym)
    return idx === 0 ? `${base} (MTD)` : base
  }

  if (loading && !monthly) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        <span className="ml-3 text-gray-600">Loading products month summary…</span>
      </div>
    )
  }

  if (error) return <div className="text-sm text-red-700">{error}</div>
  if (!current || !lastYear || months.length === 0) {
    return <div className="text-sm text-gray-600">No products month summary data available.</div>
  }

  return (
    <div className="bg-gray-50 rounded-lg overflow-hidden overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="bg-gray-200 border-b">
            <th className="py-2 px-2 text-left font-medium text-gray-900" rowSpan={2}>
              (USD '000)
            </th>
            <th className="py-2 px-2 text-center font-medium text-gray-900 bg-gray-200" colSpan={months.length}>
              {monthsLabel}
            </th>
            <th className="py-2 px-2 text-center font-medium text-gray-900 bg-amber-100" colSpan={months.length}>
              YoY
            </th>
          </tr>
          <tr className="bg-gray-200 border-b">
            {months.map((m) => (
              <th key={`m_${m}`} className="py-1 px-2 text-right font-medium text-gray-900">
                {fmtMonthHeader(m, months.indexOf(m))}
              </th>
            ))}
            {months.map((m) => (
              <th key={`yoy_${m}`} className="py-1 px-2 text-right font-medium text-gray-900 bg-amber-50">
                {fmtMonthHeader(m, months.indexOf(m))}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {METRICS.map(({ label, key, indent }) => {
            const rowTextTone = indent ? 'text-gray-600' : 'text-gray-700'
            const labelTone = indent ? 'text-gray-600 italic font-normal' : 'text-gray-900 font-medium'
            const rowPadY = indent ? 'py-1' : 'py-2'
            const rowBg = indent ? 'bg-gray-50' : ''

            return (
              <tr key={`mtd_${key}`} className={`border-b border-gray-200 last:border-b-0 ${rowBg} ${indent ? 'text-[11px]' : ''}`}>
                <td className={`${rowPadY} px-2 ${labelTone} ${indent ? 'pl-8 border-l-2 border-gray-200' : ''}`}>{label}</td>
                {months.map((m) => {
                  const v = Number(current?.[m]?.[key] || 0)
                  const bg = m === months[0] ? 'bg-gray-200 font-semibold' : ''
                  return (
                    <td key={`cur_${key}_${m}`} className={`${rowPadY} px-2 text-right ${rowTextTone} ${bg} font-mono tabular-nums`}>
                      {formatUsdThousands(v)}
                    </td>
                  )
                })}
                {months.map((m) => {
                  const v = Number(current?.[m]?.[key] || 0)
                  const ly = Number(lastYear?.[m]?.[key] || 0)
                  return (
                    <td
                      key={`yoy_${key}_${m}`}
                      className={`${rowPadY} px-2 text-right ${rowTextTone} bg-amber-50 font-mono tabular-nums`}
                    >
                      {fmtPct(growthPct(v, ly))}
                    </td>
                  )
                })}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}


