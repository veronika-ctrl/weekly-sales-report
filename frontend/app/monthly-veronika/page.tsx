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

const DEFINITION_ORDER: { key: keyof MonthlyVeronikaKpisResponse['definitions']; label: string }[] = [
  { key: 'repeat_purchase_rate_pct', label: 'Repeat purchase rate' },
  { key: 'ltv_proxy_ttm', label: 'LTV proxy (TTM)' },
  { key: 'ltv_cac_ratio', label: 'LTV / CAC ratio' },
  { key: 'conversion_rate_pct', label: 'Conversion rate' },
  { key: 'full_price_share_pct', label: 'Full-price share of ecom' },
  { key: 'new_customer_acquisition_cost', label: 'New customer acquisition cost (nCAC)' },
  { key: 'returning_customer_revenue', label: 'Returning customer revenue' },
  { key: 'cos_pct', label: 'COS %' },
  { key: 'amer', label: 'aMER' },
  { key: 'corridor', label: 'Budget corridor' },
]

const ROWS: { key: keyof MonthlyVeronikaKpisResponse['kpis']; title: string }[] = [
  { key: 'repeat_purchase_rate_pct', title: 'Repeat purchase rate' },
  { key: 'ltv_cac_ratio', title: 'LTV / CAC (ratio)' },
  { key: 'ltv_proxy_ttm', title: 'LTV proxy (TTM mean net / customer, SEK)' },
  { key: 'conversion_rate_pct', title: 'Conversion rate' },
  { key: 'full_price_share_pct', title: 'Full-price share of ecom' },
  { key: 'new_customer_acquisition_cost', title: 'New customer acquisition cost (SEK)' },
  { key: 'returning_customer_revenue', title: 'Returning customer revenue (SEK)' },
  { key: 'cos_pct', title: 'COS % (marketing ÷ online gross)' },
  { key: 'amer', title: 'aMER (online new net ÷ marketing, all markets)' },
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
  const [slowHint, setSlowHint] = useState(false)
  const [loadSeconds, setLoadSeconds] = useState(0)

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

  useEffect(() => {
    if (!loading) {
      setSlowHint(false)
      setLoadSeconds(0)
      return
    }
    setLoadSeconds(0)
    const t = setTimeout(() => setSlowHint(true), 8000)
    const int = setInterval(() => setLoadSeconds((s) => s + 1), 1000)
    return () => {
      clearTimeout(t)
      clearInterval(int)
    }
  }, [loading])

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
          {!baseWeek && hasBackend && (
            <span className="ml-2 text-amber-800">— choose a data week in Settings so metrics can load.</span>
          )}
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
              ? `${data.date_range.start} → ${data.date_range.end} · online channel, calendar month (see “How these metrics are calculated” below).`
              : 'Select a month and ensure raw exports under the selected week include those dates.'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading && !data ? (
            <div className="space-y-2 text-gray-600">
              <div className="flex items-center gap-2">
                <Loader2 className="h-5 w-5 animate-spin" />
                <span>
                  Loading… {loadSeconds > 0 && <>({loadSeconds}s)</>}
                </span>
              </div>
              <p className="text-xs text-muted-foreground max-w-prose">
                This is finished and supported on localhost: the page calls <code className="text-xs">/api/monthly-veronika-kpis</code>.
                The first run can take a long time while Python reads the full Qlik/Excel in <code className="text-xs">data/raw/…</code> (often 1–5+ minutes for large
                files). If the API is not running, the request will fail with an error below.
              </p>
              {slowHint && (
                <p className="text-xs text-amber-800">
                  Still working — large exports keep the CPU busy. If nothing happens for 5 minutes you will get a timeout;
                  then confirm Uvicorn is running and watch the API terminal for errors.
                </p>
              )}
            </div>
          ) : (
            <>
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
                {data?.budget_plan && (
                  <>
                    <tr className="border-b border-gray-200 bg-amber-50/40">
                      <td className="py-2 pr-4 text-gray-800" colSpan={2}>
                        <span className="text-xs font-semibold uppercase tracking-wide text-gray-600">Budget (same month, from budget file)</span>
                      </td>
                    </tr>
                    <tr className="border-b border-gray-100">
                      <td className="py-2 pr-4 pl-2 text-gray-800">Plan — COS %</td>
                      <td className="py-2 text-right font-mono tabular-nums">
                        {fmt(data.budget_plan.cos_pct as number, true)}
                      </td>
                    </tr>
                    <tr className="border-b border-gray-100">
                      <td className="py-2 pr-4 pl-2 text-gray-800">Plan — aMER</td>
                      <td className="py-2 text-right font-mono tabular-nums">
                        {fmt(data.budget_plan.amer as number, false)}
                      </td>
                    </tr>
                  </>
                )}
              </tbody>
            </table>
            {data?.budget_error && (
              <p className="mt-3 text-xs text-gray-600">Budget: {data.budget_error}</p>
            )}
            </>
          )}
          {data?.definitions && !loading && (
            <details className="mt-6 rounded-md border border-gray-200 bg-gray-50/80 p-4 text-sm">
              <summary className="cursor-pointer font-medium text-gray-900">How these metrics are calculated</summary>
              <div className="mt-3 text-xs text-gray-700 space-y-3">
                <p>
                  <strong>Scope:</strong> Qlik rows with <code className="text-[11px]">Sales channel = online</code>, with{' '}
                  <code className="text-[11px]">Date</code> inside the selected calendar month. DEMA marketing spend and Shopify
                  sessions are summed over the same calendar month (from files in{' '}
                  <code className="text-[11px]">data/raw/{data.base_week}/</code>).
                </p>
                <p>
                  <strong>Segments:</strong> New vs returning uses the Qlik <code className="text-[11px]">New/Returning Customer</code>{' '}
                  column (normalized the same way as the weekly online KPIs). Customers are distinct by email when that column
                  exists.
                </p>
                <ul className="list-disc pl-5 space-y-2">
                  {DEFINITION_ORDER.map(({ key, label }) => {
                    const text = data.definitions[key as keyof typeof data.definitions]
                    if (!text) return null
                    return (
                      <li key={key}>
                        <span className="font-medium text-gray-800">{label}:</span> {text}
                      </li>
                    )
                  })}
                </ul>
              </div>
            </details>
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
