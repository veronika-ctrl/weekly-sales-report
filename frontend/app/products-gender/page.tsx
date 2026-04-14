'use client'

import { useEffect } from 'react'
import ProductsGenderTable from '@/components/ProductsGenderTable'
import { Loader2 } from 'lucide-react'
import { Skeleton } from '@/components/ui/skeleton'
import { useDataCache } from '@/contexts/DataCacheContext'
import { Button } from '@/components/ui/button'
import Link from 'next/link'

export default function ProductsGender() {
  const { baseWeek, periods, loading, error, loadAllData, isDataReady } = useDataCache()

  // Load data when a week is selected and not already loaded
  useEffect(() => {
    if (!baseWeek) return
    if (!periods && !loading) {
      loadAllData(baseWeek, false)
    }
  }, [periods, loading, baseWeek, loadAllData])

  const handleRetry = async () => {
    if (baseWeek) await loadAllData(baseWeek, true)
  }

  const noDataForWeek = baseWeek && !loading && !error && (!periods || !isDataReady)

  return (
    <div className="space-y-8">
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-sm text-red-800 mb-2">{error}</p>
          <Button onClick={handleRetry} variant="outline" size="sm" className="text-red-800 border-red-300 hover:bg-red-100">
            Retry
          </Button>
        </div>
      )}
      {noDataForWeek && (
        <div className="rounded-lg border bg-muted/40 p-6 text-center">
          <p className="text-sm text-muted-foreground mb-4">No data for this week yet. Choose another week above or sync data in Settings.</p>
          <Link href="/settings" className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90">
            Go to Settings
          </Link>
        </div>
      )}
      {periods && isDataReady ? (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 lg:gap-5">
          <div className="bg-white rounded-lg border border-gray-100 shadow-sm p-4">
            <h2 className="text-base font-semibold text-gray-900 mb-2">Products Men</h2>
            <ProductsGenderTable baseWeek={baseWeek} genderFilter="men" />
          </div>
          <div className="bg-white rounded-lg border border-gray-100 shadow-sm p-4">
            <h2 className="text-base font-semibold text-gray-900 mb-2">Products Women</h2>
            <ProductsGenderTable baseWeek={baseWeek} genderFilter="women" />
          </div>
        </div>
      ) : !noDataForWeek && (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <Loader2 className="h-6 w-6 animate-spin text-primary" />
            <div>
              <h2 className="text-lg font-semibold text-gray-900">Loading Products</h2>
              <p className="text-sm text-gray-600">{loading ? 'Loading data...' : 'Initializing data...'}</p>
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

