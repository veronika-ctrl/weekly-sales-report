/**
 * Display-only: omit a Claims money column when every value in that table is 0.
 * Does not change the Cin7 calc — freight_sek / discount_sek stay on the payload.
 */

export type ClaimsMoneyRow = {
  freight_sek?: number | null
  discount_sek?: number | null
}

export function hasNonZeroAmount(
  rows: ReadonlyArray<ClaimsMoneyRow | null | undefined>,
  key: 'freight_sek' | 'discount_sek',
): boolean {
  return rows.some((row) => {
    if (row == null) return false
    const value = Number(row[key])
    return Number.isFinite(value) && value !== 0
  })
}

export type ClaimsTableColumnId =
  | 'orders'
  | 'units'
  | 'product_cost_sek'
  | 'freight_sek'
  | 'discount_sek'

export type ClaimsTableColumn = {
  id: ClaimsTableColumnId
  header: string
}

/** Column list for Claims money tables. Extra discount and shipping drop out when they are all 0. */
export function visibleClaimsTableColumns(rows: ReadonlyArray<ClaimsMoneyRow>): ClaimsTableColumn[] {
  const columns: ClaimsTableColumn[] = [
    { id: 'orders', header: 'Claims' },
    { id: 'units', header: 'Units' },
    { id: 'product_cost_sek', header: 'Landed cost' },
  ]
  if (hasNonZeroAmount(rows, 'freight_sek')) {
    columns.push({ id: 'freight_sek', header: 'Shipping' })
  }
  if (hasNonZeroAmount(rows, 'discount_sek')) {
    columns.push({ id: 'discount_sek', header: 'Extra discount' })
  }
  return columns
}
