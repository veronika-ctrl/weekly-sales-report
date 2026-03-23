'use client'

import { useState, useEffect } from 'react'
import { useDataCache } from '@/contexts/DataCacheContext'
import LoadingProgress from '@/components/LoadingProgress'
import { useSearchParams, usePathname } from 'next/navigation'
import Link from 'next/link'
import { Calendar, Settings, Loader2 } from 'lucide-react'
import WeekSelector from '@/components/WeekSelector'

export default function LayoutContent({ children }: { children: React.ReactNode }) {
  const { loading, loadingProgress, baseWeek, setBaseWeek, hasRestoredWeek, isDataReady, periods } = useDataCache()
  const [weeksWithData, setWeeksWithData] = useState<Set<string> | null>(null)

  useEffect(() => {
    import('@/lib/supabase-queries')
      .then((m) => m.getWeeksWithDataFromSupabase())
      .then((weeks) => setWeeksWithData(new Set(weeks)))
  }, [])
  const searchParams = useSearchParams()
  const pathname = usePathname()
  const pdfParam = searchParams?.get('pdf')
  const isPdfMode = pdfParam === '1' || pdfParam === 'true'
  const isSettings = pathname === '/settings'

  // Before we've restored week from URL/localStorage, show a neutral loading state (same on server and client to avoid hydration mismatch)
  if (!hasRestoredWeek && !isSettings) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] gap-4 px-4">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        <p className="text-sm text-muted-foreground">Loading...</p>
      </div>
    )
  }

  // No week selected – show prompt (except on Settings where they can select)
  if (!baseWeek && !isSettings) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] gap-4 px-4">
        <Calendar className="h-12 w-12 text-muted-foreground" />
        <h2 className="text-lg font-semibold text-foreground">No week chosen</h2>
        <p className="text-sm text-muted-foreground text-center max-w-md">
          Choose a week in Settings to load and view reports.
        </p>
        <Link
          href="/settings"
          className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
        >
          Go to Settings
        </Link>
      </div>
    )
  }

  // Don't show loading progress in PDF mode - let the page render even while loading
  if (loading && loadingProgress && !isPdfMode) {
    return <LoadingProgress progress={loadingProgress} />
  }

  // Report pages: show week selector bar so user can change week without going to Settings
  if (baseWeek && !isSettings && !isPdfMode) {
    const dataStatus = loading
      ? 'loading'
      : isDataReady
        ? 'has-data'
        : periods
          ? 'no-data'
          : 'loading'
    return (
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b bg-muted/30 px-4 py-2 rounded-md">
          <div className="flex items-center gap-3">
            <WeekSelector value={baseWeek} onChange={setBaseWeek} weeksWithData={weeksWithData} />
            <span
              className={`text-xs font-medium px-2 py-0.5 rounded ${
                dataStatus === 'has-data'
                  ? 'bg-green-100 text-green-800'
                  : dataStatus === 'no-data'
                    ? 'bg-amber-100 text-amber-800'
                    : 'bg-muted text-muted-foreground'
              }`}
              title={dataStatus === 'has-data' ? 'Data loaded for this week' : dataStatus === 'no-data' ? 'No data uploaded for this week yet' : 'Loading…'}
            >
              {dataStatus === 'has-data' ? 'Has data' : dataStatus === 'no-data' ? 'No data' : 'Loading…'}
            </span>
          </div>
          <Link
            href="/settings"
            className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
          >
            <Settings className="h-4 w-4" />
            Settings
          </Link>
        </div>
        {children}
      </div>
    )
  }

  return <>{children}</>
}

