'use client'

import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Progress } from '@/components/ui/progress'
import { CheckCircle, XCircle, Loader2, Upload, RefreshCw } from 'lucide-react'
import { getApiBaseUrl } from '@/lib/api'

function clampPct(n: number): number {
  if (!Number.isFinite(n)) return 0
  return Math.min(100, Math.max(0, n))
}

interface FileType {
  type: string
  label: string
  formats: string
  /** Week + month (or history) files stay in the same slot; input allows multi-select. */
  accumulate?: boolean
  hint?: string
}

interface UploadStatus {
  status: 'idle' | 'uploading' | 'success' | 'error'
  errorMessage?: string
}

interface BatchFileUploadProps {
  fileTypes: FileType[]
  currentWeek: string
  onUploadComplete: () => Promise<void>
  refreshData: () => Promise<void>
  loading: boolean
  loadingProgress?: { message: string; percentage: number } | null
  /** When set, a picked file whose name matches another slot in this group is moved there. */
  inferFileType?: (filename: string) => string | null
}

/** Base 5 min covers slow hosts (e.g. Render free cold start); +1 min per MB over 10 MB; max 15 min. */
function computeUploadTimeoutMs(fileSizeMB: number): number {
  const baseMs = 5 * 60 * 1000
  const extraOver10Mb = Math.max(0, fileSizeMB - 10) * 60 * 1000
  return Math.min(15 * 60 * 1000, baseMs + extraOver10Mb)
}

export default function BatchFileUpload({
  fileTypes,
  currentWeek,
  onUploadComplete,
  refreshData,
  loading,
  loadingProgress,
  inferFileType
}: BatchFileUploadProps) {
  const [selectedFiles, setSelectedFiles] = useState<Record<string, File[]>>({})
  const [uploadStatuses, setUploadStatuses] = useState<Record<string, UploadStatus>>({})
  const [isUploading, setIsUploading] = useState(false)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [uploadProgress, setUploadProgress] = useState({ current: 0, total: 0 })
  const [refreshProgress, setRefreshProgress] = useState<string>('')
  const [overallStatus, setOverallStatus] = useState<'idle' | 'uploading' | 'refreshing' | 'complete'>('idle')
  const [uploadResults, setUploadResults] = useState<{ success: string[], failed: Array<{ type: string, error: string }> }>({ success: [], failed: [] })
  const [currentUploadingFile, setCurrentUploadingFile] = useState<{
    type: string
    label: string
    fileName: string
    progress: number
    phase?: 'uploading' | 'processing'
  } | null>(null)

  // Initialize upload statuses function
  const initializeStatuses = () => {
    const statuses: Record<string, UploadStatus> = {}
    fileTypes.forEach(ft => {
      statuses[ft.type] = { status: 'idle' }
    })
    setUploadStatuses(statuses)
  }

  // Initialize on mount and when fileTypes change
  useEffect(() => {
    initializeStatuses()
  }, [fileTypes])

  const handleFileChange = (fileType: string, e: React.ChangeEvent<HTMLInputElement>) => {
    const picked = e.target.files ? Array.from(e.target.files) : []
    if (picked.length === 0) return
    const knownTypes = new Set(fileTypes.map((ft) => ft.type))
    const routed: Record<string, File[]> = {}
    for (const file of picked) {
      const inferred = inferFileType?.(file.name)
      const dest = inferred && knownTypes.has(inferred) ? inferred : fileType
      routed[dest] = [...(routed[dest] || []), file]
    }
    setSelectedFiles((prev) => {
      const next = { ...prev, ...routed }
      if (!routed[fileType]) {
        next[fileType] = []
      }
      return next
    })
    setUploadStatuses((prev) => {
      const next = { ...prev }
      for (const t of new Set([...Object.keys(routed), fileType])) {
        next[t] = { status: 'idle' }
      }
      return next
    })
    setUploadResults({ success: [], failed: [] })
  }

  const uploadSingleFile = async (
    fileType: string, 
    file: File,
    onProgress?: (progress: number, phase?: 'uploading' | 'processing') => void
  ): Promise<{ success: boolean, error?: string }> => {
    setUploadStatuses(prev => ({ ...prev, [fileType]: { status: 'uploading' } }))
    
    // Simulera progress eftersom fetch inte har inbyggd progress support
    // Vi uppdaterar status baserat på tiden för att ge användaren feedback
    const startTime = Date.now()
    const fileSize = file.size
    let progressInterval: NodeJS.Timeout | null = null
    let timeoutId: NodeJS.Timeout | null = null
    
    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('week', currentWeek)
      formData.append('file_type', fileType)

      // Använd fetch med timeout - längre timeout för större filer (QLIK kan vara stora)
      const controller = new AbortController()
      const fileSizeMB = file.size / (1024 * 1024)
      const timeoutMs = computeUploadTimeoutMs(fileSizeMB)
      timeoutId = setTimeout(() => controller.abort(), timeoutMs)

      // Start progress simulation - uppdatera progress under uppladdning och processing
      if (onProgress) {
        let uploadPhase = true // true = uploading, false = processing
        const uploadStartTime = Date.now()
        
        progressInterval = setInterval(() => {
          const elapsed = Date.now() - uploadStartTime
          
          if (uploadPhase) {
            // Upload phase: 0-80% baserat på uppskattad uppladdningstid
            // Större filer tar längre tid att ladda upp
            const estimatedUploadTime = Math.max(3000, fileSize / 5000) // Minst 3 sekunder
            const uploadProgress = Math.min(80, (elapsed / estimatedUploadTime) * 100)
            onProgress(uploadProgress, 'uploading')
            
            // Efter 80% eller 5 sekunder, gå över till processing phase
            if (uploadProgress >= 80 || elapsed > 5000) {
              uploadPhase = false
            }
          } else {
            // Processing phase: 80-99% - servern processar filen
            // Öka långsamt från 80% till 99% medan vi väntar på svar
            const processingElapsed = elapsed - 5000 // Tid sedan processing började
            const processingProgress = Math.min(99, 80 + (processingElapsed / 30000) * 19) // 19% över 30 sekunder
            onProgress(processingProgress, 'processing')
          }
        }, 200) // Uppdatera var 200ms
      }

      const response = await fetch(`${getApiBaseUrl()}/api/upload-file`, {
        method: 'POST',
        body: formData,
        credentials: 'include',
        signal: controller.signal
      })

      if (timeoutId) clearTimeout(timeoutId)
      if (progressInterval) clearInterval(progressInterval)
      if (onProgress) onProgress(100)

      if (!response.ok) {
        const raw = await response.text()
        let detail = raw.slice(0, 300)
        try {
          const parsed = JSON.parse(raw)
          const d = parsed.detail ?? parsed.message ?? parsed.error
          detail = typeof d === 'string' ? d : raw.slice(0, 300)
        } catch {
          if (/internal server error/i.test(raw) || response.status >= 500) {
            detail =
              `Upload failed (${response.status}). Large CSVs can hit the preview proxy size limit — retry; if it fails again the file may still be too large.`
          }
        }
        throw new Error(detail || 'Upload failed')
      }

      setUploadStatuses(prev => ({ ...prev, [fileType]: { status: 'success' } }))
      return { success: true }
    } catch (error: any) {
      // Cleanup on error
      if (timeoutId) clearTimeout(timeoutId)
      if (progressInterval) clearInterval(progressInterval)
      
      let errorMessage = error.message || 'Upload failed'
      const fileSizeMB = file.size / (1024 * 1024)
      
      // Handle specific error types
      if (error.name === 'AbortError' || error.name === 'TimeoutError') {
        const timeoutMs = computeUploadTimeoutMs(fileSizeMB)
        const timeoutMinutes = Math.round(timeoutMs / 60000)
        errorMessage = `Upload timeout: The file "${file.name}" (${fileSizeMB.toFixed(1)} MB) took too long to upload (over ${timeoutMinutes} minute${timeoutMinutes > 1 ? 's' : ''}). The file may be too large or the server may be slow. Please try again.`
      } else if (error.message?.includes('Failed to fetch') || error.message?.includes('NetworkError')) {
        errorMessage =
          'Network error: API unreachable. Free hosts often sleep—wait ~1 min and retry, or open https://…/docs once to wake the server. ' +
          'Verify NEXT_PUBLIC_API_URL and FRONTEND_URL on Render.'
      } else if (error.message?.includes('signal is aborted') || error.message?.includes('aborted without reason')) {
        errorMessage = `Upload was cancelled or timed out. Please try again.`
      }
      
      setUploadStatuses(prev => ({ ...prev, [fileType]: { status: 'error', errorMessage } }))
      return { success: false, error: errorMessage }
    }
  }

  const handleUploadAll = async () => {
    // Get all file types that have selected files
    const filesToUpload = Object.entries(selectedFiles).flatMap(([type, files]) =>
      (files || []).map((file) => ({ type, file }))
    )

    // If no new files selected, still allow a full refresh so users don't need to re-upload
    if (filesToUpload.length === 0) {
      setOverallStatus('refreshing')
      setIsRefreshing(true)
      
      try {
        // First call onUploadComplete to update metadata
        await onUploadComplete()
        
        // Then trigger refreshData (this includes Supabase sync via DataCacheContext)
        await refreshData()
      } catch (e) {
        console.error('Error during refresh without uploads:', e)
      } finally {
        setIsRefreshing(false)
        setOverallStatus('complete')
        // Reset after a delay
        setTimeout(() => {
          setOverallStatus('idle')
          setRefreshProgress('')
        }, 2000)
      }
      return
    }

    setIsUploading(true)
    setOverallStatus('uploading')
    setUploadResults({ success: [], failed: [] })
    setCurrentUploadingFile(null)
    initializeStatuses()
    // Avoid first paint with total=0 (React batches updates → "1 of 0", NaN% before loop runs).
    setUploadProgress({ current: 0, total: filesToUpload.length })

    // Wake cold hosts (e.g. Render free) before uploads so the first file is less likely to fail.
    const apiBase = getApiBaseUrl()
    if (String(process.env.NEXT_PUBLIC_API_URL || '').trim()) {
      const warm = new AbortController()
      const warmT = setTimeout(() => warm.abort(), 120000)
      try {
        await fetch(`${apiBase.replace(/\/$/, '')}/api/health`, {
          method: 'GET',
          cache: 'no-store',
          credentials: 'include',
          signal: warm.signal,
        })
      } catch {
        // Continue; upload may still succeed once the service is up.
      } finally {
        clearTimeout(warmT)
      }
    }

    const results: { success: string[], failed: Array<{ type: string, error: string }> } = { 
      success: [], 
      failed: [] 
    }

    // Upload files sequentially with detailed progress
    for (let i = 0; i < filesToUpload.length; i++) {
      const { type, file } = filesToUpload[i]
      const fileTypeInfo = fileTypes.find(ft => ft.type === type)
      
      // Set current file BEFORE starting upload
      setCurrentUploadingFile({
        type,
        label: fileTypeInfo?.label || type,
        fileName: file.name,
        progress: 0,
        phase: 'uploading'
      })
      
      // Update overall progress (which file we're on)
      setUploadProgress({ current: i, total: filesToUpload.length })

      // Upload with progress callback
      const result = await uploadSingleFile(type, file, (progress, phase) => {
        setCurrentUploadingFile(prev => prev ? { ...prev, progress, phase: phase || 'uploading' } : null)
      })
      
      if (result.success) {
        results.success.push(type)
      } else {
        results.failed.push({ type, error: result.error || 'Unknown error' })
      }

      // Clear current file
      setCurrentUploadingFile(null)

      // Small delay between uploads to avoid overwhelming the server
      if (i < filesToUpload.length - 1) {
        await new Promise(resolve => setTimeout(resolve, 300))
      }
    }

    setUploadProgress({ current: filesToUpload.length, total: filesToUpload.length })
    setUploadResults(results)
    setIsUploading(false)
    setCurrentUploadingFile(null)

    // Reload file metadata only — full dashboard refresh is slow (large Qlik export) and optional
    // until all files for the week are uploaded. User clicks "Refresh All Data" when ready.
    if (results.success.length > 0) {
      setOverallStatus('complete')
      try {
        await onUploadComplete()
      } catch (error) {
        console.error('Error updating metadata after upload:', error)
      }
      setTimeout(() => {
        setOverallStatus('idle')
      }, 3000)
    } else {
      setOverallStatus('idle')
    }
  }

  const hasSelectedFiles = Object.values(selectedFiles).some((files) => (files || []).length > 0)
  // Allow button to be enabled even if no files selected (for refresh-only mode)
  const canUpload = !isUploading && !isRefreshing && overallStatus !== 'refreshing' && !loading

  return (
    <div className="space-y-6">
      <div className="space-y-4">
        {fileTypes.map((ft) => {
          const files = selectedFiles[ft.type] || []
          const status = uploadStatuses[ft.type] || { status: 'idle' }
          const hasFile = files.length > 0

          return (
            <div key={ft.type} className="space-y-2">
              <Label htmlFor={`file-${ft.type}`} className="text-sm font-medium">
                {ft.label}
              </Label>
              {ft.hint && (
                <p className="text-xs text-muted-foreground">{ft.hint}</p>
              )}
              <div className="flex gap-2 items-center">
                <Input
                  id={`file-${ft.type}`}
                  type="file"
                  accept={ft.formats}
                  multiple={Boolean(ft.accumulate)}
                  onChange={(e) => handleFileChange(ft.type, e)}
                  disabled={isUploading || isRefreshing}
                  className="flex-1"
                />
                {status.status === 'idle' && hasFile && (
                  <div className="flex items-center gap-2 text-sm text-gray-600 min-w-[120px]">
                    <span>
                      {files.length === 1
                        ? files[0].name
                        : `${files.length} files selected`}
                    </span>
                  </div>
                )}
                {status.status === 'uploading' && (
                  <div className="flex items-center gap-2 text-sm text-blue-600 min-w-[120px]">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span>Uploading...</span>
                  </div>
                )}
                {status.status === 'success' && (
                  <div className="flex items-center gap-2 text-sm text-green-600 min-w-[120px]">
                    <CheckCircle className="h-4 w-4" />
                    <span>Uploaded</span>
                  </div>
                )}
                {status.status === 'error' && (
                  <div className="flex items-center gap-2 text-sm text-red-600 min-w-[120px]">
                    <XCircle className="h-4 w-4" />
                    <span>Failed</span>
                  </div>
                )}
              </div>
              {ft.accumulate && files.length > 1 && status.status === 'idle' && (
                <ul className="text-xs text-gray-600 list-disc pl-5">
                  {files.map((f) => (
                    <li key={f.name}>{f.name}</li>
                  ))}
                </ul>
              )}
              {status.status === 'error' && status.errorMessage && (
                <div className="text-xs text-red-600 ml-1">
                  {status.errorMessage}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Upload Progress */}
      {(isUploading || overallStatus === 'uploading') && (
        <div className="space-y-3 p-4 bg-blue-50 rounded-lg border border-blue-200">
          <div className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-2 flex-1">
              {currentUploadingFile ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-gray-900 truncate">
                      {currentUploadingFile.phase === 'processing' ? 'Processing' : 'Uploading'}: {currentUploadingFile.label}
                    </div>
                    <div className="text-xs text-gray-600 mt-0.5 truncate">
                      {currentUploadingFile.fileName} • File {uploadProgress.current + 1} of {uploadProgress.total}
                      {currentUploadingFile.phase === 'processing' && ' • Server is processing file...'}
                    </div>
                  </div>
                </>
              ) : (
                <span className="text-gray-700">
                  Preparing upload...
                  {uploadProgress.total > 0
                    ? ` (${uploadProgress.current + 1} of ${uploadProgress.total})`
                    : ''}
                </span>
              )}
            </div>
            <div className="text-right ml-4">
              <div className="text-sm font-medium text-gray-900">
                {currentUploadingFile
                  ? `${Math.round(clampPct(currentUploadingFile.progress))}%`
                  : `${Math.round(
                      clampPct(
                        ((uploadProgress.current + 1) / Math.max(uploadProgress.total, 1)) * 100
                      )
                    )}%`}
              </div>
              <div className="text-xs text-gray-500">
                Overall:{' '}
                {Math.round(
                  clampPct((uploadProgress.current / Math.max(uploadProgress.total, 1)) * 100)
                )}
                %
              </div>
            </div>
          </div>
          <Progress
            value={clampPct(
              currentUploadingFile && uploadProgress.total > 0
                ? (uploadProgress.current / uploadProgress.total) * 100 +
                    currentUploadingFile.progress / uploadProgress.total
                : uploadProgress.total > 0
                  ? ((uploadProgress.current + 1) / uploadProgress.total) * 100
                  : 0
            )}
          />
          {currentUploadingFile && (
            <div className="h-1 bg-gray-200 rounded-full overflow-hidden">
              <div 
                className="h-full bg-blue-500 transition-all duration-300"
                style={{ width: `${currentUploadingFile.progress}%` }}
              />
            </div>
          )}
        </div>
      )}

      {/* Refresh Progress */}
      {(isRefreshing || overallStatus === 'refreshing' || loading) && (
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-2 text-gray-700">
              <RefreshCw className="h-4 w-4 animate-spin" />
              <span>{loadingProgress?.message || 'Refreshing data...'}</span>
            </div>
            {loadingProgress && (
              <span className="text-gray-500">
                {loadingProgress.percentage}%
              </span>
            )}
          </div>
          {loadingProgress && (
            <Progress value={loadingProgress.percentage} />
          )}
        </div>
      )}

      {/* Upload Results Summary */}
      {uploadResults.success.length > 0 || uploadResults.failed.length > 0 ? (
        <div className="space-y-2 p-4 bg-gray-50 rounded-lg">
          <div className="text-sm font-medium text-gray-700">Upload Summary</div>
          {uploadResults.success.length > 0 && (
            <div className="flex items-center gap-2 text-sm text-green-600">
              <CheckCircle className="h-4 w-4" />
              <span>{uploadResults.success.length} file(s) uploaded successfully</span>
            </div>
          )}
          {uploadResults.failed.length > 0 && (
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-sm text-red-600">
                <XCircle className="h-4 w-4" />
                <span>{uploadResults.failed.length} file(s) failed</span>
              </div>
              <ul className="list-disc list-inside text-xs text-red-600 ml-6 space-y-1">
                {uploadResults.failed.map(({ type, error }, idx) => (
                  <li key={`${type}-${idx}`}>
                    {fileTypes.find(ft => ft.type === type)?.label || type}: {error}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      ) : null}

      {overallStatus === 'complete' && uploadResults.success.length > 0 && (
        <p className="text-sm text-green-700 bg-green-50 border border-green-200 rounded-md p-3">
          Upload complete. When all files for this week are uploaded, click{' '}
          <strong>Refresh All Data</strong> below to reload the dashboard (may take several minutes for large Qlik files).
        </p>
      )}

      {/* Upload All Button */}
      <div className="flex justify-end">
        <Button
          onClick={handleUploadAll}
          disabled={!canUpload}
          size="lg"
          className="min-w-[200px]"
        >
          {isUploading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Uploading...
            </>
          ) : isRefreshing || overallStatus === 'refreshing' ? (
            <>
              <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
              Refreshing...
            </>
          ) : overallStatus === 'complete' ? (
            <>
              <CheckCircle className="mr-2 h-4 w-4" />
              Complete!
            </>
          ) : hasSelectedFiles ? (
            <>
              <Upload className="mr-2 h-4 w-4" />
              Upload Selected Files
            </>
          ) : (
            <>
              <RefreshCw className="mr-2 h-4 w-4" />
              Refresh All Data
            </>
          )}
        </Button>
      </div>
    </div>
  )
}

