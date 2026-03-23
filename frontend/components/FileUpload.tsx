'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Upload, CheckCircle, XCircle, Loader2 } from 'lucide-react'

interface FileUploadProps {
  fileType: string
  fileTypeLabel: string
  acceptedFormats: string
  currentWeek: string
  onUploadSuccess: () => void
}

export default function FileUpload({ 
  fileType, 
  fileTypeLabel, 
  acceptedFormats, 
  currentWeek,
  onUploadSuccess 
}: FileUploadProps) {
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadStatus, setUploadStatus] = useState<'idle' | 'success' | 'error'>('idle')
  const [errorMessage, setErrorMessage] = useState('')

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0])
      setUploadStatus('idle')
    }
  }

  const handleUpload = async () => {
    if (!file) return

    setUploading(true)
    setUploadStatus('idle')

    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('week', currentWeek)
      formData.append('file_type', fileType)

      const response = await fetch('http://localhost:8000/api/upload-file', {
        method: 'POST',
        body: formData
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Upload failed')
      }

      setUploadStatus('success')
      onUploadSuccess()
    } catch (error: any) {
      setUploadStatus('error')
      setErrorMessage(error.message)
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="space-y-3">
      <Label htmlFor={`file-${fileType}`} className="text-sm font-medium">
        {fileTypeLabel}
      </Label>
      <div className="flex gap-2">
        <Input
          id={`file-${fileType}`}
          type="file"
          accept={acceptedFormats}
          onChange={handleFileChange}
          disabled={uploading}
          className="flex-1"
        />
        <Button
          onClick={handleUpload}
          disabled={!file || uploading}
          className="min-w-[100px]"
        >
          {uploading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Uploading
            </>
          ) : (
            <>
              <Upload className="mr-2 h-4 w-4" />
              Upload
            </>
          )}
        </Button>
      </div>
      {uploadStatus === 'success' && (
        <div className="flex items-center gap-2 text-sm text-green-600">
          <CheckCircle className="h-4 w-4" />
          File uploaded successfully
        </div>
      )}
      {uploadStatus === 'error' && (
        <div className="flex items-center gap-2 text-sm text-red-600">
          <XCircle className="h-4 w-4" />
          {errorMessage}
        </div>
      )}
    </div>
  )
}

