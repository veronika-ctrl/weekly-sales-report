'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { useDataCache } from '@/contexts/DataCacheContext'
import {
  getPeriods,
  getQuarterlyVeronikaBoard,
  hasBackend,
  type QuarterlyVeronikaBoardResponse,
} from '@/lib/api'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Loader2 } from 'lucide-react'

function fmtValue(v: number | null | undefined, format: string) {
  if (v == null || Number.isNaN(Number(v))) return '—'
  const n = Number(v)
  if (format === 'integer') return n.toLocaleString(undefined, { maximumFractionDigits: 0 })
  if (format === 'pct') return `${n.toFixed(2)}%`
  if (format === 'ratio') return n.toFixed(2)
  if (Math.abs(n) >= 1000) return n.toLocaleString(undefined, { maximumFractionDigits: 0 })
  return n.toFixed(2)
}

function fmtDelta(row: { yoy_pct: number | null; yoy_pp: number | null; format: string }) {
  const d = row.format === 'pct' ? row.yoy_pp : row.yoy_pct
  if (d == null || Number.isNaN(Number(d))) return '—'
  const n = Number(d)
  const sign = n > 0 ? '+' : ''
  if (row.format === 'pct') return `${sign}${n.toFixed(2)} pp`
  return `${sign}${n.toFixed(1)}%`
}

/** Metrics where a downward YoY change is favorable (e.g. COS %). */
const LOWER_IS_BETTER = new Set(['cos_pct'])

function deltaClass(row: { key: string; yoy_pct: number | null; yoy_pp: number | null; format: string }) {
  const d = row.format === 'pct' ? row.yoy_pp : row.yoy_pct
  if (d == null) return 'text-gray-500'
  const favorable = LOWER_IS_BETTER.has(row.key) ? -d : d
  if (favorable > 0) return 'text-emerald-700'
  if (favorable < 0) return 'text-red-700'
  return 'text-gray-600'
}

function quarterFromDate(d: Date): string {
  const q = Math.floor(d.getMonth() / 3) + 1
  return `${d.getFullYear()}-Q${q}`
}

const DEFINITION_ORDER: { key: keyof QuarterlyVeronikaBoardResponse['definitions']; label: string }[] = [
  { key: 'scope', label: 'Scope' },
  { key: 'new_customers', label: 'New customers' },
  { key: 'new_customer_net_sales', label: 'New customer net sales' },
  { key: 'returning_customers', label: 'Returning customers' },
  { key: 'returning_customer_net_sales', label: 'Returning customer net sales' },
  { key: 'orders', label: 'Orders' },
  { key: 'aov', label: 'AOV' },
  { key: 'full_price_share_pct', label: 'Full-price share' },
  { key: 'amer', label: 'aMER' },
  { key: 'cos_pct', label: 'COS %' },
  { key: 'ltv_cac_ratio', label: 'CLV / CAC' },
  { key: 'yoy', label: 'YoY comparison' },
]

export default function QuarterlyVeronikaPage() {
  const { baseWeek } = useDataCache()
  const [yearQuarter, setYearQuarter] = useState('')
  const [data, setData] = useState<QuarterlyVeronikaBoardResponse | null>(null)
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
            setYearQuarter(quarterFromDate(d))
            return
          }
        }
        setYearQuarter(quarterFromDate(new Date()))
      })
      .catch(() => setYearQuarter(quarterFromDate(new Date())))
  }, [baseWeek])

  const load = useCallback(async () => {
    if (!baseWeek || !yearQuarter) return
    setLoading(true)
    setErr(null)
    try {
      const res = await getQuarterlyVeronikaBoard(yearQuarter, baseWeek)
      setData(res)
    } catch (e: unknown) {
      setData(null)
      setErr(e instanceof Error ? e.message : 'Failed to load quarterly board KPIs')
    } finally {
      setLoading(false)
    }
  }, [baseWeek, yearQuarter])

  useEffect(() => {
    if (yearQuarter && baseWeek && hasBackend) void load()
  }, [yearQuarter, baseWeek, load])

  const yearOptions = Array.from({ length: 5 }, (_, i) => new Date().getFullYear() - i)
  const [selYear, selQ] = yearQuarter ? yearQuarter.split('-') : ['', '']

  if (!hasBackend) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Quarterly Board KPIs</CardTitle>
          <CardDescription>Configure the API URL to load calendar-quarter metrics.</CardDescription>
        </CardHeader>
      </Card>
    )
  }

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex flex-wrap items-end gap-4">
        <div className="space-y-2">
          <Label>Calendar quarter</Label>
          <div className="flex gap-2">
            <select
              className="border rounded-md px-3 py-2 text-sm bg-white"
              value={selYear}
              onChange={(e) => setYearQuarter(`${e.target.value}-${selQ || 'Q1'}`)}
            >
              {yearOptions.map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </select>
            <select
              className="border rounded-md px-3 py-2 text-sm bg-white"
              value={selQ}
              onChange={(e) => setYearQuarter(`${selYear || yearOptions[0]}-${e.target.value}`)}
            >
              {['Q1', 'Q2', 'Q3', 'Q4'].map((q) => (
                <option key={q} value={q}>
                  {q}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div className="text-sm text-gray-600 pb-2">
          Raw folder: <span className="font-mono">{baseWeek || '—'}</span>
        </div>
        <Button type="button" variant="secondary" onClick={() => void load()} disabled={loading || !yearQuarter}>
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Refresh'}
        </Button>
        <Button asChild variant="outline">
          <Link href="/monthly-veronika">Monthly view</Link>
        </Button>
      </div>

      {err && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{err}</div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Quarterly board scorecard</CardTitle>
          <CardDescription>
            {data
              ? `${data.date_range.start} → ${data.date_range.end}${
                  data.date_range.is_partial ? ' (partial quarter, through selected week)' : ''
                } · vs same quarter last year (${data.last_year_date_range.start} → ${data.last_year_date_range.end})`
              : 'CFO / board view: customer counts and net sales growth, not returning share.'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading && !data ? (
            <div className="flex items-center gap-2 text-gray-600">
              <Loader2 className="h-5 w-5 animate-spin" />
              Loading quarterly metrics… (large Qlik export can take a few minutes)
            </div>
          ) : (
            <>
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-2 pr-4 font-medium text-gray-700">Metric</th>
                    <th className="text-right py-2 px-2 font-medium text-gray-700">This quarter</th>
                    <th className="text-right py-2 px-2 font-medium text-gray-700">Same Q last year</th>
                    <th className="text-right py-2 pl-2 font-medium text-gray-700">YoY</th>
                  </tr>
                </thead>
                <tbody>
                  {data?.metrics.map((row) => (
                    <tr key={row.key} className="border-b border-gray-100">
                      <td className="py-2 pr-4 text-gray-800">{row.label}</td>
                      <td className="py-2 px-2 text-right font-mono tabular-nums">
                        {fmtValue(row.value, row.format)}
                      </td>
                      <td className="py-2 px-2 text-right font-mono tabular-nums text-gray-600">
                        {fmtValue(row.last_year, row.format)}
                      </td>
                      <td className={`py-2 pl-2 text-right font-mono tabular-nums ${deltaClass(row)}`}>
                        {fmtDelta(row)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {data?.full_price?.share_pct != null && (
                <div className="mt-8 rounded-md border border-blue-100 bg-blue-50/50 p-4">
                  <h3 className="text-sm font-semibold text-gray-900 mb-3">Full-price picture (online e-com)</h3>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
                    <div>
                      <div className="text-gray-600 text-xs">Full-price share</div>
                      <div className="font-mono font-medium">{data.full_price.share_pct?.toFixed(2)}%</div>
                      {data.full_price.share_pct_last_year != null && (
                        <div className="text-xs text-gray-500">
                          LY {data.full_price.share_pct_last_year.toFixed(2)}%
                          {data.full_price.share_pp_delta != null && (
                            <span className={data.full_price.share_pp_delta >= 0 ? ' text-emerald-700' : ' text-red-700'}>
                              {' '}
                              ({data.full_price.share_pp_delta >= 0 ? '+' : ''}
                              {data.full_price.share_pp_delta.toFixed(2)} pp)
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                    <div>
                      <div className="text-gray-600 text-xs">Full-price net (SEK)</div>
                      <div className="font-mono font-medium">
                        {data.full_price.full_price_net?.toLocaleString(undefined, { maximumFractionDigits: 0 }) ?? '—'}
                      </div>
                    </div>
                    <div>
                      <div className="text-gray-600 text-xs">Discounted net (SEK)</div>
                      <div className="font-mono font-medium">
                        {data.full_price.discounted_net?.toLocaleString(undefined, { maximumFractionDigits: 0 }) ?? '—'}
                      </div>
                    </div>
                    <div>
                      <div className="text-gray-600 text-xs">Total online net (SEK)</div>
                      <div className="font-mono font-medium">
                        {data.full_price.total_net?.toLocaleString(undefined, { maximumFractionDigits: 0 }) ?? '—'}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {data?.supporting?.ltv_proxy_ttm != null && (
                <p className="mt-4 text-xs text-gray-600">
                  LTV proxy (TTM): {data.supporting.ltv_proxy_ttm?.toLocaleString()} SEK/customer · nCAC:{' '}
                  {data.supporting.new_customer_acquisition_cost?.toLocaleString()} SEK
                </p>
              )}
            </>
          )}

          {data?.definitions && !loading && (
            <details className="mt-6 rounded-md border border-gray-200 bg-gray-50/80 p-4 text-sm">
              <summary className="cursor-pointer font-medium text-gray-900">How these metrics are calculated</summary>
              <ul className="mt-3 text-xs text-gray-700 list-disc pl-5 space-y-2">
                {DEFINITION_ORDER.map(({ key, label }) => {
                  const text = data.definitions[key]
                  if (!text) return null
                  return (
                    <li key={key}>
                      <span className="font-medium text-gray-800">{label}:</span> {text}
                    </li>
                  )
                })}
              </ul>
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
