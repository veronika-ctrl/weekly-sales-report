import { describeApiFetchFailure } from './api-fetch'

export type SettledResult<T> = { ok: true; value: T } | { ok: false; error: string }

export type FullPriceGranularity = 'week' | 'month'

export type SectionViewState = 'loading' | 'error' | 'empty' | 'ready'

export async function settleLoad<T>(
  loader: () => Promise<T>,
  endpoint: string,
  timeoutMs?: number,
): Promise<SettledResult<T>> {
  try {
    return { ok: true, value: await loader() }
  } catch (err) {
    return { ok: false, error: describeApiFetchFailure(err, { endpoint, timeoutMs }) }
  }
}

/** True when the excl-exchanges API returned a usable window, not a missing-upload stub. */
export function hasExclExchangesPayload(
  data:
    | {
        period?: unknown | null
        days?: unknown[] | null
        weeks?: unknown[] | null
        months_data?: unknown[] | null
      }
    | null
    | undefined,
): boolean {
  if (!data) return false
  if (data.period) return true
  return (
    (data.days?.length || 0) > 0 ||
    (data.weeks?.length || 0) > 0 ||
    (data.months_data?.length || 0) > 0
  )
}

/**
 * Empty-state vs error for the exchange-excluded section.
 * A sibling fetch failure must not look like “no file uploaded”.
 */
export function exclExchangesSectionState(args: {
  view: FullPriceGranularity
  weekly: Parameters<typeof hasExclExchangesPayload>[0]
  monthly: Parameters<typeof hasExclExchangesPayload>[0]
  loading: boolean
  error: string | null
}): SectionViewState {
  const data = args.view === 'week' ? args.weekly : args.monthly
  if (hasExclExchangesPayload(data)) return 'ready'
  if (args.loading) return 'loading'
  if (args.error) return 'error'
  // Successful 200 with no period/days → upload empty-state. Null means we have not loaded yet.
  if (data) return 'empty'
  return 'loading'
}

export function allOrdersSectionState(args: {
  hasRows: boolean
  loading: boolean
  error: string | null
  data: unknown
}): SectionViewState {
  if (args.hasRows) return 'ready'
  if (args.loading) return 'loading'
  if (args.error) return 'error'
  if (args.data) return 'empty'
  return 'loading'
}
