'use client'

import { useEffect, useMemo, useState, Fragment } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { useDataCache } from '@/contexts/DataCacheContext'
import { Skeleton } from '@/components/ui/skeleton'
import { Loader2 } from 'lucide-react'
import { getApiBaseUrl } from '@/lib/api'

type Row = Record<string, any>

export default function BudgetMarkets() {
  const { baseWeek, budget_raw, actuals_markets_detailed } = useDataCache()
  const [budgetData, setBudgetData] = useState<any>(budget_raw ?? null)
  const [actualsDetailed, setActualsDetailed] = useState<any>(actuals_markets_detailed ?? null)
  const [loading, setLoading] = useState(!(budget_raw && actuals_markets_detailed))
  const [selectedTabs, setSelectedTabs] = useState<string[]>([])
  const [collapsed, setCollapsed] = useState<boolean>(false)

  useEffect(() => {
    const loadData = async () => {
      if (!baseWeek) return
      // If cached for both datasets, skip network
      if (budget_raw && actuals_markets_detailed) {
        setBudgetData(budget_raw)
        setActualsDetailed(actuals_markets_detailed)
        setLoading(false)
        return
      }
      setLoading(true)

      const API_BASE_URL = getApiBaseUrl()
      
      // Prefer cached data for budget
      if (budget_raw) {
        setBudgetData(budget_raw)
      } else {
        try {
          const response = await fetch(`${API_BASE_URL}/api/budget-data?week=${baseWeek}`)
          const data = await response.json()
          setBudgetData(data)
        } catch (e) {
          setBudgetData({ error: 'Failed to load budget data' })
        }
      }
      
      // Prefer cached data for actuals detailed
      if (actuals_markets_detailed) {
        setActualsDetailed(actuals_markets_detailed)
      } else {
        try {
          const resA = await fetch(`${API_BASE_URL}/api/actuals-markets-detailed?week=${baseWeek}`)
          if (resA.ok) {
            const dataA = await resA.json()
            setActualsDetailed(dataA)
          }
        } catch (e) {
          // optional
        }
      }
      
      setLoading(false)
    }
    loadData()
  }, [baseWeek, budget_raw, actuals_markets_detailed])

  // Persist and restore UI state (tabs + collapsed) similar to General
  useEffect(() => {
    try {
      const savedTabs = localStorage.getItem('budget_markets_selectedTabs')
      if (savedTabs) {
        const arr = JSON.parse(savedTabs)
        if (Array.isArray(arr)) setSelectedTabs(arr)
      }
      const savedCollapsed = localStorage.getItem('budget_markets_collapsed')
      if (savedCollapsed !== null) setCollapsed(savedCollapsed === 'true')
    } catch {}
  }, [])
  useEffect(() => {
    try {
      localStorage.setItem('budget_markets_selectedTabs', JSON.stringify(selectedTabs))
      localStorage.setItem('budget_markets_collapsed', String(collapsed))
    } catch {}
  }, [selectedTabs, collapsed])

  // Months and metrics from detailed actuals
  const months: string[] = actualsDetailed?.months || []
  const metrics: string[] = actualsDetailed?.metrics || []
  const markets: string[] = actualsDetailed?.markets || []

  // Toggle selection (Total, YTD, months)
  const toggleTab = (key: string) => {
    setSelectedTabs((prev) => (prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]))
  }

  if (loading) {
    return (
      <div className="space-y-8">
        <div className="flex items-center gap-3">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Loading Budget Markets</h2>
            <p className="text-sm text-gray-600">Preparing overview…</p>
          </div>
        </div>
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }
  
  if (budgetData?.error) {
    return <p className="text-gray-600">{budgetData.error}</p>
  }

  const fmt = new Intl.NumberFormat('sv-SE')
  
  const renderTableForMarket = (market: string, selected: string[]) => {
    const sel = selected
    const showTotal = sel.includes('Total')
    const showYTD = sel.includes('YTD')
    const monthKeys = sel.filter((k) => k !== 'Total' && k !== 'YTD')
    return (
      <div className="mt-6 overflow-auto rounded-md border">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-3 py-2 text-left font-medium text-gray-700 whitespace-nowrap">Metric</th>
              <th className="px-3 py-2 text-left font-medium text-gray-700 whitespace-nowrap">Customer</th>
              {showTotal && (
                <th className="px-3 py-2 text-left font-medium text-gray-700 whitespace-nowrap">Total Actuals</th>
              )}
              {showYTD && (
                <th className="px-3 py-2 text-left font-medium text-gray-700 whitespace-nowrap">YTD Actuals</th>
              )}
              {monthKeys.map((m) => (
                <th key={`head-${market}-${m}`} className="px-3 py-2 text-left font-medium text-gray-700 whitespace-nowrap">{m} Actuals</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {metrics.map((metric: string, idx: number) => {
              const customer = metric.toLowerCase().startsWith('new ')
                ? 'New'
                : metric.toLowerCase().startsWith('returning ')
                ? 'Returning'
                : ''
              return (
                <tr key={`${market}-${metric}`} className={idx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                  <td className="px-3 py-2 whitespace-nowrap text-gray-900 font-medium">{metric}</td>
                  <td className="px-3 py-2 whitespace-nowrap text-gray-900">{customer}</td>
                  {showTotal && (
                    <td className="px-3 py-2 whitespace-nowrap text-gray-900">{fmt.format(Number(actualsDetailed?.totals?.[market]?.[metric] ?? 0))}</td>
                  )}
                  {showYTD && (
                    <td className="px-3 py-2 whitespace-nowrap text-gray-900">{fmt.format(Number(actualsDetailed?.ytd_totals?.[market]?.[metric] ?? 0))}</td>
                  )}
                  {monthKeys.map((m) => (
                    <td key={`row-${market}-${metric}-${m}`} className="px-3 py-2 whitespace-nowrap text-gray-900">{fmt.format(Number(actualsDetailed?.table?.[market]?.[metric]?.[m] ?? 0))}</td>
                  ))}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Markets overview</CardTitle>
            <button className="text-sm text-gray-600 underline" onClick={() => setCollapsed(!collapsed)}>
              {collapsed ? 'Expand' : 'Collapse'}
            </button>
          </div>
        </CardHeader>
        <CardContent>
          {!collapsed && (
            <Fragment>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="rounded-lg border p-3">
                  <div className="text-xs text-muted-foreground">Week</div>
                  <div className="text-sm font-medium">{actualsDetailed?.week}</div>
                </div>
                <div className="rounded-lg border p-3">
                  <div className="text-xs text-muted-foreground">Markets</div>
                  <div className="text-sm font-medium">{markets.length}</div>
                </div>
                <div className="rounded-lg border p-3">
                  <div className="text-xs text-muted-foreground">Months</div>
                  <div className="text-sm font-medium">{months.length}</div>
                </div>
              </div>

              <div className="mt-6 flex flex-wrap gap-2">
                {['Total', 'YTD', ...months].map((key) => {
                  const active = selectedTabs.includes(key)
                  return (
                    <button
                      key={key}
                      className={`px-3 py-1 rounded border ${active ? 'bg-gray-900 text-white' : 'bg-white text-gray-900'}`}
                      onClick={() => toggleTab(key)}
                    >
                      {key}
                    </button>
                  )
                })}
              </div>

              <Tabs defaultValue={markets[0] || 'All'} className="mt-6">
                <TabsList>
                  {markets.map((m) => (
                    <TabsTrigger key={m} value={m}>{m}</TabsTrigger>
                  ))}
                </TabsList>
                {markets.map((m) => (
                  <TabsContent key={`tab-${m}`} value={m}>
                    {renderTableForMarket(m, selectedTabs)}
                  </TabsContent>
                ))}
              </Tabs>
            </Fragment>
          )}
        </CardContent>
      </Card>
    </div>
  )
}


