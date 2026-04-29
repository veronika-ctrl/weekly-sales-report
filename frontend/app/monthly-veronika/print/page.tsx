'use client'

import { useEffect, useState, Suspense } from 'react'
import { useSearchParams } from 'next/navigation'
import { getMonthlyVeronikaKpis, getMonthlyVeronikaPdfUrl, hasBackend, type MonthlyVeronikaKpisResponse } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Loader2, FileDown } from 'lucide-react'

const ROWS: { key: keyof MonthlyVeronikaKpisResponse['kpis']; title: string }[] = [
  { key: 'repeat_purchase_rate_pct', title: 'Repeat purchase rate' },
  { key: 'ltv_cac_ratio', title: 'LTV / CAC (ratio)' },
  { key: 'ltv_proxy_ttm', title: 'LTV proxy (TTM, SEK)' },
  { key: 'conversion_rate_pct', title: 'Conversion rate' },
  { key: 'full_price_share_pct', title: 'Full-price share of ecom' },
  { key: 'new_customer_acquisition_cost', title: 'New customer acquisition cost (SEK)' },
  { key: 'returning_customer_revenue', title: 'Returning customer revenue (SEK)' },
  { key: 'cos_pct', title: 'COS %' },
  { key: 'cos_amer_pct', title: 'COS % — Americas' },
  { key: 'emer_amer', title: 'eMER / aMER — Americas' },
]

function fmt(v: number | null | undefined, isPct: boolean) {
  if (v == null || Number.isNaN(Number(v))) return '—'
  const n = Number(v)
  if (isPct) return `${n.toFixed(2)}%`
  if (Math.abs(n) >= 1000) return n.toLocaleString(undefined, { maximumFractionDigits: 0 })
  return n.toFixed(2)
}

function PrintBody() {
  const sp = useSearchParams()
  const yearMonth = sp.get('year_month') || ''
  const baseWeek = sp.get('base_week') || ''
  const [data, setData] = useState<MonthlyVeronikaKpisResponse | null>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    if (!hasBackend || !yearMonth || !baseWeek) return
    getMonthlyVeronikaKpis(yearMonth, baseWeek)
      .then(setData)
      .catch((e) => setErr(e instanceof Error ? e.message : 'Error'))
  }, [yearMonth, baseWeek])

  return (
    <div className="max-w-3xl mx-auto p-8 print:p-4 bg-white text-gray-900">
      <div className="flex gap-2 mb-6 print:hidden">
        <Button type="button" onClick={() => window.print()}>
          Print
        </Button>
        <Button asChild variant="outline">
          <a href={yearMonth && baseWeek ? getMonthlyVeronikaPdfUrl(yearMonth, baseWeek) : '#'} download>
            <FileDown className="h-4 w-4 mr-2" />
            Download PDF
          </a>
        </Button>
      </div>
      <h1 className="text-2xl font-semibold text-center mb-1">Veronika — Monthly KPIs</h1>
      <p className="text-center text-sm text-gray-600 mb-6">
        {yearMonth} · week folder {baseWeek}
        {data && ` · ${data.date_range.start} → ${data.date_range.end}`}
      </p>
      {err && <p className="text-red-700 text-sm mb-4">{err}</p>}
      {!data && !err && (
        <div className="flex justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
        </div>
      )}
      {data && (
        <table className="w-full text-sm border border-gray-300">
          <tbody>
            {ROWS.map(({ key, title }, i) => {
              const v = data.kpis[key]
              const isPct =
                String(key).includes('pct') || String(key).includes('rate') || key === 'conversion_rate_pct'
              return (
                <tr key={String(key)} className={i % 2 === 0 ? 'bg-gray-50' : 'bg-white'}>
                  <td className="border-t border-gray-200 px-3 py-2">{title}</td>
                  <td className="border-t border-gray-200 px-3 py-2 text-right font-mono">{fmt(v as number, isPct)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
      {data?.notes && data.notes.length > 0 && (
        <ul className="mt-4 text-xs text-gray-600 list-disc pl-5">
          {data.notes.map((n, i) => (
            <li key={i}>{n}</li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default function MonthlyVeronikaPrintPage() {
  return (
    <Suspense
      fallback={
        <div className="p-8 flex justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
        </div>
      }
    >
      <PrintBody />
    </Suspense>
  )
}
