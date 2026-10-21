'use client'

import ProductsNewTable from '@/components/ProductsNewTable'
import { useDataCache } from '@/contexts/DataCacheContext'

export default function ProductsNew() {
  const { baseWeek } = useDataCache()

  return (
    <div className="space-y-8">
      {baseWeek ? (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 lg:gap-5">
          <div className="bg-white rounded-lg border border-gray-100 shadow-sm p-4">
            <h2 className="text-base font-semibold text-gray-900 mb-2">Products New</h2>
            <ProductsNewTable baseWeek={baseWeek} customerType="new" />
          </div>
          <div className="bg-white rounded-lg border border-gray-100 shadow-sm p-4">
            <h2 className="text-base font-semibold text-gray-900 mb-2">Products Returning</h2>
            <ProductsNewTable baseWeek={baseWeek} customerType="returning" />
          </div>
        </div>
      ) : null}
    </div>
  )
}

