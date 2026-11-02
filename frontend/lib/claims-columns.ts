/** Shipping belongs on a table only when that table has a non-zero amount. */
export function bucketHasShipping(rows: { freight_sek?: number | null }[]): boolean {
  return rows.some((row) => {
    const value = Number(row.freight_sek)
    return Number.isFinite(value) && value !== 0
  })
}

/** The claims page no longer shows extra discount, including the zero-discount note. */
export function claimsPageNotes(notes: string[]): string[] {
  return notes.filter((note) => !/extra discount/i.test(note))
}
