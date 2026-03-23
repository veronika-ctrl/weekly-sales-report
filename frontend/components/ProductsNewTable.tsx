'use client'

import { getTopProducts } from '@/lib/api'
import { useEffect, useState } from 'react'
import { Skeleton } from '@/components/ui/skeleton'
import { Loader2 } from 'lucide-react'

interface ProductsNewTableProps {
  baseWeek: string
  customerType: 'new' | 'returning'
}

export default function ProductsNewTable({ baseWeek, customerType }: ProductsNewTableProps) {
  const [topProductsData, setTopProductsData] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const loadData = async () => {
      setLoading(true)
      try {
        const data = await getTopProducts(baseWeek, 1, 30, customerType)
        setTopProductsData(data)
      } catch (err) {
        console.error('Failed to load top products:', err)
      } finally {
        setLoading(false)
      }
    }
    loadData()
  }, [baseWeek, customerType])

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

  return (
    <div className="bg-gray-50 rounded-lg overflow-hidden overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="bg-gray-200 border-b">
            <th colSpan={8} className="text-center py-2 px-2 font-medium text-gray-900">
              {customerType === 'new' ? 'New Customers' : 'Returning Customers'}
            </th>
          </tr>
          <tr className="bg-gray-200 border-b">
            <th colSpan={8} className="text-center py-1 px-2 text-xs text-gray-600">
              (SEK '000)
            </th>
          </tr>
          <tr className="bg-gray-200 border-b">
            <th className="text-left py-2 px-2 font-medium text-gray-900">Rank</th>
            <th className="text-left py-2 px-2 font-medium text-gray-900">Gender</th>
            <th className="text-left py-2 px-2 font-medium text-gray-900">Category</th>
            <th className="text-left py-2 px-2 font-medium text-gray-900">Product</th>
            <th className="text-left py-2 px-2 font-medium text-gray-900">Color</th>
            <th className="text-right py-2 px-2 font-medium text-gray-900">Gross Revenue</th>
            <th className="text-right py-2 px-2 font-medium text-gray-900">Sales Qty</th>
            <th className="text-right py-2 px-2 font-medium text-gray-900">SoB%</th>
          </tr>
        </thead>
        <tbody>
          {/* Top 30 Products */}
          {products.map((product: any) => {
            const sob = (product.gross_revenue / grand_total.gross_revenue) * 100
            
            return (
              <tr key={product.rank} className="border-b border-gray-200">
                <td className="py-2 px-2 font-medium text-gray-900">{product.rank}</td>
                <td className="py-2 px-2 text-gray-700">{product.gender}</td>
                <td className="py-2 px-2 text-gray-700">{product.category}</td>
                <td className="py-2 px-2 text-gray-700">{product.product}</td>
                <td className="py-2 px-2 text-gray-700">{product.color}</td>
                <td className="py-2 px-2 text-right text-gray-700">{formatValue(product.gross_revenue)}</td>
                <td className="py-2 px-2 text-right text-gray-700">{product.sales_qty}</td>
                <td className="py-2 px-2 text-right text-gray-700">{formatSoB(sob)}</td>
              </tr>
            )
          })}
          
          {/* Top 30 Total */}
          <tr className="bg-gray-200 border-b font-semibold">
            <td colSpan={5} className="py-2 px-2 font-bold text-gray-900">Top 30 Total</td>
            <td className="py-2 px-2 text-right text-gray-700">{formatValue(top_total.gross_revenue)}</td>
            <td className="py-2 px-2 text-right text-gray-700">{top_total.sales_qty}</td>
            <td className="py-2 px-2 text-right text-gray-700">{formatSoB(top_total.sob)}</td>
          </tr>
          
          {/* Grand Total */}
          <tr className="bg-gray-300 border-b font-bold">
            <td colSpan={5} className="py-2 px-2 font-bold text-gray-900">Total</td>
            <td className="py-2 px-2 text-right text-gray-900">{formatValue(grand_total.gross_revenue)}</td>
            <td className="py-2 px-2 text-right text-gray-900">{grand_total.sales_qty}</td>
            <td className="py-2 px-2 text-right text-gray-900">{formatSoB(grand_total.sob)}</td>
          </tr>
        </tbody>
      </table>
    </div>
  )
}

