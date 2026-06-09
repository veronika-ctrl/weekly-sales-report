'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import BatchFileUpload from '@/components/BatchFileUpload'
import FileMetadata from '@/components/FileMetadata'
import PeriodSelector from '@/components/PeriodSelector'
import { Separator } from '@/components/ui/separator'
import { useDataCache } from '@/contexts/DataCacheContext'
import { useChartSettings } from '@/contexts/ChartSettingsContext'
import { RefreshCw, CheckCircle2, XCircle, Trash2 } from 'lucide-react'
import {
  hasBackend,
  getApiBaseUrl,
  getDiscountsHistoryInfo,
  resetDiscountsHistory,
  type DiscountsHistoryInfo,
} from '@/lib/api'
const METADATA_CACHE_EXPIRY = 10 * 60 * 1000 // 10 minutes
const DIMENSIONS_CACHE_EXPIRY = 10 * 60 * 1000 // 10 minutes

export default function Settings() {
  const { refreshData, loading, loadingProgress, baseWeek, setBaseWeek } = useDataCache()
  const { animationsEnabled, setAnimationsEnabled } = useChartSettings()
  const [selectedWeek, setSelectedWeek] = useState(baseWeek)
  const [periods, setPeriods] = useState<any>(null)
  const [metadata, setMetadata] = useState<any>(null)
  const [dimensions, setDimensions] = useState<any>(null)
  const [loadingDimensions, setLoadingDimensions] = useState(false)
  const [metadataLoading, setMetadataLoading] = useState(true)
  const metadataTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const [supabaseVerifyLoading, setSupabaseVerifyLoading] = useState(false)
  const [supabaseVerifyResult, setSupabaseVerifyResult] = useState<any>(null) // Track if PDF has been downloaded to prevent duplicate downloads
  const [weeksWithData, setWeeksWithData] = useState<Set<string> | null>(null)
  const [discountsHistory, setDiscountsHistory] = useState<DiscountsHistoryInfo | null>(null)
  const [discountsHistoryLoading, setDiscountsHistoryLoading] = useState(false)
  const [resettingDiscounts, setResettingDiscounts] = useState(false)
  const supabaseDisabled = process.env.NEXT_PUBLIC_DISABLE_SUPABASE === 'true'

  useEffect(() => {
    import('@/lib/supabase-queries')
      .then((m) => m.getWeeksWithDataFromSupabase())
      .then((weeks) => setWeeksWithData(new Set(weeks)))
  }, [])

  // Sync selectedWeek with baseWeek from context
  useEffect(() => {
    setSelectedWeek(baseWeek)
  }, [baseWeek])

  const loadMetadata = useCallback(async (clearCache = false) => {
    setMetadataLoading(true)
    if (!selectedWeek) {
      setMetadata(null)
      setMetadataLoading(false)
      return
    }
    if (!hasBackend) {
      setMetadata({ error: 'Backend not configured. File status is only available when NEXT_PUBLIC_API_URL is set (e.g. running locally).' })
      setMetadataLoading(false)
      return
    }
    const cacheKey = `file_metadata_${selectedWeek}`
    
    if (clearCache) {
      localStorage.removeItem(cacheKey)
    } else {
      const cached = localStorage.getItem(cacheKey)
      if (cached) {
        try {
          const parsed = JSON.parse(cached)
          const cacheAge = Date.now() - parsed.timestamp
          if (cacheAge < METADATA_CACHE_EXPIRY) {
            setMetadata(parsed.data)
            setMetadataLoading(false)
            return
          }
        } catch (err) {
          console.warn('Failed to load cached metadata:', err)
        }
      }
    }
    
    let timeoutId: NodeJS.Timeout | null = null
    try {
      const controller = new AbortController()
      timeoutId = setTimeout(() => controller.abort(), 10000) // 10 second timeout
      const response = await fetch(`${getApiBaseUrl()}/api/file-metadata?week=${selectedWeek}`, {
        signal: controller.signal
      })
      
      if (timeoutId) clearTimeout(timeoutId)
      
      if (!response.ok) {
        throw new Error(`Failed to fetch metadata: ${response.statusText}`)
      }
      
      const data = await response.json()
      
      if (data && typeof data === 'object') {
        setMetadata(data)
        localStorage.setItem(cacheKey, JSON.stringify({
          data,
          timestamp: Date.now()
        }))
      } else {
        console.error('Invalid metadata response:', data)
        setMetadata({})
      }
    } catch (error: any) {
      if (timeoutId) clearTimeout(timeoutId)
      
      // Handle different types of errors
      const errorName = error?.name || ''
      const errorMessage = error?.message || String(error) || 'Unknown error'
      
      if (errorName === 'AbortError' || errorName === 'TimeoutError') {
        setMetadata({
          error: `Request timed out after 10s while contacting ${getApiBaseUrl()}. If the API is still starting, click Retry. Otherwise start it from the project root: venv/bin/python -m uvicorn weekly_report.api.routes:app --reload --host 0.0.0.0 --port 8000`,
        })
        return
      } else if (
        errorName === 'TypeError' ||
        errorMessage.includes('Failed to fetch') ||
        errorMessage.includes('NetworkError') ||
        errorMessage.includes('Network request failed') ||
        errorMessage.includes('ERR_NAME_NOT_RESOLVED') ||
        errorMessage.includes('ERR_CONNECTION_REFUSED')
      ) {
        setMetadata({
          error: `Backend not reachable at ${getApiBaseUrl()}. Start the API from the project root: venv/bin/python -m uvicorn weekly_report.api.routes:app --reload --host 0.0.0.0 --port 8000. If the app still cannot connect, set NEXT_PUBLIC_API_URL in frontend/.env.local (e.g. http://127.0.0.1:8000) and restart npm run dev.`,
        })
      } else {
        console.error('Failed to load metadata:', error)
        setMetadata({ error: errorMessage || 'Failed to load metadata' })
      }
    } finally {
      setMetadataLoading(false)
    }
  }, [selectedWeek])

  const loadDimensions = useCallback(async (clearCache = false) => {
    setLoadingDimensions(true)
    if (!selectedWeek) {
      setDimensions(null)
      setLoadingDimensions(false)
      return
    }
    if (!hasBackend) {
      setDimensions({})
      setLoadingDimensions(false)
      return
    }
    const cacheKey = `file_dimensions_${selectedWeek}`
    
    if (clearCache) {
      localStorage.removeItem(cacheKey)
    } else {
      const cached = localStorage.getItem(cacheKey)
      if (cached) {
        try {
          const parsed = JSON.parse(cached)
          const cacheAge = Date.now() - parsed.timestamp
          if (cacheAge < DIMENSIONS_CACHE_EXPIRY) {
            setDimensions(parsed.data)
            setLoadingDimensions(false)
            return
          }
        } catch (err) {
          console.warn('Failed to load cached dimensions:', err)
        }
      }
    }
    
    try {
      const response = await fetch(`${getApiBaseUrl()}/api/file-dimensions?week=${selectedWeek}`)
      if (!response.ok) {
        console.warn(`Failed to fetch dimensions: ${response.statusText}`)
        setDimensions({})
        return
      }
      const data = await response.json()
      setDimensions(data)
      localStorage.setItem(cacheKey, JSON.stringify({
        data,
        timestamp: Date.now()
      }))
    } catch (error) {
      console.warn('Failed to load dimensions:', error)
      setDimensions({})
    } finally {
      setLoadingDimensions(false)
    }
  }, [selectedWeek])

  const loadDiscountsHistory = useCallback(async () => {
    if (!selectedWeek || !hasBackend) {
      setDiscountsHistory(null)
      return
    }
    setDiscountsHistoryLoading(true)
    try {
      const info = await getDiscountsHistoryInfo(selectedWeek)
      setDiscountsHistory(info)
    } catch (err) {
      console.warn('Failed to load discounts history:', err)
      setDiscountsHistory(null)
    } finally {
      setDiscountsHistoryLoading(false)
    }
  }, [selectedWeek])

  useEffect(() => {
    loadDiscountsHistory()
  }, [loadDiscountsHistory])

  // Load metadata on mount and when week changes
  useEffect(() => {
    // Clear any pending timeout
    if (metadataTimeoutRef.current) {
      clearTimeout(metadataTimeoutRef.current)
    }
    
    // Load metadata when week changes (debounced)
    metadataTimeoutRef.current = setTimeout(() => {
      loadMetadata(false)
    }, 300)
    
    return () => {
      if (metadataTimeoutRef.current) {
        clearTimeout(metadataTimeoutRef.current)
      }
    }
  }, [selectedWeek, loadMetadata])

  const fileTypes = [
    { type: 'qlik', label: 'Qlik Sales Data', formats: '.xlsx,.csv' },
    { type: 'dema_spend', label: 'DEMA Marketing Spend', formats: '.csv' },
    { type: 'dema_gm2', label: 'DEMA GM2 Data', formats: '.csv' },
    { type: 'shopify', label: 'Shopify Sessions Data', formats: '.csv' },
    {
      type: 'discounts',
      label: 'Shopify order lines (full price / sale)',
      formats: '.csv',
    },
    { type: 'budget', label: 'Budget Data', formats: '.csv' },
  ]

  return (
    <div className="space-y-8">
      <Card>
        <CardHeader>
          <CardTitle>Data File Management</CardTitle>
          <CardDescription>
            Upload weekly data files and view their status
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Chart Settings */}
          <div>
            <h3 className="text-sm font-medium mb-3">Chart Settings</h3>
            <div className="flex items-center justify-between py-2">
              <div className="flex-1">
                <div className="text-sm font-medium">Enable Chart Animations</div>
                <p className="text-xs text-gray-500 mt-1">
                  Chart animations are automatically disabled during PDF generation
                </p>
              </div>
              <Switch
                checked={animationsEnabled}
                onCheckedChange={setAnimationsEnabled}
              />
            </div>
          </div>

          <Separator />

          <div>
            <div className="flex items-center gap-3 mb-3">
              <h3 className="text-sm font-medium">Select Week</h3>
              {selectedWeek && weeksWithData != null && (
                <span
                  className={`text-xs font-medium px-2 py-0.5 rounded ${
                    weeksWithData.has(selectedWeek)
                      ? 'bg-green-100 text-green-800'
                      : 'bg-amber-100 text-amber-800'
                  }`}
                  title={weeksWithData.has(selectedWeek) ? 'Data loaded for this week' : 'No data uploaded for this week yet'}
                >
                  {weeksWithData.has(selectedWeek) ? 'Has data' : 'No data'}
                </span>
              )}
            </div>
            <PeriodSelector
              selectedWeek={selectedWeek || ''}
              onWeekChange={(week) => {
                setSelectedWeek(week || '')
                setBaseWeek(week || '')
              }}
              onPeriodsChange={(p) => setPeriods(p as any)}
              weeksWithData={weeksWithData}
            />
          </div>

          <Separator />

          <div>
            <h3 className="text-sm font-medium mb-3">Supabase connection (backend)</h3>
            {supabaseDisabled ? (
              <p className="text-xs text-gray-500">
                Supabase är avstängt via <code>NEXT_PUBLIC_DISABLE_SUPABASE</code>. Ingen verifiering behövs.
              </p>
            ) : (
              <>
                <p className="text-xs text-gray-500 mb-2">
                  Verifierar att backend ser .env och kan ansluta till Supabase. Inga gissningar – varje steg visas exakt.
                </p>
                <Button
                  onClick={async () => {
                    setSupabaseVerifyLoading(true)
                    setSupabaseVerifyResult(null)
                    try {
                      const { verifySupabase } = await import('@/lib/api')
                      const r = await verifySupabase()
                      setSupabaseVerifyResult(r)
                    } catch (e: any) {
                      setSupabaseVerifyResult({
                        error: e?.message || String(e),
                        env_file_loaded: false,
                        SUPABASE_URL: 'not_set',
                        SUPABASE_SERVICE_ROLE_KEY: 'not_set',
                        key_length: 0,
                        client_created: false,
                        client_error: null,
                        query_ok: false,
                        query_error: null,
                        table_row_count: null
                      })
                    } finally {
                      setSupabaseVerifyLoading(false)
                    }
                  }}
                  variant="outline"
                  size="sm"
                  disabled={supabaseVerifyLoading}
                >
                  {supabaseVerifyLoading ? 'Verifierar...' : 'Verifiera Supabase (backend)'}
                </Button>
                {supabaseVerifyResult && (
                  <div className="mt-3 p-3 rounded border bg-gray-50 text-xs font-mono space-y-1">
                    {'error' in supabaseVerifyResult ? (
                      <div className="text-red-600">{supabaseVerifyResult.error}</div>
                    ) : (
                      <>
                        <div>env_file_loaded: {String(supabaseVerifyResult.env_file_loaded)}</div>
                        <div>SUPABASE_URL: {supabaseVerifyResult.SUPABASE_URL}</div>
                        <div>
                          SUPABASE_SERVICE_ROLE_KEY: {supabaseVerifyResult.SUPABASE_SERVICE_ROLE_KEY} (length:{' '}
                          {supabaseVerifyResult.key_length})
                        </div>
                        <div>client_created: {String(supabaseVerifyResult.client_created)}</div>
                        {supabaseVerifyResult.client_error && (
                          <div className="text-amber-700">client_error: {supabaseVerifyResult.client_error}</div>
                        )}
                        <div>query_ok: {String(supabaseVerifyResult.query_ok)}</div>
                        {supabaseVerifyResult.query_error && (
                          <div className="text-amber-700">query_error: {supabaseVerifyResult.query_error}</div>
                        )}
                        {supabaseVerifyResult.table_row_count != null && (
                          <div>table_row_count: {supabaseVerifyResult.table_row_count}</div>
                        )}
                      </>
                    )}
                  </div>
                )}
              </>
            )}
          </div>

          <Separator />

          <div>
            <h3 className="text-sm font-medium mb-3">Data Management</h3>
            <div className="flex items-center gap-4">
              <Button
                onClick={async () => {
                  await loadMetadata(true)
                }}
                variant="ghost"
                className="flex items-center gap-2"
              >
                <RefreshCw className="h-4 w-4" />
                Reload Metadata
              </Button>
              <Button
                onClick={async () => {
                  await loadDimensions(true)
                }}
                variant="ghost"
                className="flex items-center gap-2"
                disabled={loadingDimensions}
              >
                <RefreshCw className={`h-4 w-4 ${loadingDimensions ? 'animate-spin' : ''}`} />
                {loadingDimensions ? 'Loading Dimensions...' : 'Check Dimensions'}
              </Button>
            </div>
            <p className="text-xs text-gray-500 mt-2">
              Reload file metadata to check current file status. Use "Check Dimensions" to validate file structure. After uploading files, click <strong>Refresh All Data</strong> when all files for the week are ready (one file at a time is fine).
            </p>
          </div>

          <Separator />

          <div className="space-y-6">
            <h3 className="text-sm font-medium">
              {selectedWeek ? `Upload Files for Week ${selectedWeek}` : 'Välj en vecka ovan för att ladda upp filer'}
            </h3>
            
            {selectedWeek && (
            <BatchFileUpload
              fileTypes={fileTypes}
              currentWeek={selectedWeek}
              onUploadComplete={async () => {
                await loadMetadata(true)
                await loadDiscountsHistory()
                // Don't auto-load dimensions - user can click button if needed
              }}
              refreshData={async () => {
                await refreshData()
                // Don't auto-load dimensions - user can click button if needed
              }}
              loading={loading}
              loadingProgress={loadingProgress}
            />
            )}

            {/* File Metadata Display */}
            <div className="space-y-4 mt-6">
              <h4 className="text-sm font-medium">Current Files</h4>
              {!selectedWeek ? (
                <p className="text-sm text-muted-foreground">Välj en vecka för att se filstatus.</p>
              ) : metadataLoading && metadata === null ? (
                <div className="text-sm text-gray-500 italic flex items-center gap-2">
                  <RefreshCw className="h-4 w-4 animate-spin" />
                  Loading file status...
                </div>
              ) : metadata?.error ? (
                <div className="text-sm text-red-600 bg-red-50 p-3 rounded border border-red-200">
                  <div className="font-medium mb-1">Error loading file metadata</div>
                  <div>{metadata.error}</div>
                  <Button
                    onClick={() => loadMetadata(true)}
                    variant="outline"
                    size="sm"
                    className="mt-2"
                  >
                    Retry
                  </Button>
                </div>
              ) : (
                <div className="space-y-3">
                  {fileTypes.map((ft) => (
                    <div key={ft.type} className="space-y-2">
                      <div className="text-sm font-medium text-gray-700">{ft.label}</div>
                      {metadata && metadata[ft.type] ? (
                        <>
                          <FileMetadata
                            filename={metadata[ft.type].filename}
                            firstDate={metadata[ft.type].first_date}
                            lastDate={metadata[ft.type].last_date}
                            uploadedAt={metadata[ft.type].uploaded_at}
                            rowCount={metadata[ft.type].row_count}
                          />
                          {/* Dimension validation status */}
                          {dimensions && dimensions[ft.type] && (
                            <div className="flex items-center gap-2 text-sm">
                              {dimensions[ft.type].has_country === true ? (
                                <div className="flex items-center gap-1 text-green-600">
                                  <CheckCircle2 className="h-4 w-4" />
                                  <span>Country dimension detected</span>
                                </div>
                              ) : dimensions[ft.type].has_country === false ? (
                                <div className="flex items-center gap-1 text-red-600">
                                  <XCircle className="h-4 w-4" />
                                  <span>Country dimension missing</span>
                                </div>
                              ) : null}
                            </div>
                          )}
                        </>
                      ) : (
                        <div className="text-sm text-gray-500 italic">
                          No file uploaded yet
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Full price vs Sale — accumulated history (spans all weeks) */}
            {selectedWeek && hasBackend && (
              <div className="mt-8 rounded-md border bg-muted/30 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h4 className="text-sm font-medium">Full price vs Sale — accumulated history</h4>
                    <p className="text-xs text-muted-foreground mt-1 max-w-xl">
                      These uploads merge by date across all weeks (newest wins), so one big export or several
                      small ones build the same history. This is separate from the per-week file list above.
                    </p>
                  </div>
                  <Button
                    onClick={loadDiscountsHistory}
                    variant="ghost"
                    size="sm"
                    className="flex items-center gap-2 shrink-0"
                    disabled={discountsHistoryLoading}
                  >
                    <RefreshCw className={`h-4 w-4 ${discountsHistoryLoading ? 'animate-spin' : ''}`} />
                    Refresh
                  </Button>
                </div>

                <div className="mt-3 text-sm">
                  {discountsHistoryLoading && !discountsHistory ? (
                    <span className="text-gray-500 italic">Loading history…</span>
                  ) : discountsHistory && discountsHistory.count > 0 ? (
                    <div className="space-y-2">
                      <div className="flex flex-wrap gap-x-6 gap-y-1 text-gray-700">
                        <span>
                          <strong>{discountsHistory.count}</strong> file(s) accumulated
                        </span>
                        {discountsHistory.range && (
                          <span>
                            Covers <strong>{discountsHistory.range.start}</strong> →{' '}
                            <strong>{discountsHistory.range.end}</strong>
                          </span>
                        )}
                        <span className="flex items-center gap-1">
                          {discountsHistory.has_discount ? (
                            <>
                              <CheckCircle2 className="h-4 w-4 text-green-600" />
                              Discount depth column detected
                              {discountsHistory.latest_file_inspection?.discount_column
                                ? ` (${discountsHistory.latest_file_inspection.discount_column})`
                                : ''}
                            </>
                          ) : (
                            <>
                              <XCircle className="h-4 w-4 text-amber-600" />
                              Missing &quot;Discount Amount&quot; column — weighted disc % stays blank
                            </>
                          )}
                        </span>
                      </div>
                      {discountsHistory.latest_file_inspection?.columns && (
                        <p className="text-xs text-gray-500">
                          Latest export columns ({discountsHistory.latest_file_inspection.file}):{' '}
                          {discountsHistory.latest_file_inspection.columns.join(', ')}
                          {!discountsHistory.has_discount && (
                            <>
                              {' '}
                              — expected an 8th column{' '}
                              <strong>Discount Amount</strong> (or Weighted disc % / Revenue excl. Discount).
                            </>
                          )}
                        </p>
                      )}
                      <ul className="text-xs text-gray-500 list-disc pl-5 max-h-32 overflow-auto">
                        {discountsHistory.files.map((f, i) => (
                          <li key={`${f.week}-${f.name}-${i}`}>
                            {f.name} <span className="text-gray-400">({f.week})</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : (
                    <span className="text-gray-500 italic">
                      No Full price vs Sale files uploaded yet. Upload the Shopify revenue-over-time export above.
                    </span>
                  )}
                </div>

                {discountsHistory && discountsHistory.count > 0 && (
                  <div className="mt-4">
                    <Button
                      onClick={async () => {
                        if (
                          !window.confirm(
                            `Delete all ${discountsHistory.count} accumulated Full price vs Sale file(s)? ` +
                              'This clears the entire history and cannot be undone.'
                          )
                        ) {
                          return
                        }
                        setResettingDiscounts(true)
                        try {
                          await resetDiscountsHistory(selectedWeek)
                          await loadDiscountsHistory()
                          await loadMetadata(true)
                        } catch (err) {
                          console.error('Failed to reset discounts history:', err)
                          window.alert('Failed to reset history. Check that the backend is running.')
                        } finally {
                          setResettingDiscounts(false)
                        }
                      }}
                      variant="outline"
                      size="sm"
                      className="flex items-center gap-2 text-red-600 border-red-200 hover:bg-red-50"
                      disabled={resettingDiscounts}
                    >
                      <Trash2 className="h-4 w-4" />
                      {resettingDiscounts ? 'Resetting…' : 'Reset history'}
                    </Button>
                  </div>
                )}
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

