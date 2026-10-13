'use client'

import type { DiscountTypesPeriod, DiscountTypesResponse, DiscountTypeBucket } from '@/lib/api'
import type { SectionViewState } from '@/lib/full-price-vs-sale-load'
import { monthlyTypesLayout, SHOPIFY_GROSS_EXCL_VAT_NOTE } from '@/lib/full-price-presentation'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Loader2 } from 'lucide-react'

const thousands = (value: number | null | undefined) =>
  Math.round((value || 0) / 1000).toLocaleString('sv-SE')

const pct = (value: number | null | undefined) =>
  value == null ? '–' : `${value.toFixed(1)}%`

const weekLabel = (w: string) => `W${String(w).split('-')[1]}`
const monthLabel = (m: string) => {
  const [y, mo] = m.split('-')
  const d = new Date(Number(y), Number(mo) - 1, 1)
  return `${d.toLocaleString('en-US', { month: 'short' })} '${y.slice(2)}`
}

function amountCell(row: DiscountTypeBucket) {
  if (row.is_free_shipping) return '–'
  return thousands(row.discount_amount)
}

function GroupRows({
  groups,
  lyGroups,
}: {
  groups: DiscountTypeBucket[]
  lyGroups?: DiscountTypeBucket[]
}) {
  const lyById = new Map((lyGroups || []).map((g) => [g.id, g]))
  const rows: Array<{ key: string; row: DiscountTypeBucket; indent: boolean; ly?: DiscountTypeBucket }> = []
  for (const g of groups) {
    rows.push({ key: `g-${g.id}`, row: g, indent: false, ly: lyById.get(g.id) })
    for (const sub of g.subgroups || []) {
      const lySub = (lyById.get(g.id)?.subgroups || []).find((s) => s.id === sub.id)
      rows.push({ key: `sub-${g.id}-${sub.id}`, row: sub, indent: true, ly: lySub })
    }
  }
  return (
    <>
      {rows.map(({ key, row, indent, ly }) => (
        <tr key={key} className="border-b last:border-0">
          <td className={`py-2 pr-4 ${indent ? 'pl-6 text-muted-foreground' : 'font-medium text-gray-900'}`}>
            {row.label}
            {row.is_free_shipping ? (
              <span className="ml-2 text-[11px] uppercase tracking-wide">orders only</span>
            ) : null}
          </td>
          <td className="py-2 px-3 text-right tabular-nums">{amountCell(row)}</td>
          <td className="py-2 px-3 text-right tabular-nums">{row.orders.toLocaleString('sv-SE')}</td>
          <td className="py-2 px-3 text-right tabular-nums">{pct(row.share_of_discounts_pct)}</td>
          <td className="py-2 px-3 text-right tabular-nums">{pct(row.pct_of_gross_sales)}</td>
          <td className="py-2 pl-3 text-right tabular-nums text-muted-foreground">
            {ly ? amountCell(ly) : '–'}
          </td>
        </tr>
      ))}
    </>
  )
}

function ByTypeCard({
  title,
  period,
  testId,
  extraNote,
}: {
  title: string
  period: DiscountTypesPeriod
  testId?: string
  extraNote?: string
}) {
  return (
    <Card data-testid={testId}>
      <CardHeader>
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        <p className="text-xs text-muted-foreground">
          {extraNote ? `${extraNote} · ` : null}
          Total {thousands(period.discount_amount)} · {pct(period.discount_of_gross_pct)} of gross{' '}
          {thousands(period.gross_sales)} · LY {thousands(period.last_year?.discount_amount)} ·{' '}
          {pct(period.last_year?.discount_of_gross_pct)} of LY gross
        </p>
      </CardHeader>
      <CardContent className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-muted-foreground">
              <th className="py-2 pr-4 font-medium">Type</th>
              <th className="py-2 px-3 font-medium text-right">Discount</th>
              <th className="py-2 px-3 font-medium text-right">Orders</th>
              <th className="py-2 px-3 font-medium text-right">Share of discounts</th>
              <th className="py-2 px-3 font-medium text-right">% of gross</th>
              <th className="py-2 pl-3 font-medium text-right">LY discount</th>
            </tr>
          </thead>
          <tbody>
            <GroupRows groups={period.groups} lyGroups={period.last_year?.groups} />
          </tbody>
        </table>
        <p className="text-[11px] text-muted-foreground mt-3">{SHOPIFY_GROSS_EXCL_VAT_NOTE}</p>
      </CardContent>
    </Card>
  )
}

export default function DiscountTypesSection({
  view,
  weekly,
  monthly,
  loading,
  error,
}: {
  view: 'week' | 'month'
  weekly: DiscountTypesResponse | null
  monthly: DiscountTypesResponse | null
  loading: boolean
  error: string | null
}) {
  const data = view === 'week' ? weekly : monthly
  const periods = data?.periods || []
  const weekPeriodsAsc = [...periods].sort((a, b) => String(a.end).localeCompare(String(b.end)))
  const monthLayout = monthlyTypesLayout(periods)
  const periodsAsc = view === 'week' ? weekPeriodsAsc : monthLayout.periodsAsc
  const latestWeek: DiscountTypesPeriod | undefined = weekPeriodsAsc[weekPeriodsAsc.length - 1]
  const periodLabel = (p: DiscountTypesPeriod) =>
    view === 'week' ? weekLabel(p.week || p.key) : monthLabel(p.month || p.key)
  const state: SectionViewState = loading
    ? 'loading'
    : error
      ? 'error'
      : !data
        ? 'loading'
        : periods.length === 0
          ? 'empty'
          : 'ready'

  const slideTitle = view === 'week' ? 'Discount Types – Weekly' : 'Discount Types – Monthly'

  return (
    <div className="space-y-4 pt-2" data-testid="discount-types-section">
      <div>
        <h3 className="text-base font-semibold text-gray-900">{slideTitle}</h3>
        <p className="text-sm text-muted-foreground mt-1">
          {data?.note ||
            'Codes and manual discounts only; lowered prices (markdowns) are shown on the Full Price vs Sale slides.'}
        </p>
        <p className="text-xs text-muted-foreground mt-1">
          Last {view === 'week' ? '8 ISO weeks' : '13 months'} vs last year. Free shipping shows order
          counts only (0 value). {SHOPIFY_GROSS_EXCL_VAT_NOTE}
        </p>
      </div>

      {state === 'loading' ? (
        <div className="flex items-center gap-3">
          <Loader2 className="h-5 w-5 animate-spin text-primary" />
          <p className="text-sm text-muted-foreground">Loading discount types…</p>
        </div>
      ) : state === 'error' ? (
        <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>
      ) : state === 'empty' ? (
        <div className="rounded-md border bg-muted/40 p-6 text-sm text-muted-foreground">
          No discount-type files found. Expected under weekly_report/data/discount_types/.
        </div>
      ) : periodsAsc.length > 0 ? (
        <>
          <Card>
            <CardHeader>
              <CardTitle className="text-sm font-medium">
                {view === 'week' ? 'Weekly' : 'Monthly'} discount totals (SEK ’000)
              </CardTitle>
              <p className="text-xs text-muted-foreground">
                Codes and manual discounts vs last year. Markdowns are on the slides above.
              </p>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="py-2 pr-4 font-medium">{view === 'week' ? 'Week' : 'Month'}</th>
                    <th className="py-2 px-3 font-medium text-right">Discount</th>
                    <th className="py-2 px-3 font-medium text-right">% of gross</th>
                    <th className="py-2 px-3 font-medium text-right">LY discount</th>
                    <th className="py-2 pl-3 font-medium text-right">LY % of gross</th>
                  </tr>
                </thead>
                <tbody>
                  {periodsAsc.map((p) => (
                    <tr key={p.key} className="border-b last:border-0">
                      <td className="py-2 pr-4 font-medium text-gray-900">{periodLabel(p)}</td>
                      <td className="py-2 px-3 text-right tabular-nums">{thousands(p.discount_amount)}</td>
                      <td className="py-2 px-3 text-right tabular-nums">{pct(p.discount_of_gross_pct)}</td>
                      <td className="py-2 px-3 text-right tabular-nums text-muted-foreground">
                        {thousands(p.last_year?.discount_amount)}
                      </td>
                      <td className="py-2 pl-3 text-right tabular-nums text-muted-foreground">
                        {pct(p.last_year?.discount_of_gross_pct)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="text-[11px] text-muted-foreground mt-3">{SHOPIFY_GROSS_EXCL_VAT_NOTE}</p>
            </CardContent>
          </Card>
          {view === 'week' && latestWeek ? (
            <ByTypeCard
              title="Discount Types – Weekly"
              period={latestWeek}
              extraNote={periodLabel(latestWeek)}
              testId="discount-types-weekly"
            />
          ) : null}
          {view === 'month' && monthLayout.primary ? (
            <ByTypeCard
              title="Discount Types – Monthly"
              period={monthLayout.primary}
              extraNote={`${periodLabel(monthLayout.primary)} vs same month last year`}
              testId="discount-types-last-full-month"
            />
          ) : null}
          {view === 'month' && monthLayout.mtd ? (
            <ByTypeCard
              title={`${periodLabel(monthLayout.mtd)} month-to-date`}
              period={monthLayout.mtd}
              extraNote={`${monthLayout.mtd.start} → ${monthLayout.mtd.end}`}
              testId="discount-types-mtd"
            />
          ) : null}
        </>
      ) : null}
    </div>
  )
}
