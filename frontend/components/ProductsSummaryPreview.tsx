'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { getDiscountsLtmMetrics, getDiscountsSummaryMetrics, type PeriodsResponse, type MetricsResponse } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Download } from 'lucide-react'

interface ProductsSummaryPreviewProps {
  periods: PeriodsResponse
  baseWeek: string
}

const METRICS: Array<{ label: string; key: string; indent?: boolean }> = [
  { label: 'Net Revenue Overall', key: 'net_revenue_overall' },
  { label: 'Net Revenue Full Price', key: 'net_revenue_full_price' },
  { label: 'Net Revenue Sale', key: 'net_revenue_sale' },
  ...[10, 20, 30, 40, 50, 60, 70].map((b) => ({ label: `${b}%`, key: `net_revenue_sale_${b}`, indent: true })),
]

export default function ProductsSummaryPreview({ periods, baseWeek }: ProductsSummaryPreviewProps) {
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null)
  const [ltmMetrics, setLtmMetrics] = useState<MetricsResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [exporting, setExporting] = useState<'png' | 'pdf' | null>(null)
  const exportRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setLoading(true)
      setError(null)
      try {
        const [weekRes, ltmRes] = await Promise.all([
          getDiscountsSummaryMetrics(baseWeek, true),
          getDiscountsLtmMetrics(baseWeek),
        ])
        if (!cancelled) {
          setMetrics(weekRes)
          setLtmMetrics(ltmRes)
        }
      } catch (e: any) {
        if (!cancelled) setError(e?.message || 'Failed to load products summary')
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [baseWeek])

  const metricsData = (metrics as any)?.periods || null
  const ltmData = (ltmMetrics as any)?.periods || null

  const latestWeekDisplay = useMemo(() => {
    return periods?.date_ranges?.actual?.display || baseWeek
  }, [periods, baseWeek])

  const weekEnd = useMemo(() => {
    const end = periods?.date_ranges?.actual?.end
    return end ? new Date(end) : null
  }, [periods])

  const ltmLabel = useMemo(() => {
    if (!weekEnd) return 'Last 12 months'
    const end = weekEnd
    const start = new Date(end)
    start.setMonth(start.getMonth() - 12)
    start.setDate(start.getDate() + 1)
    const fmt = (d: Date) => d.toISOString().slice(0, 10)
    return `Last 12 months (${fmt(start)} → ${fmt(end)})`
  }, [weekEnd])

  const formatSekThousands = (value: number) => {
    const v = Number.isFinite(value) ? value : 0
    if (v === 0) return '0'
    return Math.round(v / 1000).toLocaleString('sv-SE')
  }

  const growthPct = (current: number, previous: number): number | null => {
    if (!previous) return null
    return ((current - previous) / previous) * 100
  }

  const fmtPct = (value: number | null) => {
    if (value === null) return '—'
    const abs = Math.abs(value).toFixed(1)
    return value < 0 ? `(${abs}%)` : `${abs}%`
  }

  const exportTableToCanvas = async (): Promise<{ canvas: HTMLCanvasElement; width: number; height: number }> => {
    const node = exportRef.current
    if (!node) throw new Error('Nothing to export')

    const rect = node.getBoundingClientRect()
    const width = Math.max(1, Math.ceil(rect.width))
    const height = Math.max(1, Math.ceil(rect.height))

    // Clone node and inline computed styles so the SVG foreignObject renders correctly.
    const clone = node.cloneNode(true) as HTMLElement
    clone.style.background = 'white'

    const inline = (srcEl: Element, dstEl: HTMLElement) => {
      const cs = window.getComputedStyle(srcEl)
      let cssText = ''
      for (let i = 0; i < cs.length; i++) {
        const prop = cs[i]
        cssText += `${prop}:${cs.getPropertyValue(prop)};`
      }
      dstEl.style.cssText = cssText
    }

    inline(node, clone)
    const srcEls = Array.from(node.querySelectorAll('*'))
    const dstEls = Array.from(clone.querySelectorAll('*'))
    for (let i = 0; i < Math.min(srcEls.length, dstEls.length); i++) {
      const dst = dstEls[i] as HTMLElement
      if (!dst) continue
      inline(srcEls[i], dst)
    }

    const wrapper = document.createElement('div')
    wrapper.setAttribute('xmlns', 'http://www.w3.org/1999/xhtml')
    wrapper.style.background = 'white'
    wrapper.appendChild(clone)

    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}"><foreignObject x="0" y="0" width="100%" height="100%">${new XMLSerializer().serializeToString(
      wrapper
    )}</foreignObject></svg>`

    // Prefer data URL over blob URL; some browsers treat blob+foreignObject as tainted more often.
    const url = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`
    try {
      const img = new Image()
      // Hint for browsers that enforce CORS on rendered SVG resources.
      img.crossOrigin = 'anonymous'
      img.decoding = 'async'
      img.src = url
      await new Promise<void>((resolve, reject) => {
        img.onload = () => resolve()
        img.onerror = () => reject(new Error('Failed to render export image'))
      })

      const dpr = Math.min(2, window.devicePixelRatio || 1)
      const canvas = document.createElement('canvas')
      canvas.width = Math.round(width * dpr)
      canvas.height = Math.round(height * dpr)
      const ctx = canvas.getContext('2d')
      if (!ctx) throw new Error('Canvas not supported')
      ctx.scale(dpr, dpr)
      ctx.fillStyle = '#ffffff'
      ctx.fillRect(0, 0, width, height)
      ctx.drawImage(img, 0, 0, width, height)
      return { canvas, width, height }
    } finally {
      // no-op for data URLs
    }
  }

  const downloadBlob = (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  const handleDownloadPng = async () => {
    if (exporting) return
    setExporting('png')
    try {
      const { canvas } = await exportTableToCanvas()
      const blob: Blob | null = await new Promise((resolve) => canvas.toBlob(resolve, 'image/png'))
      if (!blob) throw new Error('Failed to export PNG')
      downloadBlob(blob, `products-summary-week-${baseWeek}.png`)
    } catch (e: any) {
      // Canvas export can be blocked by the browser (tainted canvas). Fallback to server-side export.
      const isTainted =
        typeof e?.name === 'string' && e.name === 'SecurityError' && String(e?.message || '').toLowerCase().includes('tainted')
      if (isTainted) {
        const res = await fetch(`/api/exports/products-summary?week=${encodeURIComponent(baseWeek)}&format=png`)
        if (!res.ok) throw new Error(`Failed to export PNG: ${res.statusText}`)
        const blob = await res.blob()
        downloadBlob(blob, `products-summary-week-${baseWeek}.png`)
      } else {
        throw e
      }
    } finally {
      setExporting(null)
    }
  }

  const handleDownloadPdf = async () => {
    if (exporting) return
    setExporting('pdf')
    try {
      const { canvas, width, height } = await exportTableToCanvas()
      const pngDataUrl = canvas.toDataURL('image/png')
      const pngBytes = await fetch(pngDataUrl).then((r) => r.arrayBuffer())

      const { PDFDocument } = await import('pdf-lib')
      const pdfDoc = await PDFDocument.create()
      const png = await pdfDoc.embedPng(pngBytes)

      // 96 CSS px ≈ 72 PDF points
      const pxToPt = 72 / 96
      const page = pdfDoc.addPage([width * pxToPt, height * pxToPt])
      page.drawImage(png, { x: 0, y: 0, width: page.getWidth(), height: page.getHeight() })

      const pdfBytes = await pdfDoc.save()
      // pdf-lib returns Uint8Array; make a concrete copy (ArrayBuffer-backed) for Blob typing correctness.
      const pdfCopy = Uint8Array.from(pdfBytes)
      downloadBlob(new Blob([pdfCopy], { type: 'application/pdf' }), `products-summary-week-${baseWeek}.pdf`)
    } catch (e: any) {
      const isTainted =
        typeof e?.name === 'string' && e.name === 'SecurityError' && String(e?.message || '').toLowerCase().includes('tainted')
      if (isTainted) {
        const res = await fetch(`/api/exports/products-summary?week=${encodeURIComponent(baseWeek)}&format=pdf`)
        if (!res.ok) throw new Error(`Failed to export PDF: ${res.statusText}`)
        const blob = await res.blob()
        downloadBlob(blob, `products-summary-week-${baseWeek}.pdf`)
      } else {
        throw e
      }
    } finally {
      setExporting(null)
    }
  }

  if (loading && !metricsData) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        <span className="ml-3 text-gray-600">Loading products summary…</span>
      </div>
    )
  }

  if (error) {
    return <div className="text-sm text-red-700">{error}</div>
  }

  if (!metricsData) {
    return <div className="text-sm text-gray-600">No products summary data available.</div>
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-end gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={!!exporting}
            onClick={handleDownloadPng}
          >
            <Download className="size-4" />
            {exporting === 'png' ? 'Exporting PNG…' : 'PNG'}
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={!!exporting}
            onClick={handleDownloadPdf}
          >
            <Download className="size-4" />
            {exporting === 'pdf' ? 'Exporting PDF…' : 'PDF'}
          </Button>
          <div className="hidden md:block text-[11px] text-gray-500 leading-snug">
            Exports exactly what you see in the table.
          </div>
      </div>

      <div
        ref={exportRef}
        data-export-target="products-summary-table"
        className="bg-gray-50 rounded-lg overflow-hidden overflow-x-auto"
      >
        <table className="w-full text-xs">
            <thead>
              <tr className="bg-gray-200 border-b">
                <th className="py-2 px-2 text-left font-medium text-gray-900" rowSpan={2}>
                  (USD '000)
                </th>
                <th className="py-2 px-2 text-center font-medium text-gray-900 bg-gray-200" colSpan={7}>
                  Latest Week: {latestWeekDisplay}
                </th>
                <th className="py-2 px-2 text-center font-medium text-gray-900 bg-amber-100" colSpan={5}>
                  Month-to-date
                </th>
                <th className="py-2 px-2 text-center font-medium text-gray-900 bg-blue-100" colSpan={5}>
                  Fiscal-year-to-date
                </th>
                <th className="py-2 px-2 text-center font-medium text-gray-900 bg-green-100" colSpan={3}>
                  Rolling-12-months
                </th>
              </tr>
              <tr className="bg-gray-200 border-b">
                <th className="py-1 px-2 text-right font-medium text-gray-900 bg-gray-400">Actual</th>
                <th className="py-1 px-2 text-right font-medium text-gray-900">Last Week</th>
                <th className="py-1 px-2 text-right font-medium text-gray-900">Last Year</th>
                <th className="py-1 px-2 text-right font-medium text-gray-900">2024</th>
                <th className="py-1 px-2 text-right font-medium text-gray-900">vs Last Week</th>
                <th className="py-1 px-2 text-right font-medium text-gray-900">vs Last Year</th>
                <th className="py-1 px-2 text-right font-medium text-gray-900">vs 2024</th>
                <th className="py-1 px-2 text-right font-medium text-gray-900 bg-amber-200">MTD Actual</th>
                <th className="py-1 px-2 text-right font-medium text-gray-900 bg-amber-50">MTD Last Year</th>
                <th className="py-1 px-2 text-right font-medium text-gray-900 bg-amber-50">MTD 2024</th>
                <th className="py-1 px-2 text-right font-medium text-gray-900 bg-amber-50">MTD vs Last Year</th>
                <th className="py-1 px-2 text-right font-medium text-gray-900 bg-amber-50">MTD vs 2024</th>
                <th className="py-1 px-2 text-right font-medium text-gray-900 bg-blue-200">FYTD Actual</th>
                <th className="py-1 px-2 text-right font-medium text-gray-900 bg-blue-50">FYTD Last Year</th>
                <th className="py-1 px-2 text-right font-medium text-gray-900 bg-blue-50">FYTD 2024</th>
                <th className="py-1 px-2 text-right font-medium text-gray-900 bg-blue-50">FYTD vs Last Year</th>
                <th className="py-1 px-2 text-right font-medium text-gray-900 bg-blue-50">FYTD vs 2024</th>
                <th className="py-1 px-2 text-right font-medium text-gray-900 bg-green-200">Last 12m</th>
                <th className="py-1 px-2 text-right font-medium text-gray-900 bg-green-50">Prev 12m</th>
                <th className="py-1 px-2 text-right font-medium text-gray-900 bg-green-50">YoY</th>
              </tr>
            </thead>
            <tbody>
              {METRICS.map(({ label, key, indent }) => {
              const actual = Number(metricsData?.actual?.[key] || 0)
              const lastWeek = Number(metricsData?.last_week?.[key] || 0)
              const lastYear = Number(metricsData?.last_year?.[key] || 0)
              const year2024 = Number(metricsData?.year_2024?.[key] || 0)

              const ytdActual = Number(metricsData?.ytd_actual?.[key] || 0)
              const ytdLastYear = Number(metricsData?.ytd_last_year?.[key] || 0)
              const ytd2024 = Number(metricsData?.ytd_2024?.[key] || 0)
              const mtdActual = Number(metricsData?.mtd_actual?.[key] || 0)
              const mtdLastYear = Number(metricsData?.mtd_last_year?.[key] || 0)
              const mtd2024 = Number(metricsData?.mtd_2024?.[key] || 0)

              const ltmCur = Number(ltmData?.ltm_actual?.[key] || 0)
              const ltmPrev = Number(ltmData?.ltm_last_year?.[key] || 0)

              const rowTextTone = indent ? 'text-gray-600' : 'text-gray-700'
              const labelTone = indent ? 'text-gray-600 italic font-normal' : 'text-gray-900 font-medium'
              const rowPadY = indent ? 'py-1' : 'py-2'
              const rowBg = indent ? 'bg-gray-50' : ''

              return (
                <tr
                  key={key}
                  className={`border-b border-gray-200 last:border-b-0 ${rowBg} ${indent ? 'text-[11px]' : ''}`}
                >
                  <td
                    className={`${rowPadY} px-2 ${labelTone} ${indent ? 'pl-8' : ''} ${indent ? 'border-l-2 border-gray-200' : ''}`}
                  >
                    {label}
                  </td>
                  <td className={`${rowPadY} px-2 text-right ${rowTextTone} bg-gray-200 font-semibold tabular-nums`}>
                    {formatSekThousands(actual)}
                  </td>
                  <td className={`${rowPadY} px-2 text-right ${rowTextTone} ${indent ? 'bg-gray-50' : ''} tabular-nums`}>
                    {formatSekThousands(lastWeek)}
                  </td>
                  <td className={`${rowPadY} px-2 text-right ${rowTextTone} ${indent ? 'bg-gray-50' : ''} tabular-nums`}>
                    {formatSekThousands(lastYear)}
                  </td>
                  <td className={`${rowPadY} px-2 text-right ${rowTextTone} ${indent ? 'bg-gray-50' : ''} tabular-nums`}>
                    {formatSekThousands(year2024)}
                  </td>
                  <td className={`${rowPadY} px-2 text-right ${rowTextTone} ${indent ? 'bg-gray-50' : ''} tabular-nums`}>
                    {fmtPct(growthPct(actual, lastWeek))}
                  </td>
                  <td className={`${rowPadY} px-2 text-right ${rowTextTone} ${indent ? 'bg-gray-50' : ''} tabular-nums`}>
                    {fmtPct(growthPct(actual, lastYear))}
                  </td>
                  <td className={`${rowPadY} px-2 text-right ${rowTextTone} ${indent ? 'bg-gray-50' : ''} tabular-nums`}>
                    {fmtPct(growthPct(actual, year2024))}
                  </td>
                  <td
                    className={`${rowPadY} px-2 text-right ${rowTextTone} bg-amber-100 font-semibold tabular-nums`}
                  >
                    {formatSekThousands(mtdActual)}
                  </td>
                  <td className={`${rowPadY} px-2 text-right ${rowTextTone} bg-amber-50 tabular-nums`}>
                    {formatSekThousands(mtdLastYear)}
                  </td>
                  <td className={`${rowPadY} px-2 text-right ${rowTextTone} bg-amber-50 tabular-nums`}>
                    {formatSekThousands(mtd2024)}
                  </td>
                  <td className={`${rowPadY} px-2 text-right ${rowTextTone} bg-amber-50 tabular-nums`}>
                    {fmtPct(growthPct(mtdActual, mtdLastYear))}
                  </td>
                  <td className={`${rowPadY} px-2 text-right ${rowTextTone} bg-amber-50 tabular-nums`}>
                    {fmtPct(growthPct(mtdActual, mtd2024))}
                  </td>
                  <td
                    className={`${rowPadY} px-2 text-right ${rowTextTone} bg-blue-100 font-semibold tabular-nums`}
                  >
                    {formatSekThousands(ytdActual)}
                  </td>
                  <td className={`${rowPadY} px-2 text-right ${rowTextTone} bg-blue-50 tabular-nums`}>
                    {formatSekThousands(ytdLastYear)}
                  </td>
                  <td className={`${rowPadY} px-2 text-right ${rowTextTone} bg-blue-50 tabular-nums`}>
                    {formatSekThousands(ytd2024)}
                  </td>
                  <td className={`${rowPadY} px-2 text-right ${rowTextTone} bg-blue-50 tabular-nums`}>
                    {fmtPct(growthPct(ytdActual, ytdLastYear))}
                  </td>
                  <td className={`${rowPadY} px-2 text-right ${rowTextTone} bg-blue-50 tabular-nums`}>
                    {fmtPct(growthPct(ytdActual, ytd2024))}
                  </td>
                  <td
                    className={`${rowPadY} px-2 text-right ${rowTextTone} bg-green-100 font-semibold tabular-nums`}
                  >
                    {formatSekThousands(ltmCur)}
                  </td>
                  <td className={`${rowPadY} px-2 text-right ${rowTextTone} bg-green-50 tabular-nums`}>
                    {formatSekThousands(ltmPrev)}
                  </td>
                  <td className={`${rowPadY} px-2 text-right ${rowTextTone} bg-green-50 tabular-nums`}>
                    {fmtPct(growthPct(ltmCur, ltmPrev))}
                  </td>
                </tr>
              )
              })}
            </tbody>
          </table>
      </div>
    </div>
  )
}


