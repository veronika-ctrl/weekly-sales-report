/** Supabase query helpers for budget data and weekly report metrics. */

import { supabase, isSupabaseAvailable } from './supabase'

export interface BudgetGeneralRow {
  base_week: string
  metric: string
  customer: string
  month: string
  value: number
  kind: 'budget' | 'actuals'
}

export interface BudgetGeneralTotal {
  base_week: string
  metric: string
  customer: string
  scope: 'TOTAL' | 'YTD'
  value: number
  kind: 'budget' | 'actuals'
}

/**
 * Load Budget General data from Supabase only (no API fallback).
 * Returns data in the same format as the API endpoint, or {} if none.
 */
export async function loadBudgetGeneralFromSupabase(
  baseWeek: string
): Promise<{ budget?: any; actuals?: any }> {
  try {
    if (!isSupabaseAvailable() || !supabase || !process.env.NEXT_PUBLIC_SUPABASE_URL) {
      return {}
    }

    const { data: detailedRows, error: detailedError } = await supabase
      .from('budget_general')
      .select('*')
      .eq('base_week', baseWeek)

    if (detailedError) {
      console.warn('Supabase budget_general error:', detailedError)
      return {}
    }

    const { data: totalsRows, error: totalsError } = await supabase
      .from('budget_general_totals')
      .select('*')
      .eq('base_week', baseWeek)

    if (totalsError) {
      console.warn('Supabase budget_general_totals error:', totalsError)
      return {}
    }

    if (!detailedRows || detailedRows.length === 0) {
      return {}
    }

    // Transform Supabase rows to API format
    const budgetRows = detailedRows.filter((r: BudgetGeneralRow) => r.kind === 'budget')
    const actualsRows = detailedRows.filter((r: BudgetGeneralRow) => r.kind === 'actuals')
    const budgetTotals = totalsRows?.filter((r: BudgetGeneralTotal) => r.kind === 'budget') || []
    const actualsTotals = totalsRows?.filter((r: BudgetGeneralTotal) => r.kind === 'actuals') || []

    // Build budget data structure
    const budget = rowsToBudgetFormat(baseWeek, budgetRows, budgetTotals)
    const actuals = rowsToBudgetFormat(baseWeek, actualsRows, actualsTotals)

    return { budget, actuals }
  } catch (error: any) {
    console.warn('Error loading budget from Supabase:', error?.message || error)
    return {}
  }
}

/**
 * Transform Supabase rows to API format.
 */
function rowsToBudgetFormat(
  baseWeek: string,
  rows: BudgetGeneralRow[],
  totals: BudgetGeneralTotal[]
): any {
  // Group by metric
  const table: Record<string, Record<string, number>> = {}
  const totalsMap: Record<string, number> = {}
  const ytdMap: Record<string, number> = {}
  const customerByMetric: Record<string, string> = {}
  const monthsSet = new Set<string>()

  for (const row of rows) {
    if (!table[row.metric]) {
      table[row.metric] = {}
    }
    table[row.metric][row.month] = row.value
    customerByMetric[row.metric] = row.customer
    monthsSet.add(row.month)
  }

  for (const total of totals) {
    if (total.scope === 'TOTAL') {
      totalsMap[total.metric] = total.value
    } else if (total.scope === 'YTD') {
      ytdMap[total.metric] = total.value
    }
    customerByMetric[total.metric] = total.customer
  }

  const months = Array.from(monthsSet).sort((a, b) => {
    // Sort chronologically (simple string sort for "Month YYYY" format)
    return a.localeCompare(b)
  })

  const metrics = Object.keys(table).sort()

  // Build display name mapping
  const displayNameByMetric: Record<string, string> = {}
  for (const metric of metrics) {
    const metricLower = metric.toLowerCase()
    if (metricLower.startsWith('share of returning customers')) {
      displayNameByMetric[metric] = 'Share of total %'
    } else if (metricLower.startsWith('share of new customers')) {
      displayNameByMetric[metric] = 'Share of total %'
    } else {
      displayNameByMetric[metric] = metric
    }
  }

  return {
    week: baseWeek,
    months,
    metrics,
    table,
    totals: totalsMap,
    ytd_totals: ytdMap,
    customer_by_metric: customerByMetric,
    display_name_by_metric: displayNameByMetric,
  }
}

/**
 * Get all base_week values that have data in Supabase (weekly_report_metrics).
 * Used to show "Has data" / "No data" per week in the week dropdown.
 */
export async function getWeeksWithDataFromSupabase(): Promise<string[]> {
  try {
    if (!isSupabaseAvailable() || !supabase || !process.env.NEXT_PUBLIC_SUPABASE_URL) {
      return []
    }
    const { data, error } = await supabase
      .from('weekly_report_metrics')
      .select('base_week')
      .order('base_week', { ascending: false })

    if (error) {
      console.debug('Supabase getWeeksWithData error:', error.message)
      return []
    }
    const rows = (data || []) as { base_week?: string }[]
    return rows.map((r) => r.base_week).filter((w): w is string => typeof w === 'string')
  } catch (error: any) {
    console.warn('Error getting weeks with data from Supabase:', error?.message || error)
    return []
  }
}

/**
 * Get the latest base_week that has data in Supabase (weekly_report_metrics).
 * Used to auto-select the most recent week on first load when no URL/localStorage week is set.
 */
export async function getLatestBaseWeekFromSupabase(): Promise<string | null> {
  try {
    if (!isSupabaseAvailable() || !supabase || !process.env.NEXT_PUBLIC_SUPABASE_URL) {
      return null
    }
    const { data, error } = await supabase
      .from('weekly_report_metrics')
      .select('base_week')
      .order('base_week', { ascending: false })
      .limit(1)
      .maybeSingle()

    if (error) {
      console.debug('Supabase getLatestBaseWeek error:', error.message)
      return null
    }
    const row = data as { base_week?: string } | null
    return row?.base_week ?? null
  } catch (error: any) {
    console.warn('Error getting latest base week from Supabase:', error?.message || error)
    return null
  }
}

/**
 * Load Weekly Report Metrics from Supabase only (no API fallback).
 * Returns the complete BatchMetricsResponse structure, or null if no data for the week.
 */
export async function loadWeeklyReportMetricsFromSupabase(baseWeek: string): Promise<any | null> {
  try {
    if (!isSupabaseAvailable() || !supabase || !process.env.NEXT_PUBLIC_SUPABASE_URL) {
      console.debug('Supabase not configured or not available')
      return null
    }

    console.debug(`Loading metrics from Supabase for week ${baseWeek}...`)
    const { data, error } = await supabase
      .from('weekly_report_metrics')
      .select('*')
      .eq('base_week', baseWeek)
      .maybeSingle()

    if (error) {
      console.debug(`Supabase for week ${baseWeek}:`, error.message)
      return null
    }

    if (!data) {
      console.debug(`No data in Supabase for week ${baseWeek}`)
      return null
    }

    const row = data as { base_week?: string; metrics?: unknown }
    if (!row.metrics) {
      console.warn(`Row exists but no metrics field for week ${baseWeek}`)
      return null
    }

    let metrics: any
    if (typeof row.metrics === 'string') {
      metrics = JSON.parse(row.metrics)
    } else {
      metrics = row.metrics
    }

    console.log(`✅ Loaded weekly report metrics from Supabase for ${baseWeek}`)
    return metrics
  } catch (error: any) {
    console.warn('Error loading from Supabase:', error?.message || error)
    return null
  }
}

