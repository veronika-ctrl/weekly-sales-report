'use client'

import { useEffect, useMemo, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import OnlineKPIsClient from '@/app/online-kpis/OnlineKPIsClient'
import { useDataCache } from '@/contexts/DataCacheContext'
import { Loader2 } from 'lucide-react'
import { getOnlineKPIs, type OnlineKPIsResponse } from '@/lib/api'

interface CountryKPIsClientProps {
  countryLabel: string
  apiCountry?: string
  isPdfMode?: boolean
}

export default function CountryKPIsClient({ countryLabel, apiCountry, isPdfMode = false }: CountryKPIsClientProps) {
  const { baseWeek, loadAllData, kpis } = useDataCache()
  const [countryKpis, setCountryKpis] = useState<OnlineKPIsResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState<boolean>(false)
  const targetCountry = (apiCountry || countryLabel).trim()

  const week = useMemo(() => baseWeek || '2025-42', [baseWeek])

  useEffect(() => {
    if (!kpis) {
      loadAllData(week, false)
    }
  }, [kpis, loadAllData, week])

  useEffect(() => {
    let cancelled = false
    async function fetchKPIs() {
      setLoading(true)
      setError(null)
      try {
        const data = await getOnlineKPIs(week, 8, targetCountry)
        if (!cancelled) {
          setCountryKpis(data)
        }
      } catch (err: any) {
        if (!cancelled) {
          setError(err?.message ?? 'Failed to load country KPIs')
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }
    fetchKPIs()
    return () => {
      cancelled = true
    }
  }, [targetCountry, week])

  return (
    <Card className={isPdfMode ? 'shadow-none border-0 break-inside-avoid' : ''}>
      <CardHeader className={isPdfMode ? 'p-2 pb-1' : ''}>
        <CardTitle className={isPdfMode ? 'text-sm' : ''}>
          Online KPIs — {countryLabel} (Week {week})
        </CardTitle>
      </CardHeader>
      <CardContent className={isPdfMode ? 'p-2 pt-1' : ''}>
        {loading && !countryKpis ? (
          <div className="flex items-center gap-3 text-sm text-gray-600">
            <Loader2 className="h-4 w-4 animate-spin text-primary" />
            <span>Fetching KPIs for {countryLabel}…</span>
          </div>
        ) : error ? (
          <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        ) : (
          <OnlineKPIsClient isPdfMode={isPdfMode} dataOverride={countryKpis} />
        )}
      </CardContent>
    </Card>
  )
}

