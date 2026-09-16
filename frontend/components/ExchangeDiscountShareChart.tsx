'use client'

import type { FullPriceExclExchangesResponse } from '@/lib/api'
import type { SectionViewState } from '@/lib/full-price-vs-sale-load'
import {
  buildBeforeAfterSeries,
  buildDiscountedNetTypeChartDataFromPoints,
  buildDiscountShareChartData,
  periodVsLatest,
  type BeforeAfterView,
} from '@/lib/full-price-before-after-series'
import {
  DISCOUNT_AMOUNT_FORMULA,
  DISCOUNT_AMOUNT_SLICES,
  DISCOUNTED_NET_SLICES,
  DISCOUNTED_NET_TYPE_FORMULA,
  chartConfigFromSlices,
} from '@/lib/discount-share'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ChartConfig, ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart'
import { Bar, BarChart, CartesianGrid, LabelList, Legend, ReferenceLine, XAxis, YAxis } from '@/lib/recharts'

const shareConfig = chartConfigFromSlices(DISCOUNT_AMOUNT_SLICES) satisfies ChartConfig
const netTypeConfig = chartConfigFromSlices(DISCOUNTED_NET_SLICES) satisfies ChartConfig

const pct = (value: number | null | undefined) =>
  value == null ? '–' : `${value.toFixed(1)}%`

const SHARE_PP_EPS = 0.15

function ExchangeShareLabel({
  x,
  y,
  width,
  value,
  viewBox,
}: {
  x?: number
  y?: number
  width?: number
  value?: number | string
  viewBox?: { x?: number; y?: number; width?: number }
}) {
  const px = x ?? viewBox?.x
  const py = y ?? viewBox?.y
  const pw = width ?? viewBox?.width
  const n = typeof value === 'number' ? value : Number(value)
  if (px == null || py == null || !Number.isFinite(n)) return null
  return (
    <text x={px + (pw ?? 0) / 2} y={py - 8} textAnchor="middle" fontSize={11} fontWeight={600} fill="#9A3412">
      {pct(n)}
    </text>
  )
}

export default function ExchangeDiscountShareChart({
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
  const chartData = buildDiscountShareChartData(series)
  const netTypeData = buildDiscountedNetTypeChartDataFromPoints(series)
  const periodNote = periodVsLatest(data, view)
  const grain = view === 'week' ? 'week' : 'month'
  const periodShare = periodNote?.exchangeDiscountSharePct ?? null
  const periodPromo = periodNote?.promotionalDiscountSharePct ?? null
  const latestShare = series[series.length - 1]?.exchangeDiscountSharePct ?? null
  const latestDiffers =
    latestShare != null && periodShare != null && Math.abs(latestShare - periodShare) >= SHARE_PP_EPS
  const hasNetTypeMix = netTypeData.some((row) =>
    DISCOUNTED_NET_SLICES.some((s) => Number(row[s.id] ?? 0) > 0),
  )

  if (state !== 'ready' || chartData.length === 0) return null

  const lastSliceId = DISCOUNT_AMOUNT_SLICES[DISCOUNT_AMOUNT_SLICES.length - 1]?.id ?? 'promotional'

  return (
    <div className="space-y-4">
      <Card data-testid="exchange-discount-share-chart">
        <CardHeader>
          <CardTitle className="text-sm font-medium">
            Share of recorded discount amounts — AfterShip vs promotional
          </CardTitle>
          <p className="text-xs text-muted-foreground">{DISCOUNT_AMOUNT_FORMULA}</p>
        </CardHeader>
        <CardContent className="overflow-visible space-y-3">
          {periodNote && (
            <div
              className="rounded-xl border border-orange-200 bg-orange-50 p-4 text-orange-950"
              data-testid="discount-amount-period-callout"
            >
              <p className="text-xs font-medium uppercase tracking-wide text-orange-800/80">
                {periodNote.periodLabel} · 100% of recorded discount $
              </p>
              <p className="mt-2 text-sm leading-snug" data-testid="discount-amount-window-copy">
                Of recorded discount this window:{' '}
                <strong>{pct(periodShare)} AfterShip</strong>,{' '}
                <strong>{pct(periodPromo)} promotional</strong>
              </p>
              <div className="mt-3 flex h-3 overflow-hidden rounded-full bg-white/80 ring-1 ring-orange-200">
                {periodNote.discountShare?.slices.map((slice) => (
                  <div
                    key={slice.id}
                    style={{
                      width: `${Math.max(0, Math.min(100, slice.pct ?? 0))}%`,
                      backgroundColor: slice.color,
                    }}
                  />
                ))}
              </div>
              <p className="mt-2 text-xs text-orange-900/80 leading-relaxed">
                Window total {periodNote.periodStart} → {periodNote.periodEnd}
                {latestDiffers ? (
                  <>
                    {' '}
                    — not {periodNote.latestLabel} alone ({periodNote.latestLabel} is {pct(latestShare)}{' '}
                    AfterShip).
                  </>
                ) : (
                  '.'
                )}{' '}
                Only two discount-$ buckets exist today (Exchange Discount vs Discount Amount). Extra types
                append as named slices of the promotional remainder.
              </p>
            </div>
          )}
          <ChartContainer config={shareConfig} className="h-[280px] w-full min-w-0 overflow-visible">
            <BarChart data={chartData} margin={{ top: 36, right: 12, left: 12, bottom: 8 }} barCategoryGap="18%">
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} width={48} domain={[0, 100]} tickFormatter={(v: number) => `${v}%`} />
              <ChartTooltip content={<ChartTooltipContent formatter={(v: unknown) => pct(Number(v ?? 0))} />} />
              <Legend />
              {periodShare != null && (
                <ReferenceLine y={periodShare} stroke="#9A3412" strokeDasharray="4 3" ifOverflow="extendDomain" />
              )}
              {DISCOUNT_AMOUNT_SLICES.map((slice) => (
                <Bar
                  key={slice.id}
                  dataKey={slice.id}
                  stackId="share"
                  fill={slice.color}
                  name={slice.label}
                  isAnimationActive={isAnimationActive}
                >
                  {slice.id === lastSliceId ? (
                    <LabelList dataKey="exchange" position="top" content={ExchangeShareLabel} />
                  ) : null}
                </Bar>
              ))}
            </BarChart>
          </ChartContainer>
          <p className="text-xs text-muted-foreground leading-relaxed">
            Each {grain} is stacked to 100% of that {grain}&apos;s recorded discount (orange labels = that{' '}
            {grain}&apos;s own AfterShip %). The dashed line is the <strong>window total</strong>
            {periodShare != null ? ` (${pct(periodShare)} AfterShip)` : ''}
            {periodNote ? `, ${periodNote.periodStart} → ${periodNote.periodEnd}` : ''} — not the latest {grain}{' '}
            alone
            {latestDiffers ? (
              <>
                {' '}
                ({periodNote?.latestLabel} is {pct(latestShare)}).
              </>
            ) : (
              '.'
            )}
          </p>
        </CardContent>
      </Card>

      {hasNetTypeMix && (
        <Card data-testid="discounted-net-type-chart">
          <CardHeader>
            <CardTitle className="text-sm font-medium">
              Discounted net by pricing type — sales mix, not discount $
            </CardTitle>
            <p className="text-xs text-muted-foreground">{DISCOUNTED_NET_TYPE_FORMULA}</p>
          </CardHeader>
          <CardContent className="overflow-visible space-y-3">
            <ChartContainer config={netTypeConfig} className="h-[280px] w-full min-w-0 overflow-visible">
              <BarChart data={netTypeData} margin={{ top: 16, right: 12, left: 12, bottom: 8 }} barCategoryGap="18%">
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} width={48} domain={[0, 100]} tickFormatter={(v: number) => `${v}%`} />
                <ChartTooltip content={<ChartTooltipContent formatter={(v: unknown) => pct(Number(v ?? 0))} />} />
                <Legend />
                {DISCOUNTED_NET_SLICES.map((slice) => (
                  <Bar
                    key={slice.id}
                    dataKey={slice.id}
                    stackId="netType"
                    fill={slice.color}
                    name={slice.label}
                    isAnimationActive={isAnimationActive}
                  />
                ))}
              </BarChart>
            </ChartContainer>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Each {grain} is 100% of discounted net on the excl. export (full-price net is omitted). Use this
              when splitting “the others” of promotional <em>sales</em>. Discount Amount stays one promotional
              total until more discount-$ columns exist.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
