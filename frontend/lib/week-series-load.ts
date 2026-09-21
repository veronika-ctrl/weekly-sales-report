'use client'

import { useCallback, useEffect, useState } from 'react'

export { normalizeNamedSeries } from './week-series'

/**
 * Load a week-scoped report from the API.
 * Summary only fills table1 now (to avoid Render OOM), so these pages must
 * fetch themselves instead of waiting on DataCacheContext forever.
 */
export function useWeekSeriesLoad<TPayload>(options: {
  baseWeek: string | null | undefined
  load: (week: string) => Promise<TPayload>
  cached: TPayload | null | undefined
  hasRows: (payload: TPayload | null | undefined) => boolean
}) {
  const { baseWeek, load, cached, hasRows } = options
  const [data, setData] = useState<TPayload | null>(() => (hasRows(cached) ? (cached as TPayload) : null))
  const [loading, setLoading] = useState(() => Boolean(baseWeek) && !hasRows(cached))
  const [error, setError] = useState<string | null>(null)
  const [reloadToken, setReloadToken] = useState(0)

  useEffect(() => {
    if (!baseWeek) {
      setData(null)
      setLoading(false)
      setError(null)
      return
    }

    if (reloadToken === 0 && hasRows(cached)) {
      setData(cached as TPayload)
      setLoading(false)
      setError(null)
      return
    }

    let cancelled = false
    setLoading(true)
    setError(null)
    load(baseWeek)
      .then((res) => {
        if (!cancelled) setData(res)
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setData(null)
          setError(e instanceof Error ? e.message : 'Failed to load')
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
    // Intentionally week + retry only: loaders are stable module functions.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [baseWeek, reloadToken])

  const retry = useCallback(() => setReloadToken((n) => n + 1), [])
  return { data, loading, error, retry }
}
