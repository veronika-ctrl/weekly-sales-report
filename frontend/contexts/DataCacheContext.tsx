'use client'

import { createContext, useContext, useState, useEffect, useCallback, useRef, ReactNode } from 'react'
import { 
  hasBackend,
  getPeriods, 
  getTable1Metrics, 
  getTopMarkets, 
  getOnlineKPIs,
  getContribution,
  getGenderSales,
  getMenCategorySales,
  getWomenCategorySales,
  getSessionsPerCountry,
  getConversionPerCountry,
  getNewCustomersPerCountry,
  getReturningCustomersPerCountry,
  getAOVNewCustomersPerCountry,
  getAOVReturningCustomersPerCountry,
  getMarketingSpendPerCountry,
  getNCACPerCountry,
  getContributionNewPerCountry,
  getContributionNewTotalPerCountry,
  getContributionReturningPerCountry,
  getContributionReturningTotalPerCountry,
  getTotalContributionPerCountry,
  getBatchMetrics,
  getBudgetGeneral,
  getActualsGeneral,
  getBudgetRaw,
  getActualsMarkets,
  getActualsMarketsDetailed,
  type PeriodsResponse,
  type MetricsResponse,
  type MarketsResponse,
  type OnlineKPIsResponse,
  type ContributionResponse,
  type GenderSalesResponse,
  type MenCategorySalesResponse,
  type WomenCategorySalesResponse,
  type SessionsPerCountryResponse,
  type ConversionPerCountryResponse,
  type NewCustomersPerCountryResponse,
  type ReturningCustomersPerCountryResponse,
  type AOVNewCustomersPerCountryResponse,
  type AOVReturningCustomersPerCountryResponse,
  type MarketingSpendPerCountryResponse,
  type nCACPerCountryResponse,
  type ContributionNewPerCountryResponse,
  type ContributionNewTotalPerCountryResponse,
  type ContributionReturningPerCountryResponse,
  type ContributionReturningTotalPerCountryResponse,
  type TotalContributionPerCountryResponse,
  type BatchMetricsResponse,
  type BudgetGeneralResponse,
  type ActualsGeneralResponse
} from '@/lib/api'

interface LoadingProgress {
  step: 'periods' | 'metrics' | 'markets' | 'kpis' | 'contribution' | 'gender_sales' | 'men_category_sales' | 'women_category_sales' | 'sessions_per_country' | 'conversion_per_country' | 'new_customers_per_country' | 'returning_customers_per_country' | 'aov_new_customers_per_country' | 'aov_returning_customers_per_country' | 'marketing_spend_per_country' | 'ncac_per_country' | 'contribution_new_per_country' | 'contribution_new_total_per_country' | 'contribution_returning_per_country' | 'contribution_returning_total_per_country' | 'total_contribution_per_country' | 'complete' | 'sync'
  stepNumber: number
  totalSteps: number
  message: string
  percentage: number
  /** Supabase status during refresh – e.g. "Sync: OK" or "Read: Failed (using API)" */
  supabaseStatus?: string
}

interface CacheData {
  periods: PeriodsResponse | null
  metrics: MetricsResponse | null
  markets: MarketsResponse | null
  kpis: OnlineKPIsResponse | null
  contribution: ContributionResponse | null
  gender_sales: GenderSalesResponse | null
  men_category_sales: MenCategorySalesResponse | null
  women_category_sales: WomenCategorySalesResponse | null
  sessions_per_country: SessionsPerCountryResponse | null
  conversion_per_country: ConversionPerCountryResponse | null
  new_customers_per_country: NewCustomersPerCountryResponse | null
  returning_customers_per_country: ReturningCustomersPerCountryResponse | null
  aov_new_customers_per_country: AOVNewCustomersPerCountryResponse | null
  aov_returning_customers_per_country: AOVReturningCustomersPerCountryResponse | null
  marketing_spend_per_country: MarketingSpendPerCountryResponse | null
  ncac_per_country: nCACPerCountryResponse | null
  contribution_new_per_country: ContributionNewPerCountryResponse | null
  contribution_new_total_per_country: ContributionNewTotalPerCountryResponse | null
  contribution_returning_per_country: ContributionReturningPerCountryResponse | null
  contribution_returning_total_per_country: ContributionReturningTotalPerCountryResponse | null
  total_contribution_per_country: TotalContributionPerCountryResponse | null
  budget_general?: BudgetGeneralResponse | null
  actuals_general?: ActualsGeneralResponse | null
  budget_raw?: any | null
  actuals_markets?: any | null
  actuals_markets_detailed?: any | null
  timestamp: number
}

interface DataCacheContextType {
  periods: PeriodsResponse | null
  metrics: MetricsResponse | null
  markets: MarketsResponse | null
  kpis: OnlineKPIsResponse | null
  contribution: ContributionResponse | null
  gender_sales: GenderSalesResponse | null
  men_category_sales: MenCategorySalesResponse | null
  women_category_sales: WomenCategorySalesResponse | null
  sessions_per_country: SessionsPerCountryResponse | null
  conversion_per_country: ConversionPerCountryResponse | null
  new_customers_per_country: NewCustomersPerCountryResponse | null
  returning_customers_per_country: ReturningCustomersPerCountryResponse | null
  aov_new_customers_per_country: AOVNewCustomersPerCountryResponse | null
  aov_returning_customers_per_country: AOVReturningCustomersPerCountryResponse | null
  marketing_spend_per_country: MarketingSpendPerCountryResponse | null
  ncac_per_country: nCACPerCountryResponse | null
  contribution_new_per_country: ContributionNewPerCountryResponse | null
  contribution_new_total_per_country: ContributionNewTotalPerCountryResponse | null
  contribution_returning_per_country: ContributionReturningPerCountryResponse | null
  contribution_returning_total_per_country: ContributionReturningTotalPerCountryResponse | null
  total_contribution_per_country: TotalContributionPerCountryResponse | null
  budget_general: BudgetGeneralResponse | null
  actuals_general: ActualsGeneralResponse | null
  budget_raw: any | null
  actuals_markets: any | null
  actuals_markets_detailed: any | null
  loading: boolean
  error: string | null
  loadingProgress: LoadingProgress | null
  loadAllData: (baseWeek: string, forceRefresh?: boolean) => Promise<void>
  refreshData: () => Promise<void>
  clearCache: () => void
  baseWeek: string
  setBaseWeek: (week: string) => void
  isDataReady: boolean
  /** True after the restore-from-URL/localStorage effect has run; use to avoid hydration mismatch. */
  hasRestoredWeek: boolean
}

const DataCacheContext = createContext<DataCacheContextType | undefined>(undefined)

const CACHE_EXPIRY = 24 * 60 * 60 * 1000 // 24 hours (increased since Supabase is primary)
const SUPABASE_DISABLED = process.env.NEXT_PUBLIC_DISABLE_SUPABASE === 'true'

export function DataCacheProvider({ children }: { children: ReactNode }) {
  const [periods, setPeriods] = useState<PeriodsResponse | null>(null)
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null)
  const [markets, setMarkets] = useState<MarketsResponse | null>(null)
  const [kpis, setKpis] = useState<OnlineKPIsResponse | null>(null)
  const [contribution, setContribution] = useState<ContributionResponse | null>(null)
  const [gender_sales, setGender_sales] = useState<GenderSalesResponse | null>(null)
  const [men_category_sales, setMen_category_sales] = useState<MenCategorySalesResponse | null>(null)
  const [women_category_sales, setWomen_category_sales] = useState<WomenCategorySalesResponse | null>(null)
  const [sessions_per_country, setSessions_per_country] = useState<SessionsPerCountryResponse | null>(null)
  const [conversion_per_country, setConversion_per_country] = useState<ConversionPerCountryResponse | null>(null)
  const [new_customers_per_country, setNew_customers_per_country] = useState<NewCustomersPerCountryResponse | null>(null)
  const [returning_customers_per_country, setReturning_customers_per_country] = useState<ReturningCustomersPerCountryResponse | null>(null)
  const [aov_new_customers_per_country, setAov_new_customers_per_country] = useState<AOVNewCustomersPerCountryResponse | null>(null)
  const [aov_returning_customers_per_country, setAov_returning_customers_per_country] = useState<AOVReturningCustomersPerCountryResponse | null>(null)
  const [marketing_spend_per_country, setMarketing_spend_per_country] = useState<MarketingSpendPerCountryResponse | null>(null)
  const [ncac_per_country, setNcac_per_country] = useState<nCACPerCountryResponse | null>(null)
  const [contribution_new_per_country, setContribution_new_per_country] = useState<ContributionNewPerCountryResponse | null>(null)
  const [contribution_new_total_per_country, setContribution_new_total_per_country] = useState<ContributionNewTotalPerCountryResponse | null>(null)
  const [contribution_returning_per_country, setContribution_returning_per_country] = useState<ContributionReturningPerCountryResponse | null>(null)
  const [contribution_returning_total_per_country, setContribution_returning_total_per_country] = useState<ContributionReturningTotalPerCountryResponse | null>(null)
  const [total_contribution_per_country, setTotal_contribution_per_country] = useState<TotalContributionPerCountryResponse | null>(null)
  const [budget_general, setBudget_general] = useState<BudgetGeneralResponse | null>(null)
  const [actuals_general, setActuals_general] = useState<ActualsGeneralResponse | null>(null)
  const [budget_raw, setBudget_raw] = useState<any | null>(null)
  const [actuals_markets, setActuals_markets] = useState<any | null>(null)
  const [actuals_markets_detailed, setActuals_markets_detailed] = useState<any | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loadingProgress, setLoadingProgress] = useState<LoadingProgress | null>(null)
  const [baseWeek, setBaseWeekInternal] = useState<string>('')
  /** False until the restore-from-URL/localStorage effect has run; avoids hydration mismatch (server has no localStorage). */
  const [hasRestoredWeek, setHasRestoredWeek] = useState(false)
  const [isDataReady, setIsDataReady] = useState(false)
  /** Ref to invalidate in-flight passive Supabase loads when baseWeek changes or a new load starts (so stale load cannot overwrite state). */
  const passiveLoadWeekRef = useRef<string | null>(null)
  
  // Wrap setBaseWeek to also save to localStorage (empty string = no week selected)
  const setBaseWeek = useCallback((week: string) => {
    setBaseWeekInternal(week)
    if (week) localStorage.setItem('selected_week', week)
    else localStorage.removeItem('selected_week')
  }, [])

  // Bump cache version to invalidate stale data after backend calc changes
  const CACHE_VERSION = 'v3'
  const getCacheKey = (week: string) => `dashboard_cache_${CACHE_VERSION}_${week}`

  const getCachedData = (week: string): CacheData | null => {
    try {
      const cached = localStorage.getItem(getCacheKey(week))
      if (!cached) return null
      
      const parsed: CacheData = JSON.parse(cached)
      const cacheAge = Date.now() - parsed.timestamp
      
      if (cacheAge > CACHE_EXPIRY) {
        localStorage.removeItem(getCacheKey(week))
        return null
      }
      
      return parsed
    } catch (err) {
      console.warn('Failed to load cache:', err)
      return null
    }
  }

  const saveCache = (week: string, data: CacheData) => {
    try {
      localStorage.setItem(getCacheKey(week), JSON.stringify(data))
    } catch (err) {
      console.warn('Failed to save cache:', err)
    }
  }

  const loadAllData = useCallback(async (week: string, forceRefresh = false) => {
    if (!week) return
    setError(null)

    // Check cache first
    if (!forceRefresh) {
      const cached = getCachedData(week)
      if (cached) {
        setPeriods(cached.periods)
        setMetrics(cached.metrics)
        setMarkets(cached.markets)
        setKpis(cached.kpis)
        setContribution(cached.contribution)
        setGender_sales(cached.gender_sales)
        setMen_category_sales(cached.men_category_sales)
        setWomen_category_sales(cached.women_category_sales)
        setSessions_per_country(cached.sessions_per_country)
        setConversion_per_country(cached.conversion_per_country)
        setNew_customers_per_country(cached.new_customers_per_country)
        setReturning_customers_per_country(cached.returning_customers_per_country)
        setAov_new_customers_per_country(cached.aov_new_customers_per_country)
        setAov_returning_customers_per_country(cached.aov_returning_customers_per_country)
        setMarketing_spend_per_country(cached.marketing_spend_per_country)
        setNcac_per_country(cached.ncac_per_country)
        setContribution_new_per_country(cached.contribution_new_per_country)
        setContribution_new_total_per_country(cached.contribution_new_total_per_country)
        setContribution_returning_per_country(cached.contribution_returning_per_country)
        setContribution_returning_total_per_country(cached.contribution_returning_total_per_country)
      setTotal_contribution_per_country(cached.total_contribution_per_country)
      setBudget_general(cached.budget_general ?? null)
      setActuals_general(cached.actuals_general ?? null)
      setBudget_raw(cached.budget_raw ?? null)
      // optional
      // @ts-ignore
      setActuals_markets(cached.actuals_markets ?? null)
      // @ts-ignore
      setActuals_markets_detailed(cached.actuals_markets_detailed ?? null)
      setIsDataReady(true)
      return
    }
  }

    setLoading(true)

    try {
      // When user clicks "Refresh all data": sync first so the selected week is computed and saved to Supabase
      if (forceRefresh && !SUPABASE_DISABLED) {
        if (hasBackend) {
          setLoadingProgress({
            step: 'sync',
            stepNumber: 0,
            totalSteps: 27,
            message: 'Checking Supabase – syncing data...',
            percentage: 0,
            supabaseStatus: 'Supabase: Connecting...'
          })
          try {
            const { syncSupabase } = await import('@/lib/api')
            await syncSupabase(week, 8)
            setLoadingProgress({
              step: 'sync',
              stepNumber: 0,
              totalSteps: 27,
              message: 'Supabase sync OK – data saved.',
              percentage: 2,
              supabaseStatus: 'Supabase sync: OK'
            })
            console.log(`✅ Supabase sync completed for week ${week}`)
          } catch (syncErr: any) {
            const backendMessage = syncErr?.message || String(syncErr)
            setLoadingProgress({
              step: 'sync',
              stepNumber: 0,
              totalSteps: 27,
              message: 'Supabase sync failed – using API.',
              percentage: 2,
              supabaseStatus: `Supabase sync: Failed – ${backendMessage}`
            })
            console.warn('Supabase sync failed (continuing with load):', syncErr)
          }
        } else {
          setLoadingProgress({
            step: 'sync',
            stepNumber: 0,
            totalSteps: 27,
            message: 'No backend – reading from Supabase only.',
            percentage: 2,
            supabaseStatus: 'Reading from Supabase only (no sync)'
          })
        }
      } else if (forceRefresh && SUPABASE_DISABLED) {
        setLoadingProgress({
          step: 'sync',
          stepNumber: 0,
          totalSteps: 27,
          message: 'Supabase disabled – refreshing via API only.',
          percentage: 2,
          supabaseStatus: 'Supabase: Disabled (API only)'
        })
      }

      // Load from Supabase (or API if no data) – after refresh, Supabase has the just-synced week
      if (!SUPABASE_DISABLED) {
        setLoadingProgress(prev => ({
          step: 'metrics',
          stepNumber: 1,
          totalSteps: 27,
          message: 'Loading metrics from Supabase...',
          percentage: 3,
          supabaseStatus: prev?.supabaseStatus
        }))
      }

      let batchMode = false
      let batchData: any = null

      if (!SUPABASE_DISABLED) {
        try {
          const { loadWeeklyReportMetricsFromSupabase } = await import('@/lib/supabase-queries')
          const { isSupabaseAvailable } = await import('@/lib/supabase')

          if (!isSupabaseAvailable()) {
            setLoadingProgress(prev => ({
              step: 'metrics',
              stepNumber: 1,
              totalSteps: 27,
              message: 'Supabase inte konfigurerad.',
              percentage: 5,
              supabaseStatus: 'Supabase: Lägg till NEXT_PUBLIC_SUPABASE_URL och NEXT_PUBLIC_SUPABASE_ANON_KEY'
            }))
            setError('Supabase är inte konfigurerad. Lägg till NEXT_PUBLIC_SUPABASE_URL och NEXT_PUBLIC_SUPABASE_ANON_KEY i miljövariablerna.')
          } else {
            const supabaseData = await loadWeeklyReportMetricsFromSupabase(week)
            if (supabaseData) {
              batchData = supabaseData
              batchMode = true
              setLoadingProgress(prev => ({
                step: 'metrics',
                stepNumber: 1,
                totalSteps: 27,
                message: 'Loaded from Supabase.',
                percentage: 8,
                supabaseStatus: prev?.supabaseStatus ? `${prev.supabaseStatus} · Read: OK` : 'Supabase read: OK'
              }))
              console.log(`✅ Loaded all metrics from Supabase for ${week}`)
            } else {
              setLoadingProgress(prev => ({
                step: 'metrics',
                stepNumber: 1,
                totalSteps: 27,
                message: 'Ingen data för denna vecka i Supabase.',
                percentage: 5,
                supabaseStatus: prev?.supabaseStatus ? `${prev.supabaseStatus} · No data` : 'Supabase read: No data'
              }))
              // Don't set error – "no data" is shown as friendly empty state on report pages
            }
          }
        } catch (supabaseError) {
          setLoadingProgress(prev => ({
            step: 'metrics',
            stepNumber: 1,
            totalSteps: 27,
            message: 'Kunde inte läsa från Supabase.',
            percentage: 5,
            supabaseStatus: prev?.supabaseStatus ? `${prev.supabaseStatus} · Read: Failed` : 'Supabase read: Failed'
          }))
          setError('Kunde inte läsa från Supabase. Kontrollera nätverk och att projekt-URL samt anon-nyckel är korrekta.')
          console.debug('Supabase read error:', supabaseError)
        }
      } else {
        setLoadingProgress(prev => ({
          step: 'metrics',
          stepNumber: 1,
          totalSteps: 27,
          message: 'Supabase disabled – loading from API...',
          percentage: 5,
          supabaseStatus: prev?.supabaseStatus ?? 'Supabase: Disabled (API only)'
        }))
      }

      // Only load from API when Supabase is disabled (API-only mode)
      if (!batchData && SUPABASE_DISABLED) {
        setLoadingProgress(prev => ({
          step: 'metrics',
          stepNumber: 1,
          totalSteps: 27,
          message: 'Loading all metrics from API...',
          percentage: 5,
          supabaseStatus: prev?.supabaseStatus
        }))
        try {
          batchData = await getBatchMetrics(week, 8)
          batchMode = true
          console.log(`📦 Loaded all metrics from API for ${week}`)
        } catch (batchError) {
          console.warn('Batch endpoint failed, falling back to individual calls:', batchError)
          batchMode = false
        }
      }

      // Supabase is primary but no data for this week – error already set above; load periods only and exit
      if (!batchData && !SUPABASE_DISABLED) {
        try {
          const periodsData = await getPeriods(week)
          setPeriods(periodsData)
        } catch (_) {}
        setLoading(false)
        setLoadingProgress(null)
        return
      }
      
      // Set all data from batch response (from Supabase or API)
      let periodsData: PeriodsResponse | null = null
      let marketsToSave = batchData?.markets ?? null
      if (batchData && batchMode) {
        // Always load periods from API (Supabase doesn't store periods, they're calculated)
        // This ensures periods are always available even when data comes from Supabase
        try {
          periodsData = await getPeriods(week)
          setPeriods(periodsData)
        } catch (periodsError) {
          console.warn('Failed to load periods:', periodsError)
          // Fallback to periods from batchData if available
          if (batchData.periods) {
            periodsData = batchData.periods
            setPeriods(batchData.periods)
          }
        }
        setMetrics(batchData.metrics)
        setMarkets(batchData.markets)
        marketsToSave = batchData.markets
        // Refresh markets with recalculate=true so Y/Y for last-year weeks (2024-50, 2024-51, 2024-52) is filled
        try {
          const freshMarkets = await getTopMarkets(week, 8, true)
          setMarkets(freshMarkets)
          marketsToSave = freshMarkets
        } catch (_) {
          // keep batchData.markets
        }
        setKpis(batchData.kpis)
        setContribution(batchData.contribution)
        setGender_sales(batchData.gender_sales)
        setMen_category_sales(batchData.men_category_sales)
        setWomen_category_sales(batchData.women_category_sales)
        setSessions_per_country(batchData.sessions_per_country)
        setConversion_per_country(batchData.conversion_per_country)
        setNew_customers_per_country(batchData.new_customers_per_country)
        setReturning_customers_per_country(batchData.returning_customers_per_country)
        setAov_new_customers_per_country(batchData.aov_new_customers_per_country)
        setAov_returning_customers_per_country(batchData.aov_returning_customers_per_country)
        setMarketing_spend_per_country(batchData.marketing_spend_per_country)
        setNcac_per_country(batchData.ncac_per_country)
        setContribution_new_per_country(batchData.contribution_new_per_country)
        setContribution_new_total_per_country(batchData.contribution_new_total_per_country)
        setContribution_returning_per_country(batchData.contribution_returning_per_country)
        setContribution_returning_total_per_country(batchData.contribution_returning_total_per_country)
        setTotal_contribution_per_country(batchData.total_contribution_per_country)
      }
      
      // Budget-related steps (show progress) - prefer Supabase to avoid API 404 when data is synced
      if (batchMode && batchData) {
        setLoadingProgress({ step: 'metrics', stepNumber: 22, totalSteps: 27, message: 'Loading budget general...', percentage: 85 })
        let budgetGeneralData: BudgetGeneralResponse | null = null
        let actualsGeneralData: ActualsGeneralResponse | null = null
        try {
          const { loadBudgetGeneralFromSupabase } = await import('@/lib/supabase-queries')
          const fromSupabase = await loadBudgetGeneralFromSupabase(week)
          if (fromSupabase.budget) {
            budgetGeneralData = fromSupabase.budget
            setBudget_general(budgetGeneralData)
          }
          if (fromSupabase.actuals) {
            actualsGeneralData = fromSupabase.actuals
            setActuals_general(actualsGeneralData)
          }
        } catch (_) { /* Supabase budget load failed, fall back to API */ }
        if (budgetGeneralData == null) {
          try {
            budgetGeneralData = await getBudgetGeneral(week)
            setBudget_general(budgetGeneralData)
          } catch (_) {
            budgetGeneralData = null
          }
        }
        setLoadingProgress({ step: 'metrics', stepNumber: 23, totalSteps: 27, message: 'Loading actuals general...', percentage: 88 })
        if (actualsGeneralData == null) {
          try {
            actualsGeneralData = await getActualsGeneral(week)
            setActuals_general(actualsGeneralData)
          } catch (_) {
            actualsGeneralData = null
          }
        }
        // Budget raw (for Markets prototype)
        setLoadingProgress({ step: 'metrics', stepNumber: 24, totalSteps: 27, message: 'Loading budget raw (markets)...', percentage: 91 })
        let budgetRawData: any | null = null
        try {
          budgetRawData = await getBudgetRaw(week)
          setBudget_raw(budgetRawData)
        } catch (e) {
          budgetRawData = null
        }
        // Actuals per market
        setLoadingProgress({ step: 'metrics', stepNumber: 25, totalSteps: 27, message: 'Loading actuals markets...', percentage: 94 })
        let actualsMarketsData: any | null = null
        try {
          actualsMarketsData = await getActualsMarkets(week)
          setActuals_markets(actualsMarketsData)
        } catch (e) {
          actualsMarketsData = null
        }
        // Actuals per market detailed
        setLoadingProgress({ step: 'metrics', stepNumber: 26, totalSteps: 27, message: 'Loading actuals markets detailed...', percentage: 97 })
        let actualsMarketsDetailedData: any | null = null
        try {
          actualsMarketsDetailedData = await getActualsMarketsDetailed(week)
          setActuals_markets_detailed(actualsMarketsDetailedData)
        } catch (e) {
          actualsMarketsDetailedData = null
        }

        setLoadingProgress({ 
          step: 'complete', 
          stepNumber: 27, 
          totalSteps: 27, 
          message: 'Complete!', 
          percentage: 100 
        })

        // Save to cache (marketsToSave has fresh Y/Y from recalculate=true when available)
        saveCache(week, {
          periods: periodsData || batchData.periods, // Use periodsData from API if available, otherwise fallback to batchData.periods
          metrics: batchData.metrics,
          markets: marketsToSave ?? batchData.markets,
          kpis: batchData.kpis,
          contribution: batchData.contribution,
          gender_sales: batchData.gender_sales,
          men_category_sales: batchData.men_category_sales,
          women_category_sales: batchData.women_category_sales,
          sessions_per_country: batchData.sessions_per_country,
          conversion_per_country: batchData.conversion_per_country,
          new_customers_per_country: batchData.new_customers_per_country,
          returning_customers_per_country: batchData.returning_customers_per_country,
          aov_new_customers_per_country: batchData.aov_new_customers_per_country,
          aov_returning_customers_per_country: batchData.aov_returning_customers_per_country,
          marketing_spend_per_country: batchData.marketing_spend_per_country,
          ncac_per_country: batchData.ncac_per_country,
          contribution_new_per_country: batchData.contribution_new_per_country,
          contribution_new_total_per_country: batchData.contribution_new_total_per_country,
          contribution_returning_per_country: batchData.contribution_returning_per_country,
          contribution_returning_total_per_country: batchData.contribution_returning_total_per_country,
          total_contribution_per_country: batchData.total_contribution_per_country,
          budget_general: budgetGeneralData,
          actuals_general: actualsGeneralData,
          budget_raw: budgetRawData,
          actuals_markets: actualsMarketsData,
          actuals_markets_detailed: actualsMarketsDetailedData,
          timestamp: Date.now()
        })
        
        setLoading(false)
        return
      }
      
      // Individual calls (fallback or primary if batch disabled)
      if (!batchMode) {
        // Step 1: Load periods
      setLoadingProgress({ 
        step: 'periods', 
        stepNumber: 1, 
        totalSteps: 26, 
        message: 'Loading periods...', 
        percentage: 0 
      })
      const periodsData = await getPeriods(week)
      setPeriods(periodsData)

      // Step 2: Load metrics
      setLoadingProgress({ 
        step: 'metrics', 
        stepNumber: 2, 
        totalSteps: 26, 
        message: 'Loading summary metrics...', 
        percentage: 12 
      })
      const metricsData = await getTable1Metrics(week, ['actual', 'last_week', 'last_year', 'year_2023'], true)
      setMetrics(metricsData)

      // Step 3: Load markets
      setLoadingProgress({ 
        step: 'markets', 
        stepNumber: 3, 
        totalSteps: 26, 
        message: 'Loading top markets data...', 
        percentage: 25 
      })
      let marketsData: MarketsResponse
      try {
        marketsData = await getTopMarkets(week, 8, true)
      } catch {
        marketsData = { markets: [], period_info: { latest_week: week, latest_dates: '' } }
      }
      setMarkets(marketsData)

      // Step 4: Load KPIs
      setLoadingProgress({ 
        step: 'kpis', 
        stepNumber: 4, 
        totalSteps: 26, 
        message: 'Loading online KPIs...', 
        percentage: 37 
      })
      const kpisData = await getOnlineKPIs(week, 8)
      setKpis(kpisData)

      // Step 5: Load Contribution
      setLoadingProgress({ 
        step: 'contribution', 
        stepNumber: 5, 
        totalSteps: 26, 
        message: 'Loading contribution metrics...', 
        percentage: 50 
      })
      const contributionData = await getContribution(week, 8)
      setContribution(contributionData)

      // Step 6: Load Gender Sales
      setLoadingProgress({ 
        step: 'gender_sales', 
        stepNumber: 6, 
        totalSteps: 26, 
        message: 'Loading gender sales data...', 
        percentage: 62 
      })
      const genderSalesData = await getGenderSales(week, 8)
      setGender_sales(genderSalesData)

      // Step 7: Load Men Category Sales
      setLoadingProgress({ 
        step: 'men_category_sales', 
        stepNumber: 7, 
        totalSteps: 26, 
        message: 'Loading men category sales...', 
        percentage: 75 
      })
      const menCategorySalesData = await getMenCategorySales(week, 8)
      setMen_category_sales(menCategorySalesData)

      // Step 8: Load Women Category Sales
      setLoadingProgress({ 
        step: 'women_category_sales', 
        stepNumber: 8, 
        totalSteps: 26, 
        message: 'Loading women category sales...', 
        percentage: 87 
      })
      const womenCategorySalesData = await getWomenCategorySales(week, 8)
      setWomen_category_sales(womenCategorySalesData)

      // Step 9: Load Sessions per Country
      setLoadingProgress({ 
        step: 'sessions_per_country', 
        stepNumber: 9, 
        totalSteps: 26, 
        message: 'Loading sessions per country...', 
        percentage: 90 
      })
      const sessionsPerCountryData = await getSessionsPerCountry(week, 8)
      setSessions_per_country(sessionsPerCountryData)

      // Step 10: Load Conversion per Country
      setLoadingProgress({ 
        step: 'conversion_per_country', 
        stepNumber: 10, 
        totalSteps: 26, 
        message: 'Loading conversion per country...', 
        percentage: 90 
      })
      const conversionPerCountryData = await getConversionPerCountry(week, 8)
      setConversion_per_country(conversionPerCountryData)

      // Step 11: Load New Customers per Country
      setLoadingProgress({ 
        step: 'new_customers_per_country', 
        stepNumber: 11, 
        totalSteps: 26, 
        message: 'Loading new customers per country...', 
        percentage: 92 
      })
      const newCustomersPerCountryData = await getNewCustomersPerCountry(week, 8)
      setNew_customers_per_country(newCustomersPerCountryData)

      // Step 12: Load Returning Customers per Country
      setLoadingProgress({ 
        step: 'returning_customers_per_country', 
        stepNumber: 12, 
        totalSteps: 26, 
        message: 'Loading returning customers per country...', 
        percentage: 92 
      })
      const returningCustomersPerCountryData = await getReturningCustomersPerCountry(week, 8)
      setReturning_customers_per_country(returningCustomersPerCountryData)

      // Step 13: Load AOV New Customers per Country
      setLoadingProgress({ 
        step: 'aov_new_customers_per_country', 
        stepNumber: 13, 
        totalSteps: 26, 
        message: 'Loading AOV new customers per country...', 
        percentage: 93 
      })
      const aovNewCustomersPerCountryData = await getAOVNewCustomersPerCountry(week, 8)
      setAov_new_customers_per_country(aovNewCustomersPerCountryData)

      // Step 14: Load AOV Returning Customers per Country
      setLoadingProgress({ 
        step: 'aov_returning_customers_per_country', 
        stepNumber: 14, 
        totalSteps: 26, 
        message: 'Loading AOV returning customers per country...', 
        percentage: 93 
      })
      const aovReturningCustomersPerCountryData = await getAOVReturningCustomersPerCountry(week, 8)
      setAov_returning_customers_per_country(aovReturningCustomersPerCountryData)

      // Step 15: Load Marketing Spend per Country
      setLoadingProgress({ 
        step: 'marketing_spend_per_country', 
        stepNumber: 15, 
        totalSteps: 26, 
        message: 'Loading marketing spend per country...', 
        percentage: 94 
      })
      const marketingSpendPerCountryData = await getMarketingSpendPerCountry(week, 8)
      setMarketing_spend_per_country(marketingSpendPerCountryData)

      // Step 16: Load nCAC per Country
      setLoadingProgress({ 
        step: 'ncac_per_country', 
        stepNumber: 16, 
        totalSteps: 26, 
        message: 'Loading nCAC per country...', 
        percentage: 94 
      })
      const ncacPerCountryData = await getNCACPerCountry(week, 8)
      setNcac_per_country(ncacPerCountryData)

      // Step 17: Load Contribution New per Country
      setLoadingProgress({ 
        step: 'contribution_new_per_country', 
        stepNumber: 17, 
        totalSteps: 26, 
        message: 'Loading contribution per new customer per country...', 
        percentage: 94 
      })
      const contributionNewPerCountryData = await getContributionNewPerCountry(week, 8)
      setContribution_new_per_country(contributionNewPerCountryData)

      // Step 18: Load Contribution New Total per Country
      setLoadingProgress({ 
        step: 'contribution_new_total_per_country', 
        stepNumber: 18, 
        totalSteps: 26, 
        message: 'Loading total contribution per country...', 
        percentage: 90 
      })
      const contributionNewTotalPerCountryData = await getContributionNewTotalPerCountry(week, 8)
      setContribution_new_total_per_country(contributionNewTotalPerCountryData)

      // Step 19: Load Contribution Returning per Country
      setLoadingProgress({ 
        step: 'contribution_returning_per_country', 
        stepNumber: 19, 
        totalSteps: 26, 
        message: 'Loading contribution per returning customer per country...', 
        percentage: 95 
      })
      const contributionReturningPerCountryData = await getContributionReturningPerCountry(week, 8)
      setContribution_returning_per_country(contributionReturningPerCountryData)

      // Step 20: Load Contribution Returning Total per Country
      setLoadingProgress({ 
        step: 'contribution_returning_total_per_country', 
        stepNumber: 20, 
        totalSteps: 26, 
        message: 'Loading total contribution per returning customers by country...', 
        percentage: 95 
      })
      const contributionReturningTotalPerCountryData = await getContributionReturningTotalPerCountry(week, 8)
      setContribution_returning_total_per_country(contributionReturningTotalPerCountryData)

      // Step 21: Load Total Contribution per Country
      setLoadingProgress({ 
        step: 'total_contribution_per_country', 
        stepNumber: 21, 
        totalSteps: 26, 
        message: 'Loading total contribution for all customers by country...', 
        percentage: 97 
      })
      const totalContributionPerCountryData = await getTotalContributionPerCountry(week, 8)
      setTotal_contribution_per_country(totalContributionPerCountryData)

      // Budget-related progress steps
      // Skip Supabase sync for individual calls mode - data is already loaded
      setLoadingProgress({ step: 'metrics', stepNumber: 22, totalSteps: 27, message: 'Loading budget general...', percentage: 85 })

      // Fetch and cache budget + actuals general as part of refresh
      let budgetGeneralData2: BudgetGeneralResponse | null = null
      let actualsGeneralData2: ActualsGeneralResponse | null = null
      try {
        budgetGeneralData2 = await getBudgetGeneral(week)
        setBudget_general(budgetGeneralData2)
      } catch (e) {
        budgetGeneralData2 = null
      }
      setLoadingProgress({ step: 'metrics', stepNumber: 23, totalSteps: 27, message: 'Loading actuals general...', percentage: 88 })
      try {
        actualsGeneralData2 = await getActualsGeneral(week)
        setActuals_general(actualsGeneralData2)
      } catch (e) {
        actualsGeneralData2 = null
      }
      let budgetRawData2: any | null = null
      try {
        budgetRawData2 = await getBudgetRaw(week)
        setBudget_raw(budgetRawData2)
      } catch (e) {
        budgetRawData2 = null
      }
      setLoadingProgress({ step: 'metrics', stepNumber: 24, totalSteps: 27, message: 'Loading budget raw (markets)...', percentage: 91 })
      let actualsMarketsData2: any | null = null
      try {
        actualsMarketsData2 = await getActualsMarkets(week)
        setActuals_markets(actualsMarketsData2)
      } catch (e) {
        actualsMarketsData2 = null
      }
      setLoadingProgress({ step: 'metrics', stepNumber: 25, totalSteps: 27, message: 'Loading actuals markets...', percentage: 94 })
      let actualsMarketsDetailedData2: any | null = null
      try {
        actualsMarketsDetailedData2 = await getActualsMarketsDetailed(week)
        setActuals_markets_detailed(actualsMarketsDetailedData2)
      } catch (e) {
        actualsMarketsDetailedData2 = null
      }
      setLoadingProgress({ step: 'metrics', stepNumber: 26, totalSteps: 27, message: 'Loading actuals markets detailed...', percentage: 97 })

      setLoadingProgress({ 
        step: 'complete', 
        stepNumber: 27, 
        totalSteps: 27, 
        message: 'Complete!', 
        percentage: 100 
      })
      
      // Save to cache (individual calls mode)
      saveCache(week, {
        periods: periodsData,
        metrics: metricsData,
        markets: marketsData,
        kpis: kpisData,
        contribution: contributionData,
        gender_sales: genderSalesData,
        men_category_sales: menCategorySalesData,
        women_category_sales: womenCategorySalesData,
        sessions_per_country: sessionsPerCountryData,
        conversion_per_country: conversionPerCountryData,
        new_customers_per_country: newCustomersPerCountryData,
        returning_customers_per_country: returningCustomersPerCountryData,
        aov_new_customers_per_country: aovNewCustomersPerCountryData,
        aov_returning_customers_per_country: aovReturningCustomersPerCountryData,
        marketing_spend_per_country: marketingSpendPerCountryData,
        ncac_per_country: ncacPerCountryData,
        contribution_new_per_country: contributionNewPerCountryData,
        contribution_new_total_per_country: contributionNewTotalPerCountryData,
        contribution_returning_per_country: contributionReturningPerCountryData,
        contribution_returning_total_per_country: contributionReturningTotalPerCountryData,
        total_contribution_per_country: totalContributionPerCountryData,
        budget_general: budgetGeneralData2,
        actuals_general: actualsGeneralData2,
        budget_raw: budgetRawData2,
        actuals_markets: actualsMarketsData2,
        actuals_markets_detailed: actualsMarketsDetailedData2,
        timestamp: Date.now()
      })
      } // End of if (!batchMode) block for individual calls
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load dashboard data')
      console.error('Error loading dashboard data:', err)
    } finally {
      setLoading(false)
      setIsDataReady(true)
      // Clear progress after a short delay
      setTimeout(() => setLoadingProgress(null), 500)
    }
  }, [])

  // NO AUTO-LOAD - Data should only load when user explicitly requests it
  // Removed auto-load useEffect that was triggering on baseWeek change

  const refreshData = useCallback(async () => {
    if (!baseWeek) return
    await loadAllData(baseWeek, true)
  }, [baseWeek, loadAllData])

  const clearCache = useCallback(() => {
    try {
      localStorage.removeItem(getCacheKey(baseWeek))
      setPeriods(null)
      setMetrics(null)
      setMarkets(null)
      setKpis(null)
      setContribution(null)
      setGender_sales(null)
      setMen_category_sales(null)
      setWomen_category_sales(null)
      setSessions_per_country(null)
      setBudget_general(null)
      setActuals_general(null)
      setBudget_raw(null)
    } catch (err) {
      console.warn('Failed to clear cache:', err)
    }
  }, [baseWeek])

  // Restore week from URL or localStorage (runs once on client; set hasRestoredWeek so LayoutContent can avoid hydration mismatch).
  useEffect(() => {
    if (typeof window === 'undefined') return

    const urlParams = new URLSearchParams(window.location.search)
    const weekFromUrl = urlParams.get('week')
    if (weekFromUrl) {
      console.log(`📌 Week parameter found in URL: ${weekFromUrl}`)
      setBaseWeekInternal(weekFromUrl)
      localStorage.setItem('selected_week', weekFromUrl)
      setHasRestoredWeek(true)
      return
    }

    const savedWeek = localStorage.getItem('selected_week')
    if (savedWeek) {
      setBaseWeekInternal(savedWeek)
    }
    setHasRestoredWeek(true)
  }, [])
  
  // Load cached data when baseWeek is set – from cache or Supabase (no load until user has selected a week)
  useEffect(() => {
    if (!baseWeek) return

    // First, try localStorage cache
    const cached = getCachedData(baseWeek)
    if (cached) {
      // Load from cache immediately to avoid any delay
      setPeriods(cached.periods)
      setMetrics(cached.metrics)
      setMarkets(cached.markets)
      setKpis(cached.kpis)
      setContribution(cached.contribution)
      setGender_sales(cached.gender_sales)
      setMen_category_sales(cached.men_category_sales)
      setWomen_category_sales(cached.women_category_sales)
      setSessions_per_country(cached.sessions_per_country)
      setConversion_per_country(cached.conversion_per_country)
      setNew_customers_per_country(cached.new_customers_per_country)
      setReturning_customers_per_country(cached.returning_customers_per_country)
      setAov_new_customers_per_country(cached.aov_new_customers_per_country)
      setAov_returning_customers_per_country(cached.aov_returning_customers_per_country)
      setMarketing_spend_per_country(cached.marketing_spend_per_country)
      setNcac_per_country(cached.ncac_per_country)
      setContribution_new_per_country(cached.contribution_new_per_country)
      setContribution_new_total_per_country(cached.contribution_new_total_per_country)
      setContribution_returning_per_country(cached.contribution_returning_per_country)
      setContribution_returning_total_per_country(cached.contribution_returning_total_per_country)
      setTotal_contribution_per_country(cached.total_contribution_per_country)
      setBudget_general(cached.budget_general ?? null)
      setActuals_general(cached.actuals_general ?? null)
      setBudget_raw(cached.budget_raw ?? null)
      setActuals_markets(cached.actuals_markets ?? null)
      setActuals_markets_detailed(cached.actuals_markets_detailed ?? null)
      setIsDataReady(true)
      
      // If periods are missing from cache, load them from API
      if (!cached.periods) {
        ;(async () => {
          try {
            const periodsData = await getPeriods(baseWeek)
            setPeriods(periodsData)
            console.log(`✅ Loaded missing periods from API for ${baseWeek}`)
          } catch (periodsError) {
            console.warn('Failed to load periods:', periodsError)
          }
        })()
      }
      return
    }
    
    // No cache - try Supabase (silent, no progress spinner)
    // Use a ref so only the latest load for the current week can write state (stale loads are ignored)
    const loadForWeek = baseWeek
    passiveLoadWeekRef.current = loadForWeek
    const isStale = () => passiveLoadWeekRef.current !== loadForWeek
    ;(async () => {
      try {
        const { loadWeeklyReportMetricsFromSupabase } = await import('@/lib/supabase-queries')
        const { isSupabaseAvailable } = await import('@/lib/supabase')
        
        // Only try Supabase if it's available
        if (!isSupabaseAvailable()) {
          console.debug('Supabase not available, skipping Supabase load')
          return
        }
        
        const supabaseMetrics = await loadWeeklyReportMetricsFromSupabase(loadForWeek)
        if (isStale()) return
        
        if (supabaseMetrics) {
          // Load periods from API (periods are not stored in Supabase, they're calculated)
          // This is a lightweight call that just calculates week numbers
          let periodsData: PeriodsResponse | null = null
          try {
            periodsData = await getPeriods(loadForWeek)
            if (isStale()) return
            setPeriods(periodsData)
            console.log(`✅ Loaded periods from API for ${loadForWeek}`)
          } catch (periodsError) {
            if (isStale()) return
            console.warn('Failed to load periods:', periodsError)
            // Don't fail completely - metrics can still be displayed
          }
          
          if (isStale()) return
          // Load data from Supabase metrics (supabaseMetrics is the full batch response)
          setMetrics(supabaseMetrics.metrics)
          setMarkets(supabaseMetrics.markets)
          setKpis(supabaseMetrics.kpis)
          setContribution(supabaseMetrics.contribution)
          setGender_sales(supabaseMetrics.gender_sales)
          setMen_category_sales(supabaseMetrics.men_category_sales)
          setWomen_category_sales(supabaseMetrics.women_category_sales)
          setSessions_per_country(supabaseMetrics.sessions_per_country)
          setConversion_per_country(supabaseMetrics.conversion_per_country)
          setNew_customers_per_country(supabaseMetrics.new_customers_per_country)
          setReturning_customers_per_country(supabaseMetrics.returning_customers_per_country)
          setAov_new_customers_per_country(supabaseMetrics.aov_new_customers_per_country)
          setAov_returning_customers_per_country(supabaseMetrics.aov_returning_customers_per_country)
          setMarketing_spend_per_country(supabaseMetrics.marketing_spend_per_country)
          setNcac_per_country(supabaseMetrics.ncac_per_country)
          setContribution_new_per_country(supabaseMetrics.contribution_new_per_country)
          setContribution_new_total_per_country(supabaseMetrics.contribution_new_total_per_country)
          setContribution_returning_per_country(supabaseMetrics.contribution_returning_per_country)
          setContribution_returning_total_per_country(supabaseMetrics.contribution_returning_total_per_country)
          setTotal_contribution_per_country(supabaseMetrics.total_contribution_per_country)
          setIsDataReady(true)
          
          // Save to cache for faster future loads
          saveCache(loadForWeek, {
            periods: periodsData,
            metrics: supabaseMetrics.metrics,
            markets: supabaseMetrics.markets,
            kpis: supabaseMetrics.kpis,
            contribution: supabaseMetrics.contribution,
            gender_sales: supabaseMetrics.gender_sales,
            men_category_sales: supabaseMetrics.men_category_sales,
            women_category_sales: supabaseMetrics.women_category_sales,
            sessions_per_country: supabaseMetrics.sessions_per_country,
            conversion_per_country: supabaseMetrics.conversion_per_country,
            new_customers_per_country: supabaseMetrics.new_customers_per_country,
            returning_customers_per_country: supabaseMetrics.returning_customers_per_country,
            aov_new_customers_per_country: supabaseMetrics.aov_new_customers_per_country,
            aov_returning_customers_per_country: supabaseMetrics.aov_returning_customers_per_country,
            marketing_spend_per_country: supabaseMetrics.marketing_spend_per_country,
            ncac_per_country: supabaseMetrics.ncac_per_country,
            contribution_new_per_country: supabaseMetrics.contribution_new_per_country,
            contribution_new_total_per_country: supabaseMetrics.contribution_new_total_per_country,
            contribution_returning_per_country: supabaseMetrics.contribution_returning_per_country,
            contribution_returning_total_per_country: supabaseMetrics.contribution_returning_total_per_country,
            total_contribution_per_country: supabaseMetrics.total_contribution_per_country,
            budget_general: null,
            actuals_general: null,
            budget_raw: null,
            actuals_markets: null,
            actuals_markets_detailed: null,
            timestamp: Date.now()
          })
          
          console.log(`✅ Loaded data from Supabase for ${loadForWeek}`)
        } else {
          if (isStale()) return
          // No Supabase data - but we can still load periods from API (they're calculated, not stored)
          try {
            const periodsData = await getPeriods(loadForWeek)
            if (isStale()) return
            setPeriods(periodsData)
            console.debug(`Loaded periods from API for ${loadForWeek} (no Supabase data)`)
          } catch (periodsError) {
            console.warn('Failed to load periods:', periodsError)
          }
          
          if (isStale()) return
          // Clear all other data
          setMetrics(null)
          setMarkets(null)
          setKpis(null)
          setContribution(null)
          setGender_sales(null)
          setMen_category_sales(null)
          setWomen_category_sales(null)
          setSessions_per_country(null)
          setConversion_per_country(null)
          setNew_customers_per_country(null)
          setReturning_customers_per_country(null)
          setAov_new_customers_per_country(null)
          setAov_returning_customers_per_country(null)
          setMarketing_spend_per_country(null)
          setNcac_per_country(null)
          setContribution_new_per_country(null)
          setContribution_new_total_per_country(null)
          setContribution_returning_per_country(null)
          setContribution_returning_total_per_country(null)
          setTotal_contribution_per_country(null)
          setBudget_general(null)
          setActuals_general(null)
          setBudget_raw(null)
          setActuals_markets(null)
          setActuals_markets_detailed(null)
          setIsDataReady(false)
        }
      } catch (error) {
        if (isStale()) return
        // Supabase load failed - but we can still load periods from API (they're calculated, not stored)
        console.debug('Failed to load from Supabase (non-blocking):', error)
        try {
          const periodsData = await getPeriods(loadForWeek)
          if (isStale()) return
          setPeriods(periodsData)
          console.log(`✅ Loaded periods from API for ${loadForWeek} (Supabase load failed)`)
        } catch (periodsError) {
          console.warn('Failed to load periods:', periodsError)
        }
        
        if (isStale()) return
        // Clear all other data
        setMetrics(null)
        setMarkets(null)
        setKpis(null)
        setContribution(null)
        setGender_sales(null)
        setMen_category_sales(null)
        setWomen_category_sales(null)
        setSessions_per_country(null)
        setConversion_per_country(null)
        setNew_customers_per_country(null)
        setReturning_customers_per_country(null)
        setAov_new_customers_per_country(null)
        setAov_returning_customers_per_country(null)
        setMarketing_spend_per_country(null)
        setNcac_per_country(null)
        setContribution_new_per_country(null)
        setContribution_new_total_per_country(null)
        setContribution_returning_per_country(null)
        setContribution_returning_total_per_country(null)
        setTotal_contribution_per_country(null)
        setBudget_general(null)
        setActuals_general(null)
        setBudget_raw(null)
        setActuals_markets(null)
        setActuals_markets_detailed(null)
          setIsDataReady(false)
      }
    })()
  }, [baseWeek])

  const value: DataCacheContextType = {
    periods,
    metrics,
    markets,
    kpis,
    contribution,
    gender_sales,
    men_category_sales,
    women_category_sales,
    sessions_per_country,
    conversion_per_country,
    new_customers_per_country,
    returning_customers_per_country,
    aov_new_customers_per_country,
    aov_returning_customers_per_country,
    marketing_spend_per_country,
    ncac_per_country,
    contribution_new_per_country,
    contribution_new_total_per_country,
    contribution_returning_per_country,
    contribution_returning_total_per_country,
    total_contribution_per_country,
    budget_general,
    actuals_general,
    budget_raw,
    actuals_markets,
    actuals_markets_detailed,
    loading,
    error,
    loadingProgress,
    loadAllData,
    refreshData,
    clearCache,
    baseWeek: baseWeek,
    setBaseWeek,
    isDataReady,
    hasRestoredWeek
  }

  return <DataCacheContext.Provider value={value}>{children}</DataCacheContext.Provider>
}

export function useDataCache() {
  const context = useContext(DataCacheContext)
  if (context === undefined) {
    throw new Error('useDataCache must be used within DataCacheProvider')
  }
  return context
}

export function usePeriods() {
  const { periods } = useDataCache()
  return periods
}

export function useMetrics() {
  const { metrics } = useDataCache()
  return { metrics }
}

export function useMarkets() {
  const { markets } = useDataCache()
  return { markets }
}

export function useKPIs() {
  const { kpis } = useDataCache()
  return { kpis }
}

export function useContribution() {
  const { contribution } = useDataCache()
  return { contributions: contribution }
}

export function useGenderSales() {
  const { gender_sales } = useDataCache()
  return { gender_sales }
}

export function useMenCategorySales() {
  const { men_category_sales } = useDataCache()
  return { men_category_sales }
}

export function useWomenCategorySales() {
  const { women_category_sales } = useDataCache()
  return { women_category_sales }
}

export function useSessionsPerCountry() {
  const { sessions_per_country } = useDataCache()
  return { sessions_per_country }
}

export function useConversionPerCountry() {
  const { conversion_per_country } = useDataCache()
  return { conversion_per_country }
}

export function useNewCustomersPerCountry() {
  const { new_customers_per_country } = useDataCache()
  return { new_customers_per_country }
}

export function useReturningCustomersPerCountry() {
  const { returning_customers_per_country } = useDataCache()
  return { returning_customers_per_country }
}

export function useAOVNewCustomersPerCountry() {
  const { aov_new_customers_per_country } = useDataCache()
  return { aov_new_customers_per_country }
}

export function useAOVReturningCustomersPerCountry() {
  const { aov_returning_customers_per_country } = useDataCache()
  return { aov_returning_customers_per_country }
}

export function useMarketingSpendPerCountry() {
  const { marketing_spend_per_country } = useDataCache()
  return { marketing_spend_per_country }
}

export function useNCACPerCountry() {
  const { ncac_per_country } = useDataCache()
  return { ncac_per_country }
}

export function useContributionNewPerCountry() {
  const { contribution_new_per_country } = useDataCache()
  return { contribution_new_per_country }
}

export function useContributionNewTotalPerCountry() {
  const { contribution_new_total_per_country } = useDataCache()
  return { contribution_new_total_per_country }
}

export function useContributionReturningPerCountry() {
  const { contribution_returning_per_country } = useDataCache()
  return { contribution_returning_per_country }
}

export function useContributionReturningTotalPerCountry() {
  const { contribution_returning_total_per_country } = useDataCache()
  return { contribution_returning_total_per_country }
}

export function useTotalContributionPerCountry() {
  const { total_contribution_per_country } = useDataCache()
  return { total_contribution_per_country }
}
