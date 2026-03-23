'use client'

import { useState, useEffect } from 'react'
import { Calendar, ChevronDown } from 'lucide-react'
import { getPeriods, type PeriodsResponse } from '@/lib/api'

interface PeriodSelectorProps {
  selectedWeek: string
  onWeekChange: (week: string) => void
  onPeriodsChange: (periods: PeriodsResponse | null) => void
  /** Set of base_week strings that have data in Supabase; when set, options show "week ✓" or "week (no data)". */
  weeksWithData?: Set<string> | null
}

export default function PeriodSelector({ 
  selectedWeek, 
  onWeekChange, 
  onPeriodsChange,
  weeksWithData = null
}: PeriodSelectorProps) {
  const [periods, setPeriods] = useState<PeriodsResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Generate week options (current year ± 2 years)
  const currentYear = new Date().getFullYear()
  const years = [currentYear - 2, currentYear - 1, currentYear, currentYear + 1]
  const weekOptions = []
  
  for (const year of years) {
    for (let week = 1; week <= 53; week++) {
      weekOptions.push(`${year}-${week.toString().padStart(2, '0')}`)
    }
  }

  const fetchPeriods = async (week: string) => {
    setLoading(true)
    setError(null)
    
    try {
      const periodsData = await getPeriods(week)
      setPeriods(periodsData)
      onPeriodsChange(periodsData)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch periods')
      onPeriodsChange(null)
    } finally {
      setLoading(false)
    }
  }

  const handleWeekChange = (week: string) => {
    onWeekChange(week)
  }

  const optionLabel = (week: string) => {
    if (weeksWithData == null) return week
    return weeksWithData.has(week) ? `${week} ✓` : `${week} (no data)`
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center space-x-4">
        <div className="flex-1">
          <label htmlFor="week-select" className="block text-sm font-medium text-gray-700 mb-2">
            Select Base Week (ISO Format)
          </label>
          <div className="relative">
            <select
              id="week-select"
              value={selectedWeek || ''}
              onChange={(e) => handleWeekChange(e.target.value || '')}
              className="w-full pl-10 pr-10 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 appearance-none bg-white"
            >
              <option value="">Välj vecka</option>
              {weekOptions.map((week) => (
                <option key={week} value={week}>
                  {optionLabel(week)}
                </option>
              ))}
            </select>
            <Calendar className="absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
            <ChevronDown className="absolute right-3 top-2.5 h-4 w-4 text-gray-400" />
          </div>
        </div>
      </div>

      {loading && (
        <div className="flex items-center justify-center py-4">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
          <span className="ml-2 text-gray-600">Loading periods...</span>
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-md p-4">
          <div className="text-red-800 text-sm">{error}</div>
        </div>
      )}

      {periods && !loading && (
        <div className="bg-gray-50 rounded-lg p-4">
          <h3 className="text-sm font-medium text-gray-900 mb-3">Calculated Periods</h3>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Actual:</span>
                <span className="text-sm font-medium">{periods.actual}</span>
              </div>
              <div className="text-xs text-gray-500">
                {periods.date_ranges.actual?.display || 'N/A'}
              </div>
            </div>
            
            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Last Week:</span>
                <span className="text-sm font-medium">{periods.last_week}</span>
              </div>
              <div className="text-xs text-gray-500">
                {periods.date_ranges.last_week?.display || 'N/A'}
              </div>
            </div>
            
            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Last Year:</span>
                <span className="text-sm font-medium">{periods.last_year}</span>
              </div>
              <div className="text-xs text-gray-500">
                {periods.date_ranges.last_year?.display || 'N/A'}
              </div>
            </div>
            
            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">2023:</span>
                <span className="text-sm font-medium">{periods.year_2023}</span>
              </div>
              <div className="text-xs text-gray-500">
                {periods.date_ranges.year_2023?.display || 'N/A'}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
