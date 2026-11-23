/** Shown on every report whose selected week can include 29 Sep–9 Nov 2026. */
export const UK_VAT_NOTE =
  'UK revenue adjusted for missing VAT (orders over £135, 29 Sep to 9 Nov 2026).'

const WINDOW_START = Date.UTC(2026, 8, 29)
const WINDOW_END = Date.UTC(2026, 10, 9)

function isoMonday(year: number, week: number): Date | null {
  if (week < 1 || week > 53) return null
  const jan4 = new Date(Date.UTC(year, 0, 4))
  const jan4Day = jan4.getUTCDay() || 7
  const week1 = new Date(jan4)
  week1.setUTCDate(jan4.getUTCDate() - jan4Day + 1)
  const monday = new Date(week1)
  monday.setUTCDate(week1.getUTCDate() + (week - 1) * 7)
  const check = isoWeek(monday)
  if (check.year !== year || check.week !== week) return null
  return monday
}

function isoWeek(day: Date): { year: number; week: number } {
  const date = new Date(Date.UTC(day.getUTCFullYear(), day.getUTCMonth(), day.getUTCDate()))
  const dayNum = date.getUTCDay() || 7
  date.setUTCDate(date.getUTCDate() + 4 - dayNum)
  const yearStart = new Date(Date.UTC(date.getUTCFullYear(), 0, 1))
  const week = Math.ceil(((date.getTime() - yearStart.getTime()) / 86400000 + 1) / 7)
  return { year: date.getUTCFullYear(), week }
}

function overlaps(start: Date, end: Date): boolean {
  return start.getTime() <= WINDOW_END && end.getTime() >= WINDOW_START
}

/**
 * True when this ISO week, its last-year column, an 8-week lookback, or
 * MTD / quarter / YTD ending that week includes 29 Sep–9 Nov 2026.
 */
export function reportingWeekUsesUkVatAdjustment(isoWeek: string): boolean {
  const match = /^(\d{4})-(\d{1,2})$/.exec(String(isoWeek || '').trim())
  if (!match) return false
  const year = Number(match[1])
  const week = Number(match[2])
  const monday = isoMonday(year, week)
  if (!monday) return false
  const sunday = new Date(monday)
  sunday.setUTCDate(monday.getUTCDate() + 6)
  const lookback = new Date(monday)
  lookback.setUTCDate(monday.getUTCDate() - 49)
  const ranges: Array<[Date, Date]> = [
    [monday, sunday],
    [lookback, sunday],
    [new Date(Date.UTC(year, monday.getUTCMonth(), 1)), sunday],
    [new Date(Date.UTC(year, Math.floor(monday.getUTCMonth() / 3) * 3, 1)), sunday],
    [new Date(Date.UTC(year, 0, 1)), sunday],
  ]
  const lastYear = isoMonday(year - 1, week)
  if (lastYear) {
    const lastYearSunday = new Date(lastYear)
    lastYearSunday.setUTCDate(lastYear.getUTCDate() + 6)
    ranges.push([lastYear, lastYearSunday])
  }
  return ranges.some(([start, end]) => overlaps(start, end))
}
