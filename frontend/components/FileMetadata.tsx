'use client'

import { Card, CardContent } from '@/components/ui/card'
import { Calendar, FileText } from 'lucide-react'

interface FileMetadataProps {
  filename: string
  firstDate: string
  lastDate: string
  uploadedAt: string
  rowCount?: number
}

export default function FileMetadata({ 
  filename, 
  firstDate, 
  lastDate, 
  uploadedAt,
  rowCount 
}: FileMetadataProps) {
  return (
    <Card className="bg-gray-50">
      <CardContent className="pt-4 pb-3 px-4 space-y-2">
        <div className="flex items-start gap-2 text-sm">
          <FileText className="h-4 w-4 text-gray-500 mt-0.5" />
          <div className="flex-1">
            <div className="font-medium text-gray-900">{filename}</div>
            <div className="text-xs text-gray-500 mt-1">
              Uploaded: {new Date(uploadedAt).toLocaleString('sv-SE')}
            </div>
          </div>
        </div>
        {firstDate && lastDate && (
          <div className="flex items-center gap-2 text-sm text-gray-700">
            <Calendar className="h-4 w-4 text-gray-500" />
            <span>
              Data: {firstDate} → {lastDate}
              {rowCount && <span className="text-gray-500 ml-2">({rowCount.toLocaleString()} rows)</span>}
            </span>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

