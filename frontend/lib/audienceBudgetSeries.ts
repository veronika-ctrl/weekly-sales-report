/**
 * Map budget-general (monthly) to audience chart metrics (weekly x-axis).
 * Each ISO week uses the budget row for the calendar month of that week's Sunday.
 */

import type { BudgetGeneralResponse } from '@/lib/api'
import { getWeekDateRange } from '@/lib/periods'

/** Same numeric keys as deriveMetrics() on audience-total (for chart lookup). */
export type AudienceBudgetMetrics = {
  total_aov: number
  total_customers: number
  total_orders: number
  new_customers: number
  returning_customers: number
  /** Budget New AOV (or New Net Revenue ÷ new customers). */
  aov_new_customer: number
  /** Budget Returning AOV (or Returning Net Revenue ÷ returning customers). */
  aov_returning_customer: number
  new_customer_share_pct: number
  returning_customer_share_pct: number
  return_rate_pct: number
  return_rate_new_pct: number
  return_rate_returning_pct: number
  cos_pct: number
  cac: number
  amer: number
}

function normLabel(s: string): string {
  return s.toLowerCase().replace(/[^a-z0-9]/g, '')
}

const SWEDISH_MONTHS: Record<string, number> = {
  januari: 1,
  februari: 2,
  mars: 3,
  april: 4,
  maj: 5,
  juni: 6,
  juli: 7,
  augusti: 8,
  september: 9,
  oktober: 10,
  november: 11,
  december: 12,
}

/** English month names — `new Date("March 2026")` is invalid in JS; we must parse explicitly. */
const ENGLISH_MONTHS: Record<string, number> = {
  january: 1,
  february: 2,
  march: 3,
  april: 4,
  may: 5,
  june: 6,
  july: 7,
  august: 8,
  september: 9,
  october: 10,
  november: 11,
  december: 12,
  jan: 1,
  feb: 2,
  mar: 3,
  apr: 4,
  jun: 6,
  jul: 7,
  aug: 8,
  sep: 9,
  sept: 9,
  oct: 10,
  nov: 11,
  dec: 12,
}

function parseMonthKeyToYearMonth(key: string): { y: number; m: number } | null {
  const s = String(key).trim()
  if (!s) return null
  const ym = s.match(/^(\d{4})-(\d{2})(?:-\d{2})?$/)
  if (ym) {
    const y = parseInt(ym[1], 10)
    const m = parseInt(ym[2], 10)
    if (m >= 1 && m <= 12) return { y, m }
  }
  const parts = s.toLowerCase().replace(/\./g, '').split(/\s+/).filter(Boolean)
  if (parts.length === 2 && /^\d{4}$/.test(parts[1])) {
    const y = parseInt(parts[1], 10)
    const token = parts[0]
    const mo =
      SWEDISH_MONTHS[token] ?? ENGLISH_MONTHS[token] ?? ENGLISH_MONTHS[token.slice(0, 3)]
    if (mo) return { y, m: mo }
  }
  // "2026-03-15" or ISO datetime
  const iso = s.match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (iso) {
    const y = parseInt(iso[1], 10)
    const m = parseInt(iso[2], 10)
    if (m >= 1 && m <= 12) return { y, m }
  }
  const d = new Date(s)
  if (!Number.isNaN(d.getTime())) {
    return { y: d.getFullYear(), m: d.getMonth() + 1 }
  }
  return null
}

/** Pick the budget table month column that matches the week-end calendar month. */
export function resolveBudgetMonthKey(budgetMonths: string[], isoWeek: string): string | null {
  const { end } = getWeekDateRange(isoWeek)
  const [ys, ms] = end.split('-')
  const y = parseInt(ys, 10)
  const m = parseInt(ms, 10)
  if (!y || !m) return null
  const wantYm = `${y}-${String(m).padStart(2, '0')}`
  for (const key of budgetMonths) {
    const p = parseMonthKeyToYearMonth(key)
    if (p && p.y === y && p.m === m) return key
  }
  // Substring match when month column is ISO date or starts with YYYY-MM
  for (const key of budgetMonths) {
    if (key.includes(wantYm) || key.startsWith(`${y}-${String(m).padStart(2, '0')}`)) return key
  }
  return null
}

function getBudgetCell(
  table: Record<string, Record<string, number>>,
  monthKey: string,
  aliases: string[],
): number {
  const keys = Object.keys(table)
  for (const al of aliases) {
    const want = normLabel(al)
    if (!want) continue
    for (const label of keys) {
      const ln = normLabel(label)
      if (ln === want || ln.includes(want) || want.includes(ln)) {
        const row = table[label]
        if (!row) continue
        const v = row[monthKey]
        if (v != null && Number.isFinite(Number(v))) return Number(v)
      }
    }
  }
  return 0
}

function normalizeSharePct(x: number): number {
  if (x > 0 && x <= 1) return x * 100
  return x
}

function normalizeCosPct(x: number): number {
  if (x > 0 && x <= 1) return x * 100
  return x
}

/**
 * Build audience-shaped budget metrics for one ISO week from budget-general.
 */
export function buildAudienceBudgetMetricsForWeek(
  bg: BudgetGeneralResponse | null | undefined,
  isoWeek: string,
): AudienceBudgetMetrics | null {
  if (!bg || bg.error || !bg.table || typeof bg.table !== 'object') return null
  let months = Array.isArray(bg.months) && bg.months.length ? [...bg.months] : []
  if (!months.length) {
    const firstRow = Object.values(bg.table)[0] as Record<string, number> | undefined
    if (firstRow && typeof firstRow === 'object') months = Object.keys(firstRow)
  }
  if (!months.length) return null
  const monthKey = resolveBudgetMonthKey(months, isoWeek)
  if (!monthKey) return null
  const table = bg.table as Record<string, Record<string, number>>
  const g = (...aliases: string[]) => getBudgetCell(table, monthKey, aliases)

  const newC = g('New Customers')
  const retC = g('Returning Customers')
  let totalC = g('Total Customers')
  if (totalC <= 0 && (newC > 0 || retC > 0)) totalC = newC + retC
  const totalOrders = g('Total Orders')
  let totalAov = g('Total AOV')
  if (totalAov <= 0 && totalOrders > 0) {
    const tg = g('Total Gross Revenue')
    if (tg > 0) totalAov = tg / totalOrders
  }

  const newGross = g('New Gross Revenue')
  const newReturns = g('New Returns')
  const retGross = g('Returning Gross Revenue')
  const retReturns = g('Returning Returns')
  const totalGross = g('Total Gross Revenue')

  const returnRateNewPct = newGross > 0 ? (newReturns / newGross) * 100 : 0
  const returnRateRetPct = retGross > 0 ? (retReturns / retGross) * 100 : 0
  const retSum = newReturns + retReturns
  const returnRatePct = totalGross > 0 ? (retSum / totalGross) * 100 : 0

  let shareNew = g('Share of New Customers')
  let shareRet = g('Share of Returning Customers')
  shareNew = normalizeSharePct(shareNew)
  shareRet = normalizeSharePct(shareRet)
  if (totalC > 0) {
    if (shareNew <= 0 && newC > 0) shareNew = (newC / totalC) * 100
    if (shareRet <= 0 && retC > 0) shareRet = (retC / totalC) * 100
  }

  let cosPct = normalizeCosPct(g('COS %'))
  const mkt = g('Online Marketing Spend')
  let amer = g('aMER')
  if (!amer) amer = g('AMER')
  const cac = newC > 0 ? mkt / newC : 0

  let aovNew = g('New AOV')
  let aovRet = g('Returning AOV')
  if (aovNew <= 0 && newC > 0) {
    const nn = g('New Net Revenue')
    if (nn > 0) aovNew = nn / newC
  }
  if (aovRet <= 0 && retC > 0) {
    const rn = g('Returning Net Revenue')
    if (rn > 0) aovRet = rn / retC
  }

  return {
    total_aov: Math.round(totalAov),
    total_customers: Math.round(totalC),
    total_orders: Math.round(totalOrders),
    new_customers: Math.round(newC),
    returning_customers: Math.round(retC),
    aov_new_customer: Math.round(aovNew * 100) / 100,
    aov_returning_customer: Math.round(aovRet * 100) / 100,
    new_customer_share_pct: Math.round(shareNew * 10) / 10,
    returning_customer_share_pct: Math.round(shareRet * 10) / 10,
    return_rate_pct: Math.round(returnRatePct * 10) / 10,
    return_rate_new_pct: Math.round(returnRateNewPct * 10) / 10,
    return_rate_returning_pct: Math.round(returnRateRetPct * 10) / 10,
    cos_pct: Math.round(cosPct * 10) / 10,
    cac: Math.round(cac),
    amer: Math.round(amer * 100) / 100,
  }
}

/**
 * Scale global monthly budget metrics to a market using that week's actual country / Total ratios.
 */
export function allocateAudienceBudgetToMarket(
  globalBudget: AudienceBudgetMetrics,
  actualCountry: { new_customers?: number; returning_customers?: number; total_customers?: number; total_orders?: number },
  actualTotal: { new_customers?: number; returning_customers?: number; total_customers?: number; total_orders?: number },
): AudienceBudgetMetrics {
  const safeDiv = (a: number, b: number) => (b > 0 ? a / b : 0)
  const rNew = safeDiv(Number(actualCountry.new_customers) || 0, Number(actualTotal.new_customers) || 0)
  const rRet = safeDiv(Number(actualCountry.returning_customers) || 0, Number(actualTotal.returning_customers) || 0)
  const rCust = safeDiv(Number(actualCountry.total_customers) || 0, Number(actualTotal.total_customers) || 0)
  const rOrd = safeDiv(Number(actualCountry.total_orders) || 0, Number(actualTotal.total_orders) || 0)

  return {
    ...globalBudget,
    new_customers: Math.round(globalBudget.new_customers * rNew),
    returning_customers: Math.round(globalBudget.returning_customers * rRet),
    total_customers: Math.round(globalBudget.total_customers * rCust),
    total_orders: Math.round(globalBudget.total_orders * rOrd),
    total_aov: globalBudget.total_aov,
    aov_new_customer: globalBudget.aov_new_customer,
    aov_returning_customer: globalBudget.aov_returning_customer,
    new_customer_share_pct: globalBudget.new_customer_share_pct,
    returning_customer_share_pct: globalBudget.returning_customer_share_pct,
    return_rate_pct: globalBudget.return_rate_pct,
    return_rate_new_pct: globalBudget.return_rate_new_pct,
    return_rate_returning_pct: globalBudget.return_rate_returning_pct,
    cos_pct: globalBudget.cos_pct,
    cac: globalBudget.cac,
    amer: globalBudget.amer,
  }
}
