'use client'

import { getTopProductsByGender } from '@/lib/api'
import { useEffect, useState } from 'react'
import { Skeleton } from '@/components/ui/skeleton'
import { Loader2 } from 'lucide-react'

interface ProductsGenderTableProps {
  baseWeek: string
  genderFilter: 'men' | 'women'
  /** Tighter layout for laptop screenshots (all 30 rows + totals). */
  compact?: boolean
}

export default function ProductsGenderTable({
  baseWeek,
  genderFilter,
  compact = false,
}: ProductsGenderTableProps) {
  const [topProductsData, setTopProductsData] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const loadData = async () => {
      setLoading(true)
      try {
        const data = await getTopProductsByGender(baseWeek, 1, 30, genderFilter)
        setTopProductsData(data)
      } catch (err) {
        console.error('Failed to load top products by gender:', err)
      } finally {
        setLoading(false)
      }
    }
    loadData()
  }, [baseWeek, genderFilter])

  const formatValue = (value: number): string => {
    if (value === 0) return '0'
    const thousandsValue = value / 1000
    const roundedThousands = Math.round(thousandsValue)
    return roundedThousands.toLocaleString('sv-SE')
  }

  const formatSoB = (value: number): string => `${Math.round(value)}%`

  if (loading || !topProductsData) {
    return (
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Loader2 className="h-4 w-4 animate-spin text-primary" />
          <span className="text-xs text-gray-600">Loading…</span>
        </div>
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  const { top_products } = topProductsData
  const weekData = top_products[0]

  if (!weekData) {
    return <div className="text-xs text-gray-600">No data available</div>
  }

  const { products, top_total, grand_total } = weekData
  const isMen = genderFilter === 'men'
  const titleBand = isMen
    ? 'bg-slate-100 text-slate-900 border-b border-slate-200'
    : 'bg-rose-50 text-rose-950 border-b border-rose-200'

  const cell = compact
    ? 'py-0 px-1 align-middle text-[10px] leading-[13px]'
    : 'py-1 px-1.5 align-top text-[11px] leading-snug sm:text-xs sm:leading-tight'
  const thCell = `${cell} font-semibold text-gray-800 whitespace-nowrap`
  const numCell = `${cell} tabular-nums text-right whitespace-nowrap`
  const labelCols = compact ? 4 : 5

  return (
    <div
      className={`rounded-md border overflow-hidden ${
        isMen ? 'border-slate-200 bg-white' : 'border-rose-100 bg-white'
      } ${compact ? 'shadow-none' : 'shadow-sm'}`}
    >
      <table className="w-full border-collapse table-fixed">
        <colgroup>
          <col className={compact ? 'w-[5%]' : 'w-[6%]'} />
          <col className={compact ? 'w-[14%]' : 'w-[12%]'} />
          {!compact && <col className="w-[8%]" />}
          <col />
          <col className={compact ? 'w-[12%]' : 'w-[11%]'} />
          <col className={compact ? 'w-[10%]' : 'w-[11%]'} />
          <col className={compact ? 'w-[8%]' : 'w-[9%]'} />
          <col className={compact ? 'w-[7%]' : 'w-[8%]'} />
        </colgroup>
        <thead>
          <tr className={titleBand}>
            <th colSpan={compact ? 7 : 8} className={`${cell} text-center font-semibold`}>
              <span className="uppercase">{isMen ? 'Men' : 'Women'}</span>
              <span className="ml-1.5 font-normal text-muted-foreground normal-case">(SEK &apos;000)</span>
            </th>
          </tr>
          <tr className="bg-muted/40 border-b border-gray-200">
            <th className={`${thCell} text-left`}>#</th>
            <th className={`${thCell} text-left`}>Category</th>
            {!compact && <th className={`${thCell} text-left`}>Gender</th>}
            <th className={`${thCell} text-left`}>Product</th>
            <th className={`${thCell} text-left`}>Color</th>
            <th className={`${thCell} text-right`}>{compact ? 'Gross' : 'Gross Revenue'}</th>
            <th className={`${thCell} text-right`}>{compact ? 'Qty' : 'Sales Qty'}</th>
            <th className={`${thCell} text-right`}>SoB%</th>
          </tr>
        </thead>
        <tbody>
          {products.map((product: any, i: number) => {
            const sob = (product.gross_revenue / grand_total.gross_revenue) * 100
            const zebra = i % 2 === 0 ? 'bg-white' : 'bg-muted/20'

            return (
              <tr key={`${product.rank}-${i}`} className={`border-b border-gray-100/80 ${zebra}`}>
                <td className={`${cell} font-medium text-gray-900 tabular-nums`}>{product.rank}</td>
                <td className={`${cell} text-gray-700 truncate`} title={product.category}>
                  {product.category}
                </td>
                {!compact && <td className={`${cell} text-gray-700`}>{product.gender}</td>}
                <td className={`${cell} text-gray-800 truncate`} title={product.product}>
                  {product.product}
                </td>
                <td className={`${cell} text-gray-600 truncate`} title={product.color}>
                  {product.color}
                </td>
                <td className={`${numCell} text-gray-800`}>{formatValue(product.gross_revenue)}</td>
                <td className={`${numCell} text-gray-800`}>{product.sales_qty}</td>
                <td className={`${numCell} text-gray-800`}>{formatSoB(sob)}</td>
              </tr>
            )
          })}

          <tr className="border-t border-gray-200 bg-muted/50 font-semibold">
            <td colSpan={labelCols} className={`${cell} text-left text-gray-900`}>
              Top 30 Total
            </td>
            <td className={`${numCell} text-gray-900`}>{formatValue(top_total.gross_revenue)}</td>
            <td className={`${numCell} text-gray-900`}>{top_total.sales_qty}</td>
            <td className={`${numCell} text-gray-900`}>{formatSoB(top_total.sob)}</td>
          </tr>

          <tr className="bg-muted/70 font-bold border-t border-gray-300">
            <td colSpan={labelCols} className={`${cell} text-left text-gray-900`}>
              Total
            </td>
            <td className={`${numCell} text-gray-950`}>{formatValue(grand_total.gross_revenue)}</td>
            <td className={`${numCell} text-gray-950`}>{grand_total.sales_qty}</td>
            <td className={`${numCell} text-gray-950`}>{formatSoB(grand_total.sob)}</td>
          </tr>
        </tbody>
      </table>
    </div>
  )
}
