'use client'

import TopMarketsTable from '@/components/TopMarketsTable'
import TopMarketsNetRevenueTable from '@/components/TopMarketsNetRevenueTable'
import { useDataCache } from '@/contexts/DataCacheContext'

export default function TopMarkets() {
  const { baseWeek } = useDataCache()

  return (
    <div className="space-y-8">
      {baseWeek ? (
        <div className="space-y-10">
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Top markets — online net revenue</h2>
            <p className="text-sm text-muted-foreground mb-4">
              Week, month (MTD), and fiscal YTD with last year, budget (allocated by mix), Y/Y %, and vs budget — same
              layout as Summary month-to-date, one metric (net revenue).
            </p>
            <TopMarketsNetRevenueTable baseWeek={baseWeek} />
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Eight-week trend (online gross)</h2>
            <TopMarketsTable baseWeek={baseWeek} />
          </div>
        </div>
      ) : null}
    </div>
  )
}

