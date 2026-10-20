'use client'

import { useEffect, useState } from 'react'
import { useDataCache } from '@/contexts/DataCacheContext'
import { getTopProductsMonthly, type TopProductsMonthlyResponse } from '@/lib/api'
import ReportLoadState from '@/components/ReportLoadState'
import MonthlySalesTrend from '@/components/MonthlySalesTrend'
import MonthlyTopProductsTable from '@/components/MonthlyTopProductsTable'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

type GenderTab = 'men' | 'women'

export default function ProductsGenderMonthlyPage() {
  const { baseWeek } = useDataCache()
  const [activeTab, setActiveTab] = useState<GenderTab>('men')
  const [data, setData] = useState<TopProductsMonthlyResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [reloadToken, setReloadToken] = useState(0)

  useEffect(() => {
    if (!baseWeek) {
      setData(null)
      setError(null)
      setLoading(false)
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    getTopProductsMonthly(baseWeek, activeTab)
      .then((payload) => {
        if (!cancelled) setData(payload)
      })
      .catch((e) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : 'Failed to load monthly top products')
          setData(null)
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [baseWeek, activeTab, reloadToken])

  const empty = !loading && !error && (!data || data.products.length === 0)

  return (
    <div className="space-y-4">
      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as GenderTab)} className="w-full max-w-4xl">
        <TabsList className="h-8">
          <TabsTrigger value="men" className="text-xs px-3 py-1">
            Products Men
          </TabsTrigger>
          <TabsTrigger value="women" className="text-xs px-3 py-1">
            Products Women
          </TabsTrigger>
        </TabsList>
        <TabsContent value={activeTab} className="mt-4">
          {loading || error || empty || !data ? (
            <ReportLoadState
              loading={loading}
              error={error}
              empty={empty}
              onRetry={() => setReloadToken((n) => n + 1)}
              loadingTitle="Loading monthly top selling products"
              loadingHint="Reading Qlik for the last completed month vs last year."
              emptyHint="Upload the Qlik export in Settings for this week, then open Top selling products monthly again."
            />
          ) : (
            <div className="space-y-6">
              <div>
                <h2 className="text-lg font-semibold text-gray-900">
                  Top selling products monthly · {data.focus_label}
                </h2>
                <p className="text-sm text-muted-foreground mt-1">{data.note}</p>
                <p className="text-xs text-muted-foreground mt-1">
                  {data.focus_start} → {data.focus_end}. Values in SEK ’000. Online only.
                </p>
              </div>
              <MonthlySalesTrend
                title={`${activeTab === 'men' ? 'Men' : 'Women'} sales · 13 months`}
                trend={data.trend}
              />
              <MonthlyTopProductsTable
                products={data.products}
                topTotal={data.top_total}
                grandTotal={data.grand_total}
                genderFilter={activeTab}
              />
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}
