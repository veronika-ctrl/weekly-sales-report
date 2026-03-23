'use client'

import { useEffect, useMemo, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'
import { getDiscountsCustomers, type DiscountsCustomersResponse } from '@/lib/api'

interface DiscountsCustomerTableProps {
  baseWeek: string
  months?: number
  segment?: 'all' | 'new' | 'returning'
}

export default function DiscountsCustomerTable({ baseWeek, months = 12, segment = 'all' }: DiscountsCustomerTableProps) {
  const [data, setData] = useState<DiscountsCustomersResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setLoading(true)
      setError(null)
      try {
        const res = await getDiscountsCustomers(baseWeek, months, segment)
        if (!cancelled) setData(res)
      } catch (e: any) {
        if (!cancelled) setError(e?.message || 'Failed to load customer segments')
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [baseWeek, months, segment])

  const fmtInt = (v: number) => (Number.isFinite(v) ? Math.round(v).toLocaleString('sv-SE') : '0')
  const fmtUsd = (v: number) => (Number.isFinite(v) ? Math.round(v / 1000).toLocaleString('sv-SE') : '0')
  const fmtPct = (v: number) => `${Number.isFinite(v) ? v.toFixed(1) : '0.0'}%`

  const windowLabel = useMemo(() => {
    const w = data?.window
    if (!w?.start || !w?.end) return `Last ${months} months`
    return `Last ${months} months (${w.start} → ${w.end})`
  }, [data?.window, months])

  if (loading && !data) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <Loader2 className="h-5 w-5 animate-spin text-primary" />
          <span className="text-gray-600">Loading customer segments…</span>
        </div>
        <div className="space-y-2">
          <Skeleton className="h-12 w-full" />
          {[...Array(10)].map((_, i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </div>
      </div>
    )
  }

  if (error) return <div className="text-sm text-red-700">{error}</div>
  if (!data) return <div className="text-sm text-gray-600">No data.</div>

  const overall = data.segments_overall || []
  const first = data.first_purchase || []

  return (
    <div className="space-y-8">
      <div className="bg-gray-50 rounded-lg overflow-hidden overflow-x-auto">
        <div className="px-4 py-3 border-b bg-white">
          <div className="text-sm font-semibold text-gray-900">Customer segments (Full Price vs Sale)</div>
          <div className="text-xs text-gray-600">{windowLabel}</div>
        </div>
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-gray-200 border-b">
              <th className="text-left py-2 px-2 font-medium text-gray-900">Segment</th>
              <th className="text-right py-2 px-2 font-medium text-gray-900">Customers</th>
              <th className="text-right py-2 px-2 font-medium text-gray-900">Orders</th>
              <th className="text-right py-2 px-2 font-medium text-gray-900">Revenue (USD '000)</th>
              <th className="text-right py-2 px-2 font-medium text-gray-900">AOV (USD)</th>
              <th className="text-right py-2 px-2 font-medium text-gray-900">Rev / Cust (USD)</th>
              <th className="text-right py-2 px-2 font-medium text-gray-900">Orders / Cust</th>
            </tr>
          </thead>
          <tbody>
            {overall.map((r) => (
              <tr key={r.segment} className={`border-b border-gray-200 last:border-b-0 ${r.segment === 'Total' ? 'bg-gray-100 font-semibold' : 'bg-white'}`}>
                <td className="py-2 px-2 text-gray-900">{r.segment}</td>
                <td className="py-2 px-2 text-right text-gray-700 tabular-nums">{fmtInt(r.customers)}</td>
                <td className="py-2 px-2 text-right text-gray-700 tabular-nums">{fmtInt(r.orders)}</td>
                <td className="py-2 px-2 text-right text-gray-700 tabular-nums">{fmtUsd(r.revenue)}</td>
                <td className="py-2 px-2 text-right text-gray-700 tabular-nums">{fmtInt(r.aov)}</td>
                <td className="py-2 px-2 text-right text-gray-700 tabular-nums">{fmtInt(r.rev_per_customer)}</td>
                <td className="py-2 px-2 text-right text-gray-700 tabular-nums">{Number.isFinite(r.orders_per_customer) ? r.orders_per_customer.toFixed(2) : '0.00'}</td>
              </tr>
            ))}
            {!overall.length ? (
              <tr>
                <td className="px-3 py-3 text-gray-600" colSpan={7}>
                  No customers in this window.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>

      <div className="bg-gray-50 rounded-lg overflow-hidden overflow-x-auto">
        <div className="px-4 py-3 border-b bg-white">
          <div className="text-sm font-semibold text-gray-900">First purchase → repeat behavior</div>
          <div className="text-xs text-gray-600">Repeat = any purchase after first purchase date (within the same window)</div>
        </div>
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-gray-200 border-b">
              <th className="text-left py-2 px-2 font-medium text-gray-900">First segment</th>
              <th className="text-right py-2 px-2 font-medium text-gray-900">Customers</th>
              <th className="text-right py-2 px-2 font-medium text-gray-900">Repeat customers</th>
              <th className="text-right py-2 px-2 font-medium text-gray-900">Repeat rate</th>
              <th className="text-right py-2 px-2 font-medium text-gray-900">Repeat Full</th>
              <th className="text-right py-2 px-2 font-medium text-gray-900">Repeat Sale</th>
              <th className="text-right py-2 px-2 font-medium text-gray-900">Repeat Mixed</th>
              <th className="text-right py-2 px-2 font-medium text-gray-900">No repeat</th>
            </tr>
          </thead>
          <tbody>
            {first.map((r) => (
              <tr key={r.first_segment} className={`border-b border-gray-200 last:border-b-0 ${r.first_segment === 'Total' ? 'bg-gray-100 font-semibold' : 'bg-white'}`}>
                <td className="py-2 px-2 text-gray-900">{r.first_segment}</td>
                <td className="py-2 px-2 text-right text-gray-700 tabular-nums">{fmtInt(r.customers)}</td>
                <td className="py-2 px-2 text-right text-gray-700 tabular-nums">{fmtInt(r.repeat_customers)}</td>
                <td className="py-2 px-2 text-right text-gray-700 tabular-nums">{fmtPct(r.repeat_rate_pct)}</td>
                <td className="py-2 px-2 text-right text-gray-700 tabular-nums">{fmtInt(r.repeat_full_price)}</td>
                <td className="py-2 px-2 text-right text-gray-700 tabular-nums">{fmtInt(r.repeat_sale)}</td>
                <td className="py-2 px-2 text-right text-gray-700 tabular-nums">{fmtInt(r.repeat_mixed)}</td>
                <td className="py-2 px-2 text-right text-gray-700 tabular-nums">{fmtInt(r.no_repeat)}</td>
              </tr>
            ))}
            {!first.length ? (
              <tr>
                <td className="px-3 py-3 text-gray-600" colSpan={8}>
                  No first-purchase data available.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  )
}



