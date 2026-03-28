/**
 * Client-side period calculation (mirrors backend get_periods_for_week / get_week_date_range / get_ytd_periods).
 * Used when no backend is configured (e.g. production reading only from Supabase).
 */

export interface PeriodsResponse {
  actual: string
  last_week: string
  last_year: string
  year_2023: string
  date_ranges: Record<string, { start: string; end: string; display: string }>
  ytd_periods: Record<string, { start: string; end: string }>
}

const ISO_WEEK_REGEX = /^(\d{4})-(\d{1,2})$/

function parseIsoWeek(isoWeek: string): { year: number; week: number } {
  const m = isoWeek.match(ISO_WEEK_REGEX)
  if (!m) throw new Error(`Invalid ISO week: ${isoWeek}. Expected YYYY-WW`)
  const year = parseInt(m[1], 10)
  const week = parseInt(m[2], 10)
  if (week < 1 || week > 53) throw new Error(`Invalid week number: ${week}`)
  return { year, week }
}

/** Whether the given year has 53 ISO weeks (Jan 4 is Thu or later). */
function has53Weeks(year: number): boolean {
  const jan4 = new Date(Date.UTC(year, 0, 4))
  const day = jan4.getUTCDay() // 0 Sun .. 6 Sat; Thu = 4
  return day >= 4
}

function getPreviousWeek(year: number, week: number): string {
  if (week > 1) return `${year}-${String(week - 1).padStart(2, '0')}`
  const prevYear = year - 1
  const w = has53Weeks(prevYear) ? 53 : 52
  return `${prevYear}-${String(w).padStart(2, '0')}`
}

/** Monday of ISO week (year, week). */
function getMondayOfIsoWeek(year: number, week: number): Date {
  const jan4 = new Date(Date.UTC(year, 0, 4))
  const jan4Day = jan4.getUTCDay()
  const mondayOffset = jan4Day === 0 ? -6 : 1 - jan4Day
  const firstMonday = new Date(Date.UTC(year, 0, 4 + mondayOffset))
  const targetMonday = new Date(firstMonday)
  targetMonday.setUTCDate(firstMonday.getUTCDate() + (week - 1) * 7)
  return targetMonday
}

function formatYMD(d: Date): string {
  const y = d.getUTCFullYear()
  const m = String(d.getUTCMonth() + 1).padStart(2, '0')
  const day = String(d.getUTCDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

/** Monday–Sunday date range for an ISO week (YYYY-WW). Exported for charts that need week-end calendar month (e.g. budget). */
export function getWeekDateRange(isoWeek: string): { start: string; end: string; display: string } {
  const { year, week } = parseIsoWeek(isoWeek)
  const monday = getMondayOfIsoWeek(year, week)
  const sunday = new Date(monday)
  sunday.setUTCDate(monday.getUTCDate() + 6)
  const start = formatYMD(monday)
  const end = formatYMD(sunday)
  const startDisplay = monday.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  const endDisplay = sunday.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  return { start, end, display: `${startDisplay} - ${endDisplay}` }
}

function getYtdPeriodsForWeek(isoWeek: string): Record<string, { start: string; end: string }> {
  const { year, week } = parseIsoWeek(isoWeek)
  const { end: weekEnd } = getWeekDateRange(isoWeek)
  const weekEndDt = new Date(weekEnd + 'T12:00:00Z')

  const apr1Current = new Date(Date.UTC(year, 3, 1))
  const fyStartCurrent = weekEndDt < apr1Current ? `${year - 1}-04-01` : `${year}-04-01`

  const lastYearWeek = `${year - 1}-${String(week).padStart(2, '0')}`
  const { end: weekEndLastYear } = getWeekDateRange(lastYearWeek)
  const weekEndLyDt = new Date(weekEndLastYear + 'T12:00:00Z')
  const apr1Ly = new Date(Date.UTC(year - 1, 3, 1))
  const fyStartLastYear = weekEndLyDt < apr1Ly ? `${year - 2}-04-01` : `${year - 1}-04-01`

  const week2023 = `2023-${String(week).padStart(2, '0')}`
  const { end: weekEnd2023 } = getWeekDateRange(week2023)
  const weekEnd2023Dt = new Date(weekEnd2023 + 'T12:00:00Z')
  const apr1_2023 = new Date(Date.UTC(2023, 3, 1))
  const fyStart2023 = weekEnd2023Dt < apr1_2023 ? '2022-04-01' : '2023-04-01'

  return {
    ytd_actual: { start: fyStartCurrent, end: weekEnd },
    ytd_last_year: { start: fyStartLastYear, end: weekEndLastYear },
    ytd_2023: { start: fyStart2023, end: weekEnd2023 },
  }
}

/**
 * Compute PeriodsResponse for a base week (YYYY-WW) on the client.
 * Use when no backend is available (e.g. production reading only from Supabase).
 */
export function getPeriodsFromBaseWeek(baseWeek: string): PeriodsResponse {
  const parsed = parseIsoWeek(baseWeek)
  const { year, week } = parsed
  const actual = baseWeek
  const last_week = getPreviousWeek(year, week)
  const last_year = `${year - 1}-${String(week).padStart(2, '0')}`
  const year_2023 = `2023-${String(week).padStart(2, '0')}`

  const periods: Record<string, string> = { actual, last_week, last_year, year_2023 }
  const date_ranges: Record<string, { start: string; end: string; display: string }> = {}
  for (const [name, isoWeek] of Object.entries(periods)) {
    try {
      date_ranges[name] = getWeekDateRange(isoWeek)
    } catch {
      date_ranges[name] = { start: 'N/A', end: 'N/A', display: 'N/A' }
    }
  }
  const ytd_periods = getYtdPeriodsForWeek(baseWeek)

  return {
    actual,
    last_week,
    last_year,
    year_2023,
    date_ranges,
    ytd_periods,
  }
}
