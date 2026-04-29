'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { useDataCache } from '@/contexts/DataCacheContext'
import {
  getMonthlyVeronikaKpis,
  getMonthlyVeronikaPdfUrl,
  getPeriods,
  hasBackend,
  type MonthlyVeronikaKpisResponse,
} from '@/lib/api'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Loader2, FileDown, Printer } from 'lucide-react'

const ROWS: { key: keyof MonthlyVeronikaKpisResponse['kpis']; title: string }[] = [
  { key: 'repeat_purchase_rate_pct', title: 'Repeat purchase rate' },
  { key: 'ltv_cac_ratio', title: 'LTV / CAC (ratio)' },
  { key: 'ltv_proxy_ttm', title: 'LTV proxy (TTM mean net / customer, SEK)' },
  { key: 'conversion_rate_pct', title: 'Conversion rate' },
  { key: 'full_price_share_pct', title: 'Full-price share of ecom' },
  { key: 'new_customer_acquisition_cost', title: 'New customer acquisition cost (SEK)' },
  { key: 'returning_customer_revenue', title: 'Returning customer revenue (SEK)' },
  { key: 'cos_pct', title: 'COS % (marketing ÷ online gross)' },
  { key: 'cos_amer_pct', title: 'COS % — Americas' },
  { key: 'emer_amer', title: 'eMER / aMER — Americas (new net ÷ marketing)' },
]

function fmt(v: number | null | undefined, isPct: boolean) {
  if (v == null || Number.isNaN(Number(v))) return '—'
  const n = Number(v)
  if (isPct) return `${n.toFixed(2)}%`
  if (Math.abs(n) >= 1000) return n.toLocaleString(undefined, { maximumFractionDigits: 0 })
  return n.toFixed(2)
}

export default function MonthlyVeronikaPage() {
  const { baseWeek } = useDataCache()
  const [yearMonth, setYearMonth] = useState('')
  const [data, setData] = useState<MonthlyVeronikaKpisResponse | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!baseWeek || !hasBackend) return
    getPeriods(baseWeek)
      .then((p) => {
        const end = p.date_ranges?.actual?.end
        if (end) {
          const d = new Date(end)
          if (!Number.isNaN(d.getTime())) {
            setYearMonth(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`)
            return
          }
        }
        const n = new Date()
        setYearMonth(`${n.getFullYear()}-${String(n.getMonth() + 1).padStart(2, '0')}`)
      })
      .catch(() => {
        const n = new Date()
        setYearMonth(`${n.getFullYear()}-${String(n.getMonth() + 1).padStart(2, '0')}`)
      })
  }, [baseWeek])

  const load = useCallback(async () => {
    if (!baseWeek || !yearMonth) return
    setLoading(true)
    setErr(null)
    try {
      const res = await getMonthlyVeronikaKpis(yearMonth, baseWeek)
      setData(res)
    } catch (e: unknown) {
      setData(null)
      setErr(e instanceof Error ? e.message : 'Failed to load monthly KPIs')
    } finally {
      setLoading(false)
    }
  }, [baseWeek, yearMonth])

  useEffect(() => {
    if (yearMonth && baseWeek && hasBackend) void load()
  }, [yearMonth, baseWeek, load])

  if (!hasBackend) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Monthly Veronika KPIs</CardTitle>
          <CardDescription>Configure the API URL to load calendar-month metrics.</CardDescription>
        </CardHeader>
      </Card>
    )
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex flex-wrap items-end gap-4">
        <div className="space-y-2">
          <Label htmlFor="ym">Calendar month</Label>
          <input
            id="ym"
            type="month"
            className="border rounded-md px-3 py-2 text-sm bg-white"
            value={yearMonth}
            onChange={(e) => setYearMonth(e.target.value)}
          />
        </div>
        <div className="text-sm text-gray-600 pb-2">
          Raw folder: <span className="font-mono">{baseWeek || '—'}</span> (Settings → week)
        </div>
        <Button type="button" variant="secondary" onClick={() => void load()} disabled={loading || !yearMonth}>
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Refresh'}
        </Button>
        <Button asChild variant="outline" disabled={!yearMonth || !baseWeek}>
          <a href={yearMonth && baseWeek ? getMonthlyVeronikaPdfUrl(yearMonth, baseWeek) : '#'} download>
            <FileDown className="h-4 w-4 mr-2" />
            Download PDF
          </a>
        </Button>
        <Button asChild variant="outline" disabled={!yearMonth || !baseWeek}>
          <Link
            href={`/monthly-veronika/print?year_month=${encodeURIComponent(yearMonth)}&base_week=${encodeURIComponent(baseWeek)}`}
            target="_blank"
          >
            <Printer className="h-4 w-4 mr-2" />
            Print view
          </Link>
        </Button>
      </div>

      {err && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{err}</div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Veronika — monthly scorecard</CardTitle>
          <CardDescription>
            {data
              ? `${data.date_range.start} → ${data.date_range.end} · definitions in API JSON`
              : 'Select a month and ensure raw exports under the selected week include those dates.'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading && !data ? (
            <div className="flex items-center gap-2 text-gray-600">
              <Loader2 className="h-5 w-5 animate-spin" />
              Loading…
            </div>
          ) : (
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="border-b">
                  <th className="text-left py-2 pr-4 font-medium text-gray-700">KPI</th>
                  <th className="text-right py-2 font-medium text-gray-700">Value</th>
                </tr>
              </thead>
              <tbody>
                {ROWS.map(({ key, title }) => {
                  const v = data?.kpis?.[key]
                  const isPct =
                    String(key).includes('pct') || String(key).includes('rate') || key === 'conversion_rate_pct'
                  return (
                    <tr key={String(key)} className="border-b border-gray-100">
                      <td className="py-2 pr-4 text-gray-800">{title}</td>
                      <td className="py-2 text-right font-mono tabular-nums">{fmt(v as number, isPct)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
          {data?.notes && data.notes.length > 0 && (
            <ul className="mt-4 text-xs text-amber-800 list-disc pl-5 space-y-1">
              {data.notes.map((n, i) => (
                <li key={i}>{n}</li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
