'use client'

import type { FullPriceExclExchangesResponse } from '@/lib/api'
import type { SectionViewState } from '@/lib/full-price-vs-sale-load'
import {
  buildBeforeAfterSeries,
  buildDiscountShareChartData,
  periodVsLatest,
  type BeforeAfterView,
} from '@/lib/full-price-before-after-series'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ChartConfig, ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart'
import { Bar, BarChart, CartesianGrid, LabelList, Legend, ReferenceLine, XAxis, YAxis } from '@/lib/recharts'

const shareConfig = {
  exchange: { label: 'Exchange credits', color: '#F97316' },
  promotional: { label: 'Promotional markdowns', color: '#4B5563' },
} satisfies ChartConfig

const pct = (value: number | null | undefined) =>
  value == null ? '–' : `${value.toFixed(1)}%`

const SHARE_SUBTITLE =
  'AfterShip size-swap custom discount is not a promo; this is exchange credits ÷ all-orders discount.'

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
  const periodNote = periodVsLatest(data, view)
  const grain = view === 'week' ? 'week' : 'month'
  const periodShare = periodNote?.exchangeDiscountSharePct ?? null
  const latestShare = series[series.length - 1]?.exchangeDiscountSharePct ?? null
  const latestDiffers =
    latestShare != null && periodShare != null && Math.abs(latestShare - periodShare) >= SHARE_PP_EPS

  if (state !== 'ready' || chartData.length === 0) return null

  return (
    <Card data-testid="exchange-discount-share-chart">
      <CardHeader>
        <CardTitle className="text-sm font-medium">
          Share of recorded discount that is AfterShip exchange credits
        </CardTitle>
        <p className="text-xs text-muted-foreground">{SHARE_SUBTITLE}</p>
      </CardHeader>
      <CardContent className="overflow-visible space-y-3">
        <ChartContainer config={shareConfig} className="h-[280px] w-full min-w-0 overflow-visible">
          <BarChart data={chartData} margin={{ top: 36, right: 12, left: 12, bottom: 8 }} barCategoryGap="18%">
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="label" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} width={48} domain={[0, 100]} tickFormatter={(v: number) => `${v}%`} />
            <ChartTooltip content={<ChartTooltipContent formatter={(v: unknown) => pct(Number(v ?? 0))} />} />
            <Legend />
            {periodShare != null && (
              <ReferenceLine
                y={periodShare}
                stroke="#9A3412"
                strokeDasharray="4 3"
                ifOverflow="extendDomain"
                label={{
                  value: `Period ${pct(periodShare)}`,
                  position: 'insideBottomLeft',
                  fontSize: 11,
                  fill: '#9A3412',
                }}
              />
            )}
            <Bar
              dataKey="exchange"
              stackId="share"
              fill="#F97316"
              name="Exchange credits"
              isAnimationActive={isAnimationActive}
            />
            <Bar
              dataKey="promotional"
              stackId="share"
              fill="#4B5563"
              name="Promotional markdowns"
              isAnimationActive={isAnimationActive}
            >
              <LabelList dataKey="exchange" position="top" content={ExchangeShareLabel} />
            </Bar>
          </BarChart>
        </ChartContainer>
        <p className="text-xs text-muted-foreground leading-relaxed">
          Each {grain} is stacked to 100% of that {grain}&apos;s recorded discount (orange = AfterShip credits, gray =
          promotional). The dashed line is the <strong>window total</strong>
          {periodShare != null ? ` (${pct(periodShare)})` : ''}
          {periodNote ? `, ${periodNote.periodStart} → ${periodNote.periodEnd}` : ''} — not the latest {grain} alone
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
  )
}
