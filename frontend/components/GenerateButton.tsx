'use client'

import { useState } from 'react'
import { Download, FileText, CheckCircle } from 'lucide-react'
import { generatePDF, getDownloadUrl, type GeneratePDFResponse, type MetricsResponse, type PeriodsResponse } from '@/lib/api'

interface GenerateButtonProps {
  baseWeek: string
  periods: PeriodsResponse
  metrics: MetricsResponse
  isGenerating: boolean
  onGeneratingChange: (generating: boolean) => void
}

export default function GenerateButton({ 
  baseWeek, 
  periods, 
  metrics, 
  isGenerating, 
  onGeneratingChange 
}: GenerateButtonProps) {
  const [generatedFile, setGeneratedFile] = useState<GeneratePDFResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleGenerate = async () => {
    onGeneratingChange(true)
    setError(null)
    setGeneratedFile(null)
    
    try {
      const periodsList = ['actual', 'last_week', 'last_year', 'year_2023']
      const result = await generatePDF(baseWeek, periodsList)
      setGeneratedFile(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate PDF')
    } finally {
      onGeneratingChange(false)
    }
  }

  const handleDownload = () => {
    if (generatedFile) {
      const downloadUrl = getDownloadUrl(generatedFile.file_path.split('/').pop() || '')
      window.open(downloadUrl, '_blank')
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-medium text-gray-900">Generate PDF Report</h3>
          <p className="text-sm text-gray-600 mt-1">
            Create a professional PDF with the metrics table
          </p>
        </div>
        
        <button
          onClick={handleGenerate}
          disabled={isGenerating}
          className={`
            inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white
            ${isGenerating 
              ? 'bg-gray-400 cursor-not-allowed' 
              : 'bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500'
            }
          `}
        >
          {isGenerating ? (
            <>
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
              Generating...
            </>
          ) : (
            <>
              <FileText className="h-4 w-4 mr-2" />
              Generate PDF
            </>
          )}
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-md p-4">
          <div className="text-red-800 text-sm">{error}</div>
          <button 
            onClick={handleGenerate}
            disabled={isGenerating}
            className="mt-2 text-sm text-red-600 hover:text-red-800 underline"
          >
            Try again
          </button>
        </div>
      )}

      {generatedFile && (
        <div className="bg-green-50 border border-green-200 rounded-md p-4">
          <div className="flex items-center">
            <CheckCircle className="h-5 w-5 text-green-600 mr-2" />
            <div className="flex-1">
              <div className="text-green-800 text-sm font-medium">
                PDF generated successfully!
              </div>
              <div className="text-green-700 text-xs mt-1">
                File: {generatedFile.file_path.split('/').pop()}
              </div>
            </div>
            <button
              onClick={handleDownload}
              className="inline-flex items-center px-3 py-1 border border-green-300 text-sm font-medium rounded text-green-700 bg-white hover:bg-green-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500"
            >
              <Download className="h-4 w-4 mr-1" />
              Download
            </button>
          </div>
        </div>
      )}

      {/* Generation details */}
      <div className="bg-gray-50 rounded-lg p-4">
        <h4 className="text-sm font-medium text-gray-900 mb-2">Generation Details</h4>
        <div className="grid grid-cols-2 gap-4 text-sm text-gray-600">
          <div>
            <span className="font-medium">Base Week:</span> {baseWeek}
          </div>
          <div>
            <span className="font-medium">Periods:</span> {Object.keys(periods.date_ranges).length}
          </div>
          <div>
            <span className="font-medium">Metrics:</span> 13 KPIs
          </div>
          <div>
            <span className="font-medium">Format:</span> A4 Landscape
          </div>
        </div>
      </div>
    </div>
  )
}
