'use client'

import { useParams } from 'next/navigation'
import { useEffect, useMemo, useState } from 'react'
import { useDataCache } from '@/contexts/DataCacheContext'
import { useChartAnimations } from '@/contexts/ChartSettingsContext'
import { Loader2, Maximize2 } from 'lucide-react'
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
  type BudgetGeneralResponse,
} from '@/lib/api'
import { AudienceMetricsChartGrid } from '@/components/audience/AudienceMetricsChartGrid'
import { AudienceSlideView } from '@/components/audience/AudienceSlideView'

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

export default function AudienceMarketPage() {
  const params = useParams()
  const slug = typeof params?.market === 'string' ? params.market : ''
  const marketName = slugToMarketName(slug)
  const { baseWeek, loading, periods, loadAllData, isDataReady, error, budget_general } = useDataCache()
  const chartAnimationsEnabled = useChartAnimations()
  const isAnimationActive = chartAnimationsEnabled
  const [slideView, setSlideView] = useState(false)

  const [audienceData, setAudienceData] = useState<
    Array<
      {
        week: string
        weekLabel: string
        last_year?: AudienceMetricsCountryData['last_year']
      } & AudienceMetricsCountryData
    > | null
  >(null)
  const [fetchError, setFetchError] = useState<string | null>(null)
  const [weeksRaw, setWeeksRaw] = useState<
    Array<{ week: string; countries: Record<string, AudienceMetricsCountryData> }>
  >([])
  const [resolvedCountryKey, setResolvedCountryKey] = useState<string>('')
  const [serverAudienceBudgetByWeek, setServerAudienceBudgetByWeek] = useState<Record<
    string,
    Record<string, number> | null
  > | null>(null)

  useEffect(() => {
    if (!baseWeek) return
    if ((!periods || !isDataReady) && !loading && !error) loadAllData(baseWeek, false)
  }, [baseWeek, loading, periods, isDataReady, loadAllData, error])

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

  useEffect(() => {
    if (!baseWeek || !marketName) return
    let cancelled = false
    getAudienceMetricsPerCountry(baseWeek, 8)
      .then((res) => {
        if (cancelled) return
        const byWeek = res.audience_metrics_per_country || []
        const firstWeek = byWeek[0]
        const countryKeys = firstWeek ? Object.keys(firstWeek.countries || {}) : []
        const nameMatch = countryKeys.find(
          (c) =>
            c.toLowerCase() === marketName.toLowerCase() ||
            c.toLowerCase().replace(/\s+/g, '-') === (slug || '').toLowerCase()
        )
        const countryKey = nameMatch || marketName
        setResolvedCountryKey(countryKey)
        setWeeksRaw(byWeek)

        const series = byWeek.map((w) => {
          const c = w.countries[countryKey] || w.countries[marketName]
          if (!c) return null
          return {
            week: w.week,
            weekLabel: `W${w.week.split('-')[1]}`,
            ...c,
            last_year: c.last_year ?? null,
          }
        }).filter(Boolean) as Array<
          {
            week: string
            weekLabel: string
            last_year?: AudienceMetricsCountryData['last_year']
          } & AudienceMetricsCountryData
        >
        setAudienceData(series.length ? series : null)
        setFetchError(series.length ? null : `No data for market "${marketName}"`)
      })
      .catch((e) => {
        if (!cancelled) {
          setFetchError(e?.message || 'Failed to load audience metrics')
          setAudienceData(null)
          setWeeksRaw([])
          setResolvedCountryKey('')
        }
      })
    return () => {
      cancelled = true
    }
  }, [baseWeek, marketName, slug])

  const monthlyAmerPlan = useMemo(
    () =>
      baseWeek
        ? getMonthlyAmerPlanFromBudget(baseWeek, serverAudienceBudgetByWeek, effectiveBudgetGeneral)
        : null,
    [baseWeek, serverAudienceBudgetByWeek, effectiveBudgetGeneral]
  )

  const audienceSeriesWithBudget = useMemo(() => {
    if (!audienceData?.length) return null
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

  const noData = baseWeek && !loading && !error && (!periods || !isDataReady)
  const hasData = periods && isDataReady && audienceSeriesWithBudget && audienceSeriesWithBudget.length > 0

  return (
    <div className="space-y-8">
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-sm text-red-800 mb-2">{error}</p>
          <Button onClick={() => baseWeek && loadAllData(baseWeek, true)} variant="outline" size="sm">
            Retry
          </Button>
        </div>
      )}
      {fetchError && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
          <p className="text-sm text-amber-800">{fetchError}</p>
          <Link href="/audience-total" className="text-sm text-amber-700 underline mt-2 inline-block">Back to Audience Total</Link>
        </div>
      )}
      {noData && (
        <div className="rounded-lg border bg-muted/40 p-6 text-center">
          <p className="text-sm text-muted-foreground mb-4">No data for this week. Choose another week above or sync data in Settings.</p>
          <Link href="/settings" className="inline-flex rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground">
            Go to Settings
          </Link>
        </div>
      )}
      {!hasData && !noData && !fetchError && (
        <div className="flex items-center gap-3">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
          <p className="text-sm text-muted-foreground">Loading audience metrics for {marketName}...</p>
        </div>
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
          <AudienceMetricsChartGrid series={audienceSeriesWithBudget!} isAnimationActive={isAnimationActive} compact />
          <AudienceSlideView title={`Audience — ${marketName}`} open={slideView} onClose={() => setSlideView(false)}>
            <AudienceMetricsChartGrid series={audienceSeriesWithBudget!} isAnimationActive={false} compact />
          </AudienceSlideView>
        </>
      )}
    </div>
  )
}
