'use client'

import type { FullPriceExclExchangesResponse } from '@/lib/api'
import type { SectionViewState } from '@/lib/full-price-vs-sale-load'
import {
  buildBeforeAfterSeries,
  mixIsEssentiallyFlat,
  periodVsLatest,
  type BeforeAfterView,
} from '@/lib/full-price-before-after-series'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ChartConfig, ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart'
import { Bar, BarChart, CartesianGrid, LabelList, Legend, Line, LineChart, XAxis, YAxis } from '@/lib/recharts'
import { Loader2 } from 'lucide-react'

const shareConfig = {
  before: { label: 'Including exchanges', color: '#4B5563' },
  after: { label: 'Excluding exchanges', color: '#0F766E' },
} satisfies ChartConfig

const splitConfig = {
  fullIncl: { label: 'Full price · including', color: '#4B5563' },
  discIncl: { label: 'Discounted · including', color: '#F97316' },
  fullExcl: { label: 'Full price · excluding', color: '#0F766E' },
  discExcl: { label: 'Discounted · excluding', color: '#FBBF24' },
} satisfies ChartConfig

const thousands = (value: number | null | undefined) =>
  Math.round((value || 0) / 1000).toLocaleString('sv-SE')

const pct = (value: number | null | undefined) =>
  value == null ? '–' : `${value.toFixed(1)}%`

const SHARE_FORMULA =
  'Before (gray) = all-orders Full Price ÷ Total, AfterShip size-swaps included. After (teal) = excl. export Full Price ÷ Total — those orders are dropped, not reclassified as full price. AfterShip custom discount is a size-swap credit, not a promo.'

export default function FullPriceBeforeAfterCharts({
  view,
  weekly,
  monthly,
  state,
  error,
  isAnimationActive,
  showPeriodCallout = false,
}: {
  view: BeforeAfterView
  weekly: FullPriceExclExchangesResponse | null
  monthly: FullPriceExclExchangesResponse | null
  state: SectionViewState
  error: string | null
  isAnimationActive: boolean
  showPeriodCallout?: boolean
}) {
  const data = view === 'week' ? weekly : monthly
  const series = buildBeforeAfterSeries(data, view)
  const periodNote = periodVsLatest(data, view)
  const mixFlat = mixIsEssentiallyFlat(series)
  const grain = view === 'week' ? 'week' : 'month'

  if (state === 'loading') {
    return (
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6" data-testid="fp-before-after-loading">
        <Card>
          <CardContent className="flex h-[280px] items-center gap-3 text-sm text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin text-primary" />
            Loading including vs excluding series…
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex h-[280px] items-center gap-3 text-sm text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin text-primary" />
            Loading including vs excluding split…
          </CardContent>
        </Card>
      </div>
    )
  }

  if (state === 'error') {
    return (
      <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        {error || 'Could not load including vs excluding charts.'}
      </div>
    )
  }

  if (state !== 'ready' || series.length === 0) return null

  const shareData = series.map((p) => ({
    label: p.label,
    before: p.before,
    after: p.after,
  }))
  const splitData = series.map((p) => ({
    label: p.label,
    fullIncl: p.fullIncl ?? 0,
    discIncl: p.discIncl ?? 0,
    fullExcl: p.fullExcl,
    discExcl: p.discExcl,
  }))

  return (
    <div className="space-y-4" data-testid="fp-before-after-charts">
      {showPeriodCallout && periodNote?.latestDiffersFromPeriod && (
        <div
          className="rounded-md border border-sky-200 bg-sky-50/80 p-4 text-sm text-sky-950"
          data-testid="fp-period-vs-latest"
        >
          <p className="font-medium">Window mix vs latest {grain}</p>
          <p className="text-xs mt-1 leading-relaxed">
            The period bars use the whole window ({periodNote.periodStart} → {periodNote.periodEnd}):{' '}
            <strong>{pct(periodNote.periodBefore)}</strong> full price including exchanges. {periodNote.latestLabel}{' '}
            alone is <strong>{pct(periodNote.latestBefore)}</strong> including / {pct(periodNote.latestAfter)} excluding.
            Those are different questions — a {grain}ly point is not the {view === 'week' ? '8-week' : '13-month'}{' '}
            average.
          </p>
        </div>
      )}

      {mixFlat && (
        <div
          className="rounded-md border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950"
          data-testid="fp-mix-flat-callout"
        >
          <p className="font-medium">Full-price share of net barely moves after excluding exchanges</p>
          <p className="text-xs mt-1 leading-relaxed">
            AfterShip size-swaps open a new order with a custom discount so the customer is not charged twice. Net on
            that order is ≈ 0 (gross offset by the credit), so dropping it leaves remaining Full Price ÷ Total almost
            unchanged. What exchanges distort is <strong>discount amount</strong>
            {periodNote?.exchangeDiscountSharePct != null ? (
              <>
                {' '}
                ({pct(periodNote.exchangeDiscountSharePct)} of recorded markdowns in this window)
              </>
            ) : null}
            , not the net mix. The teal series is the excl. file as uploaded — it is not reclassified as full price.
          </p>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">
              Full price share % — including vs excluding exchanges
            </CardTitle>
            <p className="text-xs text-muted-foreground">{SHARE_FORMULA}</p>
          </CardHeader>
          <CardContent className="overflow-visible">
            <ChartContainer config={shareConfig} className="h-[280px] w-full min-w-0 overflow-visible">
              <LineChart data={shareData} margin={{ top: 36, right: 12, left: 12, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} width={48} />
                <ChartTooltip content={<ChartTooltipContent formatter={(v: unknown) => pct(Number(v ?? 0))} />} />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="before"
                  stroke="#4B5563"
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  isAnimationActive={isAnimationActive}
                  name="Including exchanges"
                />
                <Line
                  type="monotone"
                  dataKey="after"
                  stroke="#0F766E"
                  strokeWidth={2}
                  strokeDasharray="5 3"
                  dot={{ r: 3 }}
                  isAnimationActive={isAnimationActive}
                  name="Excluding exchanges"
                >
                  <LabelList
                    position="top"
                    offset={10}
                    fontSize={12}
                    fontWeight={600}
                    fill="#115E59"
                    formatter={(v: unknown) => pct(Number(v ?? 0))}
                  />
                </Line>
              </LineChart>
            </ChartContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">
              Net sales split (SEK &apos;000) — including vs excluding exchanges
            </CardTitle>
            <p className="text-xs text-muted-foreground">
              Grouped stacks per {grain}: left = including exchanges (gray / orange), right = excluding (teal / gold).
              Totals look similar when exchange net is ~0; share formula is Full Price ÷ Total on each stack.
            </p>
          </CardHeader>
          <CardContent className="overflow-visible">
            <ChartContainer config={splitConfig} className="h-[280px] w-full min-w-0 overflow-visible">
              <BarChart data={splitData} margin={{ top: 16, right: 12, left: 12, bottom: 8 }} barGap={2} barCategoryGap="18%">
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} width={48} tickFormatter={(v: number) => thousands(v)} />
                <ChartTooltip content={<ChartTooltipContent formatter={(v: unknown) => thousands(Number(v ?? 0))} />} />
                <Legend />
                <Bar
                  dataKey="fullIncl"
                  stackId="incl"
                  fill="#4B5563"
                  name="Full price · including"
                  isAnimationActive={isAnimationActive}
                />
                <Bar
                  dataKey="discIncl"
                  stackId="incl"
                  fill="#F97316"
                  name="Discounted · including"
                  isAnimationActive={isAnimationActive}
                />
                <Bar
                  dataKey="fullExcl"
                  stackId="excl"
                  fill="#0F766E"
                  name="Full price · excluding"
                  isAnimationActive={isAnimationActive}
                />
                <Bar
                  dataKey="discExcl"
                  stackId="excl"
                  fill="#FBBF24"
                  name="Discounted · excluding"
                  isAnimationActive={isAnimationActive}
                />
              </BarChart>
            </ChartContainer>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
