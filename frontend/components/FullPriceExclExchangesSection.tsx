'use client'

import type {
  FullPriceExclExchangesResponse,
  FullPriceExclMetrics,
} from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

const thousands = (value: number | null | undefined) =>
  Math.round((value || 0) / 1000).toLocaleString('sv-SE')

const pct = (value: number | null | undefined) =>
  value == null ? '–' : `${value.toFixed(1)}%`

const signedPp = (value: number | null | undefined) =>
  value == null ? '–' : `${value >= 0 ? '+' : ''}${value.toFixed(1)}`

const money = (value: number | null | undefined) =>
  value == null ? '–' : thousands(value)

type View = 'week' | 'month'

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
          Non-exchange sale types, total, discount, and AfterShip exchange impact. Amounts in SEK &apos;000.
        </p>
      </CardHeader>
      <CardContent className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-muted-foreground">
              <th className="py-2 pr-4 font-medium">{periodHeader}</th>
              <th className="py-2 px-3 font-medium text-right">Full price</th>
              <th className="py-2 px-3 font-medium text-right">Compare-at</th>
              <th className="py-2 px-3 font-medium text-right">Code / auto</th>
              <th className="py-2 px-3 font-medium text-right">Both</th>
              <th className="py-2 px-3 font-medium text-right">Price drop</th>
              <th className="py-2 px-3 font-medium text-right">Total excl.</th>
              <th className="py-2 px-3 font-medium text-right">Discount excl.</th>
              <th className="py-2 px-3 font-medium text-right">FP share excl.</th>
              <th className="py-2 px-3 font-medium text-right">Exch. orders</th>
              <th className="py-2 px-3 font-medium text-right">Exch. gross</th>
              <th className="py-2 px-3 font-medium text-right">Exch. discount</th>
              <th className="py-2 pl-3 font-medium text-right">Exch. net</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.key} className="border-b last:border-0">
                <td className="py-2 pr-4 font-medium text-gray-900">{row.label}</td>
                <td className="py-2 px-3 text-right tabular-nums">{thousands(row.full_price)}</td>
                <td className="py-2 px-3 text-right tabular-nums">{thousands(row.compare_at_price_sale)}</td>
                <td className="py-2 px-3 text-right tabular-nums">{thousands(row.discount_code_auto)}</td>
                <td className="py-2 px-3 text-right tabular-nums">{thousands(row.both)}</td>
                <td className="py-2 px-3 text-right tabular-nums">{thousands(row.price_drop_sale)}</td>
                <td className="py-2 px-3 text-right tabular-nums">{thousands(row.total)}</td>
                <td className="py-2 px-3 text-right tabular-nums">{thousands(row.discount_amount)}</td>
                <td className="py-2 px-3 text-right tabular-nums">{pct(row.full_price_share_pct)}</td>
                <td className="py-2 px-3 text-right tabular-nums">{row.exchange_orders.toLocaleString('sv-SE')}</td>
                <td className="py-2 px-3 text-right tabular-nums">{thousands(row.exchange_gross_value)}</td>
                <td className="py-2 px-3 text-right tabular-nums">{thousands(row.exchange_discount)}</td>
                <td className="py-2 pl-3 text-right tabular-nums">{thousands(row.exchange_net_revenue)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  )
}

export default function FullPriceExclExchangesSection({
  view,
  weekly,
  monthly,
}: {
  view: View
  weekly: FullPriceExclExchangesResponse | null
  monthly: FullPriceExclExchangesResponse | null
}) {
  const data = view === 'week' ? weekly : monthly
  const period = data?.period
  const hasDays = (data?.days?.length || 0) > 0
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

  return (
    <div className="space-y-4 pt-2">
      <div>
        <h3 className="text-base font-semibold text-gray-900">Excluding AfterShip exchanges</h3>
        <p className="text-sm text-muted-foreground mt-1">
          Non-exchange revenue from the daily “Sales by Pricing Type Adv” export. Exchange orders,
          gross, discount, and net are AfterShip impact and are <strong>not</strong> included in the
          excl. Total or treated as ordinary full-price revenue. Amounts in SEK thousands.
        </p>
        {data?.history_range && (
          <p className="text-xs text-muted-foreground mt-1">
            Excl. history: {data.history_range.start} → {data.history_range.end} · {data.files_used.length}{' '}
            file(s)
          </p>
        )}
      </div>

      {!data || (!hasDays && !period) ? (
        <div className="rounded-md border bg-muted/40 p-6 text-sm text-muted-foreground">
          No exchange-excluded daily export yet. Upload “Full Price vs Sale excl. Exchanges — Daily” in
          Settings (separate from the all-orders slot).
        </div>
      ) : (
        <>
          {period && (
            <div className="space-y-2">
              <p className="text-xs text-muted-foreground">
                Reporting period {period.start} → {period.end}. {period.label}.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-xs font-medium text-muted-foreground">
                      Full price share excl. vs incl. exchanges
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-semibold text-gray-900">
                      {pct(period.comparison.full_price_share_excl_pct)}
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">
                      Incl. exchanges {pct(period.comparison.full_price_share_incl_pct)} ·{' '}
                      {signedPp(period.comparison.full_price_share_pp_diff)} pp
                    </div>
                    <p className="text-[11px] text-muted-foreground mt-2 leading-snug">
                      Δ pp = excl. share − all-orders share for the same dates.
                    </p>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-xs font-medium text-muted-foreground">
                      Total net (SEK &apos;000) excl. vs incl.
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-semibold text-gray-900">{thousands(period.total)}</div>
                    <div className="text-xs text-muted-foreground mt-1">
                      All-orders {money(period.comparison.total_incl)}
                    </div>
                    <p className="text-[11px] text-muted-foreground mt-2 leading-snug">
                      Excl. Total is non-exchange only — exchange net is not added here.
                    </p>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-xs font-medium text-muted-foreground">
                      Discount amount excl. vs incl.
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-semibold text-gray-900">
                      {thousands(period.discount_amount)}
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">
                      All-orders {money(period.comparison.discount_incl)} · exch. disc. share{' '}
                      {pct(period.comparison.exchange_discount_share_pct)}
                    </div>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-xs font-medium text-muted-foreground">
                      Exchange impact
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-semibold text-gray-900">
                      {period.exchange_orders.toLocaleString('sv-SE')} orders
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">
                      Gross {thousands(period.exchange_gross_value)} · disc.{' '}
                      {thousands(period.exchange_discount)} · net {thousands(period.exchange_net_revenue)}
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">
                      Gross share of context {pct(period.comparison.exchange_gross_share_pct)}
                    </div>
                    <p className="text-[11px] text-muted-foreground mt-2 leading-snug">
                      Gross context ≈ excl. Total + excl. Discount + exchange gross. Net can be ~0 with
                      large gross.
                    </p>
                  </CardContent>
                </Card>
              </div>
            </div>
          )}

          {periodRows.length > 0 && (
            <MetricTable
              rows={periodRows}
              labelFor={view === 'week' ? 'Weekly totals — excluding exchanges' : 'Monthly totals — excluding exchanges'}
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
                    <th className="py-2 px-3 font-medium text-right">Full price</th>
                    <th className="py-2 px-3 font-medium text-right">Total excl.</th>
                    <th className="py-2 px-3 font-medium text-right">FP share excl.</th>
                    <th className="py-2 px-3 font-medium text-right">FP share incl.</th>
                    <th className="py-2 px-3 font-medium text-right">Δ pp</th>
                    <th className="py-2 px-3 font-medium text-right">Exch. orders</th>
                    <th className="py-2 px-3 font-medium text-right">Exch. gross</th>
                    <th className="py-2 px-3 font-medium text-right">Exch. disc.</th>
                    <th className="py-2 pl-3 font-medium text-right">Exch. net</th>
                  </tr>
                </thead>
                <tbody>
                  {(data.days || []).map((d) => (
                    <tr key={d.date} className="border-b last:border-0">
                      <td className="py-2 pr-4 font-medium text-gray-900">{d.date}</td>
                      <td className="py-2 px-3 text-right tabular-nums">{thousands(d.full_price)}</td>
                      <td className="py-2 px-3 text-right tabular-nums">{thousands(d.total)}</td>
                      <td className="py-2 px-3 text-right tabular-nums">{pct(d.full_price_share_pct)}</td>
                      <td className="py-2 px-3 text-right tabular-nums text-muted-foreground">
                        {pct(d.comparison.full_price_share_incl_pct)}
                      </td>
                      <td className="py-2 px-3 text-right tabular-nums">
                        {signedPp(d.comparison.full_price_share_pp_diff)}
                      </td>
                      <td className="py-2 px-3 text-right tabular-nums">{d.exchange_orders}</td>
                      <td className="py-2 px-3 text-right tabular-nums">{thousands(d.exchange_gross_value)}</td>
                      <td className="py-2 px-3 text-right tabular-nums">{thousands(d.exchange_discount)}</td>
                      <td className="py-2 pl-3 text-right tabular-nums">{thousands(d.exchange_net_revenue)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}
