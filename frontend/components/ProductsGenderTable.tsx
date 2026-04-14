'use client'

import { getTopProductsByGender } from '@/lib/api'
import { useEffect, useState } from 'react'
import { Skeleton } from '@/components/ui/skeleton'
import { Loader2 } from 'lucide-react'

interface ProductsGenderTableProps {
  baseWeek: string
  genderFilter: 'men' | 'women'
}

export default function ProductsGenderTable({ baseWeek, genderFilter }: ProductsGenderTableProps) {
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

  const formatSoB = (value: number): string => {
    return `${Math.round(value)}%`
  }

  if (loading || !topProductsData) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <Loader2 className="h-5 w-5 animate-spin text-primary" />
          <span className="text-gray-600">Loading top products data...</span>
        </div>
        <div className="space-y-2">
          <Skeleton className="h-12 w-full" />
          {[...Array(25)].map((_, i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </div>
      </div>
    )
  }

  const { top_products, period_info } = topProductsData
  const weekData = top_products[0] // Get the first (and only) week

  if (!weekData) {
    return <div className="text-gray-600">No data available</div>
  }

  const { products, top_total, grand_total } = weekData

  const isMen = genderFilter === 'men'
  const titleBand = isMen
    ? 'bg-slate-100/90 text-slate-900 border-b border-slate-200/80'
    : 'bg-rose-50/90 text-rose-950 border-b border-rose-200/70'

  const cell = 'py-1 px-1.5 align-top text-[11px] leading-snug sm:text-xs sm:leading-tight'
  const thCell = `${cell} font-semibold text-gray-800`
  const numCell = `${cell} tabular-nums text-right`

  return (
    <div
      className={`rounded-lg border overflow-hidden overflow-x-auto shadow-sm ${
        isMen ? 'border-slate-200/90 bg-white' : 'border-rose-100 bg-white'
      }`}
    >
      <table className="w-full min-w-[640px] border-collapse">
        <thead>
          <tr className={titleBand}>
            <th colSpan={8} className="py-1.5 px-2 text-center text-xs font-semibold tracking-tight">
              <span className="uppercase tracking-wide">{isMen ? 'Men' : 'Women'}</span>
              <span className="ml-2 font-normal text-muted-foreground normal-case">(SEK &apos;000)</span>
            </th>
          </tr>
          <tr className="bg-muted/50 border-b border-gray-200/90">
            <th className={`${thCell} text-left`}>Rank</th>
            <th className={`${thCell} text-left`}>Gender</th>
            <th className={`${thCell} text-left`}>Category</th>
            <th className={`${thCell} text-left min-w-[7rem] max-w-[11rem]`}>Product</th>
            <th className={`${thCell} text-left`}>Color</th>
            <th className={`${thCell} text-right`}>Gross Revenue</th>
            <th className={`${thCell} text-right`}>Sales Qty</th>
            <th className={`${thCell} text-right`}>SoB%</th>
          </tr>
        </thead>
        <tbody>
          {products.map((product: any, i: number) => {
            const sob = (product.gross_revenue / grand_total.gross_revenue) * 100
            const zebra = i % 2 === 0 ? 'bg-white' : 'bg-muted/25'

            return (
              <tr key={`${product.rank}-${i}`} className={`border-b border-gray-100 ${zebra}`}>
                <td className={`${cell} font-medium text-gray-900 tabular-nums`}>{product.rank}</td>
                <td className={`${cell} text-gray-700`}>{product.gender}</td>
                <td className={`${cell} text-gray-700`}>{product.category}</td>
                <td className={`${cell} text-gray-800 max-w-[11rem] leading-tight`}>{product.product}</td>
                <td className={`${cell} text-gray-600`}>{product.color}</td>
                <td className={`${numCell} text-gray-800`}>{formatValue(product.gross_revenue)}</td>
                <td className={`${numCell} text-gray-800`}>{product.sales_qty}</td>
                <td className={`${numCell} text-gray-800`}>{formatSoB(sob)}</td>
              </tr>
            )
          })}

          <tr className="border-t border-gray-200 bg-muted/60 font-semibold">
            <td colSpan={5} className={`${cell} text-left text-gray-900`}>
              Top 30 Total
            </td>
            <td className={`${numCell} text-gray-900`}>{formatValue(top_total.gross_revenue)}</td>
            <td className={`${numCell} text-gray-900`}>{top_total.sales_qty}</td>
            <td className={`${numCell} text-gray-900`}>{formatSoB(top_total.sob)}</td>
          </tr>

          <tr className="bg-muted font-bold border-t border-gray-300/80">
            <td colSpan={5} className={`${cell} text-left text-gray-900`}>
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

