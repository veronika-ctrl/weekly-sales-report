'use client'

import type { ReactNode } from 'react'
import Link from 'next/link'
import { Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'

export default function ReportLoadState({
  loading,
  error,
  empty,
  onRetry,
  loadingTitle,
  loadingHint,
  emptyTitle = 'No data for this week yet',
  emptyHint,
  skeleton,
}: {
  loading: boolean
  error: string | null
  empty: boolean
  onRetry?: () => void
  loadingTitle: string
  loadingHint: string
  emptyTitle?: string
  emptyHint: string
  skeleton?: ReactNode
}) {
  if (loading) {
    return (
      <div className="space-y-8">
        <div className="flex items-center gap-3 mb-6">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
          <div>
            <h2 className="text-lg font-semibold text-gray-900">{loadingTitle}</h2>
            <p className="text-sm text-gray-600">{loadingHint}</p>
          </div>
        </div>
        {skeleton}
      </div>
    )
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4">
        <p className="text-sm text-red-800 mb-3">{error}</p>
        {onRetry && (
          <Button
            onClick={onRetry}
            variant="outline"
            size="sm"
            className="text-red-800 border-red-300 hover:bg-red-100"
          >
            Retry
          </Button>
        )}
      </div>
    )
  }

  if (empty) {
    return (
      <div className="rounded-lg border bg-muted/40 p-6 text-center" data-testid="report-empty-state">
        <p className="text-sm text-muted-foreground mb-2">{emptyTitle}</p>
        <p className="text-sm text-muted-foreground mb-4">{emptyHint}</p>
        <Link
          href="/settings"
          className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
        >
          Go to Settings
        </Link>
      </div>
    )
  }

  return null
}
