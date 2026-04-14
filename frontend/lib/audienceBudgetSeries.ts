/**
 * Map budget-general (monthly) to audience chart metrics (weekly x-axis).
 * Each ISO week uses the budget month matching the week-end date, then prorates **volume**
 * counts (customers, orders) by the same week-in-month fraction as Top Markets — not full month.
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

/** English + Swedish month name tokens for calendar month 1–12. */
function monthNameTokensForCalendarMonth(m: number): string[] {
  if (m < 1 || m > 12) return []
  const enLong = new Date(Date.UTC(2000, m - 1, 1)).toLocaleString('en-US', { month: 'long' }).toLowerCase()
  const enShort = new Date(Date.UTC(2000, m - 1, 1)).toLocaleString('en-US', { month: 'short' }).toLowerCase()
  const sv = [
    'januari',
    'februari',
    'mars',
    'april',
    'maj',
    'juni',
    'juli',
    'augusti',
    'september',
    'oktober',
    'november',
    'december',
  ][m - 1]
  return [enLong, enShort, enLong.slice(0, 3), sv, sv.slice(0, 3)].filter(Boolean)
}

/** Map calendar (year, month) to a budget pivot column name. */
export function resolveBudgetMonthKeyFromYMD(budgetMonths: string[], y: number, m: number): string | null {
  if (!y || !m) return null
  const wantYm = `${y}-${String(m).padStart(2, '0')}`
  for (const key of budgetMonths) {
    const p = parseMonthKeyToYearMonth(key)
    if (p && p.y === y && p.m === m) return key
  }
  for (const key of budgetMonths) {
    if (key.includes(wantYm) || key.startsWith(`${y}-${String(m).padStart(2, '0')}`)) return key
  }
  // Month-only columns (e.g. "March", "mars", "March 2026") — common in budget CSVs.
  const tokens = monthNameTokensForCalendarMonth(m)
  for (const key of budgetMonths) {
    const s = String(key).trim()
    const lower = s.toLowerCase()
    const parsed = parseMonthKeyToYearMonth(key)
    if (parsed && parsed.m !== m) continue
    for (const tok of tokens) {
      if (!tok) continue
      if (lower === tok || lower.startsWith(`${tok} `) || lower.startsWith(`${tok}.`)) {
        if (parsed && parsed.y !== y) continue
        const yMatch = s.match(/\b(20\d{2})\b/)
        if (!parsed && yMatch && parseInt(yMatch[1], 10) !== y) continue
        return key
      }
    }
  }
  return null
}

/** Pick the budget table month column that matches the week-end calendar month (legacy single-month lookup). */
export function resolveBudgetMonthKey(budgetMonths: string[], isoWeek: string): string | null {
  const { end } = getWeekDateRange(isoWeek)
  const [ys, ms] = end.split('-')
  const y = parseInt(ys, 10)
  const m = parseInt(ms, 10)
  return resolveBudgetMonthKeyFromYMD(budgetMonths, y, m)
}

/** ISO week Thursday (Mon–Sun): standard “which month does this week belong to” for monthly budgets. */
function isoWeekThursdayYMD(isoWeek: string): { y: number; m: number } {
  const { start } = getWeekDateRange(isoWeek)
  const monday = new Date(`${start}T12:00:00Z`)
  const thu = new Date(monday)
  thu.setUTCDate(monday.getUTCDate() + 3)
  return { y: thu.getUTCFullYear(), m: thu.getUTCMonth() + 1 }
}

/**
 * For each calendar month touched by Mon–Sun, fraction = (days of week in that month) / (days in that month).
 * Used to prorate monthly budget volumes without dropping to zero when week-end month has no column yet.
 */
function weekMonthFractionsForIsoWeek(
  budgetMonths: string[],
  isoWeek: string,
): Array<{ monthKey: string; fraction: number }> {
  const { start, end } = getWeekDateRange(isoWeek)
  const ws = new Date(`${start}T12:00:00Z`)
  const we = new Date(`${end}T12:00:00Z`)
  const dayCounts = new Map<string, number>()
  const cur = new Date(ws)
  while (cur <= we) {
    const y = cur.getUTCFullYear()
    const m = cur.getUTCMonth() + 1
    const k = `${y}-${m}`
    dayCounts.set(k, (dayCounts.get(k) ?? 0) + 1)
    cur.setUTCDate(cur.getUTCDate() + 1)
  }
  const out: Array<{ monthKey: string; fraction: number }> = []
  for (const [ym, overlap] of dayCounts) {
    const [ys, ms] = ym.split('-').map(Number)
    const dim = new Date(Date.UTC(ys, ms, 0)).getUTCDate()
    const monthKey = resolveBudgetMonthKeyFromYMD(budgetMonths, ys, ms)
    if (!monthKey || dim <= 0) continue
    out.push({ monthKey, fraction: overlap / dim })
  }
  return out
}

/** Days of the ISO week in the week-end calendar month ÷ days in that month (fallback when multi-month map is empty). */
export function weekOverlapFractionInMonth(isoWeek: string): number {
  const { start, end } = getWeekDateRange(isoWeek)
  const ws = new Date(`${start}T12:00:00Z`)
  const we = new Date(`${end}T12:00:00Z`)
  const y = we.getUTCFullYear()
  const m = we.getUTCMonth() + 1
  const dim = new Date(Date.UTC(y, m, 0)).getUTCDate()
  let overlap = 0
  const cur = new Date(ws)
  while (cur <= we) {
    if (cur.getUTCFullYear() === y && cur.getUTCMonth() + 1 === m) overlap += 1
    cur.setUTCDate(cur.getUTCDate() + 1)
  }
  return dim > 0 ? overlap / dim : 0
}

/**
 * Monthly aMER plan for the report (selected base week’s month). Not week-specific — used as one target on all chart points.
 */
export function getMonthlyAmerPlanFromBudget(
  baseWeek: string,
  serverByWeek: Record<string, Record<string, number> | null> | null | undefined,
  bg: BudgetGeneralResponse | null | undefined
): number | null {
  // Prefer client-side plan from budget-general: aMER = New Net ÷ Marketing Spend (same as backend fix).
  // Audience-budget-series may still return summed market aMER until API is redeployed.
  if (bg && !bg.error && bg.table && Object.keys(bg.table).length > 0) {
    const fromClient = buildAudienceBudgetMetricsForWeek(bg, baseWeek)
    if (fromClient?.amer != null && Number.isFinite(Number(fromClient.amer))) {
      return Number(fromClient.amer)
    }
  }
  const fromServer = serverByWeek?.[baseWeek]
  if (fromServer && fromServer.amer != null && Number.isFinite(Number(fromServer.amer))) {
    return Number(fromServer.amer)
  }
  return null
}

const CUSTOMER_ORDER_WANTS = new Set(['newcustomers', 'returningcustomers', 'totalcustomers', 'totalorders'])

/** Avoid Share-of-% rows and "… per Customer" rows matching base metrics. */
function labelMatchesBudgetAlias(want: string, ln: string): boolean {
  if (ln === want) return true
  if (CUSTOMER_ORDER_WANTS.has(want) && ln.includes('share')) return false
  if (want.includes(ln) || ln.includes(want)) {
    if (ln.startsWith(want) && ln.length > want.length) {
      const tail = ln.slice(want.length)
      if (tail.startsWith('per') || tail.startsWith('share')) return false
    }
    return true
  }
  return false
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
      if (ln !== want) continue
      const row = table[label]
      if (!row) continue
      const v = row[monthKey]
      if (v != null && Number.isFinite(Number(v))) return Number(v)
    }
    for (const label of keys) {
      const ln = normLabel(label)
      if (!labelMatchesBudgetAlias(want, ln)) continue
      const row = table[label]
      if (!row) continue
      const v = row[monthKey]
      if (v != null && Number.isFinite(Number(v))) return Number(v)
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
 * Client budget from budget-general (multi-month proration, Thursday month for rates) vs API fallback.
 * Prefer client whenever the table is loaded — `/api/audience-budget-series` can lag behind and ignore frontend fixes.
 */
export function resolveAudienceBudgetForWeek(
  isoWeek: string,
  bg: BudgetGeneralResponse | null | undefined,
  serverByWeek: Record<string, Record<string, number> | null> | null | undefined,
): AudienceBudgetMetrics | null {
  if (bg && !bg.error && bg.table && Object.keys(bg.table).length > 0) {
    const client = buildAudienceBudgetMetricsForWeek(bg, isoWeek)
    if (client) return client
  }
  const raw = serverByWeek?.[isoWeek]
  if (raw && typeof raw === 'object' && Object.keys(raw).length > 0) {
    return raw as AudienceBudgetMetrics
  }
  return null
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

  const table = bg.table as Record<string, Record<string, number>>
  const firstRow = Object.values(table)[0] as Record<string, number> | undefined
  const monthKeysFromTable = firstRow && typeof firstRow === 'object' ? Object.keys(firstRow) : []
  // Union API month order + actual pivot keys so "March" in cells matches even if bg.months is incomplete.
  const monthLookupList = [...new Set([...months, ...monthKeysFromTable])]
  const portions = weekMonthFractionsForIsoWeek(monthLookupList, isoWeek)
  const thu = isoWeekThursdayYMD(isoWeek)
  let rateMonthKey =
    resolveBudgetMonthKeyFromYMD(monthLookupList, thu.y, thu.m) ??
    resolveBudgetMonthKey(monthLookupList, isoWeek) ??
    portions[0]?.monthKey ??
    monthLookupList[0] ??
    null
  if (!rateMonthKey) return null

  const g = (...aliases: string[]) => getBudgetCell(table, rateMonthKey, aliases)

  /** Monthly volumes prorated across every calendar month the Mon–Sun week touches (fixes boundary dips). */
  const proratedVolume = (aliases: string[]) => {
    if (portions.length === 0) {
      const f = weekOverlapFractionInMonth(isoWeek)
      const raw = getBudgetCell(table, rateMonthKey!, aliases)
      return f > 0 ? Math.round(raw * f) : 0
    }
    let s = 0
    for (const p of portions) {
      s += getBudgetCell(table, p.monthKey, aliases) * p.fraction
    }
    return Math.round(s)
  }

  const newC = g('New Customers')
  const retC = g('Returning Customers')
  let totalC = g('Total Customers')
  if (totalC <= 0 && (newC > 0 || retC > 0)) totalC = newC + retC
  const totalOrdersMonthly = g('Total Orders')
  let totalAov = g('Total AOV')
  if (totalAov <= 0 && totalOrdersMonthly > 0) {
    const tg = g('Total Gross Revenue')
    if (tg > 0) totalAov = tg / totalOrdersMonthly
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
  const mkt = Math.abs(g('Online Marketing Spend'))
  const newNet = Math.abs(g('New Net Revenue'))
  let amer = 0
  if (mkt > 1e-9) {
    amer = newNet / mkt
  } else {
    const ex = g('aMER') || g('AMER') || g('eMER') || g('emer') || g('OJ aMER')
    amer = ex && Math.abs(ex) >= 1e-9 ? ex : 0
  }
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
    total_customers: proratedVolume(['Total Customers']),
    total_orders: proratedVolume(['Total Orders']),
    new_customers: proratedVolume(['New Customers']),
    returning_customers: proratedVolume(['Returning Customers']),
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
