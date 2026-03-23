'use client'

import { useEffect, useMemo, useState } from 'react'
import { ArrowLeft, Loader2 } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'
import { useDataCache } from '@/contexts/DataCacheContext'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ChartConfig, ChartContainer, ChartTooltip } from '@/components/ui/chart'
import { CartesianGrid, Line, LineChart, XAxis } from '@/lib/recharts'
import { useChartAnimations } from '@/contexts/ChartSettingsContext'
import {
  getDiscountsCategories,
  getDiscountsCategoriesMonthly,
  getDiscountsCategoryCountries,
  getDiscountsCategoryCountriesMonthly,
  getDiscountsCategorySeries,
  getDiscountsMonthlyMetrics,
  getDiscountsSalesYoY,
} from '@/lib/api'
import { Sheet, SheetClose, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Button } from '@/components/ui/button'

export default function ProductsDiscounts() {
  const { baseWeek } = useDataCache()
  const [periods, setPeriods] = useState<any>(null)
  const [timeGranularity, setTimeGranularity] = useState<'week' | 'month'>('week')
  const [dataAll, setDataAll] = useState<any>(null)
  const [dataAllMonthly, setDataAllMonthly] = useState<any>(null)
  const [dataNew, setDataNew] = useState<any>(null)
  const [dataNewMonthly, setDataNewMonthly] = useState<any>(null)
  const [dataReturning, setDataReturning] = useState<any>(null)
  const [dataReturningMonthly, setDataReturningMonthly] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const isAnimationActive = useChartAnimations()
  const [expanded, setExpanded] = useState<
    null | {
      segment: 'all' | 'new' | 'returning'
      mode: 'overall' | 'full_yoy' | 'discounted_yoy' | 'rolling_12m'
      sectionTitle: string
      cardTitle: string
    }
  >(null)
  const [expandedData, setExpandedData] = useState<any>(null)
  const [expandedLoading, setExpandedLoading] = useState(false)
  const [selectedIsoWeek, setSelectedIsoWeek] = useState<string | null>(null)
  const [categoryData, setCategoryData] = useState<any>(null)
  const [categoryLoading, setCategoryLoading] = useState(false)
  const [hoverIsoWeek, setHoverIsoWeek] = useState<string | null>(null)
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const [countryData, setCountryData] = useState<any>(null)
  const [countryLoading, setCountryLoading] = useState(false)
  const [categorySeries, setCategorySeries] = useState<any>(null)

  // Use periods from cache instead of loading automatically (consistent with other Products pages)
  const { periods: cachedPeriods } = useDataCache()
  
  useEffect(() => {
    if (cachedPeriods) {
      setPeriods(cachedPeriods as any)
    }
  }, [cachedPeriods])

  useEffect(() => {
    if (!baseWeek) return
    let cancelled = false
    ;(async () => {
      setLoading(true)
      setError(null)
      try {
        const [all, allMonthly, nw, nwMonthly, ret, retMonthly] = await Promise.all([
          getDiscountsSalesYoY(baseWeek, 8, 'all'),
          // Monthly history for rolling 12 months chart (Overall)
          getDiscountsMonthlyMetrics(baseWeek, 24),
          getDiscountsSalesYoY(baseWeek, 8, 'new'),
          getDiscountsMonthlyMetrics(baseWeek, 24, 'new'),
          getDiscountsSalesYoY(baseWeek, 8, 'returning'),
          getDiscountsMonthlyMetrics(baseWeek, 24, 'returning'),
        ])
        if (!cancelled) {
          setDataAll(all)
          setDataAllMonthly(allMonthly)
          setDataNew(nw)
          setDataNewMonthly(nwMonthly)
          setDataReturning(ret)
          setDataReturningMonthly(retMonthly)
        }
      } catch (e: any) {
        if (!cancelled) setError(e?.message || 'Failed to load discounts data')
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [baseWeek])

  useEffect(() => {
    if (!expanded || !baseWeek) return
    let cancelled = false
    ;(async () => {
      setExpandedLoading(true)
      setSelectedIsoWeek(null)
      setCategoryData(null)
      setSelectedCategory(null)
      setCountryData(null)
      setCategorySeries(null)
      try {
        const res =
          timeGranularity === 'month' || expanded.mode === 'rolling_12m'
            ? await getDiscountsMonthlyMetrics(baseWeek, 0, expanded.segment)
            : await getDiscountsSalesYoY(baseWeek, 8, expanded.segment, true)
        if (!cancelled) setExpandedData(res)
      } catch {
        if (!cancelled) setExpandedData(null)
      } finally {
        if (!cancelled) setExpandedLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [expanded, baseWeek, timeGranularity])

  useEffect(() => {
    if (!expanded || !baseWeek || !selectedIsoWeek) return
    let cancelled = false
    ;(async () => {
      setCategoryLoading(true)
      setSelectedCategory(null)
      setCountryData(null)
      setCategorySeries(null)
      try {
        const res =
          timeGranularity === 'month'
            ? await getDiscountsCategoriesMonthly(baseWeek, selectedIsoWeek, expanded.segment)
            : await getDiscountsCategories(baseWeek, selectedIsoWeek, expanded.segment)
        if (!cancelled) setCategoryData(res)
      } catch (e) {
        if (!cancelled) setCategoryData({ error: 'Failed to load categories', categories: [] })
      } finally {
        if (!cancelled) setCategoryLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [expanded, baseWeek, selectedIsoWeek, timeGranularity])

  useEffect(() => {
    if (!expanded || !baseWeek || !selectedCategory) return
    let cancelled = false
    ;(async () => {
      try {
        const res = await getDiscountsCategorySeries(baseWeek, selectedCategory, expanded.segment, true)
        if (!cancelled) setCategorySeries(res)
      } catch {
        if (!cancelled) setCategorySeries(null)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [expanded, baseWeek, selectedCategory])

  useEffect(() => {
    if (!expanded || !baseWeek || !selectedIsoWeek || !selectedCategory) return
    let cancelled = false
    ;(async () => {
      setCountryLoading(true)
      try {
        const res =
          timeGranularity === 'month'
            ? await getDiscountsCategoryCountriesMonthly(baseWeek, selectedIsoWeek, selectedCategory, expanded.segment)
            : await getDiscountsCategoryCountries(baseWeek, selectedIsoWeek, selectedCategory, expanded.segment)
        if (!cancelled) setCountryData(res)
      } catch (e) {
        if (!cancelled) setCountryData({ error: 'Failed to load countries', countries: [] })
      } finally {
        if (!cancelled) setCountryLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [expanded, baseWeek, selectedIsoWeek, selectedCategory, timeGranularity])

  const toChartData = (data: any) => {
    const weeks = Array.isArray(data?.weeks) ? data.weeks : []
    return weeks.map((w: any) => {
      const weekNum = String(w.week).split('-')[1] || String(w.week)
      return {
        week: `W${weekNum}`,
        discounted: Number(w.discounted || 0),
        full_price: Number(w.full_price || 0),
        discounted_last_year: Number(w.last_year?.discounted || 0),
        full_price_last_year: Number(w.last_year?.full_price || 0),
      }
    })
  }

  const toChartDataMonthly = (monthly: any, keepLast: number = 12) => {
    const months = Array.isArray(monthly?.months) ? monthly.months : []
    const current = monthly?.current || {}
    const lastYear = monthly?.last_year || {}
    if (!months.length) return []
    const asc = [...months].reverse()
    const sliced = keepLast > 0 ? asc.slice(-keepLast) : asc
    return sliced.map((m: string) => ({
      month: m, // YYYY-MM
      discounted: Number(current?.[m]?.net_revenue_sale || 0),
      full_price: Number(current?.[m]?.net_revenue_full_price || 0),
      discounted_last_year: Number(lastYear?.[m]?.net_revenue_sale || 0),
      full_price_last_year: Number(lastYear?.[m]?.net_revenue_full_price || 0),
    }))
  }

  const toChartDataExpanded = (data: any) => {
    const weeks = Array.isArray(data?.weeks) ? data.weeks : []
    return weeks.map((w: any) => {
      return {
        weekIso: String(w.week), // keep full ISO week as key
        weekLabel: `W${String(w.week).split('-')[1] || String(w.week)}`,
        discounted: Number(w.discounted || 0),
        full_price: Number(w.full_price || 0),
        discounted_last_year: Number(w.last_year?.discounted || 0),
        full_price_last_year: Number(w.last_year?.full_price || 0),
        category_net_sales: 0,
      }
    })
  }

  const chartConfig = {
    discounted: { label: 'Discounted', color: '#F97316' },
    full_price: { label: 'Full price', color: '#4B5563' },
    discounted_last_year: { label: 'Discounted (Last year)', color: '#F97316' },
    full_price_last_year: { label: 'Full price (Last year)', color: '#4B5563' },
    discounted_rolling: { label: 'Discounted (Rolling 12m)', color: '#F97316' },
    full_price_rolling: { label: 'Full price (Rolling 12m)', color: '#4B5563' },
  } satisfies ChartConfig

  const formatInt = (v: number) => {
    const n = Number.isFinite(v) ? v : 0
    return new Intl.NumberFormat('sv-SE', { maximumFractionDigits: 0 }).format(Math.round(n))
  }

  const formatGrowth = (current: number, lastYear: number) => {
    const c = Number.isFinite(current) ? current : 0
    const ly = Number.isFinite(lastYear) ? lastYear : 0
    if (ly <= 0) return null
    const pct = Math.round(((c - ly) / ly) * 100)
    const delta = c - ly
    const sign = pct > 0 ? '+' : ''
    const deltaSign = delta > 0 ? '+' : ''
    return `${sign}${pct}% (${deltaSign}${formatInt(delta)})`
  }

  const DiscountsTooltip = ({ active, payload, label, mode, showYear }: any) => {
    if (!active || !payload?.length) return null
    const d = payload?.[0]?.payload || {}
    const raw = String(label ?? d.weekIso ?? d.week ?? d.month ?? '')
    const isMonth = /^\d{4}-\d{2}$/.test(raw)
    const timeLabel = isMonth
      ? new Intl.DateTimeFormat('en-US', { month: 'short', year: 'numeric' }).format(
          new Date(Date.UTC(Number(raw.split('-')[0]), Number(raw.split('-')[1]) - 1, 1))
        )
      : raw.includes('-')
        ? showYear
          ? `${raw.split('-')[0]} W${raw.split('-')[1] || ''}`
          : `W${raw.split('-')[1] || raw}`
        : raw.replace('W', '')
          ? `W${raw.replace('W', '')}`
          : ''

    const full = Number(d.full_price || 0)
    const fullLy = Number(d.full_price_last_year || 0)
    const disc = Number(d.discounted || 0)
    const discLy = Number(d.discounted_last_year || 0)

    const rows =
      mode === 'overall'
        ? [
            { name: 'Full price', value: full, ly: fullLy, color: '#4B5563' },
            { name: 'Discounted', value: disc, ly: discLy, color: '#F97316' },
          ]
        : mode === 'full_yoy'
          ? [{ name: 'Full price', value: full, ly: fullLy, color: '#4B5563' }]
          : [{ name: 'Discounted', value: disc, ly: discLy, color: '#F97316' }]

    return (
      <div className="min-w-[220px] rounded-lg border border-border/50 bg-background px-3 py-2 text-xs shadow-xl">
        <div className="font-medium text-gray-900">{timeLabel}</div>
        <div className="mt-2 space-y-2">
          {rows.map((r) => {
            const growth = formatGrowth(r.value, r.ly)
            return (
              <div key={r.name} className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2">
                  <span className="mt-1 inline-block h-2 w-2 rounded-sm" style={{ background: r.color }} />
                  <div className="text-muted-foreground">{r.name}</div>
                </div>
                <div className="text-right">
                  <div className="font-mono font-medium tabular-nums text-gray-900">
                    {formatInt(r.value)}
                  </div>
                  <div className="font-mono tabular-nums text-gray-600">
                    LY {formatInt(r.ly)}
                  </div>
                  {growth && (
                    <div
                      className={`font-mono tabular-nums ${
                        growth.startsWith('+') ? 'text-green-700' : growth.startsWith('-') ? 'text-red-700' : 'text-gray-600'
                      }`}
                    >
                      YoY {growth}
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    )
  }

  const Rolling12Tooltip = ({ active, payload, label }: any) => {
    if (!active || !payload?.length) return null
    const d = payload?.[0]?.payload || {}
    const raw = String(label ?? d.month ?? '')
    const monthLabel = raw
      ? new Intl.DateTimeFormat('en-US', { month: 'short', year: 'numeric' }).format(
          new Date(Date.UTC(Number(raw.split('-')[0]), Number(raw.split('-')[1]) - 1, 1))
        )
      : ''
    const full = Number(d.full_price_rolling || 0)
    const disc = Number(d.discounted_rolling || 0)
    return (
      <div className="min-w-[220px] rounded-lg border border-border/50 bg-background px-3 py-2 text-xs shadow-xl">
        <div className="font-medium text-gray-900">{monthLabel}</div>
        <div className="mt-2 space-y-1">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-gray-700">
              <span className="inline-block h-2 w-2 rounded-full" style={{ background: '#4B5563' }} />
              Full price (rolling 12m)
            </div>
            <div className="font-mono tabular-nums text-gray-900">{formatInt(full)}</div>
          </div>
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-gray-700">
              <span className="inline-block h-2 w-2 rounded-full" style={{ background: '#F97316' }} />
              Discounted (rolling 12m)
            </div>
            <div className="font-mono tabular-nums text-gray-900">{formatInt(disc)}</div>
          </div>
        </div>
      </div>
    )
  }

  const rolling12AllChartData = useMemo(() => {
    const months = Array.isArray(dataAllMonthly?.months) ? dataAllMonthly.months : []
    const current = dataAllMonthly?.current || {}
    if (months.length === 0) return []

    // API returns months in descending order (latest -> oldest). Build ascending for rolling sums.
    const asc = [...months].reverse()

    const window = 12
    const q: Array<{ disc: number; full: number }> = []
    let sumDisc = 0
    let sumFull = 0

    const out = asc.map((m: string) => {
      const row = current?.[m] || {}
      // Discounted = sale (matches how the weekly charts define discounted vs full price)
      const disc = Number(row.net_revenue_sale || 0)
      const full = Number(row.net_revenue_full_price || 0)
      q.push({ disc, full })
      sumDisc += disc
      sumFull += full
      if (q.length > window) {
        const removed = q.shift()!
        sumDisc -= removed.disc
        sumFull -= removed.full
      }
      return {
        month: m,
        discounted_rolling: sumDisc,
        full_price_rolling: sumFull,
      }
    })

    // Keep only complete rolling windows and show last 12 months of rolling points for readability.
    const complete = out.slice(window - 1)
    return complete.slice(-12)
  }, [dataAllMonthly])

  const rolling12NewChartData = useMemo(() => {
    const months = Array.isArray(dataNewMonthly?.months) ? dataNewMonthly.months : []
    const current = dataNewMonthly?.current || {}
    if (months.length === 0) return []
    const asc = [...months].reverse()
    const window = 12
    const q: Array<{ disc: number; full: number }> = []
    let sumDisc = 0
    let sumFull = 0
    const out = asc.map((m: string) => {
      const row = current?.[m] || {}
      const disc = Number(row.net_revenue_sale || 0)
      const full = Number(row.net_revenue_full_price || 0)
      q.push({ disc, full })
      sumDisc += disc
      sumFull += full
      if (q.length > window) {
        const removed = q.shift()!
        sumDisc -= removed.disc
        sumFull -= removed.full
      }
      return { month: m, discounted_rolling: sumDisc, full_price_rolling: sumFull }
    })
    return out.slice(window - 1).slice(-12)
  }, [dataNewMonthly])

  const rolling12ReturningChartData = useMemo(() => {
    const months = Array.isArray(dataReturningMonthly?.months) ? dataReturningMonthly.months : []
    const current = dataReturningMonthly?.current || {}
    if (months.length === 0) return []
    const asc = [...months].reverse()
    const window = 12
    const q: Array<{ disc: number; full: number }> = []
    let sumDisc = 0
    let sumFull = 0
    const out = asc.map((m: string) => {
      const row = current?.[m] || {}
      const disc = Number(row.net_revenue_sale || 0)
      const full = Number(row.net_revenue_full_price || 0)
      q.push({ disc, full })
      sumDisc += disc
      sumFull += full
      if (q.length > window) {
        const removed = q.shift()!
        sumDisc -= removed.disc
        sumFull -= removed.full
      }
      return { month: m, discounted_rolling: sumDisc, full_price_rolling: sumFull }
    })
    return out.slice(window - 1).slice(-12)
  }, [dataReturningMonthly])

  const rolling12ExpandedChartData = useMemo(() => {
    if (!expanded || expanded.mode !== 'rolling_12m') return []
    const months = Array.isArray(expandedData?.months) ? expandedData.months : []
    const current = expandedData?.current || {}
    if (months.length === 0) return []

    // API returns months in descending order (latest -> oldest). Build ascending for rolling sums.
    const asc = [...months].reverse()

    const window = 12
    const q: Array<{ disc: number; full: number }> = []
    let sumDisc = 0
    let sumFull = 0

    const out = asc.map((m: string) => {
      const row = current?.[m] || {}
      const disc = Number(row.net_revenue_sale || 0)
      const full = Number(row.net_revenue_full_price || 0)
      q.push({ disc, full })
      sumDisc += disc
      sumFull += full
      if (q.length > window) {
        const removed = q.shift()!
        sumDisc -= removed.disc
        sumFull -= removed.full
      }
      return { month: m, discounted_rolling: sumDisc, full_price_rolling: sumFull }
    })

    // Only keep complete rolling windows; in full-screen show as far back as we can.
    return out.slice(window - 1)
  }, [expanded, expandedData])

  const ClickableWeekDot = (props: any) => {
    const { cx, cy, payload } = props || {}
    const iso = payload?.weekIso
    if (cx == null || cy == null || !iso) return null
    return (
      <circle
        cx={cx}
        cy={cy}
        r={6}
        fill="#111827"
        fillOpacity={0.08}
        stroke="#111827"
        strokeOpacity={0.12}
        style={{ cursor: 'pointer' }}
        onClick={(e: any) => {
          e?.stopPropagation?.()
          setSelectedIsoWeek(String(iso))
        }}
      />
    )
  }

  const ClickableMonthDot = (props: any) => {
    const { cx, cy, payload } = props || {}
    const month = payload?.month
    if (cx == null || cy == null || !month) return null
    return (
      <circle
        cx={cx}
        cy={cy}
        r={6}
        fill="#111827"
        fillOpacity={0.08}
        stroke="#111827"
        strokeOpacity={0.12}
        style={{ cursor: 'pointer' }}
        onClick={(e: any) => {
          e?.stopPropagation?.()
          setSelectedIsoWeek(String(month))
        }}
      />
    )
  }

  const Section = ({
    title,
    data,
    monthly,
    segment,
  }: {
    title: string
    data: any
    monthly: any
    segment: 'all' | 'new' | 'returning'
  }) => {
    const chartData = timeGranularity === 'month' ? toChartDataMonthly(monthly, 12) : toChartData(data)
    const seg = segment
    const rollingData =
      seg === 'all' ? rolling12AllChartData : seg === 'new' ? rolling12NewChartData : rolling12ReturningChartData
    const xKey = timeGranularity === 'month' ? 'month' : 'week'
    const xTick = (value: any) => {
      const s = String(value || '')
      if (timeGranularity === 'month') {
        const [y, m] = s.split('-').map(Number)
        if (!y || !m) return s
        return new Intl.DateTimeFormat('en-US', { month: 'short' }).format(new Date(Date.UTC(y, m - 1, 1)))
      }
      return s.replace('W', '')
    }
    return (
      <div className="space-y-3">
        <div className="text-sm font-semibold text-gray-900">{title}</div>
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <Card
            role="button"
            tabIndex={0}
            className="cursor-pointer transition-shadow hover:shadow-md"
            onClick={() => setExpanded({ segment: seg, mode: 'overall', sectionTitle: title, cardTitle: 'Discounted vs full price sales' })}
          >
            <CardHeader>
              <CardTitle>Discounted vs full price sales</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {!loading && !error && data?.error && (
                <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                  {data.error}. Please upload the Discounts file for week <span className="font-mono">{baseWeek}</span>.
                  {data?.detected?.columns && (
                    <div className="mt-2">
                      <div className="font-medium">Detected columns:</div>
                      <div className="font-mono text-xs break-words">{String(data.detected.columns)}</div>
                    </div>
                  )}
                </div>
              )}
              {!loading && !error && chartData.length > 0 && (
                <ChartContainer config={chartConfig}>
                  <LineChart accessibilityLayer data={chartData} margin={{ top: 20, left: 12, right: 12 }}>
                    <CartesianGrid vertical={false} />
                    <XAxis
                      dataKey={xKey}
                      tickLine={false}
                      axisLine={false}
                      tickMargin={8}
                      tickFormatter={xTick}
                    />
                    <ChartTooltip cursor={false} content={<DiscountsTooltip mode="overall" />} />
                    <Line
                      dataKey="full_price"
                      type="natural"
                      stroke="#4B5563"
                      strokeWidth={2}
                      isAnimationActive={isAnimationActive}
                      animationDuration={isAnimationActive ? undefined : 0}
                    />
                    <Line
                      dataKey="discounted"
                      type="natural"
                      stroke="#F97316"
                      strokeWidth={2}
                      isAnimationActive={isAnimationActive}
                      animationDuration={isAnimationActive ? undefined : 0}
                    />
                  </LineChart>
                </ChartContainer>
              )}
            </CardContent>
          </Card>

          <Card
            role="button"
            tabIndex={0}
            className="cursor-pointer transition-shadow hover:shadow-md"
            onClick={() => setExpanded({ segment: seg, mode: 'full_yoy', sectionTitle: title, cardTitle: 'Full price sales YoY' })}
          >
            <CardHeader>
              <CardTitle>Full price sales YoY</CardTitle>
            </CardHeader>
            <CardContent>
              {chartData.length > 0 && (
                <ChartContainer config={chartConfig}>
                  <LineChart accessibilityLayer data={chartData} margin={{ top: 20, left: 12, right: 12 }}>
                    <CartesianGrid vertical={false} />
                    <XAxis
                      dataKey={xKey}
                      tickLine={false}
                      axisLine={false}
                      tickMargin={8}
                      tickFormatter={xTick}
                    />
                    <ChartTooltip cursor={false} content={<DiscountsTooltip mode="full_yoy" />} />
                    <Line
                      dataKey="full_price"
                      type="natural"
                      stroke="#4B5563"
                      strokeWidth={2}
                      isAnimationActive={isAnimationActive}
                      animationDuration={isAnimationActive ? undefined : 0}
                    />
                    <Line
                      dataKey="full_price_last_year"
                      type="natural"
                      stroke="#4B5563"
                      strokeWidth={2}
                      strokeDasharray="5 5"
                      isAnimationActive={isAnimationActive}
                      animationDuration={isAnimationActive ? undefined : 0}
                    />
                  </LineChart>
                </ChartContainer>
              )}
            </CardContent>
          </Card>

          <Card
            role="button"
            tabIndex={0}
            className="cursor-pointer transition-shadow hover:shadow-md"
            onClick={() => setExpanded({ segment: seg, mode: 'discounted_yoy', sectionTitle: title, cardTitle: 'Discounted sales YoY' })}
          >
            <CardHeader>
              <CardTitle>Discounted sales YoY</CardTitle>
            </CardHeader>
            <CardContent>
              {chartData.length > 0 && (
                <ChartContainer config={chartConfig}>
                  <LineChart accessibilityLayer data={chartData} margin={{ top: 20, left: 12, right: 12 }}>
                    <CartesianGrid vertical={false} />
                    <XAxis
                      dataKey={xKey}
                      tickLine={false}
                      axisLine={false}
                      tickMargin={8}
                      tickFormatter={xTick}
                    />
                    <ChartTooltip cursor={false} content={<DiscountsTooltip mode="discounted_yoy" />} />
                    <Line
                      dataKey="discounted"
                      type="natural"
                      stroke="#F97316"
                      strokeWidth={2}
                      isAnimationActive={isAnimationActive}
                      animationDuration={isAnimationActive ? undefined : 0}
                    />
                    <Line
                      dataKey="discounted_last_year"
                      type="natural"
                      stroke="#F97316"
                      strokeWidth={2}
                      strokeDasharray="5 5"
                      isAnimationActive={isAnimationActive}
                      animationDuration={isAnimationActive ? undefined : 0}
                    />
                  </LineChart>
                </ChartContainer>
              )}
            </CardContent>
          </Card>

          {/* Rolling 12 months chart (Overall only) */}
          {rollingData.length > 0 && (
            <Card
              role="button"
              tabIndex={0}
              className="lg:col-span-3 cursor-pointer transition-shadow hover:shadow-md"
              onClick={() =>
                setExpanded({
                  segment: seg,
                  mode: 'rolling_12m',
                  sectionTitle: title,
                  cardTitle: 'Rolling 12 months sales (Discounted vs Full price)',
                })
              }
            >
              <CardHeader>
                <CardTitle>Rolling 12 months sales (Discounted vs Full price)</CardTitle>
              </CardHeader>
              <CardContent>
                <ChartContainer config={chartConfig} className="h-56 w-full">
                  <LineChart accessibilityLayer data={rollingData} margin={{ top: 20, left: 12, right: 12 }}>
                    <CartesianGrid vertical={false} />
                    <XAxis
                      dataKey="month"
                      tickLine={false}
                      axisLine={false}
                      tickMargin={8}
                      tickFormatter={(value) => {
                        const raw = String(value || '')
                        const [y, m] = raw.split('-').map(Number)
                        if (!y || !m) return raw
                        return new Intl.DateTimeFormat('en-US', { month: 'short' }).format(new Date(Date.UTC(y, m - 1, 1)))
                      }}
                    />
                    <ChartTooltip cursor={false} content={<Rolling12Tooltip />} />
                    <Line
                      dataKey="full_price_rolling"
                      type="natural"
                      stroke="#4B5563"
                      strokeWidth={2}
                      isAnimationActive={isAnimationActive}
                      animationDuration={isAnimationActive ? undefined : 0}
                    />
                    <Line
                      dataKey="discounted_rolling"
                      type="natural"
                      stroke="#F97316"
                      strokeWidth={2}
                      isAnimationActive={isAnimationActive}
                      animationDuration={isAnimationActive ? undefined : 0}
                    />
                  </LineChart>
                </ChartContainer>
              </CardContent>
            </Card>
          )}
        </div>
        {chartData.length > 0 && (
          <div className="text-xs text-gray-500">
            Latest file: <span className="font-mono">{data?.filename || 'unknown'}</span>. Columns used:{' '}
            <span className="font-mono">
              {data?.columns_used?.date || '?'} | {data?.columns_used?.net_sales || '?'} |{' '}
              {data?.columns_used?.ordinary_price || '?'}
            </span>
            . Values shown in SEK (formatted: {formatInt(123456)}).
          </div>
        )}
      </div>
    )
  }

  const renderExpandedChart = () => {
    if (!expanded) return null
    if (!expandedData) return <div className="text-sm text-gray-600">No data.</div>

    if (expanded.mode === 'rolling_12m') {
      const data = rolling12ExpandedChartData
      if (!data.length) return <div className="text-sm text-gray-600">No data.</div>
      return (
        <ChartContainer config={chartConfig} className="h-[70vh]">
          <LineChart accessibilityLayer data={data} margin={{ top: 20, left: 12, right: 12 }}>
            <CartesianGrid vertical={false} />
            <XAxis
              dataKey="month"
              tickLine={false}
              axisLine={false}
              tickMargin={8}
              tickFormatter={(value) => {
                const raw = String(value || '')
                const [y, m] = raw.split('-').map(Number)
                if (!y || !m) return raw
                return new Intl.DateTimeFormat('en-US', { month: 'short', year: '2-digit' }).format(
                  new Date(Date.UTC(y, m - 1, 1))
                )
              }}
            />
            <ChartTooltip cursor={false} content={<Rolling12Tooltip />} />
            <Line
              dataKey="full_price_rolling"
              type="natural"
              stroke="#4B5563"
              strokeWidth={2}
              dot={false}
              isAnimationActive={isAnimationActive}
            />
            <Line
              dataKey="discounted_rolling"
              type="natural"
              stroke="#F97316"
              strokeWidth={2}
              dot={false}
              isAnimationActive={isAnimationActive}
            />
          </LineChart>
        </ChartContainer>
      )
    }

    // Monthly expanded view (no week drilldowns / category overlays)
    if (timeGranularity === 'month') {
      const chartData = toChartDataMonthly(expandedData, 0)
      if (!chartData.length) return <div className="text-sm text-gray-600">No data.</div>
      const xTick = (value: any) => {
        const s = String(value || '')
        const [y, m] = s.split('-').map(Number)
        if (!y || !m) return s
        return new Intl.DateTimeFormat('en-US', { month: 'short' }).format(new Date(Date.UTC(y, m - 1, 1)))
      }
      return (
        <ChartContainer config={chartConfig} className="h-[70vh]">
          <LineChart accessibilityLayer data={chartData} margin={{ top: 20, left: 12, right: 12 }}>
            <CartesianGrid vertical={false} />
            <XAxis dataKey="month" tickLine={false} axisLine={false} tickMargin={8} tickFormatter={xTick} />
            <ChartTooltip cursor={false} content={<DiscountsTooltip mode={expanded.mode} showYear />} />
            {expanded.mode === 'overall' ? (
              <>
                <Line
                  dataKey="full_price"
                  type="natural"
                  stroke="#4B5563"
                  strokeWidth={2}
                  dot={<ClickableMonthDot />}
                  isAnimationActive={isAnimationActive}
                />
                <Line
                  dataKey="discounted"
                  type="natural"
                  stroke="#F97316"
                  strokeWidth={2}
                  dot={<ClickableMonthDot />}
                  isAnimationActive={isAnimationActive}
                />
              </>
            ) : expanded.mode === 'full_yoy' ? (
              <>
                <Line
                  dataKey="full_price"
                  type="natural"
                  stroke="#4B5563"
                  strokeWidth={2}
                  dot={<ClickableMonthDot />}
                  isAnimationActive={isAnimationActive}
                />
                <Line
                  dataKey="full_price_last_year"
                  type="natural"
                  stroke="#4B5563"
                  strokeWidth={2}
                  strokeDasharray="5 5"
                  dot={false}
                  isAnimationActive={isAnimationActive}
                />
              </>
            ) : (
              <>
                <Line
                  dataKey="discounted"
                  type="natural"
                  stroke="#F97316"
                  strokeWidth={2}
                  dot={<ClickableMonthDot />}
                  isAnimationActive={isAnimationActive}
                />
                <Line
                  dataKey="discounted_last_year"
                  type="natural"
                  stroke="#F97316"
                  strokeWidth={2}
                  strokeDasharray="5 5"
                  dot={false}
                  isAnimationActive={isAnimationActive}
                />
              </>
            )}
          </LineChart>
        </ChartContainer>
      )
    }

    const seriesWeeks = Array.isArray(categorySeries?.weeks) ? categorySeries.weeks : []
    const categoryMap = new Map<string, number>(seriesWeeks.map((w: any) => [String(w.week), Number(w.net_sales || 0)]))
    const chartData = toChartDataExpanded(expandedData).map((row: any) => ({
      ...row,
      category_net_sales: categoryMap.get(String(row.weekIso)) || 0,
    }))
    const xTick = (value: any) => {
      const s = String(value)
      return s.includes('-') ? String(s.split('-')[1] || s) : s.replace('W', '')
    }

    if (!chartData.length) {
      return <div className="text-sm text-gray-600">No data.</div>
    }

    if (expanded.mode === 'overall') {
      return (
        <ChartContainer config={chartConfig} className="h-[70vh]">
          <LineChart
            accessibilityLayer
            data={chartData}
            margin={{ top: 20, left: 12, right: 12 }}
            onMouseMove={(e: any) => {
              const iso = e?.activePayload?.[0]?.payload?.weekIso
              if (iso) setHoverIsoWeek(String(iso))
            }}
            onMouseLeave={() => setHoverIsoWeek(null)}
          >
            <CartesianGrid vertical={false} />
            <XAxis dataKey="weekIso" tickLine={false} axisLine={false} tickMargin={8} tickFormatter={xTick} />
            <ChartTooltip cursor={false} content={<DiscountsTooltip mode="overall" showYear />} />
            <Line
              dataKey="full_price"
              type="natural"
              stroke="#4B5563"
              strokeWidth={2}
              dot={<ClickableWeekDot />}
              isAnimationActive={isAnimationActive}
            />
            <Line
              dataKey="discounted"
              type="natural"
              stroke="#F97316"
              strokeWidth={2}
              dot={<ClickableWeekDot />}
              isAnimationActive={isAnimationActive}
            />
            {selectedCategory && (
              <Line
                dataKey="category_net_sales"
                type="natural"
                stroke="#2563EB"
                strokeWidth={2}
                strokeDasharray="4 4"
                dot={false}
                isAnimationActive={isAnimationActive}
              />
            )}
          </LineChart>
        </ChartContainer>
      )
    }

    if (expanded.mode === 'full_yoy') {
      return (
        <ChartContainer config={chartConfig} className="h-[70vh]">
          <LineChart
            accessibilityLayer
            data={chartData}
            margin={{ top: 20, left: 12, right: 12 }}
            onMouseMove={(e: any) => {
              const iso = e?.activePayload?.[0]?.payload?.weekIso
              if (iso) setHoverIsoWeek(String(iso))
            }}
            onMouseLeave={() => setHoverIsoWeek(null)}
          >
            <CartesianGrid vertical={false} />
            <XAxis dataKey="weekIso" tickLine={false} axisLine={false} tickMargin={8} tickFormatter={xTick} />
            <ChartTooltip cursor={false} content={<DiscountsTooltip mode="full_yoy" showYear />} />
            <Line
              dataKey="full_price"
              type="natural"
              stroke="#4B5563"
              strokeWidth={2}
              dot={<ClickableWeekDot />}
              isAnimationActive={isAnimationActive}
            />
            <Line
              dataKey="full_price_last_year"
              type="natural"
              stroke="#4B5563"
              strokeWidth={2}
              strokeDasharray="5 5"
              dot={false}
              isAnimationActive={isAnimationActive}
            />
            {selectedCategory && (
              <Line
                dataKey="category_net_sales"
                type="natural"
                stroke="#2563EB"
                strokeWidth={2}
                strokeDasharray="4 4"
                dot={false}
                isAnimationActive={isAnimationActive}
              />
            )}
          </LineChart>
        </ChartContainer>
      )
    }

    return (
      <ChartContainer config={chartConfig} className="h-[70vh]">
        <LineChart
          accessibilityLayer
          data={chartData}
          margin={{ top: 20, left: 12, right: 12 }}
          onMouseMove={(e: any) => {
            const iso = e?.activePayload?.[0]?.payload?.weekIso
            if (iso) setHoverIsoWeek(String(iso))
          }}
          onMouseLeave={() => setHoverIsoWeek(null)}
        >
          <CartesianGrid vertical={false} />
          <XAxis dataKey="weekIso" tickLine={false} axisLine={false} tickMargin={8} tickFormatter={xTick} />
          <ChartTooltip cursor={false} content={<DiscountsTooltip mode="discounted_yoy" showYear />} />
          <Line
            dataKey="discounted"
            type="natural"
            stroke="#F97316"
            strokeWidth={2}
            dot={<ClickableWeekDot />}
            isAnimationActive={isAnimationActive}
          />
          <Line
            dataKey="discounted_last_year"
            type="natural"
            stroke="#F97316"
            strokeWidth={2}
            strokeDasharray="5 5"
            dot={false}
            isAnimationActive={isAnimationActive}
          />
          {selectedCategory && (
            <Line
              dataKey="category_net_sales"
              type="natural"
              stroke="#2563EB"
              strokeWidth={2}
              strokeDasharray="4 4"
              dot={false}
              isAnimationActive={isAnimationActive}
            />
          )}
        </LineChart>
      </ChartContainer>
    )
  }

  return (
    <div className="space-y-8">
      {!periods ? (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <Loader2 className="h-6 w-6 animate-spin text-primary" />
            <div>
              <h2 className="text-lg font-semibold text-gray-900">Loading New &amp; Returning</h2>
              <p className="text-sm text-gray-600">Initializing data...</p>
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <Skeleton className="h-40 w-full" />
          </div>
        </div>
      ) : (
        <div className="space-y-8">
          <div className="flex items-center justify-end gap-2">
            <div className="text-xs text-gray-500 mr-2">View:</div>
            <Button
              size="sm"
              variant={timeGranularity === 'week' ? 'default' : 'outline'}
              onClick={() => setTimeGranularity('week')}
            >
              Week
            </Button>
            <Button
              size="sm"
              variant={timeGranularity === 'month' ? 'default' : 'outline'}
              onClick={() => setTimeGranularity('month')}
            >
              Month
            </Button>
          </div>
          {error && (
            <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {loading && (
            <div className="flex items-center gap-2 text-sm text-gray-600">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading discounts…
            </div>
          )}

          <Section title="Overall" data={dataAll} monthly={dataAllMonthly} segment="all" />
          <Section title="New customers" data={dataNew} monthly={dataNewMonthly} segment="new" />
          <Section title="Returning customers" data={dataReturning} monthly={dataReturningMonthly} segment="returning" />
        </div>
      )}

      <Sheet open={!!expanded} onOpenChange={(open) => !open && setExpanded(null)}>
        <SheetContent side="right" className="overflow-y-auto p-6 w-full sm:max-w-none [&_[data-slot=sheet-close]]:hidden">
          {/* Radix Dialog accessibility: Content must have a Title (can be visually hidden). */}
          <SheetHeader className="sr-only">
            <SheetTitle>{expanded?.cardTitle || 'Expanded report'}</SheetTitle>
          </SheetHeader>
          <div className="mx-auto w-full max-w-6xl">
            <div className="mb-4">
              <SheetClose asChild>
                <button
                  type="button"
                  className="inline-flex items-center gap-2 rounded-md border bg-white px-3 py-2 text-sm font-medium text-gray-900 shadow-sm hover:bg-gray-50"
                >
                  <ArrowLeft className="h-5 w-5" />
                  Back to reports
                </button>
              </SheetClose>
            </div>
            <div className="mb-4 text-sm font-semibold text-gray-900">{expanded?.sectionTitle}</div>
            <Card>
              <CardHeader>
                <CardTitle>{expanded?.cardTitle || 'Report'}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {expanded?.mode === 'rolling_12m' || timeGranularity === 'month' ? (
                  <div className="text-xs text-gray-500">
                    Showing history by month (as far back as data exists), up to{' '}
                    <span className="font-mono">{baseWeek}</span>.
                  </div>
                ) : (
                  <div className="text-xs text-gray-500">
                    Showing all available weeks up to <span className="font-mono">{baseWeek}</span>.
                    <span className="ml-2">Hover a week, then click to select it.</span>
                  </div>
                )}
                {expandedLoading ? (
                  <div className="flex items-center gap-2 text-sm text-gray-600">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Loading full history…
                  </div>
                ) : (
                  renderExpandedChart()
                )}

                {timeGranularity === 'week' && expanded?.mode !== 'rolling_12m' && selectedCategory && (
                  <div className="flex items-center gap-2 text-sm text-gray-900">
                    <span className="inline-flex items-center gap-2">
                      <span className="inline-block h-0.5 w-6 bg-blue-600" style={{ borderTop: '2px dashed #2563EB' }} />
                      <span className="text-gray-700">Category overlay:</span>
                      <span className="font-semibold">{selectedCategory}</span>
                    </span>
                  </div>
                )}

                {expanded?.mode !== 'rolling_12m' ? (
                  <div className="pt-2">
                  <div className="text-sm font-semibold text-gray-900">
                    {selectedIsoWeek
                      ? `Categories for ${selectedIsoWeek}`
                      : timeGranularity === 'month'
                        ? 'Click a month to see categories'
                        : 'Click a week to see categories'}
                  </div>
                  {selectedIsoWeek && (
                    <div className="mt-2 rounded-md border bg-white">
                      {categoryLoading ? (
                        <div className="p-3 text-sm text-gray-600 flex items-center gap-2">
                          <Loader2 className="h-4 w-4 animate-spin" />
                          Loading categories…
                        </div>
                      ) : categoryData?.error ? (
                        <div className="p-3 text-sm text-red-700">{String(categoryData.error)}</div>
                      ) : (
                        <div className="max-h-[35vh] overflow-auto">
                          {(() => {
                            const curYear = String(selectedIsoWeek).split('-')[0]
                            const lyYear = categoryData?.comparison_weeks?.last_year?.split?.('-')?.[0] || String(Number(curYear) - 1)
                            const twoYear = categoryData?.comparison_weeks?.two_years_ago?.split?.('-')?.[0] || String(Number(curYear) - 2)
                            return (
                          <table className="w-full text-sm">
                            <thead className="sticky top-0 bg-gray-50">
                              <tr className="border-b">
                                <th className="px-3 py-2 text-left font-medium text-gray-700">Category</th>
                                <th className="px-3 py-2 text-right font-medium text-gray-700">{curYear}</th>
                                <th className="px-3 py-2 text-right font-medium text-gray-700">{lyYear}</th>
                                <th className="px-3 py-2 text-right font-medium text-gray-700">{twoYear}</th>
                                <th className="px-3 py-2 text-right font-medium text-gray-700">YoY</th>
                                <th className="px-3 py-2 text-right font-medium text-gray-700">vs {twoYear}</th>
                              </tr>
                            </thead>
                            <tbody>
                              {(categoryData?.categories || []).map((row: any) => (
                                <tr key={row.category} className="border-b last:border-b-0">
                                  <td className="px-3 py-2 text-gray-900">
                                    <button
                                      type="button"
                                      className="text-left underline-offset-2 hover:underline"
                                      onClick={() => setSelectedCategory(String(row.category))}
                                    >
                                      {row.category}
                                    </button>
                                  </td>
                                  <td className="px-3 py-2 text-right font-mono tabular-nums text-gray-900">
                                    {formatInt(Number(row.net_sales || 0))}
                                  </td>
                                  <td className="px-3 py-2 text-right font-mono tabular-nums text-gray-900">
                                    {formatInt(Number(row.last_year || 0))}
                                  </td>
                                  <td className="px-3 py-2 text-right font-mono tabular-nums text-gray-900">
                                    {formatInt(Number(row.two_years_ago || 0))}
                                  </td>
                                  <td
                                    className={`px-3 py-2 text-right font-mono tabular-nums ${
                                      typeof row.yoy_pct === 'number'
                                        ? row.yoy_pct > 0
                                          ? 'text-green-700'
                                          : row.yoy_pct < 0
                                            ? 'text-red-700'
                                            : 'text-gray-700'
                                        : 'text-gray-500'
                                    }`}
                                  >
                                    {typeof row.yoy_pct === 'number'
                                      ? `${row.yoy_pct > 0 ? '+' : ''}${Math.round(row.yoy_pct)}% (${row.yoy_abs > 0 ? '+' : ''}${formatInt(Number(row.yoy_abs || 0))})`
                                      : '—'}
                                  </td>
                                  <td
                                    className={`px-3 py-2 text-right font-mono tabular-nums ${
                                      typeof row.vs_two_pct === 'number'
                                        ? row.vs_two_pct > 0
                                          ? 'text-green-700'
                                          : row.vs_two_pct < 0
                                            ? 'text-red-700'
                                            : 'text-gray-700'
                                        : 'text-gray-500'
                                    }`}
                                  >
                                    {typeof row.vs_two_pct === 'number'
                                      ? `${row.vs_two_pct > 0 ? '+' : ''}${Math.round(row.vs_two_pct)}% (${row.vs_two_abs > 0 ? '+' : ''}${formatInt(Number(row.vs_two_abs || 0))})`
                                      : '—'}
                                  </td>
                                </tr>
                              ))}
                              {(categoryData?.categories || []).length === 0 && (
                                <tr>
                                  <td className="px-3 py-3 text-gray-600" colSpan={6}>
                                    No categories for this week.
                                  </td>
                                </tr>
                              )}
                            </tbody>
                          </table>
                            )
                          })()}
                        </div>
                      )}
                    </div>
                  )}

                  {selectedIsoWeek && selectedCategory && (
                    <div className="mt-4">
                      <div className="text-sm font-semibold text-gray-900">
                        Countries for “{selectedCategory}” ({selectedIsoWeek})
                      </div>
                      <div className="mt-2 rounded-md border bg-white">
                        {countryLoading ? (
                          <div className="p-3 text-sm text-gray-600 flex items-center gap-2">
                            <Loader2 className="h-4 w-4 animate-spin" />
                            Loading countries…
                          </div>
                        ) : countryData?.error ? (
                          <div className="p-3 text-sm text-red-700">{String(countryData.error)}</div>
                        ) : (
                          <div className="max-h-[35vh] overflow-auto">
                            {(() => {
                              const curYear = String(selectedIsoWeek).split('-')[0]
                              const lyYear =
                                countryData?.comparison_weeks?.last_year?.split?.('-')?.[0] || String(Number(curYear) - 1)
                              const twoYear =
                                countryData?.comparison_weeks?.two_years_ago?.split?.('-')?.[0] || String(Number(curYear) - 2)
                              return (
                                <table className="w-full text-sm">
                                  <thead className="sticky top-0 bg-gray-50">
                                    <tr className="border-b">
                                      <th className="px-3 py-2 text-left font-medium text-gray-700">Country</th>
                                      <th className="px-3 py-2 text-right font-medium text-gray-700">{curYear}</th>
                                      <th className="px-3 py-2 text-right font-medium text-gray-700">{lyYear}</th>
                                      <th className="px-3 py-2 text-right font-medium text-gray-700">{twoYear}</th>
                                      <th className="px-3 py-2 text-right font-medium text-gray-700">YoY</th>
                                      <th className="px-3 py-2 text-right font-medium text-gray-700">vs {twoYear}</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {(countryData?.countries || []).map((r: any) => (
                                      <tr key={r.country} className="border-b last:border-b-0">
                                        <td className="px-3 py-2 text-gray-900">{r.country}</td>
                                        <td className="px-3 py-2 text-right font-mono tabular-nums text-gray-900">
                                          {formatInt(Number(r.net_sales || 0))}
                                        </td>
                                        <td className="px-3 py-2 text-right font-mono tabular-nums text-gray-900">
                                          {formatInt(Number(r.last_year || 0))}
                                        </td>
                                        <td className="px-3 py-2 text-right font-mono tabular-nums text-gray-900">
                                          {formatInt(Number(r.two_years_ago || 0))}
                                        </td>
                                        <td
                                          className={`px-3 py-2 text-right font-mono tabular-nums ${
                                            typeof r.yoy_pct === 'number'
                                              ? r.yoy_pct > 0
                                                ? 'text-green-700'
                                                : r.yoy_pct < 0
                                                  ? 'text-red-700'
                                                  : 'text-gray-700'
                                              : 'text-gray-500'
                                          }`}
                                        >
                                          {typeof r.yoy_pct === 'number'
                                            ? `${r.yoy_pct > 0 ? '+' : ''}${Math.round(r.yoy_pct)}% (${r.yoy_abs > 0 ? '+' : ''}${formatInt(Number(r.yoy_abs || 0))})`
                                            : '—'}
                                        </td>
                                        <td
                                          className={`px-3 py-2 text-right font-mono tabular-nums ${
                                            typeof r.vs_two_pct === 'number'
                                              ? r.vs_two_pct > 0
                                                ? 'text-green-700'
                                                : r.vs_two_pct < 0
                                                  ? 'text-red-700'
                                                  : 'text-gray-700'
                                              : 'text-gray-500'
                                          }`}
                                        >
                                          {typeof r.vs_two_pct === 'number'
                                            ? `${r.vs_two_pct > 0 ? '+' : ''}${Math.round(r.vs_two_pct)}% (${r.vs_two_abs > 0 ? '+' : ''}${formatInt(Number(r.vs_two_abs || 0))})`
                                            : '—'}
                                        </td>
                                      </tr>
                                    ))}
                                    {(countryData?.countries || []).length === 0 && (
                                      <tr>
                                        <td className="px-3 py-3 text-gray-600" colSpan={6}>
                                          No countries for this category/week.
                                        </td>
                                      </tr>
                                    )}
                                  </tbody>
                                </table>
                              )
                            })()}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                  </div>
                ) : null}
              </CardContent>
            </Card>
          </div>
        </SheetContent>
      </Sheet>
    </div>
  )
}


