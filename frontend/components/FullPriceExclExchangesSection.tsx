'use client'

import type {
  FullPriceExclComparison,
  FullPriceExclExchangesResponse,
  FullPriceExclMetrics,
} from '@/lib/api'
import type { SectionViewState } from '@/lib/full-price-vs-sale-load'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Loader2 } from 'lucide-react'
import { useChartAnimations } from '@/contexts/ChartSettingsContext'
import FullPriceBeforeAfterCharts from '@/components/FullPriceBeforeAfterCharts'

const thousands = (value: number | null | undefined) =>
  Math.round((value || 0) / 1000).toLocaleString('sv-SE')

const pct = (value: number | null | undefined) =>
  value == null ? '–' : `${value.toFixed(1)}%`

const signedPp = (value: number | null | undefined) =>
  value == null ? '–' : `${value >= 0 ? '+' : ''}${value.toFixed(1)}`

const money = (value: number | null | undefined) =>
  value == null ? '–' : thousands(value)

const moneyDelta = (after: number | null | undefined, before: number | null | undefined) => {
  if (after == null || before == null) return '–'
  return signedThousands(after - before)
}

const signedThousands = (value: number) => {
  const rounded = Math.round(value / 1000)
  const abs = Math.abs(rounded).toLocaleString('sv-SE')
  if (rounded === 0) return '0'
  return `${rounded > 0 ? '+' : '−'}${abs}`
}

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

function MixBar({
  fullPriceShare,
  discountedShare,
}: {
  fullPriceShare: number | null | undefined
  discountedShare: number | null | undefined
}) {
  const fp = fullPriceShare ?? 0
  const disc = discountedShare ?? Math.max(0, 100 - fp)
  if (fullPriceShare == null && discountedShare == null) {
    return <div className="h-2.5 rounded-full bg-muted" />
  }
  return (
    <div className="flex h-2.5 overflow-hidden rounded-full bg-muted" title={`Full price ${pct(fp)} · Discounted ${pct(disc)}`}>
      <div className="bg-gray-700" style={{ width: `${Math.max(0, Math.min(100, fp))}%` }} />
      <div className="bg-orange-500" style={{ width: `${Math.max(0, Math.min(100, disc))}%` }} />
    </div>
  )
}

function MetricTable({
  rows,
  labelFor,
  periodHeader,
}: {
  rows: Array<FullPriceExclMetrics & { key: string; label: string }>
  labelFor: string
  periodHeader: string
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium">{labelFor}</CardTitle>
        <p className="text-xs text-muted-foreground">
          Mix before vs after excluding AfterShip exchanges. Amounts in SEK &apos;000.
        </p>
      </CardHeader>
      <CardContent className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-muted-foreground">
              <th className="py-2 pr-4 font-medium">{periodHeader}</th>
              <th className="py-2 px-3 font-medium text-right">FP share before</th>
              <th className="py-2 px-3 font-medium text-right">FP share after</th>
              <th className="py-2 px-3 font-medium text-right">Δ FP pp</th>
              <th className="py-2 px-3 font-medium text-right">Disc. share before</th>
              <th className="py-2 px-3 font-medium text-right">Disc. share after</th>
              <th className="py-2 px-3 font-medium text-right">Δ disc. pp</th>
              <th className="py-2 px-3 font-medium text-right">Discount before</th>
              <th className="py-2 px-3 font-medium text-right">Discount after</th>
              <th className="py-2 px-3 font-medium text-right">Exch. disc. %</th>
              <th className="py-2 px-3 font-medium text-right">Exch. orders</th>
              <th className="py-2 px-3 font-medium text-right">Exch. gross</th>
              <th className="py-2 pl-3 font-medium text-right">Exch. net</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const comparison = normalizeComparison(row.comparison)
              return (
              <tr key={row.key} className="border-b last:border-0">
                <td className="py-2 pr-4 font-medium text-gray-900">{row.label}</td>
                <td className="py-2 px-3 text-right tabular-nums">{pct(comparison.full_price_share_incl_pct)}</td>
                <td className="py-2 px-3 text-right tabular-nums">{pct(comparison.full_price_share_excl_pct)}</td>
                <td className="py-2 px-3 text-right tabular-nums">{signedPp(comparison.full_price_share_pp_diff)}</td>
                <td className="py-2 px-3 text-right tabular-nums">{pct(comparison.discounted_share_incl_pct)}</td>
                <td className="py-2 px-3 text-right tabular-nums">{pct(comparison.discounted_share_excl_pct)}</td>
                <td className="py-2 px-3 text-right tabular-nums">{signedPp(comparison.discounted_share_pp_diff)}</td>
                <td className="py-2 px-3 text-right tabular-nums">{money(comparison.discount_incl)}</td>
                <td className="py-2 px-3 text-right tabular-nums">{thousands(row.discount_amount)}</td>
                <td className="py-2 px-3 text-right tabular-nums font-medium text-orange-800">
                  {pct(comparison.exchange_discount_share_pct)}
                </td>
                <td className="py-2 px-3 text-right tabular-nums">{row.exchange_orders.toLocaleString('sv-SE')}</td>
                <td className="py-2 px-3 text-right tabular-nums">{thousands(row.exchange_gross_value)}</td>
                <td className="py-2 pl-3 text-right tabular-nums">{thousands(row.exchange_net_revenue)}</td>
              </tr>
              )
            })}
          </tbody>
        </table>
      </CardContent>
    </Card>
  )
}

function BeforeAfterTable({
  comparison,
  exchangeOrders,
  grain,
}: {
  comparison: FullPriceExclComparison
  exchangeOrders: number
  grain: 'week' | 'month'
}) {
  const rows: Array<{
    label: string
    hint: string
    before: string
    after: string
    delta: string
    emphasizeDelta?: boolean
  }> = [
    {
      label: 'Full price share of net',
      hint: 'Full price ÷ total net',
      before: pct(comparison.full_price_share_incl_pct),
      after: pct(comparison.full_price_share_excl_pct),
      delta: `${signedPp(comparison.full_price_share_pp_diff)} pp`,
    },
    {
      label: 'Discounted share of net',
      hint: 'Sale / markdown net ÷ total net',
      before: pct(comparison.discounted_share_incl_pct),
      after: pct(comparison.discounted_share_excl_pct),
      delta: `${signedPp(comparison.discounted_share_pp_diff)} pp`,
    },
    {
      label: 'Discount amount (SEK ’000)',
      hint: 'Recorded markdown. After = promotional only',
      before: money(comparison.discount_incl),
      after: money(comparison.discount_excl),
      delta: moneyDelta(comparison.discount_excl, comparison.discount_incl),
      emphasizeDelta: true,
    },
    {
      label: 'Discount rate',
      hint: 'Discount ÷ (net + discount). Exchange credits inflate the before figure',
      before: pct(comparison.discount_rate_incl_pct),
      after: pct(comparison.discount_rate_excl_pct),
      delta: `${signedPp(comparison.discount_rate_pp_diff)} pp`,
      emphasizeDelta: true,
    },
    {
      label: 'Total net (SEK ’000)',
      hint: 'After does not add exchange net',
      before: money(comparison.total_incl),
      after: money(comparison.total_excl),
      delta: moneyDelta(comparison.total_excl, comparison.total_incl),
    },
  ]

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium">
          Full price vs discount — before and after excluding exchanges
        </CardTitle>
        <p className="text-xs text-muted-foreground">
          These bars are the <strong>whole reporting window</strong> (every day in the selected weeks or months), not
          the latest {grain} alone. Before = all-orders export (exchanges mixed in). After = promotional sales only —{' '}
          {exchangeOrders.toLocaleString('sv-SE')} AfterShip exchange orders in this window.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div className="rounded-lg border bg-muted/30 p-3">
            <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Before · including exchanges</p>
            <MixBar
              fullPriceShare={comparison.full_price_share_incl_pct}
              discountedShare={comparison.discounted_share_incl_pct}
            />
            <p className="mt-2 text-sm tabular-nums text-gray-900">
              <span className="font-semibold">{pct(comparison.full_price_share_incl_pct)}</span>
              <span className="text-muted-foreground"> full price · </span>
              <span className="font-semibold text-orange-700">{pct(comparison.discounted_share_incl_pct)}</span>
              <span className="text-muted-foreground"> discounted</span>
            </p>
          </div>
          <div className="rounded-lg border border-gray-900/10 bg-white p-3">
            <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">After · excluding exchanges</p>
            <MixBar
              fullPriceShare={comparison.full_price_share_excl_pct}
              discountedShare={comparison.discounted_share_excl_pct}
            />
            <p className="mt-2 text-sm tabular-nums text-gray-900">
              <span className="font-semibold">{pct(comparison.full_price_share_excl_pct)}</span>
              <span className="text-muted-foreground"> full price · </span>
              <span className="font-semibold text-orange-700">{pct(comparison.discounted_share_excl_pct)}</span>
              <span className="text-muted-foreground"> discounted</span>
            </p>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-muted-foreground">
                <th className="py-2 pr-4 font-medium">Metric</th>
                <th className="py-2 px-3 font-medium text-right">Before (incl. exchanges)</th>
                <th className="py-2 px-3 font-medium text-right">After (excl. exchanges)</th>
                <th className="py-2 pl-3 font-medium text-right">Difference</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.label} className="border-b last:border-0">
                  <td className="py-2.5 pr-4">
                    <div className="font-medium text-gray-900">{row.label}</div>
                    <div className="text-[11px] text-muted-foreground leading-snug">{row.hint}</div>
                  </td>
                  <td className="py-2.5 px-3 text-right tabular-nums text-muted-foreground">{row.before}</td>
                  <td className="py-2.5 px-3 text-right tabular-nums font-medium text-gray-900">{row.after}</td>
                  <td
                    className={`py-2.5 pl-3 text-right tabular-nums font-medium ${
                      row.emphasizeDelta ? 'text-orange-800' : 'text-gray-900'
                    }`}
                  >
                    {row.delta}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  )
}

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
  const periodRows =
    view === 'week'
      ? (weekly?.weeks || []).map((w) => ({
          key: w.week,
          label: `W${String(w.week).split('-')[1]}`,
          ...w,
        }))
      : (monthly?.months_data || []).map((m) => {
          const [y, mo] = m.month.split('-')
          const d = new Date(Number(y), Number(mo) - 1, 1)
          return {
            key: m.month,
            label: `${d.toLocaleString('en-US', { month: 'short' })} '${y.slice(2)}`,
            ...m,
          }
        })

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
          Non-exchange revenue from the daily “Sales by Pricing Type Adv” export. Exchange orders,
          gross, discount, and net are AfterShip impact and are <strong>not</strong> included in the
          excl. Total or treated as ordinary full-price revenue. Charts below compare each{' '}
          {view === 'week' ? 'week' : 'month'} including vs excluding those orders. Amounts in SEK
          thousands.
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

              <div className="rounded-xl border border-orange-200 bg-orange-50 p-5 text-orange-950">
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

              {periodComparison && (
                <>
                  <FullPriceBeforeAfterCharts
                    view={view}
                    weekly={weekly}
                    monthly={monthly}
                    state={state}
                    error={error}
                    isAnimationActive={isAnimationActive}
                    showPeriodCallout
                  />
                  <BeforeAfterTable
                    comparison={periodComparison}
                    exchangeOrders={period.exchange_orders}
                    grain={view}
                  />
                </>
              )}
            </div>
          )}

          {periodRows.length > 0 && (
            <MetricTable
              rows={periodRows}
              labelFor={view === 'week' ? 'Weekly totals — before vs after exchanges' : 'Monthly totals — before vs after exchanges'}
              periodHeader={view === 'week' ? 'Week' : 'Month'}
            />
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
                    <th className="py-2 px-3 font-medium text-right">FP before</th>
                    <th className="py-2 px-3 font-medium text-right">FP after</th>
                    <th className="py-2 px-3 font-medium text-right">Δ FP pp</th>
                    <th className="py-2 px-3 font-medium text-right">Disc. before</th>
                    <th className="py-2 px-3 font-medium text-right">Disc. after</th>
                    <th className="py-2 px-3 font-medium text-right">Δ disc. pp</th>
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
                      <td className="py-2 px-3 text-right tabular-nums text-muted-foreground">
                        {pct(comparison.full_price_share_incl_pct)}
                      </td>
                      <td className="py-2 px-3 text-right tabular-nums">{pct(comparison.full_price_share_excl_pct)}</td>
                      <td className="py-2 px-3 text-right tabular-nums">{signedPp(comparison.full_price_share_pp_diff)}</td>
                      <td className="py-2 px-3 text-right tabular-nums text-muted-foreground">
                        {pct(comparison.discounted_share_incl_pct)}
                      </td>
                      <td className="py-2 px-3 text-right tabular-nums">{pct(comparison.discounted_share_excl_pct)}</td>
                      <td className="py-2 px-3 text-right tabular-nums">{signedPp(comparison.discounted_share_pp_diff)}</td>
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
