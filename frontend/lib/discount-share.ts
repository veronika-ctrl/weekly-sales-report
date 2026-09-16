/**
 * 100% share of recorded discount dollars (not share of net sales).
 *
 * Identity (always sums to 100% when denom > 0):
 *
 *   denom = excl. Discount Amount + Exchange Discount
 *   exchange_share = Exchange Discount / denom
 *   promo_share    = excl. Discount Amount / denom
 *
 * Live all-orders Discount Amount ≈ this denom (floating-point noise only).
 * Compare-at / Discount Code / Both / Price Drop on the excl export are
 * discounted *net sales* by pricing type — not discount $. Those belong on
 * the companion mix, not this stack.
 *
 * Slices are an ordered array so extra discount-$ types can be appended later
 * (carved out of the promotional remainder) without changing the denominator.
 */

export const DISCOUNT_AMOUNT_FORMULA =
  '100% of recorded discount $: denominator = excl. Discount Amount + AfterShip Exchange Discount (≈ all-orders Discount Amount). AfterShip % = Exchange Discount ÷ denom. Promotional % = excl. Discount Amount ÷ denom. The two shares sum to 100%. Compare-at / code / both / price drop are discounted net sales by type, not discount $.'

export const DISCOUNTED_NET_TYPE_FORMULA =
  'Companion 100% of discounted *net* (excl. Total − excl. Full Price): Compare-at Price Sale, Discount Code / Auto Discount, Both, and Price Drop Sale. These are sales types, not a split of Discount Amount.'

export type DiscountSliceKind = 'discount_amount' | 'discounted_net'

export type DiscountSliceDef = {
  id: string
  label: string
  color: string
  kind: DiscountSliceKind
}

/** Named discount-$ slices. Append future types after `exchange`; they come out of promotional. */
export const DISCOUNT_AMOUNT_SLICES: DiscountSliceDef[] = [
  { id: 'exchange', label: 'AfterShip exchange credits', color: '#F97316', kind: 'discount_amount' },
  { id: 'promotional', label: 'Promotional markdowns', color: '#4B5563', kind: 'discount_amount' },
]

/** Discounted net by pricing type — not discount $. Easy to extend. */
export const DISCOUNTED_NET_SLICES: DiscountSliceDef[] = [
  { id: 'compareAt', label: 'Compare-at price sale', color: '#7C3AED', kind: 'discounted_net' },
  { id: 'discountCode', label: 'Discount code / auto', color: '#2563EB', kind: 'discounted_net' },
  { id: 'both', label: 'Both', color: '#DB2777', kind: 'discounted_net' },
  { id: 'priceDrop', label: 'Price drop sale', color: '#0F766E', kind: 'discounted_net' },
]

export type NamedDiscountAmount = {
  id: string
  label: string
  color?: string
  amount: number
}

export type DiscountSlice = {
  id: string
  label: string
  color: string
  kind: DiscountSliceKind
  amount: number
  pct: number | null
}

export type RecordedDiscountShare = {
  /** excl. Discount Amount + Exchange Discount (and any extra discount-$ not already in promo). */
  denom: number | null
  exchangeAmount: number
  promotionalAmount: number
  exchangePct: number | null
  promotionalPct: number | null
  /** Ordered 100% stack. Extra types sit between exchange and residual promotional. */
  slices: DiscountSlice[]
}

export type DiscountedNetTypeShare = {
  denom: number | null
  slices: DiscountSlice[]
}

export type DiscountShareChartRow = {
  label: string
  exchange: number | null
  promotional: number | null
  [sliceId: string]: string | number | null
}

export type DiscountedNetChartRow = {
  label: string
  compareAt: number | null
  discountCode: number | null
  both: number | null
  priceDrop: number | null
  [sliceId: string]: string | number | null
}

const SHARE_SUM_EPS = 0.05

function asAmount(value: number | null | undefined) {
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
}

function sharePct(amount: number, denom: number | null): number | null {
  if (denom == null || !(denom > 0)) return null
  return (amount / denom) * 100
}

function sliceColor(id: string, fallback: string, extras: NamedDiscountAmount[]) {
  const known = DISCOUNT_AMOUNT_SLICES.find((s) => s.id === id)
  if (known) return known.color
  const extra = extras.find((s) => s.id === id)
  return extra?.color || fallback
}

/**
 * Recorded-discount 100% mix. `others` are extra discount-$ types carved from
 * the promotional remainder (excl. Discount Amount) so the stack stays at 100%.
 */
export function computeRecordedDiscountShare(args: {
  exchangeDiscount: number | null | undefined
  promotionalDiscount: number | null | undefined
  others?: NamedDiscountAmount[]
}): RecordedDiscountShare {
  const exchangeAmount = asAmount(args.exchangeDiscount)
  const promotionalAmount = asAmount(args.promotionalDiscount)
  const others = (args.others || []).filter((s) => s.id && s.id !== 'exchange' && s.id !== 'promotional')
  const othersTotal = others.reduce((sum, s) => sum + asAmount(s.amount), 0)
  const residualPromo = promotionalAmount - othersTotal
  const denomRaw = exchangeAmount + promotionalAmount
  const denom = denomRaw > 0 ? denomRaw : null

  const slices: DiscountSlice[] = [
    {
      id: 'exchange',
      label: 'AfterShip exchange credits',
      color: sliceColor('exchange', '#F97316', others),
      kind: 'discount_amount',
      amount: exchangeAmount,
      pct: sharePct(exchangeAmount, denom),
    },
    ...others.map((s) => ({
      id: s.id,
      label: s.label || s.id,
      color: s.color || '#94A3B8',
      kind: 'discount_amount' as const,
      amount: asAmount(s.amount),
      pct: sharePct(asAmount(s.amount), denom),
    })),
    {
      id: 'promotional',
      label: others.length > 0 ? 'Other promotional' : 'Promotional markdowns',
      color: sliceColor('promotional', '#4B5563', others),
      kind: 'discount_amount',
      amount: residualPromo,
      pct: sharePct(residualPromo, denom),
    },
  ]

  return {
    denom,
    exchangeAmount,
    promotionalAmount,
    exchangePct: sharePct(exchangeAmount, denom),
    promotionalPct: sharePct(promotionalAmount, denom),
    slices,
  }
}

export function discountShareSumsTo100(share: RecordedDiscountShare, eps = SHARE_SUM_EPS) {
  if (share.exchangePct == null || share.promotionalPct == null) return false
  return Math.abs(share.exchangePct + share.promotionalPct - 100) < eps
}

export function computeDiscountedNetByType(args: {
  compareAt: number | null | undefined
  discountCode: number | null | undefined
  both: number | null | undefined
  priceDrop: number | null | undefined
}): DiscountedNetTypeShare {
  const amounts = {
    compareAt: asAmount(args.compareAt),
    discountCode: asAmount(args.discountCode),
    both: asAmount(args.both),
    priceDrop: asAmount(args.priceDrop),
  }
  const denomRaw = amounts.compareAt + amounts.discountCode + amounts.both + amounts.priceDrop
  const denom = denomRaw > 0 ? denomRaw : null
  const slices: DiscountSlice[] = DISCOUNTED_NET_SLICES.map((def) => {
    const amount = amounts[def.id as keyof typeof amounts]
    return {
      ...def,
      amount,
      pct: sharePct(amount, denom),
    }
  })
  return { denom, slices }
}

export function discountedNetTypeSumsTo100(share: DiscountedNetTypeShare, eps = SHARE_SUM_EPS) {
  const total = share.slices.reduce((sum, s) => sum + (s.pct ?? 0), 0)
  if (share.denom == null) return false
  return Math.abs(total - 100) < eps
}

export function slicesToChartRow(
  label: string,
  slices: DiscountSlice[],
): DiscountShareChartRow {
  const row: DiscountShareChartRow = {
    label,
    exchange: null,
    promotional: null,
  }
  for (const slice of slices) {
    row[slice.id] = slice.pct
  }
  return row
}

export function buildDiscountShareChartData(
  rows: Array<{
    label: string
    exchangeDiscount: number | null | undefined
    promotionalDiscount: number | null | undefined
    others?: NamedDiscountAmount[]
  }>,
): DiscountShareChartRow[] {
  return rows.map((row) =>
    slicesToChartRow(
      row.label,
      computeRecordedDiscountShare({
        exchangeDiscount: row.exchangeDiscount,
        promotionalDiscount: row.promotionalDiscount,
        others: row.others,
      }).slices,
    ),
  )
}

export function buildDiscountedNetTypeChartData(
  rows: Array<{
    label: string
    compareAt: number | null | undefined
    discountCode: number | null | undefined
    both: number | null | undefined
    priceDrop: number | null | undefined
  }>,
): DiscountedNetChartRow[] {
  return rows.map((row) => {
    const share = computeDiscountedNetByType(row)
    const out: DiscountedNetChartRow = {
      label: row.label,
      compareAt: null,
      discountCode: null,
      both: null,
      priceDrop: null,
    }
    for (const slice of share.slices) {
      out[slice.id] = slice.pct
    }
    return out
  })
}

export function chartConfigFromSlices(slices: DiscountSliceDef[]): Record<string, { label: string; color: string }> {
  return Object.fromEntries(slices.map((s) => [s.id, { label: s.label, color: s.color }]))
}
