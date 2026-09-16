'use client'

import type { FullPriceExclExchangesResponse } from '@/lib/api'
import type { SectionViewState } from '@/lib/full-price-vs-sale-load'
import {
  buildBeforeAfterSeries,
  periodVsLatest,
  type BeforeAfterView,
} from '@/lib/full-price-before-after-series'
import { buildSalesMixChartData, SALES_MIX_FORMULA } from '@/lib/sales-mix'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ChartConfig, ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart'
import { Bar, BarChart, CartesianGrid, LabelList, Legend, XAxis, YAxis } from '@/lib/recharts'
import { Loader2 } from 'lucide-react'
import type { LabelProps } from 'recharts'

const mixConfig = {
  fullPrice: { label: 'Full price', color: '#0F766E' },
  exchange: { label: 'AfterShip exchanges', color: '#EA580C' },
  promo: { label: 'Promotional discount', color: '#94A3B8' },
} satisfies ChartConfig

const pct = (value: number | null | undefined) =>
  value == null ? '–' : `${value.toFixed(1)}%`

function cartesianBox(viewBox: LabelProps['viewBox']) {
  return viewBox && 'x' in viewBox ? viewBox : undefined
}

function ExchangeSliceLabel({ x, y, width, value, viewBox }: LabelProps) {
  const box = cartesianBox(viewBox)
  const px = Number(x ?? box?.x)
  const py = Number(y ?? box?.y)
  const pw = Number(width ?? box?.width)
  const n = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(px) || !Number.isFinite(py) || !Number.isFinite(n) || n <= 0) return null
  return (
    <text
      x={px + (Number.isFinite(pw) ? pw : 0) / 2}
      y={py - 8}
      textAnchor="middle"
      fontSize={11}
      fontWeight={600}
      fill="#9A3412"
    >
      {pct(n)}
    </text>
  )
}

export default function SalesMixChart({
  view,
  weekly,
  monthly,
  state,
  isAnimationActive,
}: {
  view: BeforeAfterView
  weekly: FullPriceExclExchangesResponse | null
  monthly: FullPriceExclExchangesResponse | null
  state: SectionViewState
  isAnimationActive: boolean
}) {
  const data = view === 'week' ? weekly : monthly
  const series = buildBeforeAfterSeries(data, view)
  const chartData = buildSalesMixChartData(
    series.map((p) => ({
      label: p.label,
      exclFull: p.fullExcl,
      exclTotal: p.totalExcl,
      exchangeGross: p.exchangeGross,
    })),
  )
  const periodNote = periodVsLatest(data, view)
  const grain = view === 'week' ? 'week' : 'month'

  if (state === 'loading') {
    return (
      <Card data-testid="sales-mix-chart-loading">
        <CardContent className="flex h-[280px] items-center gap-3 text-sm text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin text-primary" />
          Loading 100% sales mix…
        </CardContent>
      </Card>
    )
  }

  if (state !== 'ready' || chartData.length === 0) return null

  return (
    <Card data-testid="sales-mix-chart">
      <CardHeader>
        <CardTitle className="text-sm font-medium">
          100% sales mix — full price, AfterShip exchanges, promotional discount
        </CardTitle>
        <p className="text-xs text-muted-foreground">{SALES_MIX_FORMULA}</p>
      </CardHeader>
      <CardContent className="overflow-visible space-y-3">
        {periodNote?.salesMix && (
          <div
            className="rounded-xl border border-teal-200 bg-teal-50/80 p-4 text-teal-950"
            data-testid="sales-mix-period-callout"
          >
            <p className="text-xs font-medium uppercase tracking-wide text-teal-800/80">
              {periodNote.periodLabel} · 100% of sales
            </p>
            <div className="mt-2 flex flex-wrap items-end gap-x-6 gap-y-2">
              <div>
                <div className="text-3xl font-semibold tabular-nums tracking-tight">
                  {pct(periodNote.salesMix.fullPricePct)}
                </div>
                <p className="text-xs mt-0.5">full price</p>
              </div>
              <div>
                <div className="text-3xl font-semibold tabular-nums tracking-tight text-orange-700">
                  {pct(periodNote.salesMix.exchangePct)}
                </div>
                <p className="text-xs mt-0.5">AfterShip exchanges</p>
              </div>
              <div>
                <div className="text-3xl font-semibold tabular-nums tracking-tight text-slate-600">
                  {pct(periodNote.salesMix.promoPct)}
                </div>
                <p className="text-xs mt-0.5">promotional discount</p>
              </div>
            </div>
            <div className="mt-3 flex h-3 overflow-hidden rounded-full bg-white/80 ring-1 ring-teal-200">
              <div
                className="bg-teal-700"
                style={{ width: `${Math.max(0, Math.min(100, periodNote.salesMix.fullPricePct ?? 0))}%` }}
              />
              <div
                className="bg-orange-500"
                style={{ width: `${Math.max(0, Math.min(100, periodNote.salesMix.exchangePct ?? 0))}%` }}
              />
              <div
                className="bg-slate-400"
                style={{ width: `${Math.max(0, Math.min(100, periodNote.salesMix.promoPct ?? 0))}%` }}
              />
            </div>
            <p className="mt-2 text-xs text-teal-900/80 leading-relaxed">
              AfterShip is a size-swap, not a promo. Exchange gross is the new-order value; net on those
              orders is ≈ 0 (custom discount is accounting so the customer is not charged twice).
            </p>
          </div>
        )}
        <ChartContainer config={mixConfig} className="h-[280px] w-full min-w-0 overflow-visible">
          <BarChart data={chartData} margin={{ top: 36, right: 12, left: 12, bottom: 8 }} barCategoryGap="18%">
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="label" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} width={48} domain={[0, 100]} tickFormatter={(v: number) => `${v}%`} />
            <ChartTooltip content={<ChartTooltipContent formatter={(v: unknown) => pct(Number(v ?? 0))} />} />
            <Legend />
            <Bar
              dataKey="fullPrice"
              stackId="mix"
              fill="#0F766E"
              name="Full price"
              isAnimationActive={isAnimationActive}
            />
            <Bar
              dataKey="exchange"
              stackId="mix"
              fill="#EA580C"
              name="AfterShip exchanges"
              isAnimationActive={isAnimationActive}
            />
            <Bar
              dataKey="promo"
              stackId="mix"
              fill="#94A3B8"
              name="Promotional discount"
              isAnimationActive={isAnimationActive}
            >
              <LabelList dataKey="exchange" position="top" content={ExchangeSliceLabel} />
            </Bar>
          </BarChart>
        </ChartContainer>
        <p className="text-xs text-muted-foreground leading-relaxed">
          Each {grain} is stacked to 100% of that {grain}&apos;s sales mix (teal = full price, orange =
          AfterShip exchanges, gray = real promotional discount). Orange labels are the exchange slice —
          visible even when exchange net is ~0. This is <strong>share of sales</strong>, not exchange
          credits ÷ recorded discount.
        </p>
      </CardContent>
    </Card>
  )
}
