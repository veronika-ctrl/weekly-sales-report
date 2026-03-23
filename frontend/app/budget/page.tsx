'use client'

import { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Loader2 } from 'lucide-react'
import { useDataCache } from '@/contexts/DataCacheContext'

export default function Budget() {
  const { baseWeek } = useDataCache()
  const [budgetData, setBudgetData] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const loadBudgetData = async () => {
      if (!baseWeek) return
      
      setLoading(true)
      try {
        const response = await fetch(`http://localhost:8000/api/budget-data?week=${baseWeek}`)
        if (!response.ok) {
          throw new Error(`Failed to fetch budget data: ${response.statusText}`)
        }
        const data = await response.json()
        setBudgetData(data)
      } catch (error) {
        console.error('Failed to load budget data:', error)
        setBudgetData({ error: 'Failed to load budget data' })
      } finally {
        setLoading(false)
      }
    }
    
    loadBudgetData()
  }, [baseWeek])

  if (loading) {
    return (
      <div className="space-y-8">
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <Loader2 className="h-6 w-6 animate-spin text-primary" />
            <div>
              <h2 className="text-lg font-semibold text-gray-900">Loading Budget Data</h2>
              <p className="text-sm text-gray-600">Processing budget information...</p>
            </div>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <Skeleton className="h-5 w-48" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-64 w-full" />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <Skeleton className="h-5 w-48" />
              </CardHeader>
              <CardContent>
                <Skeleton className="h-64 w-full" />
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    )
  }

  if (budgetData?.error) {
    return (
      <div className="space-y-8">
        <Card>
          <CardHeader>
            <CardTitle>Budget Data</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-gray-600">{budgetData.error}</p>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      <Card>
        <CardHeader>
          <CardTitle>Budget Data</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <p className="text-sm text-gray-600">Week: {budgetData?.week}</p>
            <p className="text-sm text-gray-600">Columns: {budgetData?.columns?.join(', ')}</p>
            <p className="text-sm text-gray-600">Row Count: {budgetData?.row_count}</p>
            
            {budgetData?.sample_data && (
              <div className="mt-4">
                <h3 className="text-sm font-medium mb-2">Sample Data:</h3>
                <pre className="bg-gray-100 p-4 rounded text-xs overflow-auto">
                  {JSON.stringify(budgetData.sample_data, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

