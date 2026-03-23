import { NextResponse, type NextRequest } from 'next/server'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

export async function GET(request: NextRequest) {
  const week = request.nextUrl.searchParams.get('week') || ''
  const format = (request.nextUrl.searchParams.get('format') || 'png').toLowerCase()

  if (!week || !/^\d{4}-\d{2}$/.test(week)) {
    return NextResponse.json({ error: 'Missing or invalid week (expected YYYY-WW)' }, { status: 400 })
  }
  if (format !== 'png' && format !== 'pdf') {
    return NextResponse.json({ error: 'Invalid format (png|pdf)' }, { status: 400 })
  }

  // Lazy import so normal page loads don’t pay the cost.
  const puppeteer = (await import('puppeteer')).default

  const origin = request.nextUrl.origin
  const url = `${origin}/products/summary?week=${encodeURIComponent(week)}&export=1`

  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  })

  try {
    const page = await browser.newPage()
    // Slightly wider than the table to avoid wrapping.
    await page.setViewport({ width: 1400, height: 900, deviceScaleFactor: 2 })

    await page.goto(url, { waitUntil: 'networkidle2', timeout: 60_000 })
    await page.waitForSelector('[data-export-target="products-summary-table"] table', { timeout: 60_000 })

    const el = await page.$('[data-export-target="products-summary-table"]')
    if (!el) {
      return NextResponse.json({ error: 'Export target not found' }, { status: 500 })
    }

    const pngBytes = (await el.screenshot({ type: 'png' })) as Uint8Array

    if (format === 'png') {
      return new NextResponse(Buffer.from(pngBytes), {
        headers: {
          'Content-Type': 'image/png',
          'Content-Disposition': `attachment; filename="products-summary-week-${week}.png"`,
          'Cache-Control': 'no-store',
        },
      })
    }

    const { PDFDocument } = await import('pdf-lib')
    const pdfDoc = await PDFDocument.create()
    const png = await pdfDoc.embedPng(pngBytes)
    const pagePdf = pdfDoc.addPage([png.width, png.height])
    pagePdf.drawImage(png, { x: 0, y: 0, width: png.width, height: png.height })
    const pdfBytes = await pdfDoc.save()

    return new NextResponse(Buffer.from(pdfBytes), {
      headers: {
        'Content-Type': 'application/pdf',
        'Content-Disposition': `attachment; filename="products-summary-week-${week}.pdf"`,
        'Cache-Control': 'no-store',
      },
    })
  } catch (e: any) {
    return NextResponse.json({ error: e?.message || 'Export failed' }, { status: 500 })
  } finally {
    await browser.close()
  }
}


