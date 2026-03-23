'use client'

import ProductsSummaryPreview from '@/components/ProductsSummaryPreview'
import ProductsSummaryMonthPreview from '@/components/ProductsSummaryMonthPreview'
import { useDataCache } from '@/contexts/DataCacheContext'

export default function ProductsSummaryPage() {
  const { baseWeek, periods } = useDataCache()

  return (
    <div className="space-y-8">
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Summary Week</h2>
        {periods ? (
          <ProductsSummaryPreview periods={periods} baseWeek={baseWeek} />
        ) : (
          <div className="text-sm text-gray-600">No periods loaded. Please refresh data.</div>
        )}
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Summary Month</h2>
        {periods ? (
          <ProductsSummaryMonthPreview periods={periods} baseWeek={baseWeek} />
        ) : (
          <div className="text-sm text-gray-600">No periods loaded. Please refresh data.</div>
        )}
      </div>
    </div>
  )
}


