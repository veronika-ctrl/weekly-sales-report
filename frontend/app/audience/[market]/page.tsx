'use client'

import { useParams } from 'next/navigation'
import { useEffect, useMemo, useState } from 'react'
import { useDataCache } from '@/contexts/DataCacheContext'
import { useChartAnimations } from '@/contexts/ChartSettingsContext'
import { Maximize2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import Link from 'next/link'
import {
  allocateAudienceBudgetToMarket,
  getMonthlyAmerPlanFromBudget,
  resolveAudienceBudgetForWeek,
  type AudienceBudgetMetrics,
} from '@/lib/audienceBudgetSeries'
import {
  getAudienceBudgetSeries,
  getAudienceMetricsPerCountry,
  type AudienceMetricsCountryData,
  type AudienceMetricsPerCountryResponse,
  type BudgetGeneralResponse,
} from '@/lib/api'
import { AudienceMetricsChartGrid } from '@/components/audience/AudienceMetricsChartGrid'
import { AudienceSlideView } from '@/components/audience/AudienceSlideView'
import ReportLoadState from '@/components/ReportLoadState'
import { normalizeNamedSeries, useWeekSeriesLoad } from '@/lib/week-series-load'

function budgetGeneralUsable(b: BudgetGeneralResponse | null | undefined): boolean {
  return Boolean(b && !b.error && b.table && Object.keys(b.table).length > 0)
}

const SLUG_TO_NAME: Record<string, string> = {
  sweden: 'Sweden',
  uk: 'United Kingdom',
  'united-kingdom': 'United Kingdom',
  usa: 'United States',
  'united-states': 'United States',
  germany: 'Germany',
  france: 'France',
  canada: 'Canada',
  australia: 'Australia',
  switzerland: 'Switzerland',
  uae: 'UAE',
  row: 'ROW',
}

function slugToMarketName(slug: string): string {
  const normalized = (slug || '').toLowerCase().replace(/\s+/g, '-')
  return SLUG_TO_NAME[normalized] ?? slug.replace(/-/g, ' ')
}

type AudienceMarketRow = {
  week: string
  weekLabel: string
  last_year?: AudienceMetricsCountryData['last_year']
} & AudienceMetricsCountryData

export default function AudienceMarketPage() {
  const params = useParams()
  const slug = typeof params?.market === 'string' ? params.market : ''
  const marketName = slugToMarketName(slug)
  const { baseWeek, budget_general } = useDataCache()
  const chartAnimationsEnabled = useChartAnimations()
  const isAnimationActive = chartAnimationsEnabled
  const [slideView, setSlideView] = useState(false)
  const [serverAudienceBudgetByWeek, setServerAudienceBudgetByWeek] = useState<Record<
    string,
    Record<string, number> | null
  > | null>(null)

  const { data, loading, error, retry } = useWeekSeriesLoad<AudienceMetricsPerCountryResponse>({
    baseWeek,
    load: (week) => getAudienceMetricsPerCountry(week, 8),
    cached: null,
    hasRows: (payload) =>
      normalizeNamedSeries(payload, 'audience_metrics_per_country').length > 0,
  })

  useEffect(() => {
    if (!baseWeek) {
      setServerAudienceBudgetByWeek(null)
      return
    }
    let cancelled = false
    getAudienceBudgetSeries(baseWeek, 8)
      .then((res) => {
        if (cancelled) return
        const m: Record<string, Record<string, number> | null> = {}
        for (const row of res.weeks || []) {
          m[row.week] = row.budget
        }
        setServerAudienceBudgetByWeek(m)
      })
      .catch(() => {
        if (!cancelled) setServerAudienceBudgetByWeek(null)
      })
    return () => {
      cancelled = true
    }
  }, [baseWeek])

  const effectiveBudgetGeneral = useMemo(() => {
    return budgetGeneralUsable(budget_general) ? budget_general : null
  }, [budget_general])

  const weeksRaw = useMemo(
    () =>
      normalizeNamedSeries<{ week: string; countries: Record<string, AudienceMetricsCountryData> }>(
        data,
        'audience_metrics_per_country',
      ),
    [data],
  )

  const resolvedCountryKey = useMemo(() => {
    const firstWeek = weeksRaw[0]
    const countryKeys = firstWeek ? Object.keys(firstWeek.countries || {}) : []
    const nameMatch = countryKeys.find(
      (c) =>
        c.toLowerCase() === marketName.toLowerCase() ||
        c.toLowerCase().replace(/\s+/g, '-') === (slug || '').toLowerCase(),
    )
    return nameMatch || marketName
  }, [weeksRaw, marketName, slug])

  const audienceData = useMemo(() => {
    return weeksRaw
      .map((w) => {
        const c = w.countries[resolvedCountryKey] || w.countries[marketName]
        if (!c) return null
        return {
          week: w.week,
          weekLabel: `W${w.week.split('-')[1]}`,
          ...c,
          last_year: c.last_year ?? null,
        }
      })
      .filter(Boolean) as AudienceMarketRow[]
  }, [weeksRaw, resolvedCountryKey, marketName])

  const monthlyAmerPlan = useMemo(
    () =>
      baseWeek
        ? getMonthlyAmerPlanFromBudget(baseWeek, serverAudienceBudgetByWeek, effectiveBudgetGeneral)
        : null,
    [baseWeek, serverAudienceBudgetByWeek, effectiveBudgetGeneral],
  )

  const audienceSeriesWithBudget = useMemo(() => {
    if (!audienceData.length) return []
    const weekToRow = new Map(weeksRaw.map((x) => [x.week, x] as const))
    return audienceData.map((row) => {
      const w = weekToRow.get(row.week)
      const total = w?.countries?.Total
      const country = resolvedCountryKey ? w?.countries?.[resolvedCountryKey] : undefined
      const g = resolveAudienceBudgetForWeek(row.week, effectiveBudgetGeneral, serverAudienceBudgetByWeek)
      let budget =
        g && total && country
          ? allocateAudienceBudgetToMarket(g as AudienceBudgetMetrics, country, total)
          : null
      if (budget && monthlyAmerPlan != null) {
        budget = { ...budget, amer: monthlyAmerPlan }
      }
      return { ...row, budget }
    })
  }, [
    audienceData,
    weeksRaw,
    effectiveBudgetGeneral,
    resolvedCountryKey,
    serverAudienceBudgetByWeek,
    monthlyAmerPlan,
  ])

  const hasData = audienceSeriesWithBudget.length > 0

  return (
    <div className="space-y-8">
      {(loading || error || !hasData) && (
        <ReportLoadState
          loading={loading}
          error={error}
          empty={!hasData}
          onRetry={retry}
          loadingTitle={`Loading audience metrics for ${marketName}`}
          loadingHint="Reading Qlik and DEMA by country. Large exports can take a few minutes."
          emptyHint={`No audience metrics for ${marketName} this week. Upload Qlik (online sales by country) and DEMA in Settings, then open this page again.`}
        />
      )}
      {hasData && (
        <>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-lg font-semibold text-gray-900">Audience — {marketName}</h2>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-8 text-xs gap-1.5"
              onClick={() => setSlideView(true)}
            >
              <Maximize2 className="h-3.5 w-3.5" />
              Slide view
            </Button>
          </div>
          <p className="text-xs text-muted-foreground mb-3">
            Same layout as Audience Total. Hover a point for this year and last year values.{' '}
            <Link href="/audience-total" className="text-primary hover:underline">
              ← Back to Audience Total
            </Link>
          </p>
          <AudienceMetricsChartGrid series={audienceSeriesWithBudget} isAnimationActive={isAnimationActive} compact />
          <AudienceSlideView title={`Audience — ${marketName}`} open={slideView} onClose={() => setSlideView(false)}>
            <AudienceMetricsChartGrid series={audienceSeriesWithBudget} isAnimationActive={false} compact />
          </AudienceSlideView>
        </>
      )}
    </div>
  )
}
