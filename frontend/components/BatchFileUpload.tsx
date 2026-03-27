'use client'

import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Progress } from '@/components/ui/progress'
import { CheckCircle, XCircle, Loader2, Upload, RefreshCw } from 'lucide-react'

interface FileType {
  type: string
  label: string
  formats: string
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
  loadingProgress
}: BatchFileUploadProps) {
  const [selectedFiles, setSelectedFiles] = useState<Record<string, File | null>>({})
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
    if (e.target.files && e.target.files[0]) {
      setSelectedFiles(prev => ({ ...prev, [fileType]: e.target.files![0] }))
      setUploadStatuses(prev => ({ ...prev, [fileType]: { status: 'idle' } }))
      setUploadResults({ success: [], failed: [] })
    }
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

      const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      const response = await fetch(`${API_BASE_URL}/api/upload-file`, {
        method: 'POST',
        body: formData,
        signal: controller.signal
      })

      if (timeoutId) clearTimeout(timeoutId)
      if (progressInterval) clearInterval(progressInterval)
      if (onProgress) onProgress(100)

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Upload failed')
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
    const filesToUpload = Object.entries(selectedFiles)
      .filter(([_, file]) => file !== null)
      .map(([type, file]) => ({ type, file: file! }))

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

    // Wake cold hosts (e.g. Render free) before uploads so the first file is less likely to fail.
    const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    if (process.env.NEXT_PUBLIC_API_URL) {
      const warm = new AbortController()
      const warmT = setTimeout(() => warm.abort(), 120000)
      try {
        await fetch(`${apiBase.replace(/\/$/, '')}/api/health`, {
          method: 'GET',
          cache: 'no-store',
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

    // If at least one file was uploaded successfully, trigger refresh
    if (results.success.length > 0) {
      setOverallStatus('refreshing')
      setIsRefreshing(true)
      
      try {
        // First call onUploadComplete to update metadata
        await onUploadComplete()
        
        // Then trigger refreshData (this includes Supabase sync via DataCacheContext)
        await refreshData()
      } catch (error) {
        console.error('Error during refresh:', error)
      } finally {
        setIsRefreshing(false)
        setOverallStatus('complete')
        // Reset after a delay
        setTimeout(() => {
          setOverallStatus('idle')
          setRefreshProgress('')
        }, 2000)
      }
    } else {
      setOverallStatus('idle')
    }
  }

  const hasSelectedFiles = Object.values(selectedFiles).some(file => file !== null)
  // Allow button to be enabled even if no files selected (for refresh-only mode)
  const canUpload = !isUploading && !isRefreshing && overallStatus !== 'refreshing' && !loading

  return (
    <div className="space-y-6">
      <div className="space-y-4">
        {fileTypes.map((ft) => {
          const file = selectedFiles[ft.type]
          const status = uploadStatuses[ft.type] || { status: 'idle' }
          const hasFile = file !== null

          return (
            <div key={ft.type} className="space-y-2">
              <Label htmlFor={`file-${ft.type}`} className="text-sm font-medium">
                {ft.label}
              </Label>
              <div className="flex gap-2 items-center">
                <Input
                  id={`file-${ft.type}`}
                  type="file"
                  accept={ft.formats}
                  onChange={(e) => handleFileChange(ft.type, e)}
                  disabled={isUploading || isRefreshing}
                  className="flex-1"
                />
                {status.status === 'idle' && hasFile && (
                  <div className="flex items-center gap-2 text-sm text-gray-600 min-w-[120px]">
                    <span>{file?.name}</span>
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
                  Preparing upload... ({uploadProgress.current + 1} of {uploadProgress.total})
                </span>
              )}
            </div>
            <div className="text-right ml-4">
              <div className="text-sm font-medium text-gray-900">
                {currentUploadingFile 
                  ? `${Math.round(currentUploadingFile.progress)}%` 
                  : `${Math.round(((uploadProgress.current + 1) / uploadProgress.total) * 100)}%`
                }
              </div>
              <div className="text-xs text-gray-500">
                Overall: {Math.round((uploadProgress.current / uploadProgress.total) * 100)}%
              </div>
            </div>
          </div>
          <Progress 
            value={
              currentUploadingFile 
                ? ((uploadProgress.current / uploadProgress.total) * 100) + 
                  (currentUploadingFile.progress / uploadProgress.total)
                : ((uploadProgress.current + 1) / uploadProgress.total) * 100
            } 
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
                {uploadResults.failed.map(({ type, error }) => (
                  <li key={type}>
                    {fileTypes.find(ft => ft.type === type)?.label || type}: {error}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      ) : null}

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
              Upload All & Refresh
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

