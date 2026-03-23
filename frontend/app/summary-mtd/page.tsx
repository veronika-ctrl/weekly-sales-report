'use client'

import { useState, useEffect } from 'react'
import MetricsPreviewMTD from '@/components/MetricsPreviewMTD'
import { useDataCache } from '@/contexts/DataCacheContext'
import { getTable1Mtd } from '@/lib/api'
import { Loader2 } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import Link from 'next/link'

export default function SummaryMtdPage() {
  const { baseWeek, loadAllData, loading, error, periods, isDataReady } = useDataCache()
  const [mtdData, setMtdData] = useState<Awaited<ReturnType<typeof getTable1Mtd>> | null>(null)
  const [mtdError, setMtdError] = useState<string | null>(null)
  const [mtdLoading, setMtdLoading] = useState(false)

  // Ensure base week data is loaded (for header/context)
  useEffect(() => {
    if (!baseWeek) return
    if (!periods && !loading) {
      loadAllData(baseWeek, false)
    }
  }, [baseWeek, periods, loading, loadAllData])

  // Fetch MTD metrics when base week is set
  useEffect(() => {
    if (!baseWeek) {
      setMtdData(null)
      return
    }
    let cancelled = false
    setMtdError(null)
    setMtdLoading(true)
    getTable1Mtd(baseWeek)
      .then((data) => {
        if (!cancelled) setMtdData(data)
      })
      .catch((e) => {
        if (!cancelled) {
          setMtdError(e instanceof Error ? e.message : 'Failed to load MTD metrics')
          setMtdData(null)
        }
      })
      .finally(() => {
        if (!cancelled) setMtdLoading(false)
      })
    return () => { cancelled = true }
  }, [baseWeek])

  const handleRetry = () => {
    if (baseWeek) {
      setMtdError(null)
      setMtdLoading(true)
      getTable1Mtd(baseWeek)
        .then(setMtdData)
        .catch((e) => setMtdError(e instanceof Error ? e.message : 'Failed to load MTD metrics'))
        .finally(() => setMtdLoading(false))
    }
  }

  const noBaseWeek = !baseWeek
  const showContent = baseWeek && !mtdLoading && (mtdData || mtdError)
  const noDataForWeek = baseWeek && !loading && !error && (!periods || !isDataReady) && !mtdData && !mtdError && !mtdLoading

  return (
    <div className="space-y-8">
      {(error || mtdError) && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-sm text-red-800 mb-2">{error || mtdError}</p>
          <Button
            onClick={handleRetry}
            variant="outline"
            size="sm"
            className="text-red-800 border-red-300 hover:bg-red-100"
          >
            Retry
          </Button>
        </div>
      )}
      {noDataForWeek && !mtdError && (
        <div className="rounded-lg border bg-muted/40 p-6 text-center">
          <p className="text-sm text-muted-foreground mb-2">No data for this week yet.</p>
          <p className="text-sm text-muted-foreground mb-4">
            Choose another week in the dropdown above or sync data in Settings.
          </p>
          <Link
            href="/settings"
            className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            Go to Settings
          </Link>
        </div>
      )}
      {noBaseWeek && (
        <div className="rounded-lg border bg-muted/40 p-6 text-center">
          <p className="text-sm text-muted-foreground">Select a base week above to view month-to-date metrics.</p>
        </div>
      )}
      {baseWeek && (mtdLoading || showContent) && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Summary Metrics (Month-to-Date)</h2>
          {mtdLoading ? (
            <div className="flex items-center gap-3 py-8">
              <Loader2 className="h-6 w-6 animate-spin text-primary" />
              <span className="text-sm text-muted-foreground">Loading MTD metrics...</span>
            </div>
          ) : mtdData ? (
            <MetricsPreviewMTD mtdData={mtdData} baseWeek={baseWeek} />
          ) : (
            <div className="py-8 text-center text-sm text-muted-foreground">
              Could not load month-to-date metrics. Check that data is uploaded for week {baseWeek}.
            </div>
          )}
        </div>
      )}
      {baseWeek && !mtdLoading && !showContent && !noDataForWeek && !noBaseWeek && (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <Loader2 className="h-6 w-6 animate-spin text-primary" />
            <div>
              <h2 className="text-lg font-semibold text-gray-900">Loading Summary MTD</h2>
              <p className="text-sm text-gray-600">Loading data...</p>
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <Skeleton className="h-96 w-full" />
          </div>
        </div>
      )}
    </div>
  )
}
