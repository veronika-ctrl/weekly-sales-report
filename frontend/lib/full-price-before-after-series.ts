import type {
  FullPriceExclComparison,
  FullPriceExclExchangesResponse,
  FullPriceExclMetrics,
} from './api'

export type BeforeAfterView = 'week' | 'month'

export type BeforeAfterPoint = {
  key: string
  label: string
  /** Full price share of net, including AfterShip exchanges. */
  before: number | null
  /** Full price share of net, excluding AfterShip exchanges. */
  after: number | null
  ppDiff: number | null
  fullIncl: number | null
  discIncl: number | null
  fullExcl: number
  discExcl: number
  discountIncl: number | null
  discountExcl: number
  exchangeDiscountSharePct: number | null
}

export type PeriodVsLatest = {
  latestLabel: string
  latestBefore: number | null
  latestAfter: number | null
  periodBefore: number | null
  periodAfter: number | null
  periodLabel: string
  periodStart: string
  periodEnd: string
  /** True when the window total is a different mix than the latest week/month. */
  latestDiffersFromPeriod: boolean
  /** True when excluding exchanges does not move full-price share of net. */
  mixUnchanged: boolean
  exchangeDiscountSharePct: number | null
  exchangeOrders: number
  exchangeNet: number
}

const SHARE_PP_EPS = 0.15

export function weekLabel(w: string) {
  return `W${String(w).split('-')[1]}`
}

export function monthLabel(m: string) {
  const [y, mo] = m.split('-')
  const d = new Date(Number(y), Number(mo) - 1, 1)
  return `${d.toLocaleString('en-US', { month: 'short' })} '${y.slice(2)}`
}

function approxEqual(a: number | null | undefined, b: number | null | undefined, eps = SHARE_PP_EPS) {
  if (a == null || b == null) return false
  return Math.abs(a - b) < eps
}

function splitAmounts(metrics: FullPriceExclMetrics, comparison?: FullPriceExclComparison) {
  const c = comparison
  const fullExcl = c?.full_excl ?? metrics.full_price
  const totalExcl = c?.total_excl ?? metrics.total
  const discExcl = c?.discounted_excl ?? totalExcl - fullExcl

  let fullIncl = c?.full_incl ?? null
  if (fullIncl == null && c?.full_price_share_incl_pct != null && c.total_incl != null) {
    fullIncl = (c.full_price_share_incl_pct / 100) * c.total_incl
  }
  const totalIncl = c?.total_incl ?? null
  let discIncl = c?.discounted_incl ?? null
  if (discIncl == null && fullIncl != null && totalIncl != null) {
    discIncl = totalIncl - fullIncl
  }

  return { fullIncl, discIncl, fullExcl, discExcl }
}

function toPoint(key: string, label: string, metrics: FullPriceExclMetrics): BeforeAfterPoint {
  const c = metrics.comparison
  const amounts = splitAmounts(metrics, c)
  return {
    key,
    label,
    before: c?.full_price_share_incl_pct ?? null,
    after: c?.full_price_share_excl_pct ?? metrics.full_price_share_pct,
    ppDiff: c?.full_price_share_pp_diff ?? null,
    fullIncl: amounts.fullIncl,
    discIncl: amounts.discIncl,
    fullExcl: amounts.fullExcl,
    discExcl: amounts.discExcl,
    discountIncl: c?.discount_incl ?? null,
    discountExcl: c?.discount_excl ?? metrics.discount_amount,
    exchangeDiscountSharePct: c?.exchange_discount_share_pct ?? null,
  }
}

/** Oldest → newest points for the before/after charts. */
export function buildBeforeAfterSeries(
  data: FullPriceExclExchangesResponse | null | undefined,
  view: BeforeAfterView,
): BeforeAfterPoint[] {
  if (!data) return []
  if (view === 'week') {
    return (data.weeks || []).map((w) => toPoint(w.week, weekLabel(w.week), w))
  }
  return [...(data.months_data || [])]
    .reverse()
    .filter((m) => (m.total || 0) > 0 || (m.comparison?.total_incl || 0) > 0)
    .map((m) => toPoint(m.month, monthLabel(m.month), m))
}

export function mixIsEssentiallyFlat(points: BeforeAfterPoint[], eps = SHARE_PP_EPS) {
  if (points.length === 0) return false
  return points.every((p) => {
    if (p.before == null || p.after == null) return true
    return Math.abs(p.after - p.before) < eps
  })
}

export function periodVsLatest(
  data: FullPriceExclExchangesResponse | null | undefined,
  view: BeforeAfterView,
): PeriodVsLatest | null {
  const period = data?.period
  if (!period) return null
  const series = buildBeforeAfterSeries(data, view)
  const latest = series[series.length - 1]
  if (!latest) return null
  const periodBefore = period.comparison?.full_price_share_incl_pct ?? null
  const periodAfter = period.comparison?.full_price_share_excl_pct ?? period.full_price_share_pct
  return {
    latestLabel: latest.label,
    latestBefore: latest.before,
    latestAfter: latest.after,
    periodBefore,
    periodAfter,
    periodLabel: period.label,
    periodStart: period.start,
    periodEnd: period.end,
    latestDiffersFromPeriod: !approxEqual(latest.before, periodBefore),
    mixUnchanged:
      approxEqual(latest.before, latest.after) && approxEqual(periodBefore, periodAfter),
    exchangeDiscountSharePct: period.comparison?.exchange_discount_share_pct ?? null,
    exchangeOrders: period.exchange_orders,
    exchangeNet: period.exchange_net_revenue,
  }
}
