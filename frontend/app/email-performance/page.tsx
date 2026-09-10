'use client'

import { useCallback, useEffect, useState } from 'react'
import Link from 'next/link'
import { useDataCache } from '@/contexts/DataCacheContext'
import {
  getKlaviyoEmail,
  hasBackend,
  type KlaviyoEmailResponse,
  type KlaviyoEmailRow,
} from '@/lib/api'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Loader2 } from 'lucide-react'

function fmtCount(v: number | null | undefined): string {
  if (v == null || Number.isNaN(Number(v))) return '—'
  return Number(v).toLocaleString('sv-SE')
}

function fmtPct(v: number | null | undefined): string {
  if (v == null || Number.isNaN(Number(v)) || !Number.isFinite(Number(v))) return '—'
  return `${(Number(v) * 100).toFixed(2)}%`
}

function fmtUsd(v: number | null | undefined): string {
  if (v == null || Number.isNaN(Number(v))) return '—'
  return Number(v).toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })
}

function fmtSek(v: number | null | undefined): string {
  if (v == null || Number.isNaN(Number(v))) return '—'
  return `${Number(v).toLocaleString('sv-SE', { maximumFractionDigits: 0 })} SEK`
}

function KpiCard({ title, value, hint }: { title: string; value: string; hint?: string }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-gray-700">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-semibold text-gray-900">{value}</div>
        {hint ? <p className="text-xs text-muted-foreground mt-1">{hint}</p> : null}
      </CardContent>
    </Card>
  )
}

function MetricTable({
  rows,
  showCampaignCount,
}: {
  rows: KlaviyoEmailRow[]
  showCampaignCount?: boolean
}) {
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left text-muted-foreground border-b">
          <th className="py-2 pr-3">{showCampaignCount ? 'Campaigns' : 'Flow'}</th>
          <th className="py-2 pr-3 text-right">Recipients</th>
          <th className="py-2 pr-3 text-right">Unique converters</th>
          <th className="py-2 pr-3 text-right">Conversion rate</th>
          <th className="py-2 pr-3 text-right">Revenue (SEK)</th>
          <th className="py-2 text-right">Revenue (USD)</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.name} className="border-b last:border-0">
            <td className="py-2 pr-3">
              {row.name}
              {row.campaign_count != null ? (
                <span className="block text-xs text-muted-foreground">
                  {fmtCount(row.campaign_count)} campaigns aggregated
                </span>
              ) : null}
            </td>
            <td className="py-2 pr-3 text-right">{fmtCount(row.recipients)}</td>
            <td className="py-2 pr-3 text-right">{fmtCount(row.unique_converters)}</td>
            <td className="py-2 pr-3 text-right">{fmtPct(row.conversion_rate)}</td>
            <td className="py-2 pr-3 text-right font-medium">{fmtSek(row.revenue_sek)}</td>
            <td className="py-2 text-right text-muted-foreground">{fmtUsd(row.revenue_usd)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export default function EmailPerformancePage() {
  const { baseWeek } = useDataCache()
  const weekToLoad = baseWeek || '2026-36'
  const [data, setData] = useState<KlaviyoEmailResponse | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    if (!hasBackend) return
    setLoading(true)
    setErr(null)
    try {
      setData(await getKlaviyoEmail(weekToLoad))
    } catch (e: unknown) {
      setData(null)
      setErr(e instanceof Error ? e.message : 'Failed to load Klaviyo email performance')
    } finally {
      setLoading(false)
    }
  }, [weekToLoad])

  useEffect(() => {
    void load()
  }, [load])

  if (!hasBackend) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Email Performance (Klaviyo)</CardTitle>
          <CardDescription>Configure the API URL to load this report.</CardDescription>
        </CardHeader>
      </Card>
    )
  }

  if (loading && !data) {
    return (
      <div className="flex items-center gap-3 py-12">
        <Loader2 className="h-6 w-6 animate-spin text-primary" />
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Loading Email Performance</h2>
          <p className="text-sm text-gray-600">Reading Klaviyo last-12-months email stats…</p>
        </div>
      </div>
    )
  }

  const fx = data?.fx
  const total = data?.total ?? null
  const sourceLabel =
    data?.source === 'klaviyo_api' ? 'Live Klaviyo API (last 12 months)' : 'Uploaded CSV (last 12 months)'

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-lg font-semibold text-gray-900">Email Performance (Klaviyo)</h2>
        <p className="text-sm text-muted-foreground mt-1 max-w-3xl">
          Standalone from Adjusted aMER and Dema. {sourceLabel}.
          {data?.klaviyo?.key_configured
            ? data.source === 'klaviyo_api'
              ? ' Private API key is connected — this report refreshes from Klaviyo.'
              : data.klaviyo.connected
                ? ' Private API key is connected, but this refresh used the uploaded CSV (see warning).'
                : ' A private API key is set but Klaviyo did not accept it; showing CSV fallback if available.'
            : ' Add KLAVIYO_PRIVATE_API_KEY to the backend environment to switch this report to automatic pulls.'}
        </p>
      </div>

      <div className="text-sm text-amber-950 bg-amber-50 border border-amber-300 rounded p-3 space-y-2">
        <div className="font-semibold uppercase tracking-wide text-[11px] text-amber-800">
          Recipient-based attribution — not last-click aMER
        </div>
        <p>{data?.header_note}</p>
      </div>

      {fx?.applied && fx.sample_rate != null ? (
        <p className="text-sm text-muted-foreground">
          Klaviyo amounts are <strong>USD</strong> (account native). Converted to <strong>SEK</strong> with an
          approximate ECB daily rate
          {fx.provider === 'fallback_env' ? ' (env fallback)' : ' via Frankfurter/ECB'}
          {': '}
          <strong>≈ {Number(fx.sample_rate).toFixed(2)} SEK/USD</strong>
          {fx.rate_date ? ` as of ${fx.rate_date}` : ''}. Same source as Full price vs Sale.
        </p>
      ) : (
        <p className="text-sm text-amber-900">
          USD→SEK conversion is off or unavailable{fx?.error ? ` (${fx.error})` : ''}. Revenue columns show USD.
        </p>
      )}

      {err ? (
        <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded p-3">{err}</div>
      ) : null}

      {(data?.warnings ?? []).map((w) => (
        <div key={w.code} className="text-sm text-amber-900 bg-amber-50 border border-amber-200 rounded p-3">
          {w.message}{' '}
          <Link href="/settings" className="underline font-medium">
            Open Settings
          </Link>
        </div>
      ))}

      {data && !data.available ? (
        <Card>
          <CardHeader>
            <CardTitle>No Klaviyo email data loaded</CardTitle>
            <CardDescription>
              {data.message}{' '}
              <Link href="/settings" className="underline font-medium">
                Open Settings
              </Link>
            </CardDescription>
          </CardHeader>
        </Card>
      ) : null}

      {total ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <KpiCard title="Recipients" value={fmtCount(total.recipients)} hint="Flows + newsletter campaigns" />
          <KpiCard
            title="Unique converters"
            value={fmtCount(total.unique_converters)}
            hint={`Rate ${fmtPct(total.conversion_rate)} · summed across rows`}
          />
          <KpiCard
            title="Revenue"
            value={fmtSek(total.revenue_sek)}
            hint={`${fmtUsd(total.revenue_usd)} native`}
          />
        </div>
      ) : null}

      {(data?.flows ?? []).length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Flows</CardTitle>
            <CardDescription>
              Sorted by revenue descending. Conversion rate = unique converters ÷ recipients.
            </CardDescription>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <MetricTable rows={data!.flows} />
          </CardContent>
        </Card>
      ) : null}

      {data?.newsletter ? (
        <Card>
          <CardHeader>
            <CardTitle>Newsletter campaigns</CardTitle>
            <CardDescription>
              Shown separately from flows — an aggregate across campaigns, not a single automation.
            </CardDescription>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <MetricTable rows={[data.newsletter]} showCampaignCount />
          </CardContent>
        </Card>
      ) : null}

      {data?.footnotes?.length ? (
        <div className="text-xs text-muted-foreground space-y-1">
          {data.as_of ? <p>As of {new Date(data.as_of).toLocaleString('sv-SE')}.</p> : null}
          {data.footnotes.map((f) => (
            <p key={f}>• {f}</p>
          ))}
        </div>
      ) : null}
    </div>
  )
}
