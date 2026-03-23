'use client'

import { useEffect, useMemo, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'
import { getDiscountsProducts } from '@/lib/api'

interface DiscountsProductTableProps {
  baseWeek: string
}

export default function DiscountsProductTable({ baseWeek }: DiscountsProductTableProps) {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setLoading(true)
      setError(null)
      try {
        const res = await getDiscountsProducts(baseWeek, 8, 'all', 'month', 12)
        if (!cancelled) setData(res)
      } catch (e: any) {
        if (!cancelled) setError(e?.message || 'Failed to load products')
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [baseWeek])

  const formatValue = (value: number): string => {
    if (!value) return '0'
    return Math.round(value / 1000).toLocaleString('sv-SE')
  }

  const calcYoY = (current: number, prev: number): number | null => {
    if (!prev) return null
    return ((current - prev) / prev) * 100
  }

  const fmtYoY = (value: number | null): string => {
    if (value === null) return '-'
    const abs = Math.abs(value)
    const v = Math.round(abs).toString()
    return value < 0 ? `(${v}%)` : `${v}%`
  }

  const fmtMonth = (ym: string) => {
    const parts = ym.split('-').map(Number)
    const y = parts[0]
    const m = parts[1]
    const names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    const mn = m >= 1 && m <= 12 ? names[m - 1] : ym
    return `${mn} ${y}`
  }

  const { periodKeys, fullCats, saleCats, catsByPeriod, granularity } = useMemo(() => {
    const category_sales = Array.isArray(data?.category_sales) ? data.category_sales : []
    const granularity = (data?.granularity || 'week') as 'week' | 'month'
    const periodKeys: string[] = category_sales
      .map((p: any) => String(granularity === 'month' ? p.month : p.week))
      .filter(Boolean)
      .sort()

    const catsByPeriod: Record<string, { cur: Record<string, number>; ly: Record<string, number> }> = {}
    for (const p of category_sales) {
      const key = String(granularity === 'month' ? p.month : p.week)
      if (!key) continue
      catsByPeriod[key] = {
        cur: (p.categories || {}) as any,
        ly: (p.last_year?.categories || {}) as any,
      }
    }

    const allKeys = new Set<string>()
    for (const k of periodKeys) {
      Object.keys(catsByPeriod[k]?.cur || {}).forEach((x) => allKeys.add(x))
    }

    const fullCats = Array.from(allKeys).filter((k) => k.startsWith('FULL_'))
    const saleCats = Array.from(allKeys).filter((k) => k.startsWith('SALE_'))

    const avg = (k: string) => {
      if (!periodKeys.length) return 0
      const sum = periodKeys.reduce((acc: number, p: string) => acc + Number(catsByPeriod[p]?.cur?.[k] || 0), 0)
      return sum / periodKeys.length
    }

    return {
      periodKeys,
      fullCats: fullCats.sort((a, b) => avg(b) - avg(a)),
      saleCats: saleCats.sort((a, b) => avg(b) - avg(a)),
      catsByPeriod,
      granularity,
    }
  }, [data])

  const renderCategoryRow = (key: string, indent: boolean = false) => {
    const label = key.replace(/^FULL_/, '').replace(/^SALE_/, '')
    const avg =
      periodKeys.reduce((acc: number, p: string) => acc + Number(catsByPeriod[p]?.cur?.[key] || 0), 0) / (periodKeys.length || 1)
    const lyAvg =
      periodKeys.reduce((acc: number, p: string) => acc + Number(catsByPeriod[p]?.ly?.[key] || 0), 0) / (periodKeys.length || 1)

    return (
      <tr key={key} className="border-b border-gray-200 last:border-b-0">
        <td className={`py-2 px-2 font-medium text-gray-900 ${indent ? 'pl-6 text-gray-700' : ''}`}>{label}</td>
        {periodKeys.map((p: string) => (
          <td key={`${key}-${p}`} className="py-2 px-2 text-right text-gray-700 font-mono tabular-nums">
            {formatValue(Number(catsByPeriod[p]?.cur?.[key] || 0))}
          </td>
        ))}
        <td className="py-2 px-2 text-right text-gray-700 bg-blue-50 font-semibold font-mono tabular-nums">{formatValue(avg)}</td>
        {periodKeys.map((p: string) => {
          const cur = Number(catsByPeriod[p]?.cur?.[key] || 0)
          const ly = Number(catsByPeriod[p]?.ly?.[key] || 0)
          return (
            <td key={`yoy-${key}-${p}`} className="py-2 px-2 text-right text-gray-700 bg-yellow-50 font-mono tabular-nums">
              {fmtYoY(calcYoY(cur, ly))}
            </td>
          )
        })}
        <td className="py-2 px-2 text-right text-gray-700 bg-yellow-50 font-semibold font-mono tabular-nums">
          {fmtYoY(calcYoY(avg, lyAvg))}
        </td>
      </tr>
    )
  }

  if (loading && !data) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <Loader2 className="h-5 w-5 animate-spin text-primary" />
          <span className="text-gray-600">Loading product data…</span>
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
  if (!data || !periodKeys.length) return <div className="text-sm text-gray-600">No category data available.</div>

  return (
    <div className="bg-gray-50 rounded-lg overflow-hidden overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="bg-gray-200 border-b">
            <th className="text-left py-2 px-2 font-medium text-gray-900" rowSpan={2}>Category</th>
            <th className="text-center py-2 px-2 font-medium text-gray-900 bg-gray-200" colSpan={periodKeys.length + 1}>
              {granularity === 'month' ? "Latest Month (USD '000)" : "Latest Week (USD '000)"}
            </th>
            <th className="text-center py-2 px-2 font-medium text-gray-900 bg-yellow-100" colSpan={periodKeys.length + 1}>
              Y/Y GROWTH%
            </th>
          </tr>
          <tr className="bg-gray-200 border-b">
            {periodKeys.map((p: string) => (
              <th key={`h-${p}`} className="text-right py-1 px-2 font-medium text-gray-900" rowSpan={1}>
                {granularity === 'month' ? fmtMonth(p) : `W${p.split('-')[1]}`}
              </th>
            ))}
            <th className="text-right py-1 px-2 font-medium text-gray-900 bg-blue-100">Avg</th>
            {periodKeys.map((p: string) => (
              <th key={`y-${p}`} className="text-right py-1 px-2 font-medium text-gray-900 bg-yellow-50">
                {granularity === 'month' ? fmtMonth(p) : `W${p.split('-')[1]}`}
              </th>
            ))}
            <th className="text-right py-1 px-2 font-medium text-gray-900 bg-yellow-50">Avg</th>
          </tr>
        </thead>
        <tbody>
          <tr className="bg-white">
            <td className="py-2 px-2 font-semibold text-gray-900" colSpan={1 + (periodKeys.length + 1) * 2}>
              Full Price
            </td>
          </tr>
          {fullCats.map((k) => renderCategoryRow(k, true))}
          {/* Full Price Total */}
          {(() => {
            const key = '__FULL_TOTAL__'
            const avg = periodKeys.reduce((acc: number, p: string) => {
              const s = fullCats.reduce((a: number, k: string) => a + Number(catsByPeriod[p]?.cur?.[k] || 0), 0)
              return acc + s
            }, 0) / (periodKeys.length || 1)
            const lyAvg = periodKeys.reduce((acc: number, p: string) => {
              const s = fullCats.reduce((a: number, k: string) => a + Number(catsByPeriod[p]?.ly?.[k] || 0), 0)
              return acc + s
            }, 0) / (periodKeys.length || 1)
            return (
              <tr key={key} className="border-b border-gray-200 bg-gray-100">
                <td className="py-2 px-2 font-semibold text-gray-900">Full Price Total</td>
                {periodKeys.map((p: string) => {
                  const v = fullCats.reduce((a: number, k: string) => a + Number(catsByPeriod[p]?.cur?.[k] || 0), 0)
                  return (
                    <td key={`ft-${p}`} className="py-2 px-2 text-right text-gray-900 font-mono tabular-nums">
                      {formatValue(v)}
                    </td>
                  )
                })}
                <td className="py-2 px-2 text-right text-gray-900 bg-blue-50 font-semibold font-mono tabular-nums">{formatValue(avg)}</td>
                {periodKeys.map((p: string) => {
                  const cur = fullCats.reduce((a: number, k: string) => a + Number(catsByPeriod[p]?.cur?.[k] || 0), 0)
                  const ly = fullCats.reduce((a: number, k: string) => a + Number(catsByPeriod[p]?.ly?.[k] || 0), 0)
                  return (
                    <td key={`fty-${p}`} className="py-2 px-2 text-right text-gray-900 bg-yellow-50 font-mono tabular-nums">
                      {fmtYoY(calcYoY(cur, ly))}
                    </td>
                  )
                })}
                <td className="py-2 px-2 text-right text-gray-900 bg-yellow-50 font-semibold font-mono tabular-nums">
                  {fmtYoY(calcYoY(avg, lyAvg))}
                </td>
              </tr>
            )
          })()}

          <tr className="bg-white">
            <td className="py-2 px-2 font-semibold text-gray-900" colSpan={1 + (periodKeys.length + 1) * 2}>
              Sale
            </td>
          </tr>
          {saleCats.map((k) => renderCategoryRow(k, true))}
          {/* Sale Total */}
          {(() => {
            const key = '__SALE_TOTAL__'
            const avg = periodKeys.reduce((acc: number, p: string) => {
              const s = saleCats.reduce((a: number, k: string) => a + Number(catsByPeriod[p]?.cur?.[k] || 0), 0)
              return acc + s
            }, 0) / (periodKeys.length || 1)
            const lyAvg = periodKeys.reduce((acc: number, p: string) => {
              const s = saleCats.reduce((a: number, k: string) => a + Number(catsByPeriod[p]?.ly?.[k] || 0), 0)
              return acc + s
            }, 0) / (periodKeys.length || 1)
            return (
              <tr key={key} className="border-b border-gray-200 bg-gray-100">
                <td className="py-2 px-2 font-semibold text-gray-900">Sale Total</td>
                {periodKeys.map((p: string) => {
                  const v = saleCats.reduce((a: number, k: string) => a + Number(catsByPeriod[p]?.cur?.[k] || 0), 0)
                  return (
                    <td key={`st-${p}`} className="py-2 px-2 text-right text-gray-900 font-mono tabular-nums">
                      {formatValue(v)}
                    </td>
                  )
                })}
                <td className="py-2 px-2 text-right text-gray-900 bg-blue-50 font-semibold font-mono tabular-nums">{formatValue(avg)}</td>
                {periodKeys.map((p: string) => {
                  const cur = saleCats.reduce((a: number, k: string) => a + Number(catsByPeriod[p]?.cur?.[k] || 0), 0)
                  const ly = saleCats.reduce((a: number, k: string) => a + Number(catsByPeriod[p]?.ly?.[k] || 0), 0)
                  return (
                    <td key={`sty-${p}`} className="py-2 px-2 text-right text-gray-900 bg-yellow-50 font-mono tabular-nums">
                      {fmtYoY(calcYoY(cur, ly))}
                    </td>
                  )
                })}
                <td className="py-2 px-2 text-right text-gray-900 bg-yellow-50 font-semibold font-mono tabular-nums">
                  {fmtYoY(calcYoY(avg, lyAvg))}
                </td>
              </tr>
            )
          })()}

          {/* Grand Total */}
          {(() => {
            const key = '__GRAND_TOTAL__'
            const allCats = [...fullCats, ...saleCats]
            const avg = periodKeys.reduce((acc: number, p: string) => {
              const s = allCats.reduce((a: number, k: string) => a + Number(catsByPeriod[p]?.cur?.[k] || 0), 0)
              return acc + s
            }, 0) / (periodKeys.length || 1)
            const lyAvg = periodKeys.reduce((acc: number, p: string) => {
              const s = allCats.reduce((a: number, k: string) => a + Number(catsByPeriod[p]?.ly?.[k] || 0), 0)
              return acc + s
            }, 0) / (periodKeys.length || 1)
            return (
              <tr key={key} className="border-b border-gray-200 bg-gray-200">
                <td className="py-2 px-2 font-bold text-gray-900">Grand Total</td>
                {periodKeys.map((p: string) => {
                  const v = allCats.reduce((a: number, k: string) => a + Number(catsByPeriod[p]?.cur?.[k] || 0), 0)
                  return (
                    <td key={`gt-${p}`} className="py-2 px-2 text-right text-gray-900 font-mono tabular-nums">
                      {formatValue(v)}
                    </td>
                  )
                })}
                <td className="py-2 px-2 text-right text-gray-900 bg-blue-50 font-bold font-mono tabular-nums">{formatValue(avg)}</td>
                {periodKeys.map((p: string) => {
                  const cur = allCats.reduce((a: number, k: string) => a + Number(catsByPeriod[p]?.cur?.[k] || 0), 0)
                  const ly = allCats.reduce((a: number, k: string) => a + Number(catsByPeriod[p]?.ly?.[k] || 0), 0)
                  return (
                    <td key={`gty-${p}`} className="py-2 px-2 text-right text-gray-900 bg-yellow-50 font-mono tabular-nums">
                      {fmtYoY(calcYoY(cur, ly))}
                    </td>
                  )
                })}
                <td className="py-2 px-2 text-right text-gray-900 bg-yellow-50 font-bold font-mono tabular-nums">
                  {fmtYoY(calcYoY(avg, lyAvg))}
                </td>
              </tr>
            )
          })()}
        </tbody>
      </table>
    </div>
  )
}


