'use client'

import { useState, useEffect } from 'react'
import MetricsPreview from '@/components/MetricsPreview'
import { useDataCache } from '@/contexts/DataCacheContext'
import { Loader2 } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import Link from 'next/link'

export default function Summary() {
  const { periods, baseWeek, loading, error, loadAllData, isDataReady } = useDataCache()
  const [metrics, setMetrics] = useState<unknown>(null)

  // Load data when a week is selected and not already loaded
  useEffect(() => {
    if (!baseWeek) return
    if (!periods && !loading) {
      loadAllData(baseWeek, false)
    }
  }, [periods, loading, baseWeek, loadAllData])

  const handleRetry = async () => {
    if (baseWeek) {
      await loadAllData(baseWeek, true)
    }
  }

  const noDataForWeek = baseWeek && !loading && !error && (!periods || !isDataReady)

  return (
    <div className="space-y-8">
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-sm text-red-800 mb-2">
            {error}
          </p>
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
      {noDataForWeek && (
        <div className="rounded-lg border bg-muted/40 p-6 text-center">
          <p className="text-sm text-muted-foreground mb-2">
            No data for this week yet.
          </p>
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
      {periods && isDataReady ? (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Summary Metrics</h2>
          <MetricsPreview 
            periods={periods}
            baseWeek={baseWeek}
            onMetricsChange={setMetrics}
          />
        </div>
      ) : !noDataForWeek && !error && (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <Loader2 className="h-6 w-6 animate-spin text-primary" />
            <div>
              <h2 className="text-lg font-semibold text-gray-900">Loading Summary Metrics</h2>
              <p className="text-sm text-gray-600">
                {loading ? 'Loading data...' : 'Initializing data...'}
              </p>
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

