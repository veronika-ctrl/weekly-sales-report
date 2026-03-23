#!/usr/bin/env tsx

import puppeteer from 'puppeteer'
import type { Page } from 'puppeteer'
import * as path from 'path'
import * as fs from 'fs'
import { fileURLToPath } from 'url'

const BASE_URL =
  process.env.NEXT_PUBLIC_FRONTEND_URL ||
  process.env.FRONTEND_URL ||
  'http://localhost:3000'

// Get the project root directory (one level up from frontend/scripts/)
const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const frontendDir = path.resolve(__dirname, '..')
const projectRoot = path.resolve(frontendDir, '..')
const OUTPUT_DIR = path.join(projectRoot, 'reports')

interface PageConfig {
  name: string
  slug: string
  url: string
  waitForSelector?: string
}

async function waitForPageLoad(page: Page, pageConfig: PageConfig): Promise<void> {
  // Wait for fonts to load
  try {
    await page.evaluate(() => document.fonts.ready)
  } catch {
    // ignore
  }

  // Wait for loading spinners to disappear (best-effort)
  try {
    await page.waitForFunction(
      () => {
        const spinner = document.querySelector('.animate-spin, [class*="animate-spin"]')
        if (spinner) {
          const style = window.getComputedStyle(spinner)
          return style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0'
        }
        return true
      },
      { timeout: 60000 }
    )
  } catch {
    // ignore
  }

  // Wait for page content selector, if provided (best-effort)
  if (pageConfig.waitForSelector) {
    try {
      await page.waitForSelector(pageConfig.waitForSelector, { timeout: 90000 })
    } catch {
      // ignore
    }
  }

  // Small extra delay to let charts finish rendering
  await new Promise((resolve) => setTimeout(resolve, 1200))
}

function escapeHtml(s: string): string {
  return s
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;')
}

function buildHtml(week: string, pages: Array<{ name: string; slug: string; dataUrl: string }>): string {
  const navLinks = pages
    .map((p) => `<a class="nav-link" href="#${p.slug}">${escapeHtml(p.name)}</a>`)
    .join('')

  const sections = pages
    .map(
      (p) => `
      <section id="${p.slug}" class="section">
        <h2>${escapeHtml(p.name)}</h2>
        <div class="img-wrap">
          <img alt="${escapeHtml(p.name)}" src="${p.dataUrl}" />
        </div>
      </section>
    `
    )
    .join('\n')

  return `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>Weekly report ${escapeHtml(week)}</title>
    <style>
      :root {
        --bg: #0b1220;
        --panel: #111b2e;
        --text: #e6edf7;
        --muted: #a7b3c6;
        --border: rgba(255,255,255,0.08);
        --link: #8ab4ff;
      }
      html, body { margin: 0; padding: 0; background: var(--bg); color: var(--text); font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; }
      a { color: var(--link); text-decoration: none; }
      a:hover { text-decoration: underline; }
      .wrap { max-width: 1200px; margin: 0 auto; padding: 20px; }
      .header { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; padding: 14px 16px; background: var(--panel); border: 1px solid var(--border); border-radius: 12px; }
      .title { margin: 0; font-size: 18px; }
      .meta { margin: 0; color: var(--muted); font-size: 13px; }
      .nav { position: sticky; top: 12px; margin-top: 14px; padding: 10px 12px; background: var(--panel); border: 1px solid var(--border); border-radius: 12px; display: flex; flex-wrap: wrap; gap: 10px; z-index: 10; }
      .nav-link { padding: 6px 10px; border-radius: 999px; border: 1px solid var(--border); background: rgba(255,255,255,0.03); }
      .section { margin-top: 18px; padding: 14px 16px; background: var(--panel); border: 1px solid var(--border); border-radius: 12px; }
      .section h2 { margin: 0 0 12px 0; font-size: 16px; }
      .img-wrap { border: 1px solid var(--border); border-radius: 10px; overflow: hidden; background: #0a0f1b; }
      img { width: 100%; height: auto; display: block; }
      .footer { margin-top: 18px; color: var(--muted); font-size: 12px; text-align: center; }
    </style>
  </head>
  <body>
    <div class="wrap">
      <div class="header">
        <div>
          <h1 class="title">Weekly report — ${escapeHtml(week)}</h1>
          <p class="meta">Exported as a self-contained HTML file. Use the nav below to jump between sections.</p>
        </div>
        <div class="meta">${escapeHtml(new Date().toISOString())}</div>
      </div>

      <nav class="nav">
        ${navLinks}
      </nav>

      ${sections}

      <div class="footer">Generated locally from ${escapeHtml(BASE_URL)}.</div>
    </div>
  </body>
</html>`
}

async function exportWeeklyHtml(week: string) {
  if (!week || !/^\d{4}-\d{2}$/.test(week)) {
    throw new Error('Invalid week format. Expected format: YYYY-WW (e.g., 2026-02)')
  }

  if (!fs.existsSync(OUTPUT_DIR)) fs.mkdirSync(OUTPUT_DIR, { recursive: true })
  const weekDir = path.join(OUTPUT_DIR, week)
  if (!fs.existsSync(weekDir)) fs.mkdirSync(weekDir, { recursive: true })
  const outputPath = path.join(weekDir, 'weekly-report.html')

  const debugEnabled = process.env.HTML_DEBUG === '1' || process.argv.includes('--debug')

  const pageConfigs: PageConfig[] = [
    {
      name: 'Summary',
      slug: 'summary',
      url: `${BASE_URL}/reports/weekly/${week}?export=1${debugEnabled ? '&debug=1' : ''}`,
      waitForSelector: 'table tbody tr',
    },
    {
      name: 'Top Markets',
      slug: 'top-markets',
      url: `${BASE_URL}/reports/weekly/${week}/top-markets?export=1${debugEnabled ? '&debug=1' : ''}`,
      waitForSelector: 'table tbody tr',
    },
    {
      name: 'Online KPIs',
      slug: 'online-kpis',
      url: `${BASE_URL}/reports/weekly/${week}/online-kpis?export=1${debugEnabled ? '&debug=1' : ''}`,
      waitForSelector: '.card, [class*="Card"]',
    },
  ]

  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
    timeout: 180000,
  })

  try {
    const rendered: Array<{ name: string; slug: string; dataUrl: string }> = []

    for (let i = 0; i < pageConfigs.length; i++) {
      const cfg = pageConfigs[i]
      console.log(`\n📄 [${i + 1}/${pageConfigs.length}] Rendering ${cfg.name}`)
      console.log(`   URL: ${cfg.url}`)

      const page = await browser.newPage()
      page.setDefaultNavigationTimeout(180000)
      page.setDefaultTimeout(180000)
      await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 2 })

      // Capture console errors (helpful if a page fails to load)
      page.on('console', (msg) => {
        if (msg.type() === 'error') console.error(`   🧨 [browser:${cfg.name}] ${msg.text()}`)
      })
      page.on('pageerror', (err) => {
        console.error(`   🧨 [pageerror:${cfg.name}]`, err)
      })

      try {
        await page.goto(cfg.url, { waitUntil: 'domcontentloaded', timeout: 180000 })

        // Ensure "main" exists; avoids taking screenshots while app is still booting
        try {
          await page.waitForSelector('main, body', { timeout: 90000 })
        } catch {
          // ignore
        }

        await waitForPageLoad(page, cfg)

        const b64 = await page.screenshot({
          fullPage: true,
          type: 'png',
          encoding: 'base64',
        })

        rendered.push({
          name: cfg.name,
          slug: cfg.slug,
          dataUrl: `data:image/png;base64,${b64}`,
        })

        console.log(`   ✅ Captured screenshot (${b64.length} base64 chars)`)
      } finally {
        await page.close()
      }
    }

    const html = buildHtml(week, rendered)
    fs.writeFileSync(outputPath, html, 'utf8')

    if (!fs.existsSync(outputPath)) {
      throw new Error(`HTML file was not created at ${outputPath}`)
    }
    const stats = fs.statSync(outputPath)
    console.log(`\n✅ HTML export created: ${outputPath}`)
    console.log(`📊 File size: ${stats.size} bytes`)

    return outputPath
  } finally {
    await browser.close()
  }
}

// Main execution
const week = process.argv[2]

if (!week) {
  console.error('Usage: tsx scripts/exportWeeklyHtml.ts <week>')
  console.error('Example: tsx scripts/exportWeeklyHtml.ts 2026-02')
  process.exit(1)
}

exportWeeklyHtml(week)
  .then((outputPath) => {
    console.log(`\n✅ Success! HTML saved to: ${outputPath}`)
    process.exit(0)
  })
  .catch((error) => {
    console.error('\n❌ Error generating HTML:', error)
    process.exit(1)
  })






