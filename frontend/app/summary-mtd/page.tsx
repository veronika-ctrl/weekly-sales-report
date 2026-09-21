'use client'

import { useState, useEffect } from 'react'
import MetricsPreviewMTD from '@/components/MetricsPreviewMTD'
import { useDataCache } from '@/contexts/DataCacheContext'
import { getTable1Mtd } from '@/lib/api'
import { isNetworkFetchErrorMessage } from '@/lib/api-fetch'
import { Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import Link from 'next/link'

export default function SummaryMtdPage() {
  const { baseWeek } = useDataCache()
  const [mtdData, setMtdData] = useState<Awaited<ReturnType<typeof getTable1Mtd>> | null>(null)
  const [mtdError, setMtdError] = useState<string | null>(null)
  const [mtdLoading, setMtdLoading] = useState(false)
  const [loadSeconds, setLoadSeconds] = useState(0)
  const [reloadToken, setReloadToken] = useState(0)

  useEffect(() => {
    if (!baseWeek) {
      setMtdData(null)
      setMtdError(null)
      setMtdLoading(false)
      return
    }
    let cancelled = false
    setMtdError(null)
    setMtdLoading(true)
    setLoadSeconds(0)
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
    return () => {
      cancelled = true
    }
  }, [baseWeek, reloadToken])

  useEffect(() => {
    if (!mtdLoading) return
    const started = Date.now()
    const id = window.setInterval(() => setLoadSeconds(Math.floor((Date.now() - started) / 1000)), 1000)
    return () => window.clearInterval(id)
  }, [mtdLoading])

  const handleRetry = () => setReloadToken((n) => n + 1)
  const networkError = Boolean(mtdError && isNetworkFetchErrorMessage(mtdError))

  if (!baseWeek) {
    return (
      <div className="rounded-lg border bg-muted/40 p-6 text-center">
        <p className="text-sm text-muted-foreground">Select a base week above to view month-to-date metrics.</p>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      {mtdError && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-sm text-red-800 mb-2">{mtdError}</p>
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
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Summary Metrics (Month-to-Date)</h2>
        {mtdLoading ? (
          <div className="flex items-center gap-3 py-8">
            <Loader2 className="h-6 w-6 animate-spin text-primary" />
            <span className="text-sm text-muted-foreground">
              Loading month-to-date metrics from Qlik
              {loadSeconds > 0 ? ` ({loadSeconds}s)` : ''} — large exports often take 30–90 seconds.
            </span>
          </div>
        ) : mtdData ? (
          <MetricsPreviewMTD mtdData={mtdData} baseWeek={baseWeek} />
        ) : (
          <div className="rounded-lg border bg-muted/40 p-6 text-center">
            <p className="text-sm text-muted-foreground mb-2">
              {networkError
                ? 'The API connection dropped while loading this week. Files are still on the server — wait a minute and retry. Do not re-upload.'
                : `No month-to-date metrics for week ${baseWeek} yet.`}
            </p>
            {!networkError && (
              <p className="text-sm text-muted-foreground mb-4">
                Upload Qlik in Settings for this week, then open Online Summary again.
              </p>
            )}
            {networkError ? (
              <Button onClick={handleRetry} variant="outline" size="sm">
                Retry
              </Button>
            ) : (
              <Link
                href="/settings"
                className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
              >
                Go to Settings
              </Link>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
