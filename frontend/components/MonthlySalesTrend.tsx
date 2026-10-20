'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ChartConfig, ChartContainer, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart'
import { CartesianGrid, LabelList, Line, LineChart, XAxis } from '@/lib/recharts'
import { useChartAnimations } from '@/contexts/ChartSettingsContext'
import type { MonthlyTrendPoint } from '@/lib/api'
import { formatSekThousands } from '@/lib/monthly-performance-format'

export default function MonthlySalesTrend({
  title,
  trend,
}: {
  title: string
  trend: MonthlyTrendPoint[]
}) {
  const isAnimationActive = useChartAnimations()
  const chartData = trend.map((p) => ({
    month: p.label,
    current: p.gross_revenue,
    lastYear: p.last_year_gross_revenue,
  }))
  const chartConfig = {
    current: { label: 'This year', color: '#4B5563' },
    lastYear: { label: 'Last year', color: '#F97316' },
  } satisfies ChartConfig

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
        <p className="text-xs text-muted-foreground">SEK ’000 · dashed line is the same month last year</p>
      </CardHeader>
      <CardContent>
        <ChartContainer config={chartConfig} className="h-[260px] w-full">
          <LineChart data={chartData} margin={{ top: 24, left: 12, right: 12 }} isAnimationActive={isAnimationActive}>
            <CartesianGrid vertical={false} />
            <XAxis dataKey="month" tickLine={false} axisLine={false} tickMargin={8} />
            <ChartTooltip cursor={false} content={<ChartTooltipContent indicator="line" />} />
            <Line
              dataKey="current"
              type="monotone"
              stroke="#4B5563"
              strokeWidth={2}
              isAnimationActive={isAnimationActive}
              animationDuration={isAnimationActive ? undefined : 0}
            >
              <LabelList
                position="top"
                offset={10}
                fill="#4B5563"
                fontSize={11}
                formatter={(label: unknown) => formatSekThousands(Number(label ?? 0))}
              />
            </Line>
            <Line
              dataKey="lastYear"
              type="monotone"
              stroke="#F97316"
              strokeWidth={2}
              strokeDasharray="5 5"
              isAnimationActive={isAnimationActive}
              animationDuration={isAnimationActive ? undefined : 0}
            />
          </LineChart>
        </ChartContainer>
      </CardContent>
    </Card>
  )
}
