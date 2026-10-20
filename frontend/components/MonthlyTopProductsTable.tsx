'use client'

import type { MonthlyProductRow, MonthlyTotals } from '@/lib/api'
import { formatSekThousands, formatSharePct, formatYoyPct, yoyTone } from '@/lib/monthly-performance-format'

export default function MonthlyTopProductsTable({
  products,
  topTotal,
  grandTotal,
  genderFilter,
}: {
  products: MonthlyProductRow[]
  topTotal: MonthlyTotals
  grandTotal: MonthlyTotals
  genderFilter: 'men' | 'women'
}) {
  const isMen = genderFilter === 'men'
  const titleBand = isMen
    ? 'bg-slate-100 text-slate-900 border-b border-slate-200'
    : 'bg-rose-50 text-rose-950 border-b border-rose-200'
  const cell = 'py-1 px-1.5 text-[11px] leading-tight sm:text-xs'
  const num = `${cell} tabular-nums text-right whitespace-nowrap`

  return (
    <div className={`rounded-md border overflow-x-auto ${isMen ? 'border-slate-200' : 'border-rose-100'} bg-white`}>
      <table className="w-full border-collapse min-w-[860px]">
        <thead>
          <tr className={titleBand}>
            <th colSpan={10} className={`${cell} text-center font-semibold`}>
              <span className="uppercase">{isMen ? 'Men' : 'Women'}</span>
              <span className="ml-1.5 font-normal text-muted-foreground normal-case">
                monthly top products (SEK ’000) vs last year
              </span>
            </th>
          </tr>
          <tr className="bg-muted/40 border-b border-gray-200">
            <th className={`${cell} text-left`}>#</th>
            <th className={`${cell} text-left`}>Category</th>
            <th className={`${cell} text-left`}>Product</th>
            <th className={`${cell} text-left`}>Color</th>
            <th className={`${num}`}>Gross</th>
            <th className={`${num}`}>LY gross</th>
            <th className={`${num}`}>YoY</th>
            <th className={`${num}`}>Qty</th>
            <th className={`${num}`}>LY qty</th>
            <th className={`${num}`}>SoB%</th>
          </tr>
        </thead>
        <tbody>
          {products.map((product, i) => {
            const zebra = i % 2 === 0 ? 'bg-white' : 'bg-muted/20'
            return (
              <tr key={`${product.rank}-${product.product}-${product.color}`} className={`border-b border-gray-100/80 ${zebra}`}>
                <td className={`${cell} tabular-nums font-medium`}>{product.rank}</td>
                <td className={`${cell} truncate`} title={product.category}>{product.category}</td>
                <td className={`${cell} truncate`} title={product.product}>{product.product}</td>
                <td className={`${cell} truncate text-gray-600`} title={product.color}>{product.color}</td>
                <td className={num}>{formatSekThousands(product.gross_revenue)}</td>
                <td className={`${num} text-muted-foreground`}>{formatSekThousands(product.last_year_gross_revenue)}</td>
                <td className={`${num} ${yoyTone(product.yoy_pct)}`}>{formatYoyPct(product.yoy_pct)}</td>
                <td className={num}>{product.sales_qty.toLocaleString('sv-SE')}</td>
                <td className={`${num} text-muted-foreground`}>{product.last_year_sales_qty.toLocaleString('sv-SE')}</td>
                <td className={num}>{formatSharePct(product.sob)}</td>
              </tr>
            )
          })}
          <tr className="border-t border-gray-200 bg-muted/50 font-semibold">
            <td colSpan={4} className={cell}>Top {products.length} total</td>
            <td className={num}>{formatSekThousands(topTotal.gross_revenue)}</td>
            <td className={`${num} text-muted-foreground`}>{formatSekThousands(topTotal.last_year_gross_revenue)}</td>
            <td className={`${num} ${yoyTone(topTotal.yoy_pct)}`}>{formatYoyPct(topTotal.yoy_pct)}</td>
            <td className={num}>{topTotal.sales_qty.toLocaleString('sv-SE')}</td>
            <td className={`${num} text-muted-foreground`}>{topTotal.last_year_sales_qty.toLocaleString('sv-SE')}</td>
            <td className={num}>{formatSharePct(topTotal.sob)}</td>
          </tr>
          <tr className="bg-muted/70 font-bold border-t border-gray-300">
            <td colSpan={4} className={cell}>All products</td>
            <td className={num}>{formatSekThousands(grandTotal.gross_revenue)}</td>
            <td className={`${num} text-muted-foreground`}>{formatSekThousands(grandTotal.last_year_gross_revenue)}</td>
            <td className={`${num} ${yoyTone(grandTotal.yoy_pct)}`}>{formatYoyPct(grandTotal.yoy_pct)}</td>
            <td className={num}>{grandTotal.sales_qty.toLocaleString('sv-SE')}</td>
            <td className={`${num} text-muted-foreground`}>{grandTotal.last_year_sales_qty.toLocaleString('sv-SE')}</td>
            <td className={num}>{formatSharePct(grandTotal.sob)}</td>
          </tr>
        </tbody>
      </table>
    </div>
  )
}
