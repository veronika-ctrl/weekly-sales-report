/** Accept `{ key: T[] }`, a bare array, or a keyed object map. */
export function normalizeNamedSeries<T>(payload: unknown, key: string): T[] {
  if (!payload) return []
  if (Array.isArray(payload)) return payload as T[]
  if (typeof payload !== 'object') return []
  const nested = (payload as Record<string, unknown>)[key]
  if (Array.isArray(nested)) return nested as T[]
  if (nested && typeof nested === 'object') return Object.values(nested as Record<string, T>)
  return []
}
