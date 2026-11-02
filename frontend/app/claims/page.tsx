'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { Loader2 } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { getClaims, hasBackend, type ClaimsBucket, type ClaimsResponse } from '@/lib/api'
import { bucketHasShipping, claimsPageNotes } from '@/lib/claims-columns'

function sek(value: number | null | undefined): string {
  if (value == null || Number.isNaN(Number(value))) return '—'
  return `${Number(value).toLocaleString('sv-SE', { maximumFractionDigits: 0 })} SEK`
}

function count(value: number | null | undefined): string {
  if (value == null || Number.isNaN(Number(value))) return '—'
  return Number(value).toLocaleString('sv-SE')
}

function Kpi({ title, value, hint }: { title: string; value: string; hint?: string }) {
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

function MoneyTable({
  title,
  description,
  rows,
  firstColumn,
  showShipping = true,
}: {
  title: string
  description?: string
  rows: ClaimsBucket[]
  firstColumn: string
  showShipping?: boolean
}) {
  const columns: { header: string; value: (row: ClaimsBucket) => string }[] = [
    { header: 'Claims', value: (row) => count(row.orders) },
    { header: 'Units', value: (row) => count(row.units) },
    { header: 'Landed cost', value: (row) => sek(row.product_cost_sek) },
  ]
  if (showShipping) {
    columns.push({ header: 'Shipping', value: (row) => sek(row.freight_sek) })
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
        {description ? <CardDescription>{description}</CardDescription> : null}
      </CardHeader>
      <CardContent className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-muted-foreground border-b">
              <th className="py-2 pr-3">{firstColumn}</th>
              {columns.map((column, index) => (
                <th
                  key={column.header}
                  className={`py-2 text-right${index < columns.length - 1 ? ' pr-3' : ''}`}
                >
                  {column.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.key || row.label} className="border-b last:border-0">
                <td className="py-2 pr-3">{row.label}</td>
                {columns.map((column, index) => (
                  <td
                    key={column.header}
                    className={`py-2 text-right${index < columns.length - 1 ? ' pr-3' : ''}`}
                  >
                    {column.value(row)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  )
}

export default function ClaimsPage() {
  const [data, setData] = useState<ClaimsResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!hasBackend) {
      setLoading(false)
      return
    }
    let cancelled = false
    getClaims()
      .then((payload) => {
        if (!cancelled) setData(payload)
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load claims')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (!hasBackend) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Claims · Cin7</CardTitle>
          <CardDescription>Configure the API URL to load this report.</CardDescription>
        </CardHeader>
      </Card>
    )
  }

  if (loading) {
    return (
      <div className="flex items-center gap-3 py-12">
        <Loader2 className="h-6 w-6 animate-spin text-primary" />
        <p className="text-sm text-muted-foreground">Loading Cin7 claim orders…</p>
      </div>
    )
  }

  const totals = data?.totals

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-lg font-semibold text-gray-900">Claims · Cin7</h2>
        <p className="text-sm text-muted-foreground mt-1 max-w-3xl">
          Claim orders created in Cin7. They are not part of Shopify. A later export replaces an order that is already loaded.
        </p>
        {data?.files_used?.length ? (
          <p className="text-xs text-muted-foreground mt-1">Files: {data.files_used.join(', ')}</p>
        ) : null}
      </div>

      {claimsPageNotes(data?.notes ?? []).map((note) => (
        <div key={note} className="text-sm text-amber-950 bg-amber-50 border border-amber-200 rounded p-3">
          {note}
        </div>
      ))}

      {error ? <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded p-3">{error}</div> : null}

      {data && !data.available ? (
        <Card>
          <CardHeader>
            <CardTitle>No claim orders loaded</CardTitle>
            <CardDescription>
              Upload the Cin7 orders export on{' '}
              <Link href="/settings" className="underline font-medium">
                Settings
              </Link>
              , in Claims orders — Cin7.
            </CardDescription>
          </CardHeader>
        </Card>
      ) : null}

      {totals && data?.available ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Kpi title="Claim orders" value={count(totals.orders)} hint={`${count(totals.units)} replacement units`} />
          <Kpi title="Landed cost" value={sek(totals.product_cost_sek)} hint="Replacement cost in SEK" />
          <Kpi title="Shipping cost" value={sek(totals.freight_sek)} hint="2026 carrier price, converted to SEK" />
        </div>
      ) : null}

      {data?.months?.length ? (
        <MoneyTable title="Claims by month" firstColumn="Month" rows={data.months} />
      ) : null}

      {data?.reasons?.length ? (
        <MoneyTable
          title="Claim type"
          description="Taken from a Claim Type column, or from Order Tags, when the export has one."
          firstColumn="Type"
          rows={data.reasons}
        />
      ) : null}

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        {data?.categories?.length ? (
          <MoneyTable
            title="Replacement product"
            description="An order with two product types is counted in each type."
            firstColumn="Product"
            rows={data.categories}
            showShipping={bucketHasShipping(data.categories)}
          />
        ) : null}
        {data?.countries?.length ? <MoneyTable title="Destination country" firstColumn="Country" rows={data.countries} /> : null}
      </div>

      {data?.carriers?.length ? (
        <MoneyTable title="Shipping method" firstColumn="Method" rows={data.carriers} />
      ) : null}

      {data?.orders?.length ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Orders</CardTitle>
            <CardDescription>Customer names, emails and addresses are not shown.</CardDescription>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-muted-foreground border-b">
                  <th className="py-2 pr-3">Order</th>
                  <th className="py-2 pr-3">Date</th>
                  <th className="py-2 pr-3">Country</th>
                  <th className="py-2 pr-3">Type</th>
                  <th className="py-2 pr-3">Shipping</th>
                  <th className="py-2 pr-3 text-right">Units</th>
                  <th className="py-2 pr-3 text-right">Landed cost</th>
                  <th className="py-2 text-right">Shipping cost</th>
                </tr>
              </thead>
              <tbody>
                {data.orders.map((row) => (
                  <tr key={row.order_ref} className="border-b last:border-0 align-top">
                    <td className="py-2 pr-3">
                      {row.order_ref}
                      <span className="block text-xs text-muted-foreground">{row.items}</span>
                    </td>
                    <td className="py-2 pr-3 whitespace-nowrap">{row.created}</td>
                    <td className="py-2 pr-3">{row.country}</td>
                    <td className="py-2 pr-3">{row.reason}</td>
                    <td className="py-2 pr-3">{row.freight_method}</td>
                    <td className="py-2 pr-3 text-right">{count(row.units)}</td>
                    <td className="py-2 pr-3 text-right">{sek(row.product_cost_sek)}</td>
                    <td className="py-2 text-right">{sek(row.freight_sek)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      ) : null}
    </div>
  )
}
