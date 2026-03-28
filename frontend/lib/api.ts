const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

/** True when a backend URL is configured (local or production). When false, app reads only from Supabase and uses client-side periods. */
export const hasBackend = Boolean(
  typeof process !== 'undefined' && process.env.NEXT_PUBLIC_API_URL && String(process.env.NEXT_PUBLIC_API_URL).trim()
)

import { getPeriodsFromBaseWeek } from './periods'

export interface PeriodsResponse {
  actual: string
  last_week: string
  last_year: string
  year_2023: string
  date_ranges: Record<string, {
    start: string
    end: string
    display: string
  }>
  ytd_periods: Record<string, {
    start: string
    end: string
  }>
}

export interface MetricsResponse {
  periods: Record<string, Record<string, number>>
}

export interface MetricsMtdResponse {
  periods: Record<string, Record<string, number>>
  date_ranges: Record<string, { start: string; end: string; display: string }>
}

export interface MarketsResponse {
  markets: Array<{
    country: string
    weeks: Record<string, number>
    average: number
  }>
  period_info: {
    latest_week: string
    latest_dates: string
  }
}

export interface MarketNetPeriodBlock {
  actual: number
  last_year: number
  budget: number | null
  yoy_pct: number | null
  vs_budget: number | null
}

export interface TopMarketsNetMtdResponse {
  markets: Array<{
    country: string
    week: MarketNetPeriodBlock
    month: MarketNetPeriodBlock
    ytd: MarketNetPeriodBlock
  }>
  period_info: Record<string, string>
  date_ranges: Record<string, Record<string, string>>
  /** file_per_market when budget CSV has Market; else mix_allocation */
  budget_source?: string | null
  /** How Week / Month / YTD group and per-market budgets were derived */
  budget_explanation?: string[] | null
}

export interface OnlineKPIsResponse {
  kpis: Array<{
    week: string
    aov_new_customer: number
    aov_returning_customer: number
    cos: number
    marketing_spend: number
    net_revenue?: number
    /** Online gross revenue (Qlik); optional extra KPI field. */
    gross_revenue?: number
    /** Sum of Net Revenue for online + New customers; aMER on Audience Total = this ÷ marketing_spend. */
    new_customers_net_revenue?: number
    conversion_rate: number
    new_customers: number
    returning_customers: number
    sessions: number
    new_customer_cac: number
    total_orders: number
    return_rate_new_pct?: number
    return_rate_returning_pct?: number
    last_year: {
      week: string
      aov_new_customer: number
      aov_returning_customer: number
      cos: number
      marketing_spend: number
      net_revenue?: number
      gross_revenue?: number
      new_customers_net_revenue?: number
      conversion_rate: number
      new_customers: number
      returning_customers: number
      sessions: number
      new_customer_cac: number
      total_orders: number
      return_rate_new_pct?: number
      return_rate_returning_pct?: number
    } | null
  }>
  period_info: {
    latest_week: string
    latest_dates: string
  }
}

export interface ContributionData {
  week: string
  gross_revenue_new: number
  gross_revenue_returning: number
  contribution_new: number
  contribution_returning: number
  contribution_total: number
  last_year: {
    week: string
    gross_revenue_new: number
    gross_revenue_returning: number
    contribution_new: number
    contribution_returning: number
    contribution_total: number
  } | null
}

export interface ContributionResponse {
  contributions: ContributionData[]
  period_info: {
    latest_week: string
    latest_dates: string
  }
}

export interface GenderSalesData {
  week: string
  men_unisex_sales: number
  women_sales: number
  total_sales: number
  last_year: {
    week: string
    men_unisex_sales: number
    women_sales: number
    total_sales: number
  } | null
}

export interface GenderSalesResponse {
  gender_sales: GenderSalesData[]
  period_info: {
    latest_week: string
    latest_dates: string
  }
}

export interface MenCategorySalesData {
  week: string
  categories: Record<string, number>
  last_year: {
    week: string
    categories: Record<string, number>
  } | null
}

export interface MenCategorySalesResponse {
  men_category_sales: MenCategorySalesData[]
  period_info: {
    latest_week: string
    latest_dates: string
  }
}

export interface WomenCategorySalesData {
  week: string
  categories: Record<string, number>
  last_year: {
    week: string
    categories: Record<string, number>
  } | null
}

export interface WomenCategorySalesResponse {
  women_category_sales: WomenCategorySalesData[]
  period_info: {
    latest_week: string
    latest_dates: string
  }
}

export interface CategorySalesData {
  week: string
  categories: Record<string, number>
  last_year: {
    week: string
    categories: Record<string, number>
  } | null
}

export interface CategorySalesResponse {
  category_sales: CategorySalesData[]
  period_info: {
    latest_week: string
    latest_dates: string
  }
}

export interface GeneratePDFResponse {
  success: boolean
  file_path: string
  download_url: string
}

export async function generatePDF(baseWeek: string, periods: string[]): Promise<GeneratePDFResponse> {
  const response = await fetch(`${API_BASE_URL}/api/generate/pdf`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ base_week: baseWeek, periods }),
  })
  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || `Failed to generate PDF: ${response.statusText}`)
  }
  return response.json()
}

export function getDownloadUrl(filename: string): string {
  return `${API_BASE_URL}/api/download/${encodeURIComponent(filename)}`
}

export async function getPeriods(baseWeek: string): Promise<PeriodsResponse> {
  if (!hasBackend) {
    return getPeriodsFromBaseWeek(baseWeek) as PeriodsResponse
  }
  const response = await fetch(`${API_BASE_URL}/api/periods?base_week=${baseWeek}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch periods: ${response.statusText}`)
  }
  return response.json()
}

export async function getTable1Metrics(baseWeek: string, periods: string[], includeYtd: boolean = true): Promise<MetricsResponse> {
  const periodsParam = periods.join(',')
  const response = await fetch(`${API_BASE_URL}/api/metrics/table1?base_week=${baseWeek}&periods=${periodsParam}&include_ytd=${includeYtd}`)
  if (!response.ok) {
    const errBody = await response.json().catch(() => ({}))
    const detail = typeof errBody?.detail === 'string' ? errBody.detail : response.statusText
    throw new Error(detail)
  }
  return response.json()
}

export async function getTable1Mtd(baseWeek: string): Promise<MetricsMtdResponse> {
  const response = await fetch(`${API_BASE_URL}/api/metrics/table1-mtd?base_week=${encodeURIComponent(baseWeek)}`)
  if (!response.ok) {
    const errBody = await response.json().catch(() => ({}))
    const detail = typeof errBody?.detail === 'string' ? errBody.detail : response.statusText
    throw new Error(detail)
  }
  return response.json()
}

export async function getTopMarkets(
  baseWeek: string,
  numWeeks: number = 8,
  recalculate: boolean = false
): Promise<MarketsResponse> {
  const params = new URLSearchParams({
    base_week: baseWeek,
    num_weeks: String(numWeeks),
    ...(recalculate && { recalculate: 'true' }),
  })
  const response = await fetch(`${API_BASE_URL}/api/markets/top?${params}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch markets: ${response.statusText}`)
  }
  return response.json()
}

export async function getTopMarketsNetMtd(
  baseWeek: string,
  numWeeks: number = 8
): Promise<TopMarketsNetMtdResponse> {
  const params = new URLSearchParams({
    base_week: baseWeek,
    num_weeks: String(numWeeks),
  })
  const response = await fetch(`${API_BASE_URL}/api/markets/top-net-mtd?${params}`)
  if (!response.ok) {
    const errBody = await response.json().catch(() => ({}))
    const detail = typeof errBody?.detail === 'string' ? errBody.detail : response.statusText
    throw new Error(detail)
  }
  return response.json()
}

export async function getOnlineKPIs(
  baseWeek: string,
  numWeeks: number = 8,
  country?: string
): Promise<OnlineKPIsResponse> {
  const params = new URLSearchParams({
    base_week: baseWeek,
    num_weeks: String(numWeeks),
  })
  if (country) params.set('country', country)
  const response = await fetch(`${API_BASE_URL}/api/online-kpis?${params.toString()}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch Online KPIs: ${response.statusText}`)
  }
  return response.json()
}

export async function getContribution(baseWeek: string, numWeeks: number = 8): Promise<ContributionResponse> {
  const response = await fetch(`${API_BASE_URL}/api/contribution?base_week=${baseWeek}&num_weeks=${numWeeks}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch Contribution data: ${response.statusText}`)
  }
  return response.json()
}

export async function getGenderSales(baseWeek: string, numWeeks: number = 8): Promise<GenderSalesResponse> {
  const response = await fetch(`${API_BASE_URL}/api/gender-sales?base_week=${baseWeek}&num_weeks=${numWeeks}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch Gender Sales data: ${response.statusText}`)
  }
  return response.json()
}

export async function getMenCategorySales(baseWeek: string, numWeeks: number = 8): Promise<MenCategorySalesResponse> {
  const response = await fetch(`${API_BASE_URL}/api/men-category-sales?base_week=${baseWeek}&num_weeks=${numWeeks}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch Men Category Sales data: ${response.statusText}`)
  }
  return response.json()
}

export async function getWomenCategorySales(baseWeek: string, numWeeks: number = 8): Promise<WomenCategorySalesResponse> {
  const response = await fetch(`${API_BASE_URL}/api/women-category-sales?base_week=${baseWeek}&num_weeks=${numWeeks}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch Women Category Sales data: ${response.statusText}`)
  }
  return response.json()
}

export async function getCategorySales(baseWeek: string, numWeeks: number = 8): Promise<CategorySalesResponse> {
  const response = await fetch(`${API_BASE_URL}/api/category-sales?base_week=${baseWeek}&num_weeks=${numWeeks}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch Category Sales data: ${response.statusText}`)
  }
  return response.json()
}

export interface ProductData {
  rank: number
  gender: string
  category: string
  product: string
  color: string
  gross_revenue: number
  sales_qty: number
}

export interface TopProductsData {
  week: string
  products: ProductData[]
  top_total: {
    gross_revenue: number
    sales_qty: number
    sob: number
  }
  grand_total: {
    gross_revenue: number
    sales_qty: number
    sob: number
  }
}

export interface TopProductsResponse {
  top_products: TopProductsData[]
  period_info: {
    latest_week: string
    latest_dates: string
  }
}

export interface SessionsPerCountryData {
  week: string
  countries: Record<string, number>
  last_year?: {
    week: string
    countries: Record<string, number>
  } | null
}

export interface SessionsPerCountryResponse {
  sessions_per_country: SessionsPerCountryData[]
  period_info: {
    latest_week: string
    latest_dates: string
  }
}

export interface ConversionPerCountryData {
  week: string
  countries: Record<string, {
    conversion_rate: number
    orders: number
    sessions: number
  }>
  last_year?: {
    week: string
    countries: Record<string, {
      conversion_rate: number
      orders: number
      sessions: number
    }>
  } | null
}

export interface ConversionPerCountryResponse {
  conversion_per_country: ConversionPerCountryData[]
  period_info: {
    latest_week: string
    latest_dates: string
  }
}

export interface NewCustomersPerCountryData {
  week: string
  countries: Record<string, number>
  last_year?: {
    week: string
    countries: Record<string, number>
  } | null
}

export interface NewCustomersPerCountryResponse {
  new_customers_per_country: NewCustomersPerCountryData[]
  period_info: {
    latest_week: string
    latest_dates: string
  }
}

export interface ReturningCustomersPerCountryData {
  week: string
  countries: Record<string, number>
  last_year?: {
    week: string
    countries: Record<string, number>
  } | null
}

export interface ReturningCustomersPerCountryResponse {
  returning_customers_per_country: ReturningCustomersPerCountryData[]
  period_info: {
    latest_week: string
    latest_dates: string
  }
}

export interface AOVNewCustomersPerCountryData {
  week: string
  countries: Record<string, number>
  last_year?: {
    week: string
    countries: Record<string, number>
  } | null
}

export interface AOVNewCustomersPerCountryResponse {
  aov_new_customers_per_country: AOVNewCustomersPerCountryData[]
  period_info: {
    latest_week: string
    latest_dates: string
  }
}

export interface AOVReturningCustomersPerCountryData {
  week: string
  countries: Record<string, number>
  last_year?: {
    week: string
    countries: Record<string, number>
  } | null
}

export interface AOVReturningCustomersPerCountryResponse {
  aov_returning_customers_per_country: AOVReturningCustomersPerCountryData[]
  period_info: {
    latest_week: string
    latest_dates: string
  }
}

export interface MarketingSpendPerCountryData {
  week: string
  countries: Record<string, number>
  last_year?: {
    week: string
    countries: Record<string, number>
  } | null
}

export interface MarketingSpendPerCountryResponse {
  marketing_spend_per_country: MarketingSpendPerCountryData[]
  period_info: {
    latest_week: string
    latest_dates: string
  }
}

export interface nCACPerCountryData {
  week: string
  countries: Record<string, number>
  last_year?: {
    week: string
    countries: Record<string, number>
  } | null
}

export interface nCACPerCountryResponse {
  ncac_per_country: nCACPerCountryData[]
  period_info: {
    latest_week: string
    latest_dates: string
  }
}

export interface ContributionNewPerCountryData {
  week: string
  countries: Record<string, number>
  last_year?: {
    week: string
    countries: Record<string, number>
  } | null
}

export interface ContributionNewPerCountryResponse {
  contribution_new_per_country: ContributionNewPerCountryData[]
  period_info: {
    latest_week: string
    latest_dates: string
  }
}

export interface ContributionNewTotalPerCountryResponse {
  contribution_new_total_per_country: ContributionNewPerCountryData[]
  period_info: {
    latest_week: string
    latest_dates: string
  }
}

export interface ContributionReturningPerCountryResponse {
  contribution_returning_per_country: ContributionNewPerCountryData[]
  period_info: {
    latest_week: string
    latest_dates: string
  }
}

export interface ContributionReturningTotalPerCountryResponse {
  contribution_returning_total_per_country: ContributionNewPerCountryData[]
  period_info: {
    latest_week: string
    latest_dates: string
  }
}

export interface TotalContributionPerCountryResponse {
  total_contribution_per_country: ContributionNewPerCountryData[]
  period_info: {
    latest_week: string
    latest_dates: string
  }
}

/** Budget general: aggregated by month (same shape as /api/budget-general). */
export interface BudgetGeneralResponse {
  week: string
  months: string[]
  metrics: string[]
  table: Record<string, Record<string, number>>
  totals: Record<string, number>
  ytd_totals: Record<string, number>
  customer_by_metric?: Record<string, string>
  display_name_by_metric?: Record<string, string>
  error?: string
}

/** Actuals general: same shape as budget-general when implemented. */
export interface ActualsGeneralResponse {
  week?: string
  months?: string[]
  metrics?: string[]
  table?: Record<string, Record<string, number>>
  totals?: Record<string, number>
  ytd_totals?: Record<string, number>
  error?: string
}

export interface CustomerQualityScorecardResponse {
  window_days: number
  baseline_months: number
  latest: any | null
  baseline: Record<string, any>
  trend: any[]
  meta?: Record<string, any>
  diagnostics?: Record<string, any>
}

export interface CustomerQualityDiscountDepthResponse {
  window_days: number
  buckets: Array<{
    bucket: string
    customers: number
    repeat_rate: number
    net_sales_per_customer: number
    full_price_revenue_share: number | null
    discount_cost_rate: number | null
  }>
  meta?: Record<string, any>
}

export interface CustomerQualitySegmentsResponse {
  window_days: number
  segments: Array<Record<string, any>>
  value_metric: string
  meta?: Record<string, any>
}

export interface CustomerQualityPathwaysResponse {
  window_days: number
  trend: Array<Record<string, any>>
  baseline: Record<string, any>
  meta?: Record<string, any>
}

export async function getTopProducts(baseWeek: string, numWeeks: number = 1, topN: number = 30, customerType: 'new' | 'returning' = 'new'): Promise<TopProductsResponse> {
  const response = await fetch(`${API_BASE_URL}/api/top-products?base_week=${baseWeek}&num_weeks=${numWeeks}&top_n=${topN}&customer_type=${customerType}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch Top Products data: ${response.statusText}`)
  }
  return response.json()
}

export async function getTopProductsByGender(baseWeek: string, numWeeks: number = 1, topN: number = 30, genderFilter: 'men' | 'women' = 'men'): Promise<TopProductsResponse> {
  const response = await fetch(`${API_BASE_URL}/api/top-products-gender?base_week=${baseWeek}&num_weeks=${numWeeks}&top_n=${topN}&gender_filter=${genderFilter}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch Top Products by Gender data: ${response.statusText}`)
  }
  return response.json()
}

export async function getSessionsPerCountry(baseWeek: string, numWeeks: number = 8): Promise<SessionsPerCountryResponse> {
  const response = await fetch(`${API_BASE_URL}/api/sessions-per-country?base_week=${baseWeek}&num_weeks=${numWeeks}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch Sessions per Country data: ${response.statusText}`)
  }
  return response.json()
}

export async function getConversionPerCountry(baseWeek: string, numWeeks: number = 8): Promise<ConversionPerCountryResponse> {
  const response = await fetch(`${API_BASE_URL}/api/conversion-per-country?base_week=${baseWeek}&num_weeks=${numWeeks}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch Conversion per Country data: ${response.statusText}`)
  }
  return response.json()
}

export async function getNewCustomersPerCountry(baseWeek: string, numWeeks: number = 8): Promise<NewCustomersPerCountryResponse> {
  const response = await fetch(`${API_BASE_URL}/api/new-customers-per-country?base_week=${baseWeek}&num_weeks=${numWeeks}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch New Customers per Country data: ${response.statusText}`)
  }
  return response.json()
}

export async function getReturningCustomersPerCountry(baseWeek: string, numWeeks: number = 8): Promise<ReturningCustomersPerCountryResponse> {
  const response = await fetch(`${API_BASE_URL}/api/returning-customers-per-country?base_week=${baseWeek}&num_weeks=${numWeeks}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch Returning Customers per Country data: ${response.statusText}`)
  }
  return response.json()
}

export async function getAOVNewCustomersPerCountry(baseWeek: string, numWeeks: number = 8): Promise<AOVNewCustomersPerCountryResponse> {
  const response = await fetch(`${API_BASE_URL}/api/aov-new-customers-per-country?base_week=${baseWeek}&num_weeks=${numWeeks}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch AOV New Customers per Country data: ${response.statusText}`)
  }
  return response.json()
}

export async function getAOVReturningCustomersPerCountry(baseWeek: string, numWeeks: number = 8): Promise<AOVReturningCustomersPerCountryResponse> {
  const response = await fetch(`${API_BASE_URL}/api/aov-returning-customers-per-country?base_week=${baseWeek}&num_weeks=${numWeeks}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch AOV Returning Customers per Country data: ${response.statusText}`)
  }
  return response.json()
}

export async function getMarketingSpendPerCountry(baseWeek: string, numWeeks: number = 8): Promise<MarketingSpendPerCountryResponse> {
  const response = await fetch(`${API_BASE_URL}/api/marketing-spend-per-country?base_week=${baseWeek}&num_weeks=${numWeeks}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch Marketing Spend per Country data: ${response.statusText}`)
  }
  return response.json()
}

export async function getNCACPerCountry(baseWeek: string, numWeeks: number = 8): Promise<nCACPerCountryResponse> {
  const response = await fetch(`${API_BASE_URL}/api/ncac-per-country?base_week=${baseWeek}&num_weeks=${numWeeks}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch nCAC per Country data: ${response.statusText}`)
  }
  return response.json()
}

export async function getContributionNewPerCountry(baseWeek: string, numWeeks: number = 8): Promise<ContributionNewPerCountryResponse> {
  const response = await fetch(`${API_BASE_URL}/api/contribution-new-per-country?base_week=${baseWeek}&num_weeks=${numWeeks}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch Contribution New per Country data: ${response.statusText}`)
  }
  return response.json()
}

export async function getContributionNewTotalPerCountry(baseWeek: string, numWeeks: number = 8): Promise<ContributionNewTotalPerCountryResponse> {
  const response = await fetch(`${API_BASE_URL}/api/contribution-new-total-per-country?base_week=${baseWeek}&num_weeks=${numWeeks}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch Contribution New Total per Country data: ${response.statusText}`)
  }
  return response.json()
}

export async function getContributionReturningPerCountry(baseWeek: string, numWeeks: number = 8): Promise<ContributionReturningPerCountryResponse> {
  const response = await fetch(`${API_BASE_URL}/api/contribution-returning-per-country?base_week=${baseWeek}&num_weeks=${numWeeks}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch Contribution Returning per Country data: ${response.statusText}`)
  }
  return response.json()
}

export async function getContributionReturningTotalPerCountry(baseWeek: string, numWeeks: number = 8): Promise<ContributionReturningTotalPerCountryResponse> {
  const response = await fetch(`${API_BASE_URL}/api/contribution-returning-total-per-country?base_week=${baseWeek}&num_weeks=${numWeeks}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch Contribution Returning Total per Country data: ${response.statusText}`)
  }
  return response.json()
}

export async function getTotalContributionPerCountry(baseWeek: string, numWeeks: number = 8): Promise<TotalContributionPerCountryResponse> {
  const response = await fetch(`${API_BASE_URL}/api/total-contribution-per-country?base_week=${baseWeek}&num_weeks=${numWeeks}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch Total Contribution per Country data: ${response.statusText}`)
  }
  return response.json()
}

export interface BatchMetricsResponse {
  periods: PeriodsResponse
  metrics: MetricsResponse
  markets: MarketsResponse
  kpis: OnlineKPIsResponse
  contribution: ContributionResponse
  gender_sales: GenderSalesResponse
  men_category_sales: MenCategorySalesResponse
  women_category_sales: WomenCategorySalesResponse
  category_sales: any
  products_new: any
  products_gender: any
  sessions_per_country: SessionsPerCountryResponse
  conversion_per_country: ConversionPerCountryResponse
  new_customers_per_country: NewCustomersPerCountryResponse
  returning_customers_per_country: ReturningCustomersPerCountryResponse
  aov_new_customers_per_country: AOVNewCustomersPerCountryResponse
  aov_returning_customers_per_country: AOVReturningCustomersPerCountryResponse
  marketing_spend_per_country: MarketingSpendPerCountryResponse
  ncac_per_country: nCACPerCountryResponse
  contribution_new_per_country: ContributionNewPerCountryResponse
  contribution_new_total_per_country: ContributionNewTotalPerCountryResponse
  contribution_returning_per_country: ContributionReturningPerCountryResponse
  contribution_returning_total_per_country: ContributionReturningTotalPerCountryResponse
  total_contribution_per_country: TotalContributionPerCountryResponse
}

/** Batch compute can be slow; without a timeout the UI sits at ~5% forever if the API is down. */
const BATCH_METRICS_TIMEOUT_MS = 180_000

export async function getBatchMetrics(baseWeek: string, numWeeks: number = 8): Promise<BatchMetricsResponse> {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), BATCH_METRICS_TIMEOUT_MS)
  const url = `${API_BASE_URL}/api/batch/all-metrics?base_week=${encodeURIComponent(baseWeek)}&num_weeks=${numWeeks}`
  try {
    const response = await fetch(url, { signal: controller.signal })
    if (!response.ok) {
      const errBody = await response.json().catch(() => ({}))
      const detail = typeof errBody?.detail === 'string' ? errBody.detail : response.statusText
      throw new Error(detail)
    }
    return response.json()
  } catch (e) {
    if (e instanceof Error && e.name === 'AbortError') {
      throw new Error(
        `Batch metrics timed out after ${BATCH_METRICS_TIMEOUT_MS / 1000}s. Is the API running at ${API_BASE_URL}?`
      )
    }
    throw e
  } finally {
    clearTimeout(timeoutId)
  }
}

export async function getBudgetGeneral(week: string): Promise<BudgetGeneralResponse> {
  const response = await fetch(`${API_BASE_URL}/api/budget-general?week=${encodeURIComponent(week)}`)
  if (!response.ok) {
    const err = await response.json().catch(() => ({}))
    throw new Error(err?.detail || `Failed to fetch budget general: ${response.statusText}`)
  }
  return response.json()
}

export async function getActualsGeneral(week: string): Promise<ActualsGeneralResponse> {
  const response = await fetch(`${API_BASE_URL}/api/actuals-general?week=${encodeURIComponent(week)}`)
  if (!response.ok) {
    const err = await response.json().catch(() => ({}))
    throw new Error(err?.detail || `Failed to fetch actuals general: ${response.statusText}`)
  }
  return response.json()
}

export async function getBudgetRaw(week: string): Promise<{ week: string; columns: string[]; row_count: number; sample_data: Record<string, unknown>[]; error?: string }> {
  const response = await fetch(`${API_BASE_URL}/api/budget-data?week=${encodeURIComponent(week)}`)
  if (!response.ok) {
    const err = await response.json().catch(() => ({}))
    throw new Error(err?.detail || err?.error || `Failed to fetch budget data: ${response.statusText}`)
  }
  return response.json()
}

export async function getActualsMarkets(week: string): Promise<{ columns: string[]; sample_data: Record<string, unknown>[] }> {
  const response = await fetch(`${API_BASE_URL}/api/actuals-markets?week=${encodeURIComponent(week)}`)
  if (!response.ok) {
    const err = await response.json().catch(() => ({}))
    throw new Error(err?.detail || err?.error || `Failed to fetch actuals markets: ${response.statusText}`)
  }
  return response.json()
}

export async function getActualsMarketsDetailed(week: string): Promise<Record<string, unknown>> {
  const response = await fetch(`${API_BASE_URL}/api/actuals-markets-detailed?week=${encodeURIComponent(week)}`)
  if (!response.ok) {
    const err = await response.json().catch(() => ({}))
    throw new Error(err?.detail || err?.error || `Failed to fetch actuals markets detailed: ${response.statusText}`)
  }
  return response.json()
}

export interface AudienceMetricsCountryData {
  total_aov: number
  total_customers: number
  total_orders: number
  new_customers: number
  returning_customers: number
  /** Net revenue ÷ unique customers in segment (same as Online KPIs). */
  aov_new_customer?: number
  aov_returning_customer?: number
  return_rate_pct: number
  return_rate_new_pct?: number
  return_rate_returning_pct?: number
  cos_pct: number
  cac: number
  /** Online new-customer net revenue ÷ DEMA marketing spend (same formula as summary slide 1). */
  amer?: number
  last_year?: {
    total_aov: number
    total_customers: number
    total_orders: number
    new_customers: number
    returning_customers: number
    aov_new_customer?: number
    aov_returning_customer?: number
    return_rate_pct: number
    return_rate_new_pct?: number
    return_rate_returning_pct?: number
    cos_pct: number
    cac: number
    amer?: number
  } | null
}

export interface AudienceMetricsPerCountryResponse {
  audience_metrics_per_country: Array<{
    week: string
    countries: Record<string, AudienceMetricsCountryData>
  }>
  period_info: { latest_week: string; latest_dates: string }
}

export async function getAudienceMetricsPerCountry(
  week: string,
  numWeeks: number = 8
): Promise<AudienceMetricsPerCountryResponse> {
  const params = new URLSearchParams({ base_week: week, num_weeks: String(numWeeks) })
  const response = await fetch(`${API_BASE_URL}/api/audience-metrics-per-country?${params}`)
  if (!response.ok) {
    const err = await response.json().catch(() => ({}))
    throw new Error(err?.detail || `Failed to fetch audience metrics: ${response.statusText}`)
  }
  return response.json()
}

/** Server-resolved audience chart budget (wide + long-format budget CSV). */
export interface AudienceBudgetSeriesResponse {
  base_week: string
  num_weeks: number
  weeks: Array<{ week: string; budget: Record<string, number> | null }>
  budget_general_error?: string | null
}

export async function getAudienceBudgetSeries(
  baseWeek: string,
  numWeeks: number = 8
): Promise<AudienceBudgetSeriesResponse> {
  const params = new URLSearchParams({ base_week: baseWeek, num_weeks: String(numWeeks) })
  const response = await fetch(`${API_BASE_URL}/api/audience-budget-series?${params}`)
  if (!response.ok) {
    const err = await response.json().catch(() => ({}))
    throw new Error(err?.detail || `Failed to fetch audience budget series: ${response.statusText}`)
  }
  return response.json()
}

/** Verify Supabase connection (env, client, query). Returns exact status for each step – no guesswork. */
export async function verifySupabase(): Promise<{
  env_file_loaded: boolean
  SUPABASE_URL: string
  SUPABASE_SERVICE_ROLE_KEY: string
  key_length: number
  client_created: boolean
  client_error: string | null
  query_ok: boolean
  query_error: string | null
  table_row_count: number | null
}> {
  if (!hasBackend) {
    return {
      env_file_loaded: false,
      SUPABASE_URL: 'not_set',
      SUPABASE_SERVICE_ROLE_KEY: 'not_set',
      key_length: 0,
      client_created: false,
      client_error: 'Backend not configured. Set NEXT_PUBLIC_API_URL for sync and verify.',
      query_ok: false,
      query_error: null,
      table_row_count: null,
    }
  }
  const response = await fetch(`${API_BASE_URL}/api/supabase/verify`)
  if (!response.ok) throw new Error(`Verify failed: ${response.statusText}`)
  return response.json()
}

/** Sync precomputed metrics for the given week to Supabase (backend computes and saves). Call when user clicks "Refresh all data". */
export async function syncSupabase(
  baseWeek: string,
  numWeeks: number = 8
): Promise<{ success: boolean; week: string; row_counts?: Record<string, number>; elapsed_seconds?: number; sync_id?: string; error?: string }> {
  if (!hasBackend) {
    throw new Error(
      'Backend not configured. Sync is only available when NEXT_PUBLIC_API_URL is set. Run sync locally and data will appear in production from Supabase.'
    )
  }
  const response = await fetch(
    `${API_BASE_URL}/api/sync-supabase?week=${encodeURIComponent(baseWeek)}&num_weeks=${numWeeks}`,
    { method: 'POST' }
  )
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(data?.detail || data?.error || `Sync failed: ${response.statusText}`)
  }
  return data
}

export interface DiscountsMonthlyResponse {
  months: string[]
  current: Record<string, Record<string, number>> | null
  last_year: Record<string, Record<string, number>> | null
}

export interface DiscountLevelPointYoY {
  discounted_sales: number
  full_price_sales: number
  total_sales: number
  discounted_share_pct: number
  discount_amount: number
  discount_level_pct: number
}

export interface DiscountLevelPoint extends DiscountLevelPointYoY {
  last_year?: { week: string } & DiscountLevelPointYoY
}

export interface DiscountLevelResponse {
  base_week: string
  num_weeks: number
  markets: string[]
  weeks: Array<{
    week: string
    total: DiscountLevelPoint
    markets: Record<string, DiscountLevelPoint>
  }>
}

export async function getDiscountsSalesYoY(
  baseWeek: string,
  numWeeks: number = 8,
  segment: 'all' | 'new' | 'returning' = 'all',
  expanded: boolean = false
): Promise<any> {
  const response = await fetch(
    `${API_BASE_URL}/api/discounts/sales-yoy?base_week=${baseWeek}&num_weeks=${numWeeks}&segment=${segment}&expanded=${expanded}`
  )
  if (!response.ok) {
    throw new Error(`Failed to fetch Discounts YoY: ${response.statusText}`)
  }
  return response.json()
}

export async function getDiscountsLevel(
  baseWeek: string,
  numWeeks: number = 8
): Promise<DiscountLevelResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/discounts/level?base_week=${baseWeek}&num_weeks=${numWeeks}`
  )
  if (!response.ok) {
    throw new Error(`Failed to fetch discount level: ${response.statusText}`)
  }
  return response.json()
}

export async function getDiscountsMonthlyMetrics(
  baseWeek: string,
  months: number = 12,
  segment: 'all' | 'new' | 'returning' = 'all'
): Promise<DiscountsMonthlyResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/discounts/monthly-metrics?base_week=${baseWeek}&months=${months}&segment=${segment}`
  )
  if (!response.ok) {
    throw new Error(`Failed to fetch Discounts monthly metrics: ${response.statusText}`)
  }
  return response.json()
}

export async function getDiscountsSummaryMetrics(baseWeek: string, includeYtd: boolean = true): Promise<any> {
  const response = await fetch(`${API_BASE_URL}/api/discounts/summary?base_week=${baseWeek}&include_ytd=${includeYtd}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch Discounts summary: ${response.statusText}`)
  }
  return response.json()
}

export async function getDiscountsLtmMetrics(baseWeek: string): Promise<any> {
  const response = await fetch(`${API_BASE_URL}/api/discounts/ltm?base_week=${baseWeek}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch Discounts LTM: ${response.statusText}`)
  }
  return response.json()
}

export async function getDiscountsProducts(
  baseWeek: string,
  numWeeks: number = 8,
  segment: 'all' | 'new' | 'returning' = 'all',
  granularity: 'week' | 'month' = 'week',
  months: number = 12
): Promise<any> {
  const response = await fetch(
    `${API_BASE_URL}/api/discounts/products?base_week=${baseWeek}&num_weeks=${numWeeks}&segment=${segment}&granularity=${granularity}&months=${months}`
  )
  if (!response.ok) {
    throw new Error(`Failed to fetch Discounts products: ${response.statusText}`)
  }
  return response.json()
}

export interface DiscountsCustomersResponse {
  window?: { start?: string; end?: string }
  segments_overall?: Array<{
    segment: string
    customers: number
    orders: number
    revenue: number
    aov: number
    rev_per_customer: number
    orders_per_customer: number
  }>
  first_purchase?: Array<{
    first_segment: string
    customers: number
    repeat_customers: number
    repeat_rate_pct: number
    repeat_full_price: number
    repeat_sale: number
    repeat_mixed: number
    no_repeat: number
  }>
}

export async function getDiscountsCustomers(
  baseWeek: string,
  months: number = 12,
  segment: 'all' | 'new' | 'returning' = 'all'
): Promise<DiscountsCustomersResponse> {
  // Stub: no backend endpoint yet – return empty structure so UI renders
  return { window: {}, segments_overall: [], first_purchase: [] }
}

export async function getCustomerQualityScorecard(
  baseWeek: string,
  windowDays: number = 180,
  asOfDate?: string,
  baselineMonths: number = 24
): Promise<CustomerQualityScorecardResponse> {
  const params = new URLSearchParams({
    base_week: baseWeek,
    window_days: String(windowDays),
    baseline_months: String(baselineMonths),
  })
  if (asOfDate) params.set('as_of_date', asOfDate)
  const response = await fetch(`${API_BASE_URL}/api/customer-quality/scorecard?${params.toString()}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch customer quality scorecard: ${response.statusText}`)
  }
  return response.json()
}

export async function getCustomerQualityDiscountDepth(
  baseWeek: string,
  windowDays: number = 180,
  asOfDate?: string
): Promise<CustomerQualityDiscountDepthResponse> {
  const params = new URLSearchParams({
    base_week: baseWeek,
    window_days: String(windowDays),
  })
  if (asOfDate) params.set('as_of_date', asOfDate)
  const response = await fetch(`${API_BASE_URL}/api/customer-quality/discount-depth?${params.toString()}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch customer quality discount depth: ${response.statusText}`)
  }
  return response.json()
}

export async function getCustomerQualitySegments(
  baseWeek: string,
  windowDays: number = 180,
  asOfDate: string | undefined,
  thresholdLow: number,
  thresholdHigh: number
): Promise<CustomerQualitySegmentsResponse> {
  const params = new URLSearchParams({
    base_week: baseWeek,
    window_days: String(windowDays),
    threshold_low: String(thresholdLow),
    threshold_high: String(thresholdHigh),
  })
  if (asOfDate) params.set('as_of_date', asOfDate)
  const response = await fetch(`${API_BASE_URL}/api/customer-quality/segments?${params.toString()}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch customer quality segments: ${response.statusText}`)
  }
  return response.json()
}

export async function getCustomerQualityPathways(
  baseWeek: string,
  windowDays: number = 180,
  asOfDate: string | undefined,
  thresholdLow: number,
  thresholdHigh: number,
  baselineMonths: number = 24
): Promise<CustomerQualityPathwaysResponse> {
  const params = new URLSearchParams({
    base_week: baseWeek,
    window_days: String(windowDays),
    threshold_low: String(thresholdLow),
    threshold_high: String(thresholdHigh),
    baseline_months: String(baselineMonths),
  })
  if (asOfDate) params.set('as_of_date', asOfDate)
  const response = await fetch(`${API_BASE_URL}/api/customer-quality/pathways?${params.toString()}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch customer quality pathways: ${response.statusText}`)
  }
  return response.json()
}

// Discounts Categories API functions
export async function getDiscountsCategories(
  baseWeek: string,
  isoWeek: string,
  segment: string = 'all'
): Promise<any> {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), 30000) // 30 second timeout
  
  try {
    const response = await fetch(
      `${API_BASE_URL}/api/discounts/categories?base_week=${baseWeek}&iso_week=${isoWeek}&segment=${segment}`,
      { signal: controller.signal }
    )
    clearTimeout(timeoutId)
    
    if (!response.ok) {
      throw new Error(`Failed to fetch Discounts Categories: ${response.statusText}`)
    }
    return response.json()
  } catch (error: any) {
    clearTimeout(timeoutId)
    if (error.name === 'AbortError' || error.name === 'TimeoutError') {
      throw new Error('Request timeout. The calculation is taking longer than expected.')
    }
    throw error
  }
}

export async function getDiscountsCategoriesMonthly(
  baseWeek: string,
  month: string,
  segment: string = 'all'
): Promise<any> {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), 30000) // 30 second timeout
  
  try {
    const response = await fetch(
      `${API_BASE_URL}/api/discounts/categories-monthly?base_week=${baseWeek}&month=${month}&segment=${segment}`,
      { signal: controller.signal }
    )
    clearTimeout(timeoutId)
    
    if (!response.ok) {
      throw new Error(`Failed to fetch Discounts Categories Monthly: ${response.statusText}`)
    }
    return response.json()
  } catch (error: any) {
    clearTimeout(timeoutId)
    if (error.name === 'AbortError' || error.name === 'TimeoutError') {
      throw new Error('Request timeout. The calculation is taking longer than expected.')
    }
    throw error
  }
}

export async function getDiscountsCategorySeries(
  baseWeek: string,
  category: string,
  segment: string = 'all',
  expanded: boolean = false
): Promise<any> {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), 30000) // 30 second timeout
  
  try {
    const response = await fetch(
      `${API_BASE_URL}/api/discounts/category-series?base_week=${baseWeek}&category=${category}&segment=${segment}&expanded=${expanded}`,
      { signal: controller.signal }
    )
    clearTimeout(timeoutId)
    
    if (!response.ok) {
      throw new Error(`Failed to fetch Discounts Category Series: ${response.statusText}`)
    }
    return response.json()
  } catch (error: any) {
    clearTimeout(timeoutId)
    if (error.name === 'AbortError' || error.name === 'TimeoutError') {
      throw new Error('Request timeout. The calculation is taking longer than expected.')
    }
    throw error
  }
}

export async function getDiscountsCategoryCountries(
  baseWeek: string,
  isoWeek: string,
  category: string,
  segment: string = 'all'
): Promise<any> {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), 30000) // 30 second timeout
  
  try {
    const response = await fetch(
      `${API_BASE_URL}/api/discounts/category-countries?base_week=${baseWeek}&iso_week=${isoWeek}&category=${category}&segment=${segment}`,
      { signal: controller.signal }
    )
    clearTimeout(timeoutId)
    
    if (!response.ok) {
      throw new Error(`Failed to fetch Discounts Category Countries: ${response.statusText}`)
    }
    return response.json()
  } catch (error: any) {
    clearTimeout(timeoutId)
    if (error.name === 'AbortError' || error.name === 'TimeoutError') {
      throw new Error('Request timeout. The calculation is taking longer than expected.')
    }
    throw error
  }
}

export async function getDiscountsCategoryCountriesMonthly(
  baseWeek: string,
  month: string,
  category: string,
  segment: string = 'all'
): Promise<any> {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), 30000) // 30 second timeout
  
  try {
    const response = await fetch(
      `${API_BASE_URL}/api/discounts/category-countries-monthly?base_week=${baseWeek}&month=${month}&category=${category}&segment=${segment}`,
      { signal: controller.signal }
    )
    clearTimeout(timeoutId)
    
    if (!response.ok) {
      throw new Error(`Failed to fetch Discounts Category Countries Monthly: ${response.statusText}`)
    }
    return response.json()
  } catch (error: any) {
    clearTimeout(timeoutId)
    if (error.name === 'AbortError' || error.name === 'TimeoutError') {
      throw new Error('Request timeout. The calculation is taking longer than expected.')
    }
    throw error
  }
}
