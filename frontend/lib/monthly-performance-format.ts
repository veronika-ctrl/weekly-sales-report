export function formatSekThousands(value: number | null | undefined): string {
  const n = Number(value || 0)
  if (!Number.isFinite(n) || n === 0) return '0'
  return Math.round(n / 1000).toLocaleString('sv-SE')
}

export function formatYoyPct(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(Number(value))) return '—'
  const n = Number(value)
  const rounded = Math.round(Math.abs(n))
  if (rounded === 0) return '0%'
  return n < 0 ? `(${rounded}%)` : `${rounded}%`
}

export function formatSharePct(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(Number(value))) return '—'
  return `${Math.round(Number(value))}%`
}

export function yoyTone(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(Number(value))) return 'text-muted-foreground'
  if (Number(value) > 0.5) return 'text-emerald-700'
  if (Number(value) < -0.5) return 'text-rose-700'
  return 'text-gray-700'
}
