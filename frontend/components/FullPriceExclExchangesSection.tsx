'use client'

import type {
  FullPriceExclComparison,
  FullPriceExclExchangesResponse,
} from '@/lib/api'
import type { SectionViewState } from '@/lib/full-price-vs-sale-load'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Loader2 } from 'lucide-react'
import { useChartAnimations } from '@/contexts/ChartSettingsContext'
import ExchangeDiscountShareChart from '@/components/ExchangeDiscountShareChart'

const thousands = (value: number | null | undefined) =>
  Math.round((value || 0) / 1000).toLocaleString('sv-SE')

const pct = (value: number | null | undefined) =>
  value == null ? '–' : `${value.toFixed(1)}%`

const money = (value: number | null | undefined) =>
  value == null ? '–' : thousands(value)

function complementShare(share: number | null | undefined) {
  return share == null ? null : 100 - share
}

function discountRate(discount: number | null | undefined, total: number | null | undefined) {
  if (discount == null || total == null) return null
  const den = discount + total
  if (den <= 0) return null
  return (discount / den) * 100
}

function normalizeComparison(c: FullPriceExclComparison | undefined): FullPriceExclComparison {
  const empty: FullPriceExclComparison = {
    full_price_share_incl_pct: null,
    full_price_share_excl_pct: null,
    full_price_share_pp_diff: null,
    discounted_share_incl_pct: null,
    discounted_share_excl_pct: null,
    discounted_share_pp_diff: null,
    discount_rate_incl_pct: null,
    discount_rate_excl_pct: null,
    discount_rate_pp_diff: null,
    total_incl: null,
    total_excl: 0,
    discount_incl: null,
    discount_excl: 0,
    exchange_gross_share_pct: null,
    exchange_discount_share_pct: null,
    promotional_discount_share_pct: null,
    non_exchange_gross_est: 0,
    gross_context: 0,
    sales_mix_denom: null,
    sales_mix_full_price_pct: null,
    sales_mix_exchange_pct: null,
    sales_mix_promo_pct: null,
  }
  if (!c) return empty
  const fpIncl = c.full_price_share_incl_pct
  const fpExcl = c.full_price_share_excl_pct
  const discIncl = c.discounted_share_incl_pct ?? complementShare(fpIncl)
  const discExcl = c.discounted_share_excl_pct ?? complementShare(fpExcl)
  const rateIncl = c.discount_rate_incl_pct ?? discountRate(c.discount_incl, c.total_incl)
  const rateExcl = c.discount_rate_excl_pct ?? discountRate(c.discount_excl, c.total_excl)
  const exchShare = c.exchange_discount_share_pct
  return {
    ...c,
    discounted_share_incl_pct: discIncl,
    discounted_share_excl_pct: discExcl,
    discounted_share_pp_diff:
      c.discounted_share_pp_diff ??
      (discExcl != null && discIncl != null ? discExcl - discIncl : null),
    discount_rate_incl_pct: rateIncl,
    discount_rate_excl_pct: rateExcl,
    discount_rate_pp_diff:
      c.discount_rate_pp_diff ??
      (rateExcl != null && rateIncl != null ? rateExcl - rateIncl : null),
    promotional_discount_share_pct:
      c.promotional_discount_share_pct ?? complementShare(exchShare),
  }
}

type View = 'week' | 'month'

export default function FullPriceExclExchangesSection({
  view,
  weekly,
  monthly,
  state,
  error,
}: {
  view: View
  weekly: FullPriceExclExchangesResponse | null
  monthly: FullPriceExclExchangesResponse | null
  state: SectionViewState
  error: string | null
}) {
  const isAnimationActive = useChartAnimations()
  const data = view === 'week' ? weekly : monthly
  const period = data?.period
  const exchDiscShare = period?.comparison
    ? normalizeComparison(period.comparison).exchange_discount_share_pct
    : null
  const promoDiscShare = period?.comparison
    ? normalizeComparison(period.comparison).promotional_discount_share_pct
    : null
  const periodComparison = period ? normalizeComparison(period.comparison) : null

  return (
    <div className="space-y-4 pt-2">
      <div>
        <h3 className="text-base font-semibold text-gray-900">Excluding AfterShip exchanges</h3>
        <p className="text-sm text-muted-foreground mt-1">
          100% sales mix of full price, AfterShip size-swaps, and real promotional discount is above.
          This section is the exchange-credit share of recorded discount (not the sales mix) plus
          daily rows from the excl. export. Amounts in SEK thousands.
        </p>
        {data?.history_range && (
          <p className="text-xs text-muted-foreground mt-1">
            Excl. history: {data.history_range.start} → {data.history_range.end} · {data.files_used.length}{' '}
            file(s)
          </p>
        )}
      </div>

      {state === 'loading' ? (
        <div className="flex items-center gap-3">
          <Loader2 className="h-5 w-5 animate-spin text-primary" />
          <p className="text-sm text-muted-foreground">Loading exchange-excluded daily export…</p>
        </div>
      ) : state === 'error' ? (
        <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error || 'Could not load exchange-excluded full price vs sale.'}
        </div>
      ) : state === 'empty' ? (
        <div className="rounded-md border bg-muted/40 p-6 text-sm text-muted-foreground">
          No exchange-excluded daily export yet. Upload “Full Price vs Sale excl. Exchanges — Daily” in
          Settings (separate from the all-orders slot).
        </div>
      ) : (
        <>
          {period && (
            <div className="space-y-4">
              <p className="text-xs text-muted-foreground">
                Reporting period {period.start} → {period.end}. {period.label}.
              </p>

              <div className="space-y-4" data-testid="exchange-discount-share-block">
              <div className="rounded-xl border border-orange-200 bg-orange-50 p-5 text-orange-950" data-testid="exchange-discount-period-callout">
                <p className="text-xs font-medium uppercase tracking-wide text-orange-800/80">
                  Exchange credits inside recorded discount
                </p>
                <div className="mt-2 flex flex-wrap items-end gap-x-8 gap-y-3">
                  <div>
                    <div className="text-4xl font-semibold tabular-nums tracking-tight">
                      {pct(exchDiscShare)}
                    </div>
                    <p className="mt-1 max-w-xl text-sm leading-snug">
                      of all-orders discount is AfterShip exchange credits, not promotional markdowns.
                      This is share of recorded discount — not the 100% sales mix above.
                    </p>
                  </div>
                  <div className="min-w-[220px] flex-1">
                    <div className="flex h-4 overflow-hidden rounded-full bg-white/80 ring-1 ring-orange-200">
                      <div
                        className="bg-gray-700"
                        style={{ width: `${Math.max(0, Math.min(100, promoDiscShare ?? 0))}%` }}
                      />
                      <div
                        className="bg-orange-500"
                        style={{ width: `${Math.max(0, Math.min(100, exchDiscShare ?? 0))}%` }}
                      />
                    </div>
                    <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs">
                      <span>
                        <span className="mr-1 inline-block h-2 w-2 rounded-sm bg-gray-700 align-middle" />
                        Promotional {pct(promoDiscShare)} · {money(periodComparison?.discount_excl)} SEK ’000
                      </span>
                      <span>
                        <span className="mr-1 inline-block h-2 w-2 rounded-sm bg-orange-500 align-middle" />
                        Exchange credits {pct(exchDiscShare)} · {thousands(period.exchange_discount)} SEK ’000
                      </span>
                    </div>
                  </div>
                </div>
                <p className="mt-3 text-xs text-orange-900/80">
                  All-orders discount {money(periodComparison?.discount_incl)} SEK ’000 vs promotional{' '}
                  {money(periodComparison?.discount_excl)} after exclusion.{' '}
                  {period.exchange_orders.toLocaleString('sv-SE')} exchange orders · gross{' '}
                  {thousands(period.exchange_gross_value)} · net {thousands(period.exchange_net_revenue)} (SEK
                  ’000). Gross share of activity {pct(periodComparison?.exchange_gross_share_pct)}.
                </p>
              </div>

                  <ExchangeDiscountShareChart
                    view={view}
                    weekly={weekly}
                    monthly={monthly}
                    state={state}
                    isAnimationActive={isAnimationActive}
                  />
              </div>
            </div>
          )}

          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">Daily detail — excluding exchanges (SEK &apos;000)</CardTitle>
              <p className="text-xs text-muted-foreground">
                One row per calendar date in the selected reporting period, including zero-sales days from the
                upload. Zero-filled dates are preserved.
              </p>
            </CardHeader>
            <CardContent className="overflow-x-auto max-h-[420px] overflow-y-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-white">
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="py-2 pr-4 font-medium">Date</th>
                    <th className="py-2 px-3 font-medium text-right">FP %</th>
                    <th className="py-2 px-3 font-medium text-right">Disc. %</th>
                    <th className="py-2 px-3 font-medium text-right">Exch. disc. %</th>
                    <th className="py-2 px-3 font-medium text-right">Exch. orders</th>
                    <th className="py-2 px-3 font-medium text-right">Exch. gross</th>
                    <th className="py-2 pl-3 font-medium text-right">Exch. net</th>
                  </tr>
                </thead>
                <tbody>
                  {(data?.days || []).map((d) => {
                    const comparison = normalizeComparison(d.comparison)
                    return (
                    <tr key={d.date} className="border-b last:border-0">
                      <td className="py-2 pr-4 font-medium text-gray-900">{d.date}</td>
                      <td className="py-2 px-3 text-right tabular-nums">{pct(comparison.full_price_share_excl_pct)}</td>
                      <td className="py-2 px-3 text-right tabular-nums">{pct(comparison.discounted_share_excl_pct)}</td>
                      <td className="py-2 px-3 text-right tabular-nums text-orange-800">
                        {pct(comparison.exchange_discount_share_pct)}
                      </td>
                      <td className="py-2 px-3 text-right tabular-nums">{d.exchange_orders}</td>
                      <td className="py-2 px-3 text-right tabular-nums">{thousands(d.exchange_gross_value)}</td>
                      <td className="py-2 pl-3 text-right tabular-nums">{thousands(d.exchange_net_revenue)}</td>
                    </tr>
                    )
                  })}
                </tbody>
              </table>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}
