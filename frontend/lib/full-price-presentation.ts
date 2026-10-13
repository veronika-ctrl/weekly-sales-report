/**
 * Display-only helpers for Full Price vs Sale and Discount Types slides.
 * Do not use these for metric math — they only decide how values are shown.
 */

export const AMOUNTS_INCL_VAT_NOTE = 'Amounts incl. VAT, before returns.'
export const SHOPIFY_GROSS_EXCL_VAT_NOTE = 'Shopify gross sales and discounts, excl. VAT.'

export const MIX_AXIS_DOMAIN: [number, number] = [0, 100]
export const MIX_AXIS_TICKS = [0, 25, 50, 75, 100] as const

type LastYearTotals = {
  total?: number | null
  full_price_pct?: number | null
  weighted_discount_pct?: number | null
} | null | undefined

/** Last-year totals of 0 (or a missing last_year object) are treated as no LY data. */
export function hasLastYearTotal(lastYear: LastYearTotals): boolean {
  return lastYear != null && Number(lastYear.total) > 0
}

/** Chart series value: skip the LY line when last-year total is missing/zero. */
export function lastYearShareForChart(lastYear: LastYearTotals): number | null {
  if (!hasLastYearTotal(lastYear)) return null
  const pct = lastYear?.full_price_pct
  return pct == null ? null : Number(pct)
}

export function lyOrNull<T>(lastYear: LastYearTotals, value: T | null | undefined): T | null {
  if (!hasLastYearTotal(lastYear)) return null
  return value == null ? null : value
}

export function shareChartPoint(args: {
  label: string
  fullPricePct: number | null | undefined
  lastYear?: LastYearTotals
}): { label: string; value: number; lastYear: number | null } {
  return {
    label: args.label,
    value: args.fullPricePct ?? 0,
    lastYear: lastYearShareForChart(args.lastYear),
  }
}

/** Integer percent ticks for stacked 100% charts. Avoids "0000001%" from float/scientific ticks. */
export function formatMixAxisTick(value: unknown): string {
  const n = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(n)) return ''
  return `${Math.round(n)}%`
}

export type TypesPeriodLike = {
  key: string
  month?: string
  end: string
}

function lastDayOfMonthISO(ym: string): string {
  const [y, mo] = ym.split('-').map(Number)
  if (!Number.isFinite(y) || !Number.isFinite(mo)) return ''
  return new Date(Date.UTC(y, mo, 0)).toISOString().slice(0, 10)
}

export function isPartialCalendarMonth(period: TypesPeriodLike): boolean {
  const ym = period.month || period.key
  const last = lastDayOfMonthISO(ym)
  if (!last) return false
  return String(period.end).slice(0, 10) < last
}

/**
 * Monthly discount-types layout: last full month is the primary table;
 * current month-to-date (if the latest month is still partial) sits below.
 */
export function monthlyTypesLayout<T extends TypesPeriodLike>(
  periods: T[],
): { periodsAsc: T[]; primary: T | undefined; mtd: T | undefined } {
  const periodsAsc = [...periods].sort((a, b) => String(a.key).localeCompare(String(b.key)))
  if (periodsAsc.length === 0) return { periodsAsc, primary: undefined, mtd: undefined }
  const latest = periodsAsc[periodsAsc.length - 1]
  if (isPartialCalendarMonth(latest) && periodsAsc.length > 1) {
    return {
      periodsAsc,
      primary: periodsAsc[periodsAsc.length - 2],
      mtd: latest,
    }
  }
  return { periodsAsc, primary: latest, mtd: undefined }
}
