/**
 * 100% sales mix: full price + AfterShip exchanges + promotional discount.
 *
 * AfterShip size-swaps have ~0 net (custom discount so the customer is not
 * charged twice). A net-only mix hides them. To show exchanges as a sales
 * slice, put exchange *gross* in the denominator next to non-exchange net.
 *
 *   denom = excl. Total + Exchange Gross Value
 *   full price % = excl. Full Price / denom
 *   exchanges %  = Exchange Gross Value / denom
 *   promo %      = (excl. Total − excl. Full Price) / denom
 *
 * Identity: excl. Full Price + exchange gross + (excl. Total − excl. Full Price) = denom.
 * This is share of sales, not exchange credits ÷ recorded discount.
 */

export const SALES_MIX_FORMULA =
  '100% of sales: denominator = non-exchange net (excl. Total) + AfterShip exchange gross. Full price = excl. Full Price ÷ denom. AfterShip exchanges = Exchange Gross Value ÷ denom (size-swap new-order value, not a promo markdown). Promotional discount = (excl. Total − excl. Full Price) ÷ denom. The three shares sum to 100%. AfterShip net is ~0, so a net-only mix would hide exchanges.'

export type SalesMixShares = {
  denom: number | null
  fullPrice: number
  exchangeGross: number
  promoNet: number
  fullPricePct: number | null
  exchangePct: number | null
  promoPct: number | null
}

export type SalesMixChartRow = {
  label: string
  fullPrice: number | null
  exchange: number | null
  promo: number | null
}

const MIX_SUM_EPS = 0.05

export function computeSalesMix(args: {
  exclFull: number
  exclTotal: number
  exchangeGross: number
}): SalesMixShares {
  const fullPrice = Number(args.exclFull) || 0
  const exclTotal = Number(args.exclTotal) || 0
  const exchangeGross = Number(args.exchangeGross) || 0
  const promoNet = exclTotal - fullPrice
  const denom = exclTotal + exchangeGross
  if (!(denom > 0)) {
    return {
      denom: null,
      fullPrice,
      exchangeGross,
      promoNet,
      fullPricePct: null,
      exchangePct: null,
      promoPct: null,
    }
  }
  return {
    denom,
    fullPrice,
    exchangeGross,
    promoNet,
    fullPricePct: (fullPrice / denom) * 100,
    exchangePct: (exchangeGross / denom) * 100,
    promoPct: (promoNet / denom) * 100,
  }
}

/** True when the three mix %s are present and sum to ~100. */
export function salesMixSumsTo100(mix: SalesMixShares, eps = MIX_SUM_EPS) {
  if (mix.fullPricePct == null || mix.exchangePct == null || mix.promoPct == null) return false
  return Math.abs(mix.fullPricePct + mix.exchangePct + mix.promoPct - 100) < eps
}

export function buildSalesMixChartData(
  rows: Array<{ label: string } & Parameters<typeof computeSalesMix>[0]>,
): SalesMixChartRow[] {
  return rows.map((row) => {
    const mix = computeSalesMix(row)
    return {
      label: row.label,
      fullPrice: mix.fullPricePct,
      exchange: mix.exchangePct,
      promo: mix.promoPct,
    }
  })
}
