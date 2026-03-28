'use client'

import { useEffect, useMemo, useState } from 'react'
import { useDataCache } from '@/contexts/DataCacheContext'
import { useChartAnimations } from '@/contexts/ChartSettingsContext'
import { Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import Link from 'next/link'
import { AudienceMetricsChartGrid } from '@/components/audience/AudienceMetricsChartGrid'
import { buildAudienceBudgetMetricsForWeek } from '@/lib/audienceBudgetSeries'
import { getAudienceBudgetSeries, type BudgetGeneralResponse } from '@/lib/api'

function budgetGeneralUsable(b: BudgetGeneralResponse | null | undefined): boolean {
  return Boolean(b && !b.error && b.table && Object.keys(b.table).length > 0)
}

function deriveMetrics(k: {
  new_customers?: number
  returning_customers?: number
  total_orders?: number
  aov_new_customer?: number
  aov_returning_customer?: number
  cos?: number
  new_customer_cac?: number
  marketing_spend?: number
  /** Online new-customer net revenue (Qlik); aMER = this ÷ DEMA marketing spend (same as slide 1). */
  new_customers_net_revenue?: number
  return_rate_pct?: number
  return_rate_new_pct?: number
  return_rate_returning_pct?: number
}) {
  const newC = Number(k.new_customers) || 0
  const retC = Number(k.returning_customers) || 0
  const totalC = newC + retC
  const totalAov = totalC > 0
    ? (newC * (Number(k.aov_new_customer) || 0) + retC * (Number(k.aov_returning_customer) || 0)) / totalC
    : 0
  // Return rate % = (Gross − Net) / Gross from API (~5–6%). Do not use returning-customer share (that would be ~55%).
  const returnRatePct =
    typeof k.return_rate_pct === 'number' && Number.isFinite(k.return_rate_pct)
      ? k.return_rate_pct
      : 0
  const returnRateNewPct =
    typeof k.return_rate_new_pct === 'number' && Number.isFinite(k.return_rate_new_pct)
      ? k.return_rate_new_pct
      : 0
  const returnRateReturningPct =
    typeof k.return_rate_returning_pct === 'number' && Number.isFinite(k.return_rate_returning_pct)
      ? k.return_rate_returning_pct
      : 0
  const newCustomerSharePct = totalC > 0 ? (newC / totalC) * 100 : 0
  const returningCustomerSharePct = totalC > 0 ? (retC / totalC) * 100 : 0
  // Prefer API field; fallback for older cached payloads: revenue ≈ new_customers × AOV_new
  const rawNewNet = k.new_customers_net_revenue
  const newNet =
    typeof rawNewNet === 'number' && Number.isFinite(rawNewNet)
      ? rawNewNet
      : (Number(k.new_customers) || 0) * (Number(k.aov_new_customer) || 0)
  const mktSpend = Number(k.marketing_spend) || 0
  const amer = mktSpend > 0 ? Math.round((newNet / mktSpend) * 100) / 100 : 0
  return {
    total_aov: Math.round(totalAov),
    total_customers: totalC,
    total_orders: Math.round(Number(k.total_orders) || 0),
    new_customers: newC,
    returning_customers: retC,
    aov_new_customer: Math.round(Number(k.aov_new_customer) || 0),
    aov_returning_customer: Math.round(Number(k.aov_returning_customer) || 0),
    new_customer_share_pct: Math.round(newCustomerSharePct * 10) / 10,
    returning_customer_share_pct: Math.round(returningCustomerSharePct * 10) / 10,
    return_rate_pct: Math.round(returnRatePct * 10) / 10,
    return_rate_new_pct: Math.round(returnRateNewPct * 10) / 10,
    return_rate_returning_pct: Math.round(returnRateReturningPct * 10) / 10,
    cos_pct: Number(k.cos) ?? 0,
    cac: Math.round(Number(k.new_customer_cac) ?? 0),
    amer,
  }
}

export default function AudienceTotalPage() {
  const { baseWeek, loading, error, loadAllData, kpis: kpisData, periods, isDataReady, budget_general } =
    useDataCache()
  const chartAnimationsEnabled = useChartAnimations()
  const isAnimationActive = chartAnimationsEnabled
  const [serverAudienceBudgetByWeek, setServerAudienceBudgetByWeek] = useState<Record<
    string,
    Record<string, number> | null
  > | null>(null)

  useEffect(() => {
    if (!baseWeek) return
    if (!periods && !loading) loadAllData(baseWeek, false)
  }, [baseWeek, loading, periods, loadAllData])

  let kpis: Array<{
    week: string
    new_customers?: number
    returning_customers?: number
    total_orders?: number
    aov_new_customer?: number
    aov_returning_customer?: number
    cos?: number
    new_customer_cac?: number
    last_year?: Record<string, number>
  }> = []
  if (kpisData) {
    if (Array.isArray(kpisData)) kpis = kpisData as any[]
    else if (kpisData?.kpis && Array.isArray(kpisData.kpis)) kpis = kpisData.kpis as any[]
    else if (typeof kpisData === 'object' && (kpisData as any).kpis)
      kpis = Object.values((kpisData as any).kpis) as any[]
  }

  const numBudgetWeeks = kpis.length >= 1 ? kpis.length : 8

  useEffect(() => {
    if (!baseWeek) {
      setServerAudienceBudgetByWeek(null)
      return
    }
    let cancelled = false
    getAudienceBudgetSeries(baseWeek, numBudgetWeeks)
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
  }, [baseWeek, numBudgetWeeks])

  const effectiveBudgetGeneral = useMemo(() => {
    return budgetGeneralUsable(budget_general) ? budget_general : null
  }, [budget_general])

  const metrics = useMemo(() => {
    return kpis.map((k) => {
      const current = deriveMetrics(k)
      const ly = k.last_year ? deriveMetrics(k.last_year as any) : null
      const budgetMetrics =
        serverAudienceBudgetByWeek != null && k.week in serverAudienceBudgetByWeek
          ? serverAudienceBudgetByWeek[k.week]
          : buildAudienceBudgetMetricsForWeek(effectiveBudgetGeneral, k.week)
      return {
        week: k.week,
        weekLabel: `W${k.week.split('-')[1]}`,
        ...current,
        last_year: ly,
        budget: budgetMetrics,
      }
    })
  }, [kpis, effectiveBudgetGeneral, serverAudienceBudgetByWeek])

  const noData = baseWeek && !loading && !error && (!periods || !isDataReady)
  const hasData = periods && isDataReady && metrics.length > 0
  const noAudienceData = baseWeek && !loading && !error && periods && isDataReady && metrics.length === 0

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
      {noData && (
        <div className="rounded-lg border bg-muted/40 p-6 text-center">
          <p className="text-sm text-muted-foreground mb-4">No data for this week. Choose another week above or sync data in Settings.</p>
          <Link href="/settings" className="inline-flex rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground">
            Go to Settings
          </Link>
        </div>
      )}
      {noAudienceData && (
        <div className="rounded-lg border bg-amber-50 border-amber-200 p-6 text-center">
          <p className="text-sm font-medium text-amber-900 mb-2">No audience data for this week</p>
          <p className="text-sm text-amber-800 mb-4">
            Audience metrics (Total AOV, customers, Return rate, COS, CAC) use the same data as the Summary and Online KPIs: <strong>Qlik</strong> (with Sales Channel, Country, New/Returning Customer) and <strong>DEMA</strong> (for COS and CAC). Upload or sync data for this week in Settings and ensure the files contain online sales by country.
          </p>
          <Link href="/settings" className="inline-flex rounded-md bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-700">
            Go to Settings
          </Link>
        </div>
      )}
      {!hasData && !noData && !noAudienceData && (
        <div className="flex items-center gap-3">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
          <p className="text-sm text-muted-foreground">Loading audience metrics...</p>
        </div>
      )}
      {hasData && (
        <>
          <h2 className="text-lg font-semibold text-gray-900">Audience Total</h2>
          <p className="text-sm text-muted-foreground mb-2">
            Charts read left-to-right, top-to-bottom: total customers, total orders, total AOV, returning customers,
            return rate (returning), new customers, return rate (new), COS, then aMER (online new-customer net revenue ÷
            DEMA marketing spend — same as summary slide). Below the divider: returning and new AOV (same definition as
            Online KPIs), then customer share, blended return rate, and CAC.
            Comparison to last year uses the same ISO week (matching weekdays). The green dashed line is{' '}
            <strong>vs budget</strong> (actual − week-prorated plan), same sign convention as Top Markets net: positive =
            ahead of plan, negative = shortfall. It uses the right-hand axis; gray dash at 0 is on plan. Tooltip shows
            the variance and the prorated plan.
          </p>
          <p className="text-xs text-muted-foreground mb-4">
            By market:{' '}
            {['sweden', 'uk', 'usa', 'germany', 'france', 'canada', 'australia', 'row'].map((m) => (
              <Link key={m} href={`/audience/${m}`} className="text-primary hover:underline mr-2">
                {m === 'uk' ? 'UK' : m === 'usa' ? 'USA' : m === 'row' ? 'ROW' : m.charAt(0).toUpperCase() + m.slice(1)}
              </Link>
            ))}
          </p>
          <AudienceMetricsChartGrid series={metrics} isAnimationActive={isAnimationActive} />
        </>
      )}
    </div>
  )
}
