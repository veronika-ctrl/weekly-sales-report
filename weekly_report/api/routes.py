"""FastAPI routes for weekly report API."""

import os
from pathlib import Path

# Load .env so SUPABASE_* and other vars are available before any request.
# Try project root (relative to this file) first, then cwd so it works regardless of how server is started.
from dotenv import load_dotenv
_env_path_root = Path(__file__).resolve().parent.parent.parent / ".env"
_env_path_cwd = Path.cwd() / ".env"
if _env_path_root.exists():
    load_dotenv(_env_path_root)
if _env_path_cwd.exists() and (
    not _env_path_root.exists() or _env_path_root.resolve() != _env_path_cwd.resolve()
):
    load_dotenv(_env_path_cwd)  # fallback when root missing or started from another cwd
# Supabase env check is logged at startup (after logger is imported)

from fastapi import FastAPI, HTTPException, Query, File, UploadFile, Form, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, Response
import json
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import tempfile
import shutil
from datetime import datetime
from loguru import logger
import pandas as pd
import pandas as pd
import hashlib

from weekly_report.src.periods.calculator import get_periods_for_week, get_week_date_range, get_ytd_periods_for_week, get_mtd_periods_for_week, validate_iso_week
from weekly_report.src.metrics.table1 import calculate_table1_for_periods, calculate_table1_for_periods_with_ytd, calculate_table1_mtd_and_ytd
from weekly_report.src.metrics.markets import calculate_top_markets_for_weeks
from weekly_report.src.metrics.online_kpis import calculate_online_kpis_for_weeks
from weekly_report.src.metrics.contribution import calculate_contribution_for_weeks
from weekly_report.src.metrics.gender_sales import calculate_gender_sales_for_weeks
from weekly_report.src.metrics.men_category_sales import calculate_men_category_sales_for_weeks
from weekly_report.src.metrics.women_category_sales import calculate_women_category_sales_for_weeks
from weekly_report.src.metrics.category_sales import calculate_category_sales_for_weeks
from weekly_report.src.metrics.top_products import calculate_top_products_for_weeks
from weekly_report.src.metrics.top_products_gender import calculate_top_products_by_gender_for_weeks
from weekly_report.src.metrics.sessions_per_country import calculate_sessions_per_country_for_weeks
from weekly_report.src.metrics.conversion_per_country import calculate_conversion_per_country_for_weeks
from weekly_report.src.metrics.new_customers_per_country import calculate_new_customers_per_country_for_weeks
from weekly_report.src.metrics.returning_customers_per_country import calculate_returning_customers_per_country_for_weeks
from weekly_report.src.metrics.aov_new_customers_per_country import calculate_aov_new_customers_per_country_for_weeks
from weekly_report.src.metrics.aov_returning_customers_per_country import calculate_aov_returning_customers_per_country_for_weeks
from weekly_report.src.metrics.marketing_spend_per_country import calculate_marketing_spend_per_country_for_weeks
from weekly_report.src.metrics.ncac_per_country import calculate_ncac_per_country_for_weeks
from weekly_report.src.metrics.contribution_new_per_country import calculate_contribution_new_per_country_for_weeks
from weekly_report.src.metrics.contribution_new_total_per_country import calculate_contribution_new_total_per_country_for_weeks
from weekly_report.src.metrics.contribution_returning_per_country import calculate_contribution_returning_per_country_for_weeks
from weekly_report.src.metrics.contribution_returning_total_per_country import calculate_contribution_returning_total_per_country_for_weeks
from weekly_report.src.metrics.total_contribution_per_country import calculate_total_contribution_per_country_for_weeks
from weekly_report.src.metrics.audience_metrics_per_country import calculate_audience_metrics_per_country_for_weeks
from weekly_report.src.metrics.batch_calculator import calculate_all_metrics
from weekly_report.src.pdf.table1_builder import build_table1_pdf
# Note: weekly_reports_builder not available, using Puppeteer-based approach instead
# from weekly_report.src.pdf.weekly_reports_builder import build_weekly_reports_pdf
from weekly_report.src.cache.manager import metrics_cache, raw_data_cache
from weekly_report.src.config import load_config
from weekly_report.src.utils.file_metadata import extract_file_metadata


# Pydantic models
class PeriodsResponse(BaseModel):
    actual: str
    last_week: str
    last_year: str
    year_2023: str
    date_ranges: Dict[str, Dict[str, str]]
    ytd_periods: Dict[str, Dict[str, str]]


class MetricsResponse(BaseModel):
    periods: Dict[str, Dict[str, Any]]


class MetricsMtdResponse(BaseModel):
    """Table 1 metrics for month-to-date report: mtd_actual, mtd_last_year, mtd_last_month, ytd_actual, ytd_last_year."""
    periods: Dict[str, Dict[str, Any]]
    date_ranges: Dict[str, Dict[str, str]]


class GeneratePDFRequest(BaseModel):
    base_week: str
    periods: List[str]


class MarketData(BaseModel):
    country: str
    weeks: Dict[str, float]  # Explicit dict type
    average: float
    
    class Config:
        json_schema_extra = {
            "example": {
                "country": "United States",
                "weeks": {"2025-42": 450000, "2024-42": 420000},
                "average": 435000
            }
        }

class MarketsResponse(BaseModel):
    markets: List[MarketData]  # Use explicit model instead of Dict[str, Any]
    period_info: Dict[str, str]


class KPIData(BaseModel):
    week: str
    aov_new_customer: float
    aov_returning_customer: float
    cos: float
    marketing_spend: float
    conversion_rate: float
    new_customers: int
    returning_customers: int
    sessions: int
    new_customer_cac: float
    total_orders: int
    return_rate_pct: float = 0.0
    last_year: Optional[Dict[str, Any]] = None


class OnlineKPIsResponse(BaseModel):
    kpis: List[KPIData]
    period_info: Dict[str, Any]


class ContributionData(BaseModel):
    week: str
    gross_revenue_new: float
    gross_revenue_returning: float
    contribution_new: float
    contribution_returning: float
    contribution_total: float
    last_year: Optional[Dict[str, Any]] = None


class ContributionResponse(BaseModel):
    contributions: List[ContributionData]
    period_info: Dict[str, Any]


class GenderSalesData(BaseModel):
    week: str
    men_unisex_sales: float
    women_sales: float
    total_sales: float
    last_year: Optional[Dict[str, Any]] = None


class GenderSalesResponse(BaseModel):
    gender_sales: List[GenderSalesData]
    period_info: Dict[str, Any]


class MenCategorySalesData(BaseModel):
    week: str
    categories: Dict[str, float]
    last_year: Optional[Dict[str, Any]] = None


class MenCategorySalesResponse(BaseModel):
    men_category_sales: List[MenCategorySalesData]
    period_info: Dict[str, Any]


class WomenCategorySalesData(BaseModel):
    week: str
    categories: Dict[str, float]
    last_year: Optional[Dict[str, Any]] = None


class WomenCategorySalesResponse(BaseModel):
    women_category_sales: List[WomenCategorySalesData]
    period_info: Dict[str, Any]


class CategorySalesData(BaseModel):
    week: str
    categories: Dict[str, float]
    last_year: Optional[Dict[str, Any]] = None


class CategorySalesResponse(BaseModel):
    category_sales: List[CategorySalesData]
    period_info: Dict[str, Any]


class ProductData(BaseModel):
    rank: int
    gender: str
    category: str
    product: str
    color: str
    gross_revenue: float
    sales_qty: int


class TopProductsData(BaseModel):
    week: str
    products: List[ProductData]
    top_total: Dict[str, Any]
    grand_total: Dict[str, Any]


class TopProductsResponse(BaseModel):
    top_products: List[TopProductsData]
    period_info: Dict[str, Any]


class SessionsPerCountryData(BaseModel):
    week: str
    countries: Dict[str, float]
    last_year: Optional[Dict[str, Any]] = None


class SessionsPerCountryResponse(BaseModel):
    sessions_per_country: List[SessionsPerCountryData]
    period_info: Dict[str, Any]


class ConversionPerCountryData(BaseModel):
    week: str
    countries: Dict[str, Dict[str, Any]]
    last_year: Optional[Dict[str, Any]] = None


class ConversionPerCountryResponse(BaseModel):
    conversion_per_country: List[ConversionPerCountryData]
    period_info: Dict[str, Any]


class NewCustomersPerCountryData(BaseModel):
    week: str
    countries: Dict[str, float]
    last_year: Optional[Dict[str, Any]] = None


class NewCustomersPerCountryResponse(BaseModel):
    new_customers_per_country: List[NewCustomersPerCountryData]
    period_info: Dict[str, Any]


class ReturningCustomersPerCountryData(BaseModel):
    week: str
    countries: Dict[str, float]
    last_year: Optional[Dict[str, Any]] = None


class ReturningCustomersPerCountryResponse(BaseModel):
    returning_customers_per_country: List[ReturningCustomersPerCountryData]
    period_info: Dict[str, Any]


class AOVNewCustomersPerCountryData(BaseModel):
    week: str
    countries: Dict[str, float]
    last_year: Optional[Dict[str, Any]] = None


class AOVNewCustomersPerCountryResponse(BaseModel):
    aov_new_customers_per_country: List[AOVNewCustomersPerCountryData]
    period_info: Dict[str, Any]


class AOVReturningCustomersPerCountryData(BaseModel):
    week: str
    countries: Dict[str, float]
    last_year: Optional[Dict[str, Any]] = None


class AOVReturningCustomersPerCountryResponse(BaseModel):
    aov_returning_customers_per_country: List[AOVReturningCustomersPerCountryData]
    period_info: Dict[str, Any]


class MarketingSpendPerCountryData(BaseModel):
    week: str
    countries: Dict[str, float]
    last_year: Optional[Dict[str, Any]] = None


class MarketingSpendPerCountryResponse(BaseModel):
    marketing_spend_per_country: List[MarketingSpendPerCountryData]
    period_info: Dict[str, Any]


class nCACPerCountryData(BaseModel):
    week: str
    countries: Dict[str, float]
    last_year: Optional[Dict[str, Any]] = None


class nCACPerCountryResponse(BaseModel):
    ncac_per_country: List[nCACPerCountryData]
    period_info: Dict[str, Any]


class ContributionNewPerCountryData(BaseModel):
    week: str
    countries: Dict[str, float]
    last_year: Optional[Dict[str, Any]] = None


class ContributionNewPerCountryResponse(BaseModel):
    contribution_new_per_country: List[ContributionNewPerCountryData]
    period_info: Dict[str, Any]


class ContributionNewTotalPerCountryResponse(BaseModel):
    contribution_new_total_per_country: List[ContributionNewPerCountryData]  # Same data structure, different metric
    period_info: Dict[str, Any]


class ContributionReturningPerCountryResponse(BaseModel):
    contribution_returning_per_country: List[ContributionNewPerCountryData]  # Same data structure
    period_info: Dict[str, Any]


class ContributionReturningTotalPerCountryResponse(BaseModel):
    contribution_returning_total_per_country: List[ContributionNewPerCountryData]  # Same data structure
    period_info: Dict[str, Any]


class TotalContributionPerCountryResponse(BaseModel):
    total_contribution_per_country: List[ContributionNewPerCountryData]  # Same data structure
    period_info: Dict[str, Any]


class AudienceMetricsCountryDataInner(BaseModel):
    total_aov: float
    total_customers: int
    return_rate_pct: float
    cos_pct: float
    cac: float


class AudienceMetricsCountryData(BaseModel):
    total_aov: float
    total_customers: int
    return_rate_pct: float
    cos_pct: float
    cac: float
    last_year: Optional[AudienceMetricsCountryDataInner] = None


class AudienceMetricsPerCountryWeekData(BaseModel):
    week: str
    countries: Dict[str, AudienceMetricsCountryData]


class AudienceMetricsPerCountryResponse(BaseModel):
    audience_metrics_per_country: List[AudienceMetricsPerCountryWeekData]
    period_info: Dict[str, str]


class BatchMetricsResponse(BaseModel):
    """Unified response containing all metrics calculated in a single batch."""
    periods: Dict[str, Any]
    metrics: Dict[str, Any]
    markets: List[Any]
    kpis: List[Any]
    contribution: List[Any]
    gender_sales: List[Any]
    men_category_sales: List[Any]
    women_category_sales: List[Any]
    category_sales: Dict[str, Any]
    products_new: Dict[str, Any]
    products_gender: Dict[str, Any]
    sessions_per_country: List[Any]
    conversion_per_country: List[Any]
    new_customers_per_country: List[Any]
    returning_customers_per_country: List[Any]
    aov_new_customers_per_country: List[Any]
    aov_returning_customers_per_country: List[Any]
    marketing_spend_per_country: List[Any]
    ncac_per_country: List[Any]
    contribution_new_per_country: List[Any]
    contribution_new_total_per_country: List[Any]
    contribution_returning_per_country: List[Any]
    contribution_returning_total_per_country: List[Any]
    total_contribution_per_country: List[Any]


# Helper function to read metrics from Supabase cache
def get_metrics_from_supabase(base_week: str, metric_key: str = None):
    """
    Read metrics from Supabase cache if available and file hashes match.
    
    Args:
        base_week: ISO week string like '2025-42'
        metric_key: Optional key to extract from metrics dict (e.g., 'markets', 'kpis')
        
    Returns:
        Tuple (found: bool, data: dict or None)
    """
    if not _supabase_enabled():
        return False, None
    try:
        from weekly_report.src.adapters.supabase_client import get_supabase_client
        from weekly_report.src.export.weekly_reports import reconstruct_metrics_from_supabase
        from weekly_report.src.utils.file_hashes import get_file_hashes_for_week, hashes_match
        from weekly_report.src.config import load_config
        
        supabase = get_supabase_client()
        if not supabase:
            return False, None
        
        try:
            cached_result = supabase.table("weekly_report_metrics").select("*").eq("base_week", base_week).limit(1).execute()
            if cached_result.data and len(cached_result.data) > 0:
                cached_row = cached_result.data[0]
                config = load_config(week=base_week)
                current_file_hashes = get_file_hashes_for_week(base_week, config.data_root)
                
                stored_hashes = cached_row.get("file_hashes")
                if stored_hashes and isinstance(stored_hashes, str):
                    import json
                    stored_hashes = json.loads(stored_hashes)
                elif isinstance(stored_hashes, dict):
                    pass
                else:
                    stored_hashes = {}
                
                if hashes_match(stored_hashes, current_file_hashes):
                    metrics_dict = reconstruct_metrics_from_supabase(cached_row)
                    if metric_key:
                        if metric_key in metrics_dict:
                            return True, metrics_dict[metric_key]
                        else:
                            return False, None
                    return True, metrics_dict
        except Exception as e:
            logger.debug(f"Error reading from Supabase cache: {e}")
    except ImportError:
        logger.debug("Supabase client not available")
    
    return False, None


# Initialize FastAPI app
app = FastAPI(
    title="Weekly Report API",
    description="API for generating weekly report tables",
    version="1.0.0"
)

# Configure logging to file
log_file = Path("backend.log")
logger.add(
    str(log_file),
    rotation="10 MB",
    retention="7 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    backtrace=True,
    diagnose=True
)
logger.info("Backend logging configured. Logs will be written to backend.log")


def _supabase_enabled() -> bool:
    """True only when Supabase is not disabled via DISABLE_SUPABASE."""
    return os.getenv("DISABLE_SUPABASE", "").lower() not in ("1", "true", "yes")


@app.on_event("startup")
def _log_supabase_status():
    """Log whether Supabase is configured and enabled."""
    if not _supabase_enabled():
        logger.info("Supabase: disabled (DISABLE_SUPABASE=true). All Supabase read/write skipped.")
        return
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if url and key:
        logger.info("Supabase: configured (SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY set)")
    else:
        logger.warning(
            "Supabase: not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env at project root. "
            "Sync and cache will be disabled until then."
        )


# Add CORS middleware
# Allow localhost for development and Vercel domains for production
import os
cors_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "http://localhost:3002",
    "http://127.0.0.1:3002",
]

# Add Vercel domain if provided via environment variable
vercel_url = os.getenv("VERCEL_URL")
if vercel_url:
    # Vercel provides URL without protocol, add https
    if not vercel_url.startswith("http"):
        cors_origins.append(f"https://{vercel_url}")
    else:
        cors_origins.append(vercel_url)

# Also allow custom frontend URL if set
frontend_url = os.getenv("FRONTEND_URL")
if frontend_url:
    cors_origins.append(frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/periods", response_model=PeriodsResponse)
async def get_periods(base_week: str = Query(..., description="Base ISO week like '2025-42'")):
    """Get period information for a base week."""
    
    try:
        # Validate input
        if not validate_iso_week(base_week):
            raise HTTPException(status_code=400, detail=f"Invalid ISO week format: {base_week}")
        
        # Calculate periods
        periods = get_periods_for_week(base_week)
        
        # Get YTD periods
        ytd_periods = get_ytd_periods_for_week(base_week)
        
        # Get date ranges for each period
        date_ranges = {}
        for period_name, period_week in periods.items():
            try:
                date_ranges[period_name] = get_week_date_range(period_week)
            except Exception as e:
                logger.warning(f"Could not get date range for {period_week}: {e}")
                date_ranges[period_name] = {
                    'start': 'N/A',
                    'end': 'N/A', 
                    'display': 'N/A'
                }
        
        return PeriodsResponse(
            actual=periods['actual'],
            last_week=periods['last_week'],
            last_year=periods['last_year'],
            year_2023=periods['year_2023'],
            date_ranges=date_ranges,
            ytd_periods=ytd_periods
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting periods for {base_week}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# New: Actuals aggregated per market (for Budget Markets caching)
@app.get("/api/actuals-markets")
async def get_actuals_markets(week: str = Query(...)):
    """Aggregate actuals per Market with total gross revenue and total orders."""
    try:
        if not validate_iso_week(week):
            raise HTTPException(status_code=400, detail="Invalid ISO week format")

        # Use compute function to handle raw Qlik data correctly
        from weekly_report.src.compute.budget import compute_actuals_markets_detailed
        result = compute_actuals_markets_detailed(week)
        
        # Check if there's an error
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        # Aggregate per market from detailed results
        markets = result.get("markets", [])
        totals = result.get("totals", {})
        metrics = result.get("metrics", [])
        
        # Shape to columns/sample_data format
        candidate_cols = [
            "Total Gross Revenue", "Total Net Revenue", "Returns", "Total Returns",
            "Total Orders", "Total Customers",
            "Returning Gross Revenue", "Returning Net Revenue", "Returning Returns", 
            "Returning Orders", "Returning Customers",
            "New Gross Revenue", "New Net Revenue", "New Returns", "New Orders", "New Customers",
        ]
        agg_cols = [c for c in candidate_cols if c in metrics]
        
        sample_data = []
        for market in markets:
            market_totals = totals.get(market, {})
            row = {"Market": market}
            for col in agg_cols:
                row[col] = market_totals.get(col, 0.0)
            sample_data.append(row)
        
        # Sort by first metric (descending)
        if agg_cols and sample_data:
            sample_data.sort(key=lambda x: x.get(agg_cols[0], 0.0), reverse=True)
        
        columns = ["Market"] + agg_cols
        return {"columns": columns, "sample_data": sample_data}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error aggregating actuals per market: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# New: Actuals detailed per Market and Month (for Budget Markets detailed views)
@app.get("/api/actuals-markets-detailed")
async def get_actuals_markets_detailed(week: str = Query(...)):
    """Aggregate actuals per Market and Month with the same metrics derivations used in general."""
    try:
        if not validate_iso_week(week):
            raise HTTPException(status_code=400, detail="Invalid ISO week format")

        # Use compute function to handle raw Qlik data correctly
        from weekly_report.src.compute.budget import compute_actuals_markets_detailed
        result = compute_actuals_markets_detailed(week)
        
        # Check if there's an error
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error aggregating actuals per market detailed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/metrics/table1", response_model=MetricsResponse)
async def get_table1_metrics(
    base_week: str = Query(..., description="Base ISO week like '2025-42'"),
    periods: str = Query("actual,last_week,last_year,year_2023", description="Comma-separated list of periods"),
    include_ytd: bool = Query(True, description="Include YTD columns")
):
    """Get Table 1 metrics for specified periods."""
    
    try:
        # Validate input
        if not validate_iso_week(base_week):
            raise HTTPException(status_code=400, detail=f"Invalid ISO week format: {base_week}")
        
        # Parse periods
        requested_periods = [p.strip() for p in periods.split(',')]
        valid_periods = ['actual', 'last_week', 'last_year', 'year_2023']
        
        for period in requested_periods:
            if period not in valid_periods:
                raise HTTPException(status_code=400, detail=f"Invalid period: {period}")
        
        # Try to read from Supabase first (only when Supabase is enabled)
        if _supabase_enabled():
            try:
                from weekly_report.src.adapters.supabase_client import get_supabase_client
                from weekly_report.src.export.weekly_reports import reconstruct_metrics_from_supabase
                from weekly_report.src.utils.file_hashes import get_file_hashes_for_week, hashes_match

                supabase = get_supabase_client()
                if supabase:
                    try:
                        cached_result = supabase.table("weekly_report_metrics").select("*").eq("base_week", base_week).limit(1).execute()
                        if cached_result.data and len(cached_result.data) > 0:
                            cached_row = cached_result.data[0]
                            config = load_config(week=base_week)
                            current_file_hashes = get_file_hashes_for_week(base_week, config.data_root)

                            stored_hashes = cached_row.get("file_hashes")
                            if stored_hashes and isinstance(stored_hashes, str):
                                import json
                                stored_hashes = json.loads(stored_hashes)
                            elif isinstance(stored_hashes, dict):
                                pass
                            else:
                                stored_hashes = {}

                            if hashes_match(stored_hashes, current_file_hashes):
                                metrics_dict = reconstruct_metrics_from_supabase(cached_row)
                                if "metrics" in metrics_dict:
                                    cached_metrics = metrics_dict["metrics"]
                                    filtered_metrics = {k: v for k, v in cached_metrics.items() if k in requested_periods}
                                    if not include_ytd:
                                        logger.info(f"✅ Returning table1 metrics from Supabase for {base_week}")
                                        return MetricsResponse(periods=filtered_metrics)
                    except Exception as cache_error:
                        logger.debug(f"Could not read from Supabase cache: {cache_error}")
            except ImportError:
                logger.debug("Supabase client not available, skipping cache check")

        # Check in-memory cache
        cached_result = metrics_cache.get(base_week, requested_periods)
        if cached_result and not include_ytd:
            return MetricsResponse(periods=cached_result)
        
        # Calculate all periods
        all_periods = get_periods_for_week(base_week)
        
        # Filter to requested periods
        filtered_periods = {k: v for k, v in all_periods.items() if k in requested_periods}
        
        # Load config to get data root
        config = load_config(week=base_week)
        
        # Calculate metrics
        if include_ytd:
            metrics_results = calculate_table1_for_periods_with_ytd(filtered_periods, Path(config.data_root))
        else:
            metrics_results = calculate_table1_for_periods(filtered_periods, Path(config.data_root))
        
        # Cache the results
        metrics_cache.set(base_week, requested_periods, metrics_results)
        
        return MetricsResponse(periods=metrics_results)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        logger.warning(f"No data for table1 metrics {base_week}: {e}")
        raise HTTPException(
            status_code=404,
            detail=f"No data files found for week {base_week}. Upload data in Settings (e.g. Qlik, DEMA, Shopify CSVs in data/raw/{base_week}/)."
        )
    except Exception as e:
        import traceback
        logger.error(f"Error getting metrics for {base_week}: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


def _parse_budget_number(value: Any) -> float:
    """Parse a number from budget CSV (handles locale, parentheses, %)."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 0.0
    if isinstance(value, (int, float)):
        v = float(value)
        return 0.0 if (v != v or v == float("inf") or v == float("-inf")) else v
    s = str(value).strip().replace("\ufeff", "").replace(" ", "").replace("%", "")
    if not s or s == "-":
        return 0.0
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    if "," in s and "." in s:
        s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        v = float(s)
        return 0.0 if (v != v or v == float("inf") or v == float("-inf")) else v
    except Exception:
        return 0.0


def _load_mtd_budget_direct(base_week: str, data_root: Path) -> Dict[str, Any]:
    """Load budget CSV directly from disk and return mtd_budget dict for the target month. Tries multiple paths and layouts."""
    try:
        from weekly_report.src.periods.calculator import get_week_date_range
        week_range = get_week_date_range(base_week)
        end_dt = datetime.strptime(week_range["end"], "%Y-%m-%d")
        target_year, target_month = end_dt.year, end_dt.month
        month_str = end_dt.strftime("%B %Y")
    except Exception:
        return {}
    root = Path(data_root).resolve()
    raw = root / "raw"
    if not raw.exists():
        return {}
    csv_path = None
    # 1) Week folder
    week_dir = raw / base_week
    if week_dir.exists():
        budget_dir = week_dir / "budget"
        if budget_dir.exists():
            csvs = [f for f in budget_dir.glob("*.csv") if not f.name.startswith(".")]
            if csvs:
                csv_path = max(csvs, key=lambda f: f.stat().st_mtime)
    # 2) Any same-year week folder
    if csv_path is None:
        year = int(base_week.split("-")[0])
        for p in sorted(raw.iterdir(), reverse=True):
            if p.is_dir() and p.name.startswith(str(year) + "-"):
                bd = p / "budget"
                if bd.exists():
                    csvs = [f for f in bd.glob("*.csv") if not f.name.startswith(".")]
                    if csvs:
                        csv_path = max(csvs, key=lambda f: f.stat().st_mtime)
                        logger.info(f"Budget: using CSV from {p.name}/budget for {base_week}")
                        break
    # 3) Shared data/raw/budget
    if csv_path is None:
        shared = raw / "budget"
        if shared.exists():
            csvs = [f for f in shared.glob("*.csv") if not f.name.startswith(".")]
            if csvs:
                csv_path = max(csvs, key=lambda f: f.stat().st_mtime)
    if csv_path is None:
        logger.info(f"Budget: no CSV found for {base_week} (tried week folder, same-year weeks, data/raw/budget)")
        return {}
    try:
        df = pd.read_csv(
            csv_path,
            encoding="utf-8-sig",
            na_values=["", "NULL", "N/A"],
            sep=None,
            engine="python",
        )
    except Exception as e:
        logger.warning(f"Failed to read budget CSV {csv_path}: {e}")
        return {}
    if df.empty:
        return {}
    df.columns = df.columns.str.replace("\ufeff", "").str.strip()
    logger.info(f"Budget: loaded {csv_path.name} for {base_week}, shape={df.shape}, columns={list(df.columns)[:8]}")
    # Drop source columns if present
    for drop in ["_source_file", "_source_type", "_source_location"]:
        if drop in df.columns:
            df = df.drop(columns=[drop])
    # Target month variants for matching
    month_variants = [month_str, end_dt.strftime("%Y-%m"), end_dt.strftime("%b %Y")]

    # Swedish month names (Mars = March, etc.)
    _swedish_months = {"januari": 1, "februari": 2, "mars": 3, "april": 4, "maj": 5, "juni": 6,
                       "juli": 7, "augusti": 8, "september": 9, "oktober": 10, "november": 11, "december": 12}

    def month_key_matches(col: str) -> bool:
        s = str(col).strip()
        if not s:
            return False
        if s in month_variants or s.lower() == month_str.lower():
            return True
        for fmt in ("%B %Y", "%b %Y", "%Y-%m"):
            try:
                dt = datetime.strptime(s[:7] if fmt == "%Y-%m" else s, fmt)
                return dt.year == target_year and dt.month == target_month
            except Exception:
                continue
        # Try "Mars 2026" (Swedish)
        parts = s.lower().split()
        if len(parts) == 2 and parts[1].isdigit():
            mo = _swedish_months.get(parts[0])
            yr = int(parts[1])
            if mo is not None and yr == target_year and mo == target_month:
                return True
        return False

    def metric_row_matches(label: str, *names: str) -> bool:
        if not label:
            return False
        L = str(label).strip().lower()
        for n in names:
            if n.lower() == L or n.lower() in L or L in n.lower():
                return True
        return False

    def month_value_matches(month_val, year_val=None) -> bool:
        """Return True if month_val (and optionally year_val) match target month/year."""
        if month_val is None or (isinstance(month_val, float) and pd.isna(month_val)):
            return False
        s = str(month_val).strip()
        if not s:
            return False
        if s in month_variants or s.lower() == month_str.lower():
            return True
        # Numeric month (e.g. 3 or "3")
        try:
            m = int(float(s))
            if 1 <= m <= 12 and m == target_month:
                if year_val is not None:
                    try:
                        y = int(float(str(year_val).strip()))
                        return y == target_year
                    except (ValueError, TypeError):
                        pass
                return True
        except (ValueError, TypeError):
            pass
        # "March" or "Mars" (Swedish) or English month name
        s_lower = s.lower()
        _english_months = {"january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
                          "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12}
        month_num = _swedish_months.get(s_lower) or _english_months.get(s_lower)
        if month_num is not None and month_num == target_month:
            if year_val is not None:
                try:
                    y = int(float(str(year_val).strip()))
                    return y == target_year
                except (ValueError, TypeError):
                    return False
            return True
        for fmt in ("%B %Y", "%b %Y", "%Y-%m", "%m/%Y", "%Y/%m"):
            try:
                part = s[:7] if "%-" in fmt or fmt == "%Y-%m" else s
                dt = datetime.strptime(part, fmt)
                if dt.year == target_year and dt.month == target_month:
                    return True
            except Exception:
                continue
        return False

    # Layout D: long format — columns Metric, Month, Value (and optionally Market, Year, Type)
    if "Metric" in df.columns and "Value" in df.columns and "Month" in df.columns:
        # Prefer BUDGET type if present and has rows, else use all rows
        type_vals = df["Type"].astype(str).str.strip().str.upper() if "Type" in df.columns else pd.Series(dtype=object)
        if "Type" in df.columns and (type_vals == "BUDGET").any():
            df_sub = df[type_vals == "BUDGET"].copy()
        else:
            df_sub = df.copy()
        # Filter by target month (and year if column exists)
        year_col = "Year" if "Year" in df_sub.columns else None
        month_col = "Month"
        mask = df_sub.apply(
            lambda r: month_value_matches(r.get(month_col), r.get(year_col) if year_col else None),
            axis=1,
        )
        df_month = df_sub.loc[mask]
        # If we filtered to BUDGET but got no rows for target month, try all types (e.g. ACTUAL)
        if df_month.empty and "Type" in df.columns and (type_vals == "BUDGET").any():
            df_sub = df.copy()
            mask = df_sub.apply(
                lambda r: month_value_matches(r.get(month_col), r.get(year_col) if year_col else None),
                axis=1,
            )
            df_month = df_sub.loc[mask]
        # Optionally filter to totals (e.g. Market == "Total CDLP" or contains "Total")
        if "Market" in df_month.columns and len(df_month["Market"].dropna().unique()) > 1:
            total_mask = df_month["Market"].astype(str).str.strip().str.lower().str.contains("total", na=False)
            if total_mask.any():
                df_month = df_month.loc[total_mask]
        if not df_month.empty:
            out = {}
            for _, row in df_month.iterrows():
                label = str(row.get("Metric", "")).strip()
                if not label:
                    continue
                v = _parse_budget_number(row.get("Value"))
                if metric_row_matches(label, "Total Gross Revenue", "Online Gross Revenue"):
                    out["online_gross_revenue"] = v
                elif metric_row_matches(label, "Returns"):
                    out["returns"] = v
                elif metric_row_matches(label, "Return rate (%)", "Return rate", "Return Rate %"):
                    out["return_rate_pct"] = v
                elif metric_row_matches(label, "Net Revenue", "Online Net Revenue"):
                    out["online_net_revenue"] = out["total_net_revenue"] = v
                elif metric_row_matches(label, "Returning Customers"):
                    out["returning_customers"] = int(round(v))
                elif metric_row_matches(label, "New Customers"):
                    out["new_customers"] = int(round(v))
                elif metric_row_matches(label, "Online Marketing Spend", "Marketing Spend"):
                    out["marketing_spend"] = v
                elif metric_row_matches(label, "COS %", "COS", "Online Cost of Sale"):
                    out["online_cost_of_sale_3"] = v
                elif metric_row_matches(label, "aMER"):
                    out["emer"] = v
            if out:
                return_rate = out.get("return_rate_pct", 0) or (
                    (out.get("returns", 0) / out.get("online_gross_revenue", 1) * 100
                    if out.get("online_gross_revenue")
                    else 0
                ))
                logger.info(f"Budget: parsed long-format CSV for {target_month}/{target_year}, keys={list(out.keys())}")
                return {
                    "online_gross_revenue": out.get("online_gross_revenue", 0),
                    "returns": out.get("returns", 0),
                    "return_rate_pct": round(return_rate, 1),
                    "online_net_revenue": out.get("online_net_revenue", 0),
                    "retail_concept_store": 0.0,
                    "retail_popups_outlets": 0.0,
                    "retail_net_revenue": 0.0,
                    "wholesale_net_revenue": 0.0,
                    "total_net_revenue": out.get("total_net_revenue", out.get("online_net_revenue", 0)),
                    "returning_customers": out.get("returning_customers", 0),
                    "new_customers": out.get("new_customers", 0),
                    "marketing_spend": out.get("marketing_spend", 0),
                    "online_cost_of_sale_3": round(out.get("online_cost_of_sale_3", 0), 1),
                    "emer": round(out.get("emer", 0), 1),
                }

    # Layout A: columns include month-like -> first column is metric, others are months
    month_cols = [c for c in df.columns if month_key_matches(c)]
    if month_cols:
        key_col = df.columns[0]
        # Use the column that matches our target month (e.g. "March 2026")
        month_col = None
        for c in month_cols:
            s = str(c).strip()
            if s in month_variants or s.lower() == month_str.lower():
                month_col = c
                break
            for fmt in ("%B %Y", "%b %Y", "%Y-%m"):
                try:
                    dt = datetime.strptime(s[:7] if fmt == "%Y-%m" else s, fmt)
                    if dt.year == target_year and dt.month == target_month:
                        month_col = c
                        break
                except Exception:
                    continue
            if month_col is not None:
                break
        if month_col is None:
            month_col = month_cols[0]
        out = {}
        for _, row in df.iterrows():
            label = str(row.get(key_col, "")).strip()
            if not label:
                continue
            val = row.get(month_col)
            v = _parse_budget_number(val)
            if metric_row_matches(label, "Total Gross Revenue"):
                out["online_gross_revenue"] = v
            elif metric_row_matches(label, "Returns"):
                out["returns"] = v
            elif metric_row_matches(label, "Return rate (%)", "Return rate"):
                out["return_rate_pct"] = v
            elif metric_row_matches(label, "Net Revenue"):
                out["online_net_revenue"] = out["total_net_revenue"] = v
            elif metric_row_matches(label, "Returning Customers"):
                out["returning_customers"] = int(round(v))
            elif metric_row_matches(label, "New Customers"):
                out["new_customers"] = int(round(v))
            elif metric_row_matches(label, "Online Marketing Spend"):
                out["marketing_spend"] = v
            elif metric_row_matches(label, "COS %", "COS"):
                out["online_cost_of_sale_3"] = v
            elif metric_row_matches(label, "aMER"):
                out["emer"] = v
        if out:
            return_rate = out.get("return_rate_pct", 0) or (
                (out.get("returns", 0) / out.get("online_gross_revenue", 1) * 100
                if out.get("online_gross_revenue")
                else 0
            ))
            return {
                "online_gross_revenue": out.get("online_gross_revenue", 0),
                "returns": out.get("returns", 0),
                "return_rate_pct": round(return_rate, 1),
                "online_net_revenue": out.get("online_net_revenue", 0),
                "retail_concept_store": 0.0,
                "retail_popups_outlets": 0.0,
                "retail_net_revenue": 0.0,
                "wholesale_net_revenue": 0.0,
                "total_net_revenue": out.get("total_net_revenue", out.get("online_net_revenue", 0)),
                "returning_customers": out.get("returning_customers", 0),
                "new_customers": out.get("new_customers", 0),
                "marketing_spend": out.get("marketing_spend", 0),
                "online_cost_of_sale_3": round(out.get("online_cost_of_sale_3", 0), 1),
                "emer": round(out.get("emer", 0), 1),
            }
    # Layout B: "Month" column -> rows are months, columns are metrics
    if "Month" in df.columns:
        month_col = "Month"
        df[month_col] = df[month_col].astype(str).str.strip().str.replace("\ufeff", "")
        row = None
        for _, r in df.iterrows():
            m_val = str(r.get(month_col, "")).strip()
            if not m_val:
                continue
            if m_val in month_variants or m_val.lower() == month_str.lower():
                row = r
                break
            for fmt in ("%B %Y", "%b %Y", "%Y-%m"):
                try:
                    dt = datetime.strptime(m_val[:7] if fmt == "%Y-%m" else m_val, fmt)
                    if dt.year == target_year and dt.month == target_month:
                        row = r
                        break
                except Exception:
                    continue
            if row is not None:
                break
        if row is not None:
            out = {}
            for col in df.columns:
                if col == month_col:
                    continue
                label = str(col).strip().lower()
                v = _parse_budget_number(row.get(col))
                if "total" in label and "gross" in label and "revenue" in label:
                    out["online_gross_revenue"] = v
                elif label == "returns":
                    out["returns"] = v
                elif "return rate" in label or "return rate (%)" in label:
                    out["return_rate_pct"] = v
                elif "net revenue" in label and "total" in label or label == "net revenue":
                    out["online_net_revenue"] = out["total_net_revenue"] = v
                elif "returning customers" in label:
                    out["returning_customers"] = int(round(v))
                elif "new customers" in label:
                    out["new_customers"] = int(round(v))
                elif "online marketing" in label or "marketing spend" in label:
                    out["marketing_spend"] = v
                elif "cos %" in label or label == "cos":
                    out["online_cost_of_sale_3"] = v
                elif label == "amer":
                    out["emer"] = v
            if out:
                return {
                    "online_gross_revenue": out.get("online_gross_revenue", 0),
                    "returns": out.get("returns", 0),
                    "return_rate_pct": round(out.get("return_rate_pct", 0), 1),
                    "online_net_revenue": out.get("online_net_revenue", 0),
                    "retail_concept_store": 0.0,
                    "retail_popups_outlets": 0.0,
                    "retail_net_revenue": 0.0,
                    "wholesale_net_revenue": 0.0,
                    "total_net_revenue": out.get("total_net_revenue", out.get("online_net_revenue", 0)),
                    "returning_customers": out.get("returning_customers", 0),
                    "new_customers": out.get("new_customers", 0),
                    "marketing_spend": out.get("marketing_spend", 0),
                    "online_cost_of_sale_3": round(out.get("online_cost_of_sale_3", 0), 1),
                    "emer": round(out.get("emer", 0), 1),
                }
    # Layout C: two columns (Metric name, Value) - use the single value column
    if len(df.columns) >= 2:
        key_col = df.columns[0]
        val_col = df.columns[1]
        out = {}
        for _, row in df.iterrows():
            label = str(row.get(key_col, "")).strip()
            if not label:
                continue
            v = _parse_budget_number(row.get(val_col))
            if metric_row_matches(label, "Total Gross Revenue"):
                out["online_gross_revenue"] = v
            elif metric_row_matches(label, "Returns"):
                out["returns"] = v
            elif metric_row_matches(label, "Return rate (%)", "Return rate"):
                out["return_rate_pct"] = v
            elif metric_row_matches(label, "Net Revenue"):
                out["online_net_revenue"] = out["total_net_revenue"] = v
            elif metric_row_matches(label, "Returning Customers"):
                out["returning_customers"] = int(round(v))
            elif metric_row_matches(label, "New Customers"):
                out["new_customers"] = int(round(v))
            elif metric_row_matches(label, "Online Marketing Spend"):
                out["marketing_spend"] = v
            elif metric_row_matches(label, "COS %", "COS"):
                out["online_cost_of_sale_3"] = v
            elif metric_row_matches(label, "aMER"):
                out["emer"] = v
        if out:
            return_rate = out.get("return_rate_pct", 0) or (
                (out.get("returns", 0) / out.get("online_gross_revenue", 1) * 100
                if out.get("online_gross_revenue")
                else 0
            ))
            return {
                "online_gross_revenue": out.get("online_gross_revenue", 0),
                "returns": out.get("returns", 0),
                "return_rate_pct": round(return_rate, 1),
                "online_net_revenue": out.get("online_net_revenue", 0),
                "retail_concept_store": 0.0,
                "retail_popups_outlets": 0.0,
                "retail_net_revenue": 0.0,
                "wholesale_net_revenue": 0.0,
                "total_net_revenue": out.get("total_net_revenue", out.get("online_net_revenue", 0)),
                "returning_customers": out.get("returning_customers", 0),
                "new_customers": out.get("new_customers", 0),
                "marketing_spend": out.get("marketing_spend", 0),
                "online_cost_of_sale_3": round(out.get("online_cost_of_sale_3", 0), 1),
                "emer": round(out.get("emer", 0), 1),
            }
    return {}


def _build_mtd_budget_from_budget_general(base_week: str, budget_result: Dict[str, Any]) -> Dict[str, Any]:
    """Build mtd_budget dict (table1 metric keys) from budget-general for the MTD month."""
    if "error" in budget_result or "table" not in budget_result:
        return {}
    table = budget_result["table"]
    # MTD month string from base_week end date (e.g. "2026-03-15" -> "March 2026")
    try:
        from weekly_report.src.periods.calculator import get_week_date_range
        week_range = get_week_date_range(base_week)
        end_date = week_range["end"]
        from datetime import datetime
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        month_str = end_dt.strftime("%B %Y")  # "March 2026"
    except Exception:
        return {}
    # Budget table: table[metric_name][month] = value. Month key may be "March 2026", "Mar 2026", "2026-03" etc.
    month_variants = [month_str, end_dt.strftime("%Y-%m"), end_dt.strftime("%b %Y"), end_dt.strftime("%B %Y")]
    target_year, target_month = end_dt.year, end_dt.month

    def _month_matches(m_key: str) -> bool:
        if not m_key or not str(m_key).strip():
            return False
        s = str(m_key).strip()
        for fmt in ("%B %Y", "%b %Y", "%Y-%m"):
            try:
                if fmt == "%Y-%m" and len(s) >= 7:
                    dt = datetime.strptime(s[:7], "%Y-%m")
                else:
                    dt = datetime.strptime(s, fmt)
                return dt.year == target_year and dt.month == target_month
            except Exception:
                continue
        return s.lower() == month_str.lower()

    def get_val(metric_name: str) -> float:
        by_month = table.get(metric_name) or {}
        for variant in month_variants:
            v = by_month.get(variant)
            if v is not None:
                return float(v)
        for m, val in by_month.items():
            if _month_matches(m):
                return float(val)
        return 0.0
    # Map budget metrics to table1 keys. Budget file row names (totals): Total Gross Revenue, Returns,
    # Return rate (%), Net Revenue, Returning Customers, New Customers, Online Marketing Spend, COS %, aMER.
    def get_budget_val(*preferred_names: str) -> float:
        for name in preferred_names:
            v = get_val(name)
            if v != 0.0 or name == preferred_names[-1]:
                return v
        key_lower = {k.strip().lower(): k for k in table.keys()}
        for name in preferred_names:
            k = key_lower.get(name.strip().lower())
            if k is not None:
                return get_val(k)
        return 0.0
    # Report metric <- budget row name(s)
    total_gross = get_budget_val("Total Gross Revenue")
    returns = get_budget_val("Returns")
    return_rate_pct = get_budget_val("Return rate (%)")
    if return_rate_pct == 0.0 and total_gross and total_gross > 0 and returns != 0.0:
        return_rate_pct = (returns / total_gross) * 100
    total_net = get_budget_val("Net Revenue")
    returning_customers = int(get_budget_val("Returning Customers"))
    new_customers = int(get_budget_val("New Customers"))
    marketing_spend = get_budget_val("Online Marketing Spend")
    cos_pct = get_budget_val("COS %", "COS")
    amer = get_budget_val("aMER")
    return {
        "online_gross_revenue": total_gross,
        "returns": returns,
        "return_rate_pct": round(return_rate_pct, 1),
        "online_net_revenue": total_net,
        "retail_concept_store": 0.0,
        "retail_popups_outlets": 0.0,
        "retail_net_revenue": 0.0,
        "wholesale_net_revenue": 0.0,
        "total_net_revenue": total_net,
        "returning_customers": returning_customers,
        "new_customers": new_customers,
        "marketing_spend": float(marketing_spend),
        "online_cost_of_sale_3": round(float(cos_pct), 1),
        "emer": round(float(amer), 1),
    }


@app.get("/api/budget-mtd-debug")
async def get_budget_mtd_debug(base_week: str = Query(..., description="Base ISO week e.g. 2026-11")):
    """Debug: show what budget data is loaded for MTD and why it might be empty."""
    try:
        if not validate_iso_week(base_week):
            raise HTTPException(status_code=400, detail="Invalid ISO week format")
        config = load_config(week=base_week)
        from weekly_report.src.periods.calculator import get_week_date_range
        week_range = get_week_date_range(base_week)
        end_dt = datetime.strptime(week_range["end"], "%Y-%m-%d")
        target_month = end_dt.strftime("%B %Y")
        root = Path(config.data_root).resolve()
        raw = root / "raw"
        tried_paths = []
        if raw.exists():
            week_dir = raw / base_week
            if week_dir.exists():
                tried_paths.append(str((week_dir / "budget").resolve()))
            year = int(base_week.split("-")[0])
            for p in sorted(raw.iterdir(), reverse=True):
                if p.is_dir() and p.name.startswith(str(year) + "-"):
                    tried_paths.append(str((p / "budget").resolve()))
                    break
            tried_paths.append(str((raw / "budget").resolve()))
        mtd_budget = _load_mtd_budget_direct(base_week, Path(config.data_root))
        has_values = bool(mtd_budget and any(v != 0 for k, v in mtd_budget.items() if isinstance(v, (int, float))))
        # Try to read first 2 rows for preview (same paths as loader)
        csv_path = None
        if raw.exists():
            for check in [raw / base_week / "budget", raw / "budget"]:
                if check.exists():
                    csvs = [f for f in check.glob("*.csv") if not f.name.startswith(".")]
                    if csvs:
                        csv_path = max(csvs, key=lambda f: f.stat().st_mtime)
                        break
            if csv_path is None:
                year = int(base_week.split("-")[0])
                for p in sorted(raw.iterdir(), reverse=True):
                    if p.is_dir() and p.name.startswith(str(year) + "-"):
                        bd = p / "budget"
                        if bd.exists():
                            csvs = [f for f in bd.glob("*.csv") if not f.name.startswith(".")]
                            if csvs:
                                csv_path = max(csvs, key=lambda f: f.stat().st_mtime)
                                break
        preview = {}
        if csv_path:
            try:
                df = pd.read_csv(csv_path, encoding="utf-8-sig", sep=None, engine="python", nrows=5)
                df.columns = df.columns.str.replace("\ufeff", "").str.strip()
                preview = {
                    "file": str(csv_path),
                    "columns": list(df.columns),
                    "row_count_preview": len(df),
                    "first_row": df.iloc[0].astype(str).to_dict() if len(df) > 0 else None,
                }
            except Exception as e:
                preview = {"file": str(csv_path), "error": str(e)}
        return {
            "ok": has_values,
            "base_week": base_week,
            "target_month": target_month,
            "data_root_resolved": str(root),
            "tried_paths": tried_paths,
            "mtd_budget_sample": dict(list((mtd_budget or {}).items())[:8]),
            "has_mtd_budget": has_values,
            "preview": preview,
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "base_week": base_week}


@app.get("/api/metrics/table1-mtd", response_model=MetricsMtdResponse)
async def get_table1_mtd_metrics(
    base_week: str = Query(..., description="Base ISO week like '2025-42'"),
):
    """Get Table 1 metrics for month-to-date report: MTD actual, MTD last year, MTD last month, YTD actual, YTD last year. Includes mtd_budget when budget data exists."""
    try:
        if not validate_iso_week(base_week):
            raise HTTPException(status_code=400, detail=f"Invalid ISO week format: {base_week}")
        config = load_config(week=base_week)
        result = calculate_table1_mtd_and_ytd(base_week, Path(config.data_root))
        periods = result["periods"]
        # Add MTD budget (current month): try direct CSV load first, then compute_budget_general
        mtd_budget = _load_mtd_budget_direct(base_week, Path(config.data_root))
        if not mtd_budget or all(v == 0 for k, v in mtd_budget.items() if isinstance(v, (int, float))):
            try:
                from weekly_report.src.compute.budget import compute_budget_general
                budget_result = compute_budget_general(base_week)
                if "error" not in budget_result:
                    mtd_budget = _build_mtd_budget_from_budget_general(base_week, budget_result)
            except Exception as budget_err:
                logger.debug(f"Budget fallback for MTD {base_week}: {budget_err}")
        if mtd_budget:
            periods["mtd_budget"] = mtd_budget
        return MetricsMtdResponse(periods=periods, date_ranges=result["date_ranges"])
    except FileNotFoundError as e:
        logger.warning(f"No data for table1-mtd {base_week}: {e}")
        raise HTTPException(
            status_code=404,
            detail=f"No data files found for week {base_week}. Upload data in Settings.",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        logger.error(f"Error getting MTD metrics for {base_week}: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/generate/pdf")
async def generate_pdf(request: GeneratePDFRequest):
    """Generate PDF with confirmed data."""
    
    try:
        # Validate input
        if not validate_iso_week(request.base_week):
            raise HTTPException(status_code=400, detail=f"Invalid ISO week format: {request.base_week}")
        
        # Calculate periods
        all_periods = get_periods_for_week(request.base_week)
        
        # Filter to requested periods
        filtered_periods = {k: v for k, v in all_periods.items() if k in request.periods}
        
        # Load config
        config = load_config(week=request.base_week)
        
        # Calculate metrics
        metrics_results = calculate_table1_for_periods(filtered_periods, Path(config.data_root))
        
        # Generate PDF using the professional builder
        output_path = config.reports_path / f"table1_{request.base_week}.pdf"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Build the PDF
        pdf_path = build_table1_pdf(metrics_results, filtered_periods, output_path)
        
        logger.info(f"Generated PDF: {pdf_path}")
        
        return {
            "success": True,
            "file_path": str(pdf_path),
            "download_url": f"/api/download/{pdf_path.name}"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating PDF for {request.base_week}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/download/{filename}")
async def download_file(filename: str):
    """Download generated PDF file."""
    
    try:
        # Security: only allow PDF files
        if not filename.endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are allowed")
        
        # Look for file in reports directory
        # Use output_root (defaults to ./reports) instead of data_root/reports
        config = load_config()
        reports_path = config.output_root
        
        # Try to extract week from filename (e.g., weekly_reports_2025-44.pdf -> 2025-44)
        week_from_filename = None
        if 'weekly_reports_' in filename:
            try:
                # Extract week from filename like "weekly_reports_2025-44.pdf"
                week_part = filename.replace('weekly_reports_', '').replace('.pdf', '')
                if validate_iso_week(week_part):
                    week_from_filename = week_part
            except:
                pass
        
        # If we have a week, check that specific week's directory first
        file_path = None
        if week_from_filename:
            specific_path = reports_path / week_from_filename / filename
            if specific_path.exists():
                file_path = specific_path
                logger.info(f"Found file at specific week path: {file_path}")
        
        # If not found, search all subdirectories
        if not file_path and reports_path.exists():
            for subdir in reports_path.iterdir():
                if subdir.is_dir():
                    potential_file = subdir / filename
                    if potential_file.exists():
                        file_path = potential_file
                        logger.info(f"Found file in subdirectory: {file_path}")
                        break
        
        # Also check root reports directory
        if not file_path:
            root_file = reports_path / filename
            if root_file.exists():
                file_path = root_file
                logger.info(f"Found file in root reports directory: {file_path}")
        
        if not file_path:
            logger.error(f"File not found: {filename}. Searched in: {reports_path}")
            raise HTTPException(status_code=404, detail=f"File not found: {filename}")
        
        return FileResponse(
            path=str(file_path),
            filename=filename,
            media_type='application/pdf'
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading file {filename}: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# Weekly Reports PDF endpoint removed
async def generate_weekly_reports_pdf(request: GeneratePDFRequest):
    """Generate a combined Weekly Reports PDF using Puppeteer (replaces screenshot-based approach)."""
    async def generate_with_progress():
        """Generator function that yields progress updates."""
        try:
            if not validate_iso_week(request.base_week):
                yield f"data: {json.dumps({'error': f'Invalid ISO week format: {request.base_week}'})}\n\n"
                return

            config = load_config(week=request.base_week)
            frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")

            logger.info(f"Starting PDF generation using Puppeteer for {request.base_week}")
            logger.info(f"Frontend URL: {frontend_url}")

            # Define pages to capture
            pages_to_capture = [
                {'name': 'Summary', 'step': 4},
                {'name': 'Top Markets', 'step': 5},
                {'name': 'Online KPIs', 'step': 6}
            ]
            total_steps = 8  # Starting + Initializing + Loading page + 3 pages + Combining + Complete
            
            # Send initial progress
            initial_progress = {
                'step': 'starting',
                'stepNumber': 1,
                'totalSteps': total_steps,
                'message': 'Starting PDF generation...',
                'currentPage': None,
                'percentage': 0
            }
            yield f"data: {json.dumps(initial_progress)}\n\n"
            
            # Create a queue to collect progress updates
            import asyncio
            progress_queue = asyncio.Queue()
            
            async def progress_callback_async(progress_data):
                """Async progress callback that puts data in queue."""
                await progress_queue.put(progress_data)
            
            async def progress_callback_async_wrapper(progress_data):
                """Async wrapper for progress callback that can be called from async context.
                
                This is called from screenshot_builder which runs in an async context,
                so we can directly await the queue put.
                """
                try:
                    await progress_queue.put(progress_data)
                    logger.debug(f"Progress data queued: {progress_data.get('step', 'unknown')} - {progress_data.get('message', '')}")
                except Exception as e:
                    logger.warning(f"Error queuing progress data: {e}")
                    # Fallback: just log the progress
                    logger.info(f"Progress: {progress_data.get('message', 'Unknown')}")
            
            def progress_callback_sync(progress_data):
                """Synchronous progress callback that schedules async callback.
                
                This is called from screenshot_builder which runs in an async context,
                but progress_callback is defined as sync. We need to ensure the task
                actually executes and puts data in the queue.
                """
                try:
                    # Since we're already in an async context (inside generate_pdf),
                    # we can directly schedule the async callback
                    loop = asyncio.get_running_loop()
                    if loop.is_running():
                        # Create a task to put data in queue
                        # Use ensure_future to ensure it runs
                        task = asyncio.ensure_future(progress_callback_async_wrapper(progress_data))
                        # Store task reference to prevent garbage collection
                        if not hasattr(progress_callback_sync, '_tasks'):
                            progress_callback_sync._tasks = []
                        progress_callback_sync._tasks.append(task)
                    else:
                        # If loop is not running, use run_until_complete (shouldn't happen)
                        loop.run_until_complete(progress_callback_async_wrapper(progress_data))
                except RuntimeError:
                    # No running loop, try to get default loop
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            task = asyncio.ensure_future(progress_callback_async_wrapper(progress_data))
                            if not hasattr(progress_callback_sync, '_tasks'):
                                progress_callback_sync._tasks = []
                            progress_callback_sync._tasks.append(task)
                        else:
                            loop.run_until_complete(progress_callback_async_wrapper(progress_data))
                    except Exception as e:
                        logger.warning(f"Error in progress callback: {e}")
                        # Fallback: just log the progress
                        logger.info(f"Progress: {progress_data.get('message', 'Unknown')}")
                except Exception as e:
                    logger.warning(f"Error in progress callback: {e}")
                    # Fallback: just log the progress
                    logger.info(f"Progress: {progress_data.get('message', 'Unknown')}")
            
            # Start PDF generation using Puppeteer
            async def generate_pdf():
                try:
                    import subprocess
                    from pathlib import Path
                    
                    # Send initial progress
                    await progress_queue.put({
                        'step': 'initializing',
                        'stepNumber': 2,
                        'totalSteps': total_steps,
                        'message': 'Initializing Puppeteer...',
                        'currentPage': None,
                        'percentage': 20
                    })
                    
                    # Determine frontend directory
                    current_file = Path(__file__)
                    project_root = current_file.parent.parent.parent  # weekly_report -> project root
                    frontend_dir = project_root / 'frontend'
                    script_path = frontend_dir / 'scripts' / 'makeReportPdf.ts'

                    logger.info(f"Looking for Puppeteer script at: {script_path}")
                    logger.info(f"Script exists: {script_path.exists()}")

                    if not script_path.exists():
                        raise FileNotFoundError(f"Puppeteer script not found at {script_path}")

                    # Set environment variables
                    env = os.environ.copy()
                    env["NEXT_PUBLIC_API_URL"] = frontend_url
                    env["NEXT_PUBLIC_FRONTEND_URL"] = frontend_url
                    env["FRONTEND_URL"] = frontend_url

                    logger.info(f"Starting Puppeteer script: npx tsx {script_path} {request.base_week}")
                    logger.info(f"Working directory: {frontend_dir}")

                    # Send progress before starting process
                    await progress_queue.put({
                        'step': 'loading',
                        'stepNumber': 3,
                        'totalSteps': total_steps,
                        'message': 'Starting Puppeteer process...',
                        'currentPage': None,
                        'percentage': 30
                    })

                    # Run Puppeteer script
                    process = await asyncio.create_subprocess_exec(
                        'npx', 'tsx', str(script_path), request.base_week,
                        cwd=str(frontend_dir),
                        env=env,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )

                    logger.info(f"Puppeteer process started with PID: {process.pid}")
                    
                    # Send progress after process starts
                    await progress_queue.put({
                        'step': 'loading',
                        'stepNumber': 3,
                        'totalSteps': total_steps,
                        'message': 'Puppeteer process started, loading pages...',
                        'currentPage': None,
                        'percentage': 40
                    })

                    # Read stdout line by line to track progress
                    import re
                    current_page_index = 0
                    stdout_lines = []
                    
                    # Send progress when we start reading output
                    await progress_queue.put({
                        'step': 'loading',
                        'stepNumber': 3,
                        'totalSteps': total_steps,
                        'message': 'Reading Puppeteer output...',
                        'currentPage': None,
                        'percentage': 45
                    })
                    
                    # Read stdout in real-time
                    current_page_index = 0
                    while True:
                        line = await process.stdout.readline()
                        if not line:
                            break
                        
                        line_str = line.decode('utf-8', errors='ignore').strip()
                        if not line_str:  # Skip empty lines
                            continue
                        stdout_lines.append(line_str)
                        logger.debug(f"Puppeteer stdout: {line_str}")
                        
                        # Send progress when we see first output
                        if len(stdout_lines) == 1:
                            await progress_queue.put({
                                'step': 'loading',
                                'stepNumber': 3,
                                'totalSteps': total_steps,
                                'message': 'Puppeteer is running...',
                                'currentPage': None,
                                'percentage': 50
                            })
                        
                        # Log all output for debugging
                        logger.debug(f"Puppeteer stdout line {len(stdout_lines)}: {line_str}")
                        
                        # Parse progress from Puppeteer output
                        # Match patterns like: "📄 [1/2] Generating Summary page..." or "[1/2] Generating Summary page..."
                        # Handle emojis - try multiple regex patterns
                        page_match = None
                        
                        # Check for "Loading [Page] page..." messages
                        loading_match = re.search(r'Loading\s+([A-Za-z\s]+?)\s+page', line_str, re.IGNORECASE)
                        if loading_match:
                            page_name = loading_match.group(1).strip()
                            # Find which page this is by matching against known pages
                            for idx, page_info in enumerate(pages_to_capture):
                                if page_info['name'].lower() == page_name.lower():
                                    page_num = idx + 1
                                    total_pages = len(pages_to_capture)
                                    current_page_index = idx
                                    # Progress during loading: slightly less than generating
                                    page_progress = 45 + (page_num - 1) * (35 / max(total_pages, 1)) - 3
                                    await progress_queue.put({
                                        'step': 'loading',
                                        'stepNumber': 3 + page_num,
                                        'totalSteps': total_steps,
                                        'message': f'Loading {page_name} page ({page_num}/{total_pages})...',
                                        'currentPage': page_name,
                                        'percentage': int(page_progress)
                                    })
                                    break
                        
                        # Check for "Page loaded, waiting for content..." messages
                        if 'page loaded' in line_str.lower() and 'waiting for content' in line_str.lower():
                            # This is the first step after navigation
                            if current_page_index < len(pages_to_capture):
                                page_info = pages_to_capture[current_page_index]
                                page_num = current_page_index + 1
                                total_pages = len(pages_to_capture)
                                page_progress = 45 + (page_num - 1) * (35 / max(total_pages, 1)) - 5
                                await progress_queue.put({
                                    'step': 'loading',
                                    'stepNumber': 3 + page_num,
                                    'totalSteps': total_steps,
                                    'message': f'Navigating to {page_info["name"]} page ({page_num}/{total_pages})...',
                                    'currentPage': page_info['name'],
                                    'percentage': int(page_progress)
                                })
                        
                        # Check for "content loaded" messages (more specific)
                        content_loaded_match = re.search(r'([A-Za-z\s]+?)\s+content\s+loaded', line_str, re.IGNORECASE)
                        if content_loaded_match:
                            page_name = content_loaded_match.group(1).strip()
                            for idx, page_info in enumerate(pages_to_capture):
                                if page_info['name'].lower() == page_name.lower():
                                    page_num = idx + 1
                                    total_pages = len(pages_to_capture)
                                    page_progress = 48 + (page_num - 1) * (35 / max(total_pages, 1))
                                    await progress_queue.put({
                                        'step': 'generating',
                                        'stepNumber': 3 + page_num,
                                        'totalSteps': total_steps,
                                        'message': f'{page_name} content loaded ({page_num}/{total_pages})...',
                                        'currentPage': page_name,
                                        'percentage': int(page_progress)
                                    })
                                    break
                        
                        # Check for "Generating PDF for [Page]..." messages
                        generating_pdf_match = re.search(r'Generating\s+PDF\s+for\s+([A-Za-z\s]+?)\.\.\.', line_str, re.IGNORECASE)
                        if generating_pdf_match:
                            page_name = generating_pdf_match.group(1).strip()
                            for idx, page_info in enumerate(pages_to_capture):
                                if page_info['name'].lower() == page_name.lower():
                                    page_num = idx + 1
                                    total_pages = len(pages_to_capture)
                                    page_progress = 50 + (page_num - 1) * (35 / max(total_pages, 1))
                                    await progress_queue.put({
                                        'step': 'generating',
                                        'stepNumber': 3 + page_num,
                                        'totalSteps': total_steps,
                                        'message': f'Generating PDF for {page_name} ({page_num}/{total_pages})...',
                                        'currentPage': page_name,
                                        'percentage': int(page_progress)
                                    })
                                    break
                        
                        # Try pattern 1: with spaces after brackets
                        page_match = re.search(r'\[(\d+)/(\d+)\]\s+Generating\s+(.+?)\s+page', line_str)
                        if not page_match:
                            # Try pattern 2: more flexible spacing
                            page_match = re.search(r'\[(\d+)/(\d+)\].*?Generating\s+(.+?)\s+page', line_str)
                        if not page_match:
                            # Try pattern 3: extract page name differently (handle emojis)
                            page_match = re.search(r'\[(\d+)/(\d+)\].*?Generating\s+([A-Za-z\s]+?)\s+page', line_str)
                        
                        if page_match:
                            page_num = int(page_match.group(1))
                            total_pages = int(page_match.group(2))
                            page_name = page_match.group(3).strip()
                            
                            # Update current_page_index based on parsed page number
                            current_page_index = page_num - 1
                            
                            # Calculate progress based on page number
                            # Steps: Starting(0%), Init(20%), Load(40%), Pages(45-80%), Combining(90%), Complete(100%)
                            # Each page gets ~11.67% between 45% and 80% (35% / 3 pages)
                            page_progress = 45 + (page_num - 1) * (35 / max(total_pages, 1))
                            
                            logger.info(f"✅ Parsed page progress: {page_name} ({page_num}/{total_pages})")
                            await progress_queue.put({
                                'step': 'generating',
                                'stepNumber': 3 + page_num,  # Step 4 for page 1, Step 5 for page 2, Step 6 for page 3
                                'totalSteps': total_steps,
                                'message': f'Generating {page_name} page ({page_num}/{total_pages})...',
                                'currentPage': page_name,
                                'percentage': int(page_progress)
                            })
                        
                        # Check for page PDF generated messages (with or without emoji)
                        page_generated_match = None
                        page_generated_match = re.search(r'\[(\d+)/(\d+)\]\s+(.+?)\s+page\s+generated', line_str, re.IGNORECASE)
                        if not page_generated_match:
                            # Try without explicit "page generated" text
                            page_generated_match = re.search(r'\[(\d+)/(\d+)\]\s+(.+?)\s+generated\s+\d+\s+bytes', line_str, re.IGNORECASE)
                        if page_generated_match:
                            page_num = int(page_generated_match.group(1))
                            total_pages = int(page_generated_match.group(2))
                            page_name = page_generated_match.group(3).strip()
                            
                            # Progress slightly higher when page PDF is generated
                            # Each page gets ~11.67% between 50% and 85% (35% / 3 pages)
                            page_progress = 50 + (page_num - 1) * (35 / max(total_pages, 1))
                            
                            logger.info(f"✅ Parsed page generated: {page_name} ({page_num}/{total_pages})")
                            await progress_queue.put({
                                'step': 'generating',
                                'stepNumber': 3 + page_num,
                                'totalSteps': total_steps,
                                'message': f'{page_name} page PDF generated ({page_num}/{total_pages})',
                                'currentPage': page_name,
                                'percentage': int(page_progress)
                            })
                        
                        # Check for combining messages (with or without emoji)
                        if 'Combining' in line_str and ('pages' in line_str.lower() or 'PDF' in line_str):
                            await progress_queue.put({
                                'step': 'combining',
                                'stepNumber': total_steps - 1,
                                'totalSteps': total_steps,
                                'message': 'Combining pages into final PDF...',
                                'currentPage': None,
                                'percentage': 90
                            })
                        
                        # Check for final success message
                        if 'PDF generated successfully' in line_str:
                            await progress_queue.put({
                                'step': 'complete',
                                'stepNumber': total_steps,
                                'totalSteps': total_steps,
                                'message': 'PDF generation complete!',
                                'currentPage': None,
                                'percentage': 100
                            })
                    
                    # Read stderr in parallel while waiting for process
                    stderr_lines = []
                    async def read_stderr():
                        while True:
                            line = await process.stderr.readline()
                            if not line:
                                break
                            stderr_line = line.decode('utf-8', errors='ignore').strip()
                            if stderr_line:
                                stderr_lines.append(stderr_line)
                                logger.warning(f"Puppeteer stderr: {stderr_line}")
                    
                    # Start reading stderr
                    stderr_task = asyncio.create_task(read_stderr())
                    
                    # Wait for process to complete
                    await process.wait()
                    
                    # Wait a bit for stderr to finish reading
                    try:
                        await asyncio.wait_for(stderr_task, timeout=2.0)
                    except asyncio.TimeoutError:
                        logger.warning("Stderr reading timed out, continuing...")

                    # Log script output for debugging
                    if stdout_lines:
                        stdout_text = '\n'.join(stdout_lines)
                        logger.info(f"Puppeteer script stdout: {stdout_text}")
                    if stderr_lines:
                        stderr_text = '\n'.join(stderr_lines)
                        logger.warning(f"Puppeteer script stderr: {stderr_text}")

                    logger.info(f"Puppeteer process finished with return code: {process.returncode}")

                    if process.returncode != 0:
                        # Check if there's a timeout error in stderr
                        timeout_error = False
                        if stderr_lines:
                            for line in stderr_lines:
                                if 'TimeoutError' in line or 'timeout' in line.lower():
                                    timeout_error = True
                                    break
                        
                        if timeout_error:
                            error_msg = "PDF generation timed out. The page took too long to load. Please try again or check if the frontend server is running properly."
                        else:
                            stderr_text = '\n'.join(stderr_lines) if stderr_lines else 'Unknown error'
                            error_msg = f"Puppeteer script failed: {stderr_text}"
                        
                        logger.error(error_msg)
                        
                        # Send error to progress queue
                        await progress_queue.put({
                            'step': 'error',
                            'stepNumber': 0,
                            'totalSteps': total_steps,
                            'message': error_msg,
                            'currentPage': None,
                            'percentage': 0,
                            'error': error_msg
                        })
                        
                        raise RuntimeError(error_msg)

                    # Determine output path - use absolute path
                    pdf_path = config.output_root.resolve() / request.base_week / 'weekly-report.pdf'
                    
                    logger.info(f"Checking for PDF at: {pdf_path}")
                    logger.info(f"PDF path exists: {pdf_path.exists()}")
                    
                    if not pdf_path.exists():
                        # Wait a bit more - PDF might still be generating
                        import time
                        for i in range(5):
                            time.sleep(1)
                            if pdf_path.exists():
                                break
                            logger.info(f"Waiting for PDF... ({i+1}/5)")
                        
                        if not pdf_path.exists():
                            # List directory contents for debugging
                            week_dir = config.output_root.resolve() / request.base_week
                            if week_dir.exists():
                                files = list(week_dir.glob('*'))
                                logger.error(f"Files in {week_dir}: {[f.name for f in files]}")
                            raise FileNotFoundError(f"PDF file not found at expected path: {pdf_path} (absolute: {pdf_path.resolve()})")

                    # Only send complete result if we haven't already sent it from stdout parsing
                    # Check if we already sent a complete message
                    final_result_sent = False
                    for line in stdout_lines:
                        if 'PDF generated successfully' in line:
                            final_result_sent = True
                            break
                    
                    # If we didn't send complete from stdout, send it now
                    if not final_result_sent:
                        await progress_queue.put({
                            'step': 'complete',
                            'stepNumber': total_steps,
                            'totalSteps': total_steps,
                            'message': 'PDF generation complete!',
                            'currentPage': None,
                            'percentage': 100,
                            'result': {
                                'success': True,
                                'file_path': str(pdf_path),
                                'download_url': f"/api/download/{pdf_path.name}",
                            }
                        })
                    else:
                        # Just send the result part if we already sent complete
                        await progress_queue.put({
                            'step': 'complete',
                            'stepNumber': total_steps,
                            'totalSteps': total_steps,
                            'message': 'PDF generation complete!',
                            'currentPage': None,
                            'percentage': 100,
                            'result': {
                                'success': True,
                                'file_path': str(pdf_path),
                                'download_url': f"/api/download/{pdf_path.name}",
                            }
                        })
                except Exception as e:
                    logger.error(f"❌ Error building PDF with Puppeteer: {e}")
                    import traceback
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    error_msg = str(e)
                    await progress_queue.put({
                        'step': 'error',
                        'stepNumber': 0,
                        'totalSteps': total_steps,
                        'message': f'Error: {error_msg}',
                        'currentPage': None,
                        'percentage': 0,
                        'error': error_msg,
                        'result': None
                    })
            
            # Start PDF generation task
            pdf_task = asyncio.create_task(generate_pdf())
            
            # Initialize task list for progress callback
            progress_callback_sync._tasks = []
            
            # Yield progress updates as they come in
            result_received = False
            logger.info("📊 Starting progress update loop...")
            while True:
                try:
                    # Wait for progress update with shorter timeout to check if task is still running
                    try:
                        logger.debug(f"⏳ Waiting for progress update from queue (timeout: 10s)...")
                        progress_data = await asyncio.wait_for(progress_queue.get(), timeout=10.0)
                        logger.info(f"📨 Received progress update: {progress_data.get('step')} - {progress_data.get('message')} ({progress_data.get('percentage')}%)")
                    except asyncio.TimeoutError:
                        # Check if task is still running
                        logger.debug(f"⏱️ Timeout waiting for progress, checking task status...")
                        if pdf_task.done():
                            # Task completed - check if it succeeded or failed
                            try:
                                await pdf_task  # This will raise exception if task failed
                                # Task succeeded but we didn't get final progress - wait a bit more
                                try:
                                    progress_data = await asyncio.wait_for(progress_queue.get(), timeout=3.0)
                                except asyncio.TimeoutError:
                                    # Task done but no progress - send error
                                    logger.error("Task completed but no progress received")
                                    yield f"data: {json.dumps({'error': 'PDF generation task completed but no progress received', 'step': 'error'})}\n\n"
                                    break
                            except Exception as task_error:
                                # Task failed - send error
                                logger.error(f"PDF task failed: {task_error}")
                                yield f"data: {json.dumps({'error': str(task_error), 'step': 'error'})}\n\n"
                                break
                        else:
                            # Task still running, send a heartbeat to show we're still alive
                            heartbeat = {
                                'step': 'processing',
                                'stepNumber': 3,
                                'totalSteps': total_steps,
                                'message': 'Puppeteer is processing...',
                                'currentPage': None,
                                'percentage': 45
                            }
                            yield f"data: {json.dumps(heartbeat)}\n\n"
                            continue
                    
                    # Yield the progress update
                    yield f"data: {json.dumps(progress_data)}\n\n"
                    
                    # If we got an error, we're done (error will be thrown on frontend)
                    if progress_data.get('step') == 'error':
                        # Error step - break immediately so frontend can handle it
                        logger.info("✅ Error step received, ending stream")
                        break
                    
                    # If we got a result/complete with result, we're done
                    if progress_data.get('step') == 'complete':
                        # Check if result is included
                        if progress_data.get('result'):
                            logger.info(f"✅ Complete step received with result: {progress_data.get('result')}")
                            result_received = True
                            break
                        else:
                            logger.warning("⚠️ Complete step received but no result - waiting for more data...")
                            # Continue waiting in case result comes in next message
                        
                except Exception as e:
                    logger.error(f"Error in progress loop: {e}")
                    error_data = {
                        'step': 'error',
                        'stepNumber': 0,
                        'totalSteps': total_steps,
                        'message': f'Progress loop error: {str(e)}',
                        'currentPage': None,
                        'percentage': 0,
                        'error': str(e),
                        'result': None
                    }
                    yield f"data: {json.dumps(error_data)}\n\n"
                    break
            
            # Final check: if task completed but we didn't get result, try to get it from task
            if not result_received and pdf_task.done():
                try:
                    pdf_path = await pdf_task
                    # Task succeeded but result wasn't sent via progress - this shouldn't happen
                    # as the task should always send result via progress_queue
                    logger.warning("PDF task completed but no result received via progress queue")
                    if not result_received:
                        error_data = {
                            'step': 'error',
                            'stepNumber': 0,
                            'totalSteps': total_steps,
                            'message': 'PDF generation completed but no result received',
                            'currentPage': None,
                            'percentage': 0,
                            'error': 'PDF generation completed but no result received',
                            'result': None
                        }
                        yield f"data: {json.dumps(error_data)}\n\n"
                except Exception as task_error:
                    logger.error(f"PDF task failed: {task_error}")
                    if not result_received:
                        error_data = {
                            'step': 'error',
                            'stepNumber': 0,
                            'totalSteps': total_steps,
                            'message': f'PDF task error: {str(task_error)}',
                            'currentPage': None,
                            'percentage': 0,
                            'error': str(task_error),
                            'result': None
                        }
                        yield f"data: {json.dumps(error_data)}\n\n"
            
            # Wait for PDF task to complete (in case it's still running)
            try:
                await asyncio.wait_for(pdf_task, timeout=2.0)
            except asyncio.TimeoutError:
                logger.warning("PDF task still running after progress loop ended")
            except Exception as e:
                logger.error(f"Error waiting for PDF task: {e}")
                # Send error if task failed (only if we haven't already sent one)
                if not result_received:
                    error_data = {
                        'step': 'error',
                        'stepNumber': 0,
                        'totalSteps': total_steps,
                        'message': f'PDF task error: {str(e)}',
                        'currentPage': None,
                        'percentage': 0,
                        'error': str(e),
                        'result': None
                    }
                    yield f"data: {json.dumps(error_data)}\n\n"
            
        except Exception as e:
            logger.error(f"Error in PDF generation stream: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(
        generate_with_progress(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@app.post("/api/cache/clear")
async def clear_cache():
    """Clear all cached metrics and raw data."""
    try:
        metrics_cache.clear()
        # Also clear raw data cache
        from weekly_report.src.metrics.table1 import raw_data_cache
        raw_data_cache.clear()
        return {"success": True, "message": "All caches cleared successfully"}
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear cache")


@app.post("/api/cache/invalidate/{base_week}")
async def invalidate_cache(base_week: str):
    """Invalidate cache for a specific week."""
    try:
        metrics_cache.invalidate(base_week)
        return {"success": True, "message": f"Cache invalidated for {base_week}"}
    except Exception as e:
        logger.error(f"Error invalidating cache for {base_week}: {e}")
        raise HTTPException(status_code=500, detail="Failed to invalidate cache")


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "weekly-report-api"}


@app.get("/api/debug/markets")
async def debug_markets(
    base_week: str = Query(..., description="Base ISO week like '2025-42'"),
    num_weeks: int = Query(8, description="Number of weeks to analyze")
):
    """Debug endpoint to see raw markets data."""
    
    config = load_config(week=base_week)
    markets_data = calculate_top_markets_for_weeks(base_week, num_weeks, config.data_root)
    
    # Return raw data without Pydantic
    return markets_data


def _empty_markets_response(base_week: str) -> MarketsResponse:
    """Return a valid empty markets response so the UI can finish loading instead of hanging."""
    return MarketsResponse(
        markets=[],
        period_info={"latest_week": base_week, "latest_dates": ""},
    )


@app.get("/api/markets/top", response_model=MarketsResponse)
async def get_top_markets(
    base_week: str = Query(..., description="Base ISO week like '2025-42'"),
    num_weeks: int = Query(8, description="Number of weeks to analyze"),
    recalculate: bool = Query(False, description="If true, skip Supabase cache and recalculate (for fresh Y/Y data)")
):
    """Get top markets based on average Online Gross Revenue over last N weeks. Reads from Supabase if available."""
    
    try:
        # Validate input
        if not validate_iso_week(base_week):
            raise HTTPException(status_code=400, detail=f"Invalid ISO week format: {base_week}")
        
        if num_weeks < 1 or num_weeks > 52:
            raise HTTPException(status_code=400, detail=f"Number of weeks must be between 1 and 52")
        
        # Try to read from Supabase first (unless recalculate=true) and only when Supabase is enabled
        if not recalculate and _supabase_enabled():
            found, markets_data = get_metrics_from_supabase(base_week, "markets")
            if found:
                logger.info(f"✅ Returning markets from Supabase for {base_week}")
                response = MarketsResponse(**markets_data)
                return response
        
        # Calculate top markets (fresh or fallback)
        config = load_config(week=base_week)
        markets_data = calculate_top_markets_for_weeks(base_week, num_weeks, config.data_root)
        
        # Debug: Log raw data (only when we have at least one market)
        if markets_data.get("markets"):
            logger.info(f"Raw data - First market weeks count: {len(markets_data['markets'][0]['weeks'])}")
            logger.info(f"Raw data - Sample weeks: {list(markets_data['markets'][0]['weeks'].keys())[:5]}")
        
        response = MarketsResponse(**markets_data)
        if response.markets:
            logger.info(f"After Pydantic - First market weeks count: {len(response.markets[0].weeks)}")
        
        return response
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        logger.warning(f"No data for top markets {base_week}: {e}")
        return _empty_markets_response(base_week)
    except Exception as e:
        import traceback
        logger.warning(f"Error getting top markets for {base_week}, returning empty: {e}")
        logger.debug(traceback.format_exc())
        return _empty_markets_response(base_week)


@app.get("/api/online-kpis", response_model=OnlineKPIsResponse)
async def get_online_kpis(
    base_week: str = Query(..., description="Base ISO week like '2025-42'"),
    num_weeks: int = Query(8, description="Number of weeks to analyze")
):
    """Get Online KPIs for the last N weeks. Reads from Supabase if available."""
    
    try:
        # Validate input
        if not validate_iso_week(base_week):
            raise HTTPException(status_code=400, detail=f"Invalid ISO week format: {base_week}")
        
        if num_weeks < 1 or num_weeks > 52:
            raise HTTPException(status_code=400, detail=f"Number of weeks must be between 1 and 52")
        
        # Try to read from Supabase first
        found, kpis_data = get_metrics_from_supabase(base_week, "kpis")
        if found:
            logger.info(f"✅ Returning KPIs from Supabase for {base_week}")
            response = OnlineKPIsResponse(**kpis_data)
            return response
        
        # Fallback: Calculate Online KPIs
        config = load_config(week=base_week)
        kpis_data = calculate_online_kpis_for_weeks(base_week, num_weeks, config.data_root)
        
        response = OnlineKPIsResponse(**kpis_data)
        
        return response
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        logger.error(f"Error getting Online KPIs for {base_week}: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/contribution", response_model=ContributionResponse)
async def get_contribution(
    base_week: str = Query(..., description="Base ISO week like '2025-42'"),
    num_weeks: int = Query(8, description="Number of weeks to analyze")
):
    """Get Contribution metrics for the last N weeks."""
    
    try:
        if not validate_iso_week(base_week):
            raise HTTPException(status_code=400, detail=f"Invalid ISO week format: {base_week}")
        
        if num_weeks < 1 or num_weeks > 52:
            raise HTTPException(status_code=400, detail=f"Number of weeks must be between 1 and 52")
        
        config = load_config(week=base_week)
        contribution_data = calculate_contribution_for_weeks(base_week, num_weeks, config.data_root)
        
        response = ContributionResponse(**contribution_data)
        
        return response
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        logger.error(f"Error getting Contribution metrics for {base_week}: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/gender-sales", response_model=GenderSalesResponse)
async def get_gender_sales(
    base_week: str = Query(..., description="Base ISO week like '2025-42'"),
    num_weeks: int = Query(8, description="Number of weeks to analyze")
):
    """Get Gender Sales metrics for the last N weeks."""
    
    try:
        if not validate_iso_week(base_week):
            raise HTTPException(status_code=400, detail=f"Invalid ISO week format: {base_week}")
        
        if num_weeks < 1 or num_weeks > 52:
            raise HTTPException(status_code=400, detail=f"Number of weeks must be between 1 and 52")
        
        config = load_config(week=base_week)
        gender_sales_data = calculate_gender_sales_for_weeks(base_week, num_weeks, config.data_root)
        
        # Format response
        response = GenderSalesResponse(
            gender_sales=gender_sales_data,
            period_info={
                "latest_week": base_week,
                "latest_dates": "N/A"  # Could add date range if needed
            }
        )
        
        return response
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        logger.error(f"Error getting Gender Sales metrics for {base_week}: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/men-category-sales", response_model=MenCategorySalesResponse)
async def get_men_category_sales(
    base_week: str = Query(..., description="Base ISO week like '2025-42'"),
    num_weeks: int = Query(8, description="Number of weeks to analyze")
):
    """Get Men Category Sales metrics for the last N weeks."""
    
    try:
        if not validate_iso_week(base_week):
            raise HTTPException(status_code=400, detail=f"Invalid ISO week format: {base_week}")
        
        if num_weeks < 1 or num_weeks > 52:
            raise HTTPException(status_code=400, detail=f"Number of weeks must be between 1 and 52")
        
        config = load_config(week=base_week)
        men_category_sales_data = calculate_men_category_sales_for_weeks(base_week, num_weeks, config.data_root)
        
        # Format response
        response = MenCategorySalesResponse(
            men_category_sales=men_category_sales_data,
            period_info={
                "latest_week": base_week,
                "latest_dates": "N/A"  # Could add date range if needed
            }
        )
        
        return response
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        logger.error(f"Error getting Men Category Sales metrics for {base_week}: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/women-category-sales", response_model=WomenCategorySalesResponse)
async def get_women_category_sales(
    base_week: str = Query(..., description="Base ISO week like '2025-42'"),
    num_weeks: int = Query(8, description="Number of weeks to analyze")
):
    """Get Women Category Sales metrics for the last N weeks."""
    
    try:
        if not validate_iso_week(base_week):
            raise HTTPException(status_code=400, detail=f"Invalid ISO week format: {base_week}")
        
        if num_weeks < 1 or num_weeks > 52:
            raise HTTPException(status_code=400, detail=f"Number of weeks must be between 1 and 52")
        
        config = load_config(week=base_week)
        women_category_sales_data = calculate_women_category_sales_for_weeks(base_week, num_weeks, config.data_root)
        
        # Format response
        response = WomenCategorySalesResponse(
            women_category_sales=women_category_sales_data,
            period_info={
                "latest_week": base_week,
                "latest_dates": "N/A"  # Could add date range if needed
            }
        )
        
        return response
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        logger.error(f"Error getting Women Category Sales metrics for {base_week}: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/category-sales", response_model=CategorySalesResponse)
async def get_category_sales(
    base_week: str = Query(..., description="Base ISO week like '2025-42'"),
    num_weeks: int = Query(8, description="Number of weeks to analyze")
):
    """Get Category Sales metrics for the last N weeks."""
    
    try:
        if not validate_iso_week(base_week):
            raise HTTPException(status_code=400, detail=f"Invalid ISO week format: {base_week}")
        
        if num_weeks < 1 or num_weeks > 52:
            raise HTTPException(status_code=400, detail=f"Number of weeks must be between 1 and 52")
        
        config = load_config(week=base_week)
        category_sales_data = calculate_category_sales_for_weeks(base_week, num_weeks, config.data_root)
        
        # Format response
        response = CategorySalesResponse(
            category_sales=category_sales_data,
            period_info={
                "latest_week": base_week,
                "latest_dates": "N/A"  # Could add date range if needed
            }
        )
        
        # Add cache headers for better performance
        return Response(
            content=response.model_dump_json(),
            media_type="application/json",
            headers={
                "Cache-Control": "public, max-age=600",  # Cache for 10 minutes
            }
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        logger.error(f"Error getting Category Sales metrics for {base_week}: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/top-products", response_model=TopProductsResponse)
async def get_top_products(
    base_week: str = Query(..., description="Base ISO week like '2025-42'"),
    num_weeks: int = Query(1, description="Number of weeks to analyze"),
    top_n: int = Query(30, description="Number of top products to return"),
    customer_type: str = Query('new', description="Customer type: 'new' or 'returning'")
):
    """Get Top Products metrics for the last N weeks."""
    
    try:
        if not validate_iso_week(base_week):
            raise HTTPException(status_code=400, detail=f"Invalid ISO week format: {base_week}")
        
        if num_weeks < 1 or num_weeks > 52:
            raise HTTPException(status_code=400, detail=f"Number of weeks must be between 1 and 52")
        
        if top_n < 1 or top_n > 100:
            raise HTTPException(status_code=400, detail=f"Number of top products must be between 1 and 100")
        
        if customer_type not in ['new', 'returning']:
            raise HTTPException(status_code=400, detail=f"Customer type must be 'new' or 'returning'")
        
        config = load_config(week=base_week)
        top_products_data = calculate_top_products_for_weeks(base_week, num_weeks, config.data_root, top_n, customer_type)
        
        # Format response
        response = TopProductsResponse(
            top_products=top_products_data,
            period_info={
                "latest_week": base_week,
                "latest_dates": "N/A"  # Could add date range if needed
            }
        )
        
        return response
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        logger.error(f"Error getting Top Products metrics for {base_week}: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/top-products-gender", response_model=TopProductsResponse)
async def get_top_products_by_gender(
    base_week: str = Query(..., description="Base ISO week like '2025-42'"),
    num_weeks: int = Query(1, description="Number of weeks to analyze"),
    top_n: int = Query(30, description="Number of top products to return"),
    gender_filter: str = Query('men', description="Gender filter: 'men' or 'women'")
):
    """Get Top Products by Gender metrics for the last N weeks."""
    
    try:
        if not validate_iso_week(base_week):
            raise HTTPException(status_code=400, detail=f"Invalid ISO week format: {base_week}")
        
        if num_weeks < 1 or num_weeks > 52:
            raise HTTPException(status_code=400, detail=f"Number of weeks must be between 1 and 52")
        
        if top_n < 1 or top_n > 100:
            raise HTTPException(status_code=400, detail=f"Number of top products must be between 1 and 100")
        
        if gender_filter not in ['men', 'women']:
            raise HTTPException(status_code=400, detail=f"Gender filter must be 'men' or 'women'")
        
        config = load_config(week=base_week)
        top_products_data = calculate_top_products_by_gender_for_weeks(base_week, num_weeks, config.data_root, gender_filter, top_n)
        
        # Format response
        response = TopProductsResponse(
            top_products=top_products_data,
            period_info={
                "latest_week": base_week,
                "latest_dates": "N/A"  # Could add date range if needed
            }
        )
        
        return response
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        logger.error(f"Error getting Top Products by Gender metrics for {base_week}: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/sessions-per-country", response_model=SessionsPerCountryResponse)
async def get_sessions_per_country(
    base_week: str = Query(..., description="Base ISO week like '2025-42'"),
    num_weeks: int = Query(8, description="Number of weeks to analyze")
):
    """Get Sessions per Country metrics for the last N weeks."""
    
    try:
        if not validate_iso_week(base_week):
            raise HTTPException(status_code=400, detail=f"Invalid ISO week format: {base_week}")
        
        if num_weeks < 1 or num_weeks > 52:
            raise HTTPException(status_code=400, detail=f"Number of weeks must be between 1 and 52")
        
        config = load_config(week=base_week)
        sessions_data = calculate_sessions_per_country_for_weeks(base_week, num_weeks, config.data_root)
        
        # Format response
        response = SessionsPerCountryResponse(
            sessions_per_country=sessions_data,
            period_info={
                "latest_week": base_week,
                "latest_dates": "N/A"  # Could add date range if needed
            }
        )
        
        return response
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        logger.error(f"Error getting Sessions per Country metrics for {base_week}: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/conversion-per-country", response_model=ConversionPerCountryResponse)
async def get_conversion_per_country(
    base_week: str = Query(..., description="Base ISO week like '2025-42'"),
    num_weeks: int = Query(8, description="Number of weeks to analyze")
):
    """Get Conversion per Country metrics for the last N weeks."""
    
    try:
        if not validate_iso_week(base_week):
            raise HTTPException(status_code=400, detail=f"Invalid ISO week format: {base_week}")
        
        if num_weeks < 1 or num_weeks > 52:
            raise HTTPException(status_code=400, detail=f"Number of weeks must be between 1 and 52")
        
        config = load_config(week=base_week)
        conversion_data = calculate_conversion_per_country_for_weeks(base_week, num_weeks, config.data_root)
        
        # Format response
        response = ConversionPerCountryResponse(
            conversion_per_country=conversion_data,
            period_info={
                "latest_week": base_week,
                "latest_dates": "N/A"
            }
        )
        
        return response
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        logger.error(f"Error getting Conversion per Country metrics for {base_week}: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/new-customers-per-country", response_model=NewCustomersPerCountryResponse)
async def get_new_customers_per_country(
    base_week: str = Query(..., description="Base ISO week like '2025-42'"),
    num_weeks: int = Query(8, description="Number of weeks to analyze")
):
    """Get New Customers per Country metrics for the last N weeks."""
    
    try:
        if not validate_iso_week(base_week):
            raise HTTPException(status_code=400, detail=f"Invalid ISO week format: {base_week}")
        
        if num_weeks < 1 or num_weeks > 52:
            raise HTTPException(status_code=400, detail=f"Number of weeks must be between 1 and 52")
        
        config = load_config(week=base_week)
        new_customers_data = calculate_new_customers_per_country_for_weeks(base_week, num_weeks, config.data_root)
        
        # Format response
        response = NewCustomersPerCountryResponse(
            new_customers_per_country=new_customers_data,
            period_info={
                "latest_week": base_week,
                "latest_dates": "N/A"
            }
        )
        
        return response
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        logger.error(f"Error getting New Customers per Country metrics for {base_week}: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/returning-customers-per-country", response_model=ReturningCustomersPerCountryResponse)
async def get_returning_customers_per_country(
    base_week: str = Query(..., description="Base ISO week like '2025-42'"),
    num_weeks: int = Query(8, description="Number of weeks to analyze")
):
    """Get Returning Customers per Country metrics for the last N weeks."""
    
    try:
        if not validate_iso_week(base_week):
            raise HTTPException(status_code=400, detail=f"Invalid ISO week format: {base_week}")
        
        if num_weeks < 1 or num_weeks > 52:
            raise HTTPException(status_code=400, detail=f"Number of weeks must be between 1 and 52")
        
        config = load_config(week=base_week)
        returning_customers_data = calculate_returning_customers_per_country_for_weeks(base_week, num_weeks, config.data_root)
        
        # Format response
        response = ReturningCustomersPerCountryResponse(
            returning_customers_per_country=returning_customers_data,
            period_info={
                "latest_week": base_week,
                "latest_dates": "N/A"
            }
        )
        
        return response
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        logger.error(f"Error getting Returning Customers per Country metrics for {base_week}: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/aov-new-customers-per-country", response_model=AOVNewCustomersPerCountryResponse)
async def get_aov_new_customers_per_country(
    base_week: str = Query(..., description="Base ISO week like '2025-42'"),
    num_weeks: int = Query(8, description="Number of weeks to analyze")
):
    """Get AOV for New Customers per Country metrics for the last N weeks."""
    
    try:
        if not validate_iso_week(base_week):
            raise HTTPException(status_code=400, detail=f"Invalid ISO week format: {base_week}")
        
        if num_weeks < 1 or num_weeks > 52:
            raise HTTPException(status_code=400, detail=f"Number of weeks must be between 1 and 52")
        
        config = load_config(week=base_week)
        aov_data = calculate_aov_new_customers_per_country_for_weeks(base_week, num_weeks, config.data_root)
        
        # Format response
        response = AOVNewCustomersPerCountryResponse(
            aov_new_customers_per_country=aov_data,
            period_info={
                "latest_week": base_week,
                "latest_dates": "N/A"
            }
        )
        
        return response
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        logger.error(f"Error getting AOV New Customers per Country metrics for {base_week}: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/aov-returning-customers-per-country", response_model=AOVReturningCustomersPerCountryResponse)
async def get_aov_returning_customers_per_country(
    base_week: str = Query(..., description="Base ISO week like '2025-42'"),
    num_weeks: int = Query(8, description="Number of weeks to analyze")
):
    """Get AOV for Returning Customers per Country metrics for the last N weeks."""
    
    try:
        if not validate_iso_week(base_week):
            raise HTTPException(status_code=400, detail=f"Invalid ISO week format: {base_week}")
        
        if num_weeks < 1 or num_weeks > 52:
            raise HTTPException(status_code=400, detail=f"Number of weeks must be between 1 and 52")
        
        config = load_config(week=base_week)
        aov_data = calculate_aov_returning_customers_per_country_for_weeks(base_week, num_weeks, config.data_root)
        
        # Format response
        response = AOVReturningCustomersPerCountryResponse(
            aov_returning_customers_per_country=aov_data,
            period_info={
                "latest_week": base_week,
                "latest_dates": "N/A"
            }
        )
        
        return response
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        logger.error(f"Error getting AOV Returning Customers per Country metrics for {base_week}: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/marketing-spend-per-country", response_model=MarketingSpendPerCountryResponse)
async def get_marketing_spend_per_country(
    base_week: str = Query(..., description="Base ISO week like '2025-42'"),
    num_weeks: int = Query(8, description="Number of weeks to analyze")
):
    """Get Marketing Spend per Country metrics for the last N weeks."""
    
    try:
        if not validate_iso_week(base_week):
            raise HTTPException(status_code=400, detail=f"Invalid ISO week format: {base_week}")
        
        if num_weeks < 1 or num_weeks > 52:
            raise HTTPException(status_code=400, detail=f"Number of weeks must be between 1 and 52")
        
        config = load_config(week=base_week)
        spend_data = calculate_marketing_spend_per_country_for_weeks(base_week, num_weeks, config.data_root)
        
        # Format response
        response = MarketingSpendPerCountryResponse(
            marketing_spend_per_country=spend_data,
            period_info={
                "latest_week": base_week,
                "latest_dates": "N/A"
            }
        )
        
        return response
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        logger.error(f"Error getting Marketing Spend per Country metrics for {base_week}: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/ncac-per-country", response_model=nCACPerCountryResponse)
async def get_ncac_per_country(
    base_week: str = Query(..., description="Base ISO week like '2025-42'"),
    num_weeks: int = Query(8, description="Number of weeks to analyze")
):
    """Get nCAC per country metrics for the last N weeks."""
    
    try:
        if not validate_iso_week(base_week):
            raise HTTPException(status_code=400, detail=f"Invalid ISO week format: {base_week}")
        
        if num_weeks < 1 or num_weeks > 52:
            raise HTTPException(status_code=400, detail=f"Number of weeks must be between 1 and 52")
        
        config = load_config(week=base_week)
        ncac_data = calculate_ncac_per_country_for_weeks(base_week, num_weeks, config.data_root)
        
        # Format response
        response = nCACPerCountryResponse(
            ncac_per_country=ncac_data,
            period_info={
                "latest_week": base_week,
                "latest_dates": "N/A"
            }
        )
        
        return response
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        logger.error(f"Error getting nCAC per country metrics for {base_week}: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/contribution-new-per-country", response_model=ContributionNewPerCountryResponse)
async def get_contribution_new_per_country(
    base_week: str = Query(..., description="Base ISO week like '2025-42'"),
    num_weeks: int = Query(8, description="Number of weeks to analyze")
):
    """Get Contribution per New Customer per Country metrics for the last N weeks."""
    
    try:
        if not validate_iso_week(base_week):
            raise HTTPException(status_code=400, detail=f"Invalid ISO week format: {base_week}")
        
        if num_weeks < 1 or num_weeks > 52:
            raise HTTPException(status_code=400, detail=f"Number of weeks must be between 1 and 52")
        
        config = load_config(week=base_week)
        contribution_data = calculate_contribution_new_per_country_for_weeks(base_week, num_weeks, config.data_root)
        
        # Format response
        response = ContributionNewPerCountryResponse(
            contribution_new_per_country=contribution_data,
            period_info={
                "latest_week": base_week,
                "latest_dates": "N/A"
            }
        )
        
        return response
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        logger.error(f"Error getting Contribution per New Customer per Country metrics for {base_week}: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/contribution-new-total-per-country")
async def get_contribution_new_total_per_country(
    base_week: str = Query(..., description="Base ISO week like '2025-42'"),
    num_weeks: int = Query(8, description="Number of weeks to analyze")
):
    """Get Total Contribution per Country for new customers for the last N weeks."""
    
    try:
        if not validate_iso_week(base_week):
            raise HTTPException(status_code=400, detail=f"Invalid ISO week format: {base_week}")
        
        if num_weeks < 1 or num_weeks > 52:
            raise HTTPException(status_code=400, detail=f"Number of weeks must be between 1 and 52")
        
        config = load_config(week=base_week)
        contribution_data = calculate_contribution_new_total_per_country_for_weeks(base_week, num_weeks, config.data_root)
        
        # Format response
        response = ContributionNewTotalPerCountryResponse(
            contribution_new_total_per_country=contribution_data,
            period_info={
                "latest_week": base_week,
                "latest_dates": "N/A"
            }
        )
        
        return response
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        logger.error(f"Error getting Total Contribution per Country metrics for {base_week}: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/contribution-returning-per-country")
async def get_contribution_returning_per_country(
    base_week: str = Query(..., description="Base ISO week like '2025-42'"),
    num_weeks: int = Query(8, description="Number of weeks to analyze")
):
    """Get Contribution per Returning Customer per Country metrics for the last N weeks."""
    
    try:
        if not validate_iso_week(base_week):
            raise HTTPException(status_code=400, detail=f"Invalid ISO week format: {base_week}")
        
        if num_weeks < 1 or num_weeks > 52:
            raise HTTPException(status_code=400, detail=f"Number of weeks must be between 1 and 52")
        
        config = load_config(week=base_week)
        contribution_data = calculate_contribution_returning_per_country_for_weeks(base_week, num_weeks, config.data_root)
        
        # Format response
        response = ContributionReturningPerCountryResponse(
            contribution_returning_per_country=contribution_data,
            period_info={
                "latest_week": base_week,
                "latest_dates": "N/A"
            }
        )
        
        return response
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        logger.error(f"Error getting Contribution per Returning Customer per Country metrics for {base_week}: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/contribution-returning-total-per-country")
async def get_contribution_returning_total_per_country(
    base_week: str = Query(..., description="Base ISO week like '2025-42'"),
    num_weeks: int = Query(8, description="Number of weeks to analyze")
):
    """Get Total Contribution per Country for returning customers for the last N weeks."""
    
    try:
        if not validate_iso_week(base_week):
            raise HTTPException(status_code=400, detail=f"Invalid ISO week format: {base_week}")
        
        if num_weeks < 1 or num_weeks > 52:
            raise HTTPException(status_code=400, detail=f"Number of weeks must be between 1 and 52")
        
        config = load_config(week=base_week)
        contribution_data = calculate_contribution_returning_total_per_country_for_weeks(base_week, num_weeks, config.data_root)
        
        # Format response
        response = ContributionReturningTotalPerCountryResponse(
            contribution_returning_total_per_country=contribution_data,
            period_info={
                "latest_week": base_week,
                "latest_dates": "N/A"
            }
        )
        
        return response
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        logger.error(f"Error getting Total Contribution per Country for returning customers for {base_week}: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/total-contribution-per-country")
async def get_total_contribution_per_country(
    base_week: str = Query(..., description="Base ISO week like '2025-42'"),
    num_weeks: int = Query(8, description="Number of weeks to analyze")
):
    """Get Total Contribution per Country for all customers for the last N weeks."""
    
    try:
        if not validate_iso_week(base_week):
            raise HTTPException(status_code=400, detail=f"Invalid ISO week format: {base_week}")
        
        if num_weeks < 1 or num_weeks > 52:
            raise HTTPException(status_code=400, detail=f"Number of weeks must be between 1 and 52")
        
        config = load_config(week=base_week)
        contribution_data = calculate_total_contribution_per_country_for_weeks(base_week, num_weeks, config.data_root)
        
        # Format response
        response = TotalContributionPerCountryResponse(
            total_contribution_per_country=contribution_data,
            period_info={
                "latest_week": base_week,
                "latest_dates": "N/A"
            }
        )
        
        return response
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        logger.error(f"Error getting Total Contribution per Country for {base_week}: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/audience-metrics-per-country", response_model=AudienceMetricsPerCountryResponse)
async def get_audience_metrics_per_country(
    base_week: str = Query(..., description="Base ISO week like '2025-42'"),
    num_weeks: int = Query(8, description="Number of weeks to analyze")
):
    """Get audience metrics per country (and Total): Total AOV, Total customers, Return rate %, COS %, CAC. No split by customer type."""
    try:
        if not validate_iso_week(base_week):
            raise HTTPException(status_code=400, detail=f"Invalid ISO week format: {base_week}")
        if num_weeks < 1 or num_weeks > 52:
            raise HTTPException(status_code=400, detail="Number of weeks must be between 1 and 52")
        config = load_config(week=base_week)
        data = calculate_audience_metrics_per_country_for_weeks(base_week, num_weeks, config.data_root)
        # Ensure each country's value is valid for AudienceMetricsCountryData (with optional last_year)
        weeks_data = []
        for w in data["audience_metrics_per_country"]:
            countries_typed = {}
            for country, vals in w.get("countries", {}).items():
                if isinstance(vals, dict):
                    ly = vals.get("last_year")
                    last_year_inner = None
                    if isinstance(ly, dict) and ly:
                        last_year_inner = AudienceMetricsCountryDataInner(
                            total_aov=float(ly.get("total_aov", 0)),
                            total_customers=int(ly.get("total_customers", 0)),
                            return_rate_pct=float(ly.get("return_rate_pct", 0)),
                            cos_pct=float(ly.get("cos_pct", 0)),
                            cac=float(ly.get("cac", 0)),
                        )
                    countries_typed[country] = AudienceMetricsCountryData(
                        total_aov=float(vals.get("total_aov", 0)),
                        total_customers=int(vals.get("total_customers", 0)),
                        return_rate_pct=float(vals.get("return_rate_pct", 0)),
                        cos_pct=float(vals.get("cos_pct", 0)),
                        cac=float(vals.get("cac", 0)),
                        last_year=last_year_inner,
                    )
            weeks_data.append(AudienceMetricsPerCountryWeekData(week=w["week"], countries=countries_typed))
        return AudienceMetricsPerCountryResponse(
            audience_metrics_per_country=weeks_data,
            period_info=data.get("period_info", {"latest_week": base_week, "latest_dates": ""}),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        logger.warning(f"No data for audience metrics {base_week}: {e}")
        return AudienceMetricsPerCountryResponse(
            audience_metrics_per_country=[],
            period_info={"latest_week": base_week, "latest_dates": ""},
        )
    except Exception as e:
        import traceback
        logger.error(f"Error getting audience metrics per country for {base_week}: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/batch/all-metrics")
async def get_batch_all_metrics(
    base_week: str = Query(..., description="Base ISO week like '2025-42'"),
    num_weeks: int = Query(8, description="Number of weeks to analyze")
):
    """Get all metrics in a single batch request for optimal performance. Reads from Supabase if available."""
    
    try:
        if not validate_iso_week(base_week):
            raise HTTPException(status_code=400, detail=f"Invalid ISO week format: {base_week}")
        
        if num_weeks < 1 or num_weeks > 52:
            raise HTTPException(status_code=400, detail=f"Number of weeks must be between 1 and 52")
        
        # Try to read from Supabase first (only when Supabase is enabled)
        if _supabase_enabled():
            try:
                from weekly_report.src.adapters.supabase_client import get_supabase_client
                from weekly_report.src.export.weekly_reports import reconstruct_metrics_from_supabase
                from weekly_report.src.utils.file_hashes import get_file_hashes_for_week, hashes_match

                supabase = get_supabase_client()
                if supabase:
                    try:
                        cached_result = supabase.table("weekly_report_metrics").select("*").eq("base_week", base_week).limit(1).execute()
                        if cached_result.data and len(cached_result.data) > 0:
                            cached_row = cached_result.data[0]
                            cached_num_weeks = cached_row.get("num_weeks", 8)

                            if cached_num_weeks == num_weeks:
                                config = load_config(week=base_week)
                                current_file_hashes = get_file_hashes_for_week(base_week, config.data_root)

                                stored_hashes = cached_row.get("file_hashes")
                                if stored_hashes and isinstance(stored_hashes, str):
                                    import json
                                    stored_hashes = json.loads(stored_hashes)
                                elif isinstance(stored_hashes, dict):
                                    pass
                                else:
                                    stored_hashes = {}

                                if hashes_match(stored_hashes, current_file_hashes):
                                    logger.info(f"✅ Returning cached metrics from Supabase for {base_week}")
                                    metrics_dict = reconstruct_metrics_from_supabase(cached_row)
                                    response = BatchMetricsResponse(**metrics_dict)
                                    return response
                                else:
                                    logger.info(f"⚠️ File hashes changed for {base_week}, recomputing...")
                    except Exception as cache_error:
                        logger.warning(f"Error reading from Supabase cache: {cache_error}, will compute")
            except ImportError:
                logger.debug("Supabase client not available, skipping cache check")

        # Fallback: Compute metrics
        config = load_config(week=base_week)
        logger.info(f"Computing batch metrics for {base_week} with {num_weeks} weeks")
        all_metrics = calculate_all_metrics(base_week, config.data_root, num_weeks)
        
        # Save to Supabase for future use (only when Supabase is enabled)
        if _supabase_enabled():
            try:
                from weekly_report.src.adapters.supabase_client import get_supabase_client
                supabase = get_supabase_client()
                if supabase:
                    try:
                        from weekly_report.src.export.weekly_reports import map_batch_metrics_to_supabase
                        from weekly_report.src.utils.file_hashes import get_file_hashes_for_week
                        current_file_hashes = get_file_hashes_for_week(base_week, config.data_root)
                        weekly_metrics_row = map_batch_metrics_to_supabase(
                            base_week=base_week,
                            metrics=all_metrics,
                            file_hashes=current_file_hashes,
                            num_weeks=num_weeks
                        )
                        supabase.table("weekly_report_metrics").upsert(weekly_metrics_row, on_conflict="base_week").execute()
                        logger.info(f"✅ Saved computed metrics to Supabase for {base_week}")
                    except Exception as save_error:
                        logger.warning(f"Failed to save to Supabase (non-blocking): {save_error}")
            except ImportError:
                logger.debug("Supabase client not available, skipping save")

        # Convert to response format - handle type mismatches gracefully
        try:
            # Helper function to normalize data types
            def normalize_field(value, expected_type, field_name=''):
                if value is None:
                    return [] if expected_type == list else {}
                if isinstance(value, dict) and expected_type == list:
                    # Check for common nested structures
                    # MarketsResponse-like: {'markets': [...], 'period_info': {...}}
                    if 'markets' in value:
                        return value.get('markets', [])
                    # KPIsResponse-like: {'kpis': [...], 'period_info': {...}}
                    if 'kpis' in value:
                        return value.get('kpis', [])
                    # Other response-like structures: extract the main list field
                    # Try to find a list value in the dict
                    for key, val in value.items():
                        if isinstance(val, list):
                            logger.debug(f"Extracting list from {field_name} dict key '{key}'")
                            return val
                    # If no list found, return empty list
                    logger.warning(f"Could not extract list from {field_name} dict, returning empty list")
                    return []
                if isinstance(value, list) and expected_type == dict:
                    return {}  # Can't convert list to dict
                return value
            
            # Enhance periods with date_ranges and ytd_periods (required by PeriodsResponse)
            periods_dict = all_metrics.get('periods', {})
            if isinstance(periods_dict, dict) and 'date_ranges' not in periods_dict:
                # Calculate date_ranges and ytd_periods
                from weekly_report.src.periods.calculator import get_week_date_range, get_ytd_periods_for_week
                date_ranges = {}
                for period_name, period_week in periods_dict.items():
                    try:
                        date_ranges[period_name] = get_week_date_range(period_week)
                    except Exception as e:
                        logger.warning(f"Could not get date range for {period_week}: {e}")
                        date_ranges[period_name] = {
                            'start': 'N/A',
                            'end': 'N/A', 
                            'display': 'N/A'
                        }
                ytd_periods = get_ytd_periods_for_week(base_week)
                periods_dict = {
                    **periods_dict,
                    'date_ranges': date_ranges,
                    'ytd_periods': ytd_periods
                }
            
            # Normalize each field according to BatchMetricsResponse structure
            response_dict = {
                'periods': periods_dict,
                'metrics': normalize_field(all_metrics.get('metrics'), dict, 'metrics'),
                'markets': normalize_field(all_metrics.get('markets'), list, 'markets'),
                'kpis': normalize_field(all_metrics.get('kpis'), list, 'kpis'),
                'contribution': normalize_field(all_metrics.get('contribution'), list, 'contribution'),
                'gender_sales': normalize_field(all_metrics.get('gender_sales'), list, 'gender_sales'),
                'men_category_sales': normalize_field(all_metrics.get('men_category_sales'), list, 'men_category_sales'),
                'women_category_sales': normalize_field(all_metrics.get('women_category_sales'), list, 'women_category_sales'),
                'category_sales': normalize_field(all_metrics.get('category_sales'), dict, 'category_sales'),
                'products_new': normalize_field(all_metrics.get('products_new'), dict, 'products_new'),
                'products_gender': normalize_field(all_metrics.get('products_gender'), dict, 'products_gender'),
                'sessions_per_country': normalize_field(all_metrics.get('sessions_per_country'), list, 'sessions_per_country'),
                'conversion_per_country': normalize_field(all_metrics.get('conversion_per_country'), list, 'conversion_per_country'),
                'new_customers_per_country': normalize_field(all_metrics.get('new_customers_per_country'), list, 'new_customers_per_country'),
                'returning_customers_per_country': normalize_field(all_metrics.get('returning_customers_per_country'), list, 'returning_customers_per_country'),
                'aov_new_customers_per_country': normalize_field(all_metrics.get('aov_new_customers_per_country'), list, 'aov_new_customers_per_country'),
                'aov_returning_customers_per_country': normalize_field(all_metrics.get('aov_returning_customers_per_country'), list, 'aov_returning_customers_per_country'),
                'marketing_spend_per_country': normalize_field(all_metrics.get('marketing_spend_per_country'), list, 'marketing_spend_per_country'),
                'ncac_per_country': normalize_field(all_metrics.get('ncac_per_country'), list, 'ncac_per_country'),
                'contribution_new_per_country': normalize_field(all_metrics.get('contribution_new_per_country'), list, 'contribution_new_per_country'),
                'contribution_new_total_per_country': normalize_field(all_metrics.get('contribution_new_total_per_country'), list, 'contribution_new_total_per_country'),
                'contribution_returning_per_country': normalize_field(all_metrics.get('contribution_returning_per_country'), list, 'contribution_returning_per_country'),
                'contribution_returning_total_per_country': normalize_field(all_metrics.get('contribution_returning_total_per_country'), list, 'contribution_returning_total_per_country'),
                'total_contribution_per_country': normalize_field(all_metrics.get('total_contribution_per_country'), list, 'total_contribution_per_country'),
            }
            
            response = BatchMetricsResponse(**response_dict)
            logger.info(f"✅ Successfully created BatchMetricsResponse for {base_week}")
            return response
        except Exception as validation_error:
            logger.error(f"Error creating BatchMetricsResponse: {validation_error}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            logger.error(f"Metrics structure: {list(all_metrics.keys())}")
            logger.error(f"Sample metrics content: {str(all_metrics)[:500]}")
            # Return raw dict as fallback if validation fails
            logger.warning(f"Returning raw metrics dict as fallback for {base_week}")
            return all_metrics
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        logger.warning(f"No data for batch metrics {base_week}: {e}")
        raise HTTPException(
            status_code=404,
            detail=f"No data files found for week {base_week}. Upload data in Settings (e.g. Qlik, DEMA, Shopify CSVs in data/raw/{base_week}/)."
        )
    except Exception as e:
        import traceback
        logger.error(f"Error getting batch all metrics for {base_week}: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/upload-file")
async def upload_file(
    file: UploadFile = File(...),
    week: str = Form(...),
    file_type: str = Form(..., description="qlik, dema_spend, dema_gm2, or shopify")
):
    """
    Upload data file for specific week and type.
    Validates file type, extracts date range, saves to correct location.
    """
    try:
        # Validate week format
        if not validate_iso_week(week):
            raise HTTPException(status_code=400, detail="Invalid ISO week format")
        
        # Validate file_type
        allowed_types = ["qlik", "dema_spend", "dema_gm2", "shopify", "budget"]
        if file_type not in allowed_types:
            raise HTTPException(status_code=400, detail=f"Invalid file type. Must be one of {allowed_types}")
        
        # Validate file extension
        file_extension = Path(file.filename).suffix.lower()
        if file_type == "qlik" and file_extension not in ['.xlsx', '.csv']:
            raise HTTPException(status_code=400, detail="Qlik file must be .xlsx or .csv")
        if file_type in ["dema_spend", "dema_gm2", "shopify", "budget"] and file_extension != '.csv':
            raise HTTPException(status_code=400, detail=f"{file_type} file must be .csv")
        
        # Create target directory
        config = load_config(week=week)
        target_dir = config.raw_data_path / file_type
        target_dir.mkdir(parents=True, exist_ok=True)
        
        # Delete existing files in the directory (except .DS_Store)
        for existing_file in target_dir.glob("*.*"):
            if not existing_file.name.startswith('.'):
                existing_file.unlink()
                logger.info(f"Deleted old file: {existing_file}")
        
        # Save file
        target_path = target_dir / file.filename
        with target_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        logger.info(f"File uploaded: {target_path}")
        logger.info(f"DEBUG: file_type='{file_type}', week='{week}', filename='{file.filename}'")
        
        # Special handling for budget files: save to Supabase for reuse (only when Supabase is enabled)
        if file_type == "budget" and _supabase_enabled():
            logger.info(f"🔍 DEBUG: Entering budget file Supabase save logic")
            try:
                from weekly_report.src.adapters.supabase_client import get_supabase_client
                supabase = get_supabase_client()
                if supabase:
                    # Extract year from week (ISO format: YYYY-WW)
                    year = int(week.split("-")[0])
                    
                    # Read file content as text
                    # Try UTF-8 first, fallback to latin-1 if needed
                    try:
                        with target_path.open("r", encoding="utf-8") as f:
                            content = f.read()
                    except UnicodeDecodeError:
                        logger.warning(f"UTF-8 decode failed, trying latin-1 for {file.filename}")
                        with target_path.open("r", encoding="latin-1") as f:
                            content = f.read()
                    
                    logger.info(f"📦 Saving budget file to Supabase for year {year} (filename: {file.filename}, size: {len(content)} chars)")
                    
                    # Upsert to Supabase (unique per year)
                    # Check if file already exists for this year
                    existing = supabase.table("budget_files").select("id").eq("year", year).limit(1).execute()
                    
                    budget_data = {
                        "year": year,
                        "week": week,
                        "filename": file.filename,
                        "content": content
                    }
                    
                    if existing.data and len(existing.data) > 0:
                        # Update existing record
                        budget_id = existing.data[0]["id"]
                        result = supabase.table("budget_files").update(budget_data).eq("id", budget_id).execute()
                        logger.info(f"✅ Updated budget file in Supabase for year {year} (id: {budget_id})")
                    else:
                        # Insert new record
                        result = supabase.table("budget_files").insert(budget_data).execute()
                        logger.info(f"✅ Inserted budget file to Supabase for year {year}")
                    
                    if result.data:
                        logger.info(f"✅ Budget file saved to Supabase - {len(result.data)} row(s) affected")
                    else:
                        logger.warning(f"⚠️ Budget file save result has no data - result: {result}")
                else:
                    logger.error("❌ Supabase client not available - check SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables")
            except ImportError:
                logger.debug("Supabase client not available, skipping budget file save")
            except Exception as e:
                import traceback
                logger.error(f"❌ Failed to save budget file to Supabase: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
        else:
            logger.info(f"🔍 DEBUG: Skipping Supabase save - file_type='{file_type}' (not 'budget')")
        
        # Clear caches to ensure fresh data after upload
        # Get the week's data path for cache invalidation
        week_data_path_str = str(config.raw_data_path)
        
        # Clear the entire cache first (safest approach)
        raw_data_cache.clear()
        
        # Also try to clear cache using alternative path formats that might have been used
        alternative_paths = [
            week_data_path_str,
            str(config.data_root / "raw" / week),
            f"data/raw/{week}",
            f"data/raw/{week}/{file_type}"
        ]
        
        for alt_path in alternative_paths:
            if alt_path in raw_data_cache.cache:
                del raw_data_cache.cache[alt_path]
                logger.info(f"Cleared raw data cache for path: {alt_path}")
        
        logger.info(f"Cleared raw data cache after file upload for week {week}")
        
        # Invalidate Supabase cache for this week (delete cached metrics)
        # This ensures metrics are recomputed next time
        try:
            from weekly_report.src.adapters.supabase_client import get_supabase_client
            supabase_client = get_supabase_client()
            if supabase_client:
                supabase_client.table("weekly_report_metrics").delete().eq("base_week", week).execute()
                logger.info(f"✅ Invalidated Supabase cache for week {week} (will recompute on next access)")
        except ImportError:
            logger.debug("Supabase client not available, skipping cache invalidation")
        except Exception as invalidation_error:
            logger.warning(f"Failed to invalidate Supabase cache (non-blocking): {invalidation_error}")
        
        # Extract metadata (date range)
        metadata = extract_file_metadata(target_path, file_type)
        
        return {
            "success": True,
            "file_path": str(target_path),
            "metadata": metadata
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


def validate_file_dimensions(file_path: Path, file_type: str) -> Dict[str, Any]:
    """Validate that required columns/dimensions exist in the file."""
    
    result = {
        "has_country": False,
        "columns": []
    }
    
    if not file_path.exists():
        return result
    
    try:
        if file_type in ["dema_spend", "dema_gm2"]:
            # Try semicolon first, then comma
            try:
                df = pd.read_csv(file_path, sep=';', encoding='utf-8', nrows=1, quotechar='"')
            except:
                df = pd.read_csv(file_path, sep=',', encoding='utf-8', nrows=1, quotechar='"')
            
            # Strip whitespace and quotes from column names
            df.columns = df.columns.str.strip().str.replace('"', '')
            result["columns"] = df.columns.tolist()
            
            # Check for country dimension (case insensitive)
            result["has_country"] = any("country" in col.lower() for col in df.columns)
        
        elif file_type == "shopify":
            # Try to load the file
            try:
                df = pd.read_csv(file_path, sep=';', encoding='utf-8', nrows=1, quotechar='"')
            except:
                df = pd.read_csv(file_path, sep=',', encoding='utf-8', nrows=1, quotechar='"')
            
            df.columns = df.columns.str.strip().str.replace('"', '')
            result["columns"] = df.columns.tolist()
            result["has_country"] = any("country" in col.lower() for col in df.columns)
        
        elif file_type == "qlik":
            # For Qlik, check if it's CSV or Excel
            if file_path.suffix == '.csv':
                try:
                    df = pd.read_csv(file_path, sep=';', encoding='utf-8', nrows=1, quotechar='"')
                except:
                    df = pd.read_csv(file_path, sep=',', encoding='utf-8', nrows=1, quotechar='"')
                df.columns = df.columns.str.strip().str.replace('"', '')
            else:
                df = pd.read_excel(file_path, nrows=1)
            
            result["columns"] = df.columns.tolist()
            result["has_country"] = any("country" in col.lower() for col in df.columns)
        
        elif file_type == "budget":
            # Budget files don't need country dimension - they use Market instead
            try:
                df = pd.read_csv(file_path, sep=',', encoding='utf-8', nrows=1, quotechar='"')
            except:
                try:
                    df = pd.read_csv(file_path, sep=';', encoding='utf-8', nrows=1, quotechar='"')
                except:
                    df = pd.DataFrame()
            
            df.columns = df.columns.str.strip().str.replace('"', '')
            result["columns"] = df.columns.tolist()
            # Check for Market dimension instead of Country
            result["has_country"] = any("market" in col.lower() for col in df.columns)
    
    except Exception as e:
        logger.error(f"Error validating dimensions for {file_path}: {e}")
    
    return result


# Cache for file dimensions validation results
_dimensions_cache: Dict[str, Dict[str, Any]] = {}

@app.get("/api/file-dimensions")
async def get_file_dimensions(week: str = Query(...)):
    """Get validation status for required dimensions in data files."""
    try:
        if not validate_iso_week(week):
            raise HTTPException(status_code=400, detail="Invalid ISO week format")
        
        config = load_config(week=week)
        raw_path = config.raw_data_path
        
        # Check cache first
        cache_key = f"{week}"
        if cache_key in _dimensions_cache:
            cached_result = _dimensions_cache[cache_key]
            # Verify files haven't changed
            cache_valid = True
            for file_type in ["qlik", "dema_spend", "dema_gm2", "shopify", "budget"]:
                type_path = raw_path / file_type
                if type_path.exists():
                    files = list(type_path.glob("*.*"))
                    files = [f for f in files if not f.name.startswith('.')]
                    if files:
                        latest_file = max(files, key=lambda f: f.stat().st_mtime)
                        cached_file_info = cached_result.get(file_type, {})
                        if cached_file_info.get("filename") != latest_file.name or \
                           cached_file_info.get("mtime") != latest_file.stat().st_mtime:
                            cache_valid = False
                            break
            
            if cache_valid:
                # Return cached result (without mtime)
                result = {}
                for file_type, data in cached_result.items():
                    result[file_type] = {
                        "filename": data.get("filename"),
                        "has_country": data.get("has_country"),
                        "columns": data.get("columns", [])
                    }
                return result
        
        # Cache miss or invalid - compute result
        result = {}
        file_hashes = []
        
        # Check each file type
        for file_type in ["qlik", "dema_spend", "dema_gm2", "shopify", "budget"]:
            type_path = raw_path / file_type
            if type_path.exists():
                files = list(type_path.glob("*.*"))
                # Filter out hidden files
                files = [f for f in files if not f.name.startswith('.')]
                
                if files:
                    # Get the most recently modified file
                    latest_file = max(files, key=lambda f: f.stat().st_mtime)
                    validation = validate_file_dimensions(latest_file, file_type)
                    
                    result[file_type] = {
                        "filename": latest_file.name,
                        "has_country": validation["has_country"],
                        "columns": validation["columns"]
                    }
                    # Cache with mtime for validation
                    _dimensions_cache[cache_key] = _dimensions_cache.get(cache_key, {})
                    _dimensions_cache[cache_key][file_type] = {
                        "filename": latest_file.name,
                        "mtime": latest_file.stat().st_mtime,
                        "has_country": validation["has_country"],
                        "columns": validation["columns"]
                    }
                    file_hashes.append(f"{file_type}:{latest_file.name}:{latest_file.stat().st_mtime}")
                else:
                    result[file_type] = {
                        "filename": None,
                        "has_country": None,
                        "columns": []
                    }
            else:
                result[file_type] = {
                    "filename": None,
                    "has_country": None,
                    "columns": []
                }
        
        # Generate ETag and add caching headers
        etag_content = f"{week}:{':'.join(file_hashes)}"
        etag = hashlib.md5(etag_content.encode()).hexdigest()
        
        response = Response(
            content=json.dumps(result),
            media_type="application/json",
            headers={
                "Cache-Control": "public, max-age=600",  # Cache for 10 minutes
                "ETag": etag
            }
        )
        return response
        
    except Exception as e:
        logger.error(f"Error validating file dimensions: {e}")
        raise HTTPException(status_code=500, detail="Failed to validate file dimensions")


@app.get("/api/file-metadata")
async def get_file_metadata(week: str = Query(...)):
    """Get metadata for all data files in a specific week - only check if files exist."""
    try:
        if not validate_iso_week(week):
            raise HTTPException(status_code=400, detail="Invalid ISO week format")
        
        config = load_config(week=week)
        raw_path = config.raw_data_path
        
        metadata = {}
        file_hashes = []
        for file_type in ["qlik", "dema_spend", "dema_gm2", "shopify", "budget"]:
            type_path = raw_path / file_type
            if type_path.exists():
                files = list(type_path.glob("*.*"))
                # Filter out hidden files (.DS_Store, etc.)
                files = [f for f in files if not f.name.startswith('.')]
                if files:
                    # Get the most recently modified file
                    latest_file = max(files, key=lambda f: f.stat().st_mtime)
                    # Only return basic file info - don't read the entire file
                    metadata[file_type] = {
                        "filename": latest_file.name,
                        "uploaded_at": datetime.fromtimestamp(latest_file.stat().st_mtime).isoformat()
                    }
                    # Add file hash for ETag
                    file_hashes.append(f"{file_type}:{latest_file.name}:{latest_file.stat().st_mtime}")
        
        # Generate ETag from file metadata
        etag_content = f"{week}:{':'.join(file_hashes)}"
        etag = hashlib.md5(etag_content.encode()).hexdigest()
        
        # Create response with caching headers
        response = Response(
            content=json.dumps(metadata),
            media_type="application/json",
            headers={
                "Cache-Control": "public, max-age=600",  # Cache for 10 minutes
                "ETag": etag
            }
        )
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting file metadata: {e}")
        raise HTTPException(status_code=500, detail="Failed to get file metadata")


@app.get("/api/budget-data")
async def get_budget_data(week: str = Query(...)):
    """Get budget data for a specific week."""
    try:
        if not validate_iso_week(week):
            raise HTTPException(status_code=400, detail="Invalid ISO week format")
        
        config = load_config(week=week)
        # Note: load_data will check Supabase first, then fallback to local files
        from weekly_report.src.adapters.budget import load_data
        budget_df = load_data(config.raw_data_path, base_week=week)
        
        if budget_df.empty:
            return {"error": "Budget file is empty"}
        
        # Convert sample data to dict, handling NaN and infinite values
        sample_dicts = []
        for _, row in budget_df.head(5).iterrows():
            row_dict = {}
            for col, val in row.items():
                # Check for NaN
                if pd.isna(val):
                    row_dict[col] = None
                # Check for infinite values using math
                elif isinstance(val, float) and (val == float('inf') or val == float('-inf')):
                    row_dict[col] = None
                else:
                    row_dict[col] = str(val) if isinstance(val, (int, float)) else val
            sample_dicts.append(row_dict)
        
        # Return basic structure
        return {
            "week": week,
            "columns": budget_df.columns.tolist(),
            "row_count": len(budget_df),
            "sample_data": sample_dicts
        }
        
    except FileNotFoundError:
        return {"error": "No budget data found"}
    except Exception as e:
        logger.error(f"Error loading budget data: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load budget data: {str(e)}")


# --- Discounts / Customer quality (no Supabase required) ---
@app.get("/api/discounts/sales-yoy")
async def get_discounts_sales_yoy(
    base_week: str = Query(...),
    num_weeks: int = Query(8),
    segment: str = Query("all"),
    expanded: bool = Query(False),
):
    try:
        if not validate_iso_week(base_week):
            raise HTTPException(status_code=400, detail="Invalid ISO week format")
        config = load_config(week=base_week)
        from weekly_report.src.metrics.discounts_sales import calculate_discount_sales_yoy_for_weeks
        return calculate_discount_sales_yoy_for_weeks(base_week, num_weeks, config.data_root, segment, expanded)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading discounts sales YoY: {e}")
        raise HTTPException(status_code=500, detail="Failed to load discounts sales YoY")


@app.get("/api/discounts/monthly-metrics")
async def get_discounts_monthly_metrics(
    base_week: str = Query(...),
    months: int = Query(12),
    segment: str = Query("all"),
):
    try:
        if not validate_iso_week(base_week):
            raise HTTPException(status_code=400, detail="Invalid ISO week format")
        config = load_config(week=base_week)
        from weekly_report.src.metrics.discounts_sales import calculate_discounts_monthly_metrics
        return calculate_discounts_monthly_metrics(base_week, config.data_root, months, segment)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading discounts monthly metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to load discounts monthly metrics")


@app.get("/api/discounts/summary")
async def get_discounts_summary(
    base_week: str = Query(...),
    include_ytd: bool = Query(True),
):
    try:
        if not validate_iso_week(base_week):
            raise HTTPException(status_code=400, detail="Invalid ISO week format")
        config = load_config(week=base_week)
        from weekly_report.src.metrics.discounts_sales import calculate_discounts_summary_metrics
        return calculate_discounts_summary_metrics(base_week, config.data_root, include_ytd)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading discounts summary metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to load discounts summary metrics")


@app.get("/api/discounts/ltm")
async def get_discounts_ltm(
    base_week: str = Query(...),
):
    try:
        if not validate_iso_week(base_week):
            raise HTTPException(status_code=400, detail="Invalid ISO week format")
        config = load_config(week=base_week)
        from weekly_report.src.metrics.discounts_sales import calculate_discounts_ltm_metrics
        return calculate_discounts_ltm_metrics(base_week, config.data_root)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading discounts LTM metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to load discounts LTM metrics")


@app.get("/api/discounts/products")
async def get_discounts_products(
    base_week: str = Query(...),
    num_weeks: int = Query(8),
    segment: str = Query("all"),
    granularity: str = Query("week"),
    months: int = Query(12),
):
    try:
        if not validate_iso_week(base_week):
            raise HTTPException(status_code=400, detail="Invalid ISO week format")
        config = load_config(week=base_week)
        from weekly_report.src.metrics.discounts_sales import (
            calculate_discount_category_price_sales_for_weeks,
            calculate_discount_category_price_sales_for_months,
        )
        if granularity == "month":
            result = calculate_discount_category_price_sales_for_months(base_week, months, config.data_root, segment)
            result["granularity"] = "month"
            return result
        result = calculate_discount_category_price_sales_for_weeks(base_week, num_weeks, config.data_root, segment)
        result["granularity"] = "week"
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading discounts products: {e}")
        raise HTTPException(status_code=500, detail="Failed to load discounts products")


@app.get("/api/discounts/categories")
async def get_discounts_categories(
    base_week: str = Query(...),
    iso_week: str = Query(...),
    segment: str = Query("all"),
):
    try:
        if not validate_iso_week(base_week):
            raise HTTPException(status_code=400, detail="Invalid ISO week format")
        config = load_config(week=base_week)
        from weekly_report.src.metrics.discounts_sales import calculate_discount_category_breakdown
        return calculate_discount_category_breakdown(base_week, iso_week, config.data_root, segment)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading discounts categories: {e}")
        raise HTTPException(status_code=500, detail="Failed to load discounts categories")


@app.get("/api/discounts/categories-monthly")
async def get_discounts_categories_monthly(
    base_week: str = Query(...),
    month: str = Query(...),
    segment: str = Query("all"),
):
    try:
        if not validate_iso_week(base_week):
            raise HTTPException(status_code=400, detail="Invalid ISO week format")
        config = load_config(week=base_week)
        from weekly_report.src.metrics.discounts_sales import calculate_discount_category_breakdown_month
        return calculate_discount_category_breakdown_month(base_week, month, config.data_root, segment)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading discounts categories monthly: {e}")
        raise HTTPException(status_code=500, detail="Failed to load discounts categories monthly")


@app.get("/api/discounts/category-countries")
async def get_discounts_category_countries(
    base_week: str = Query(...),
    iso_week: str = Query(...),
    category: str = Query(...),
    segment: str = Query("all"),
):
    try:
        if not validate_iso_week(base_week):
            raise HTTPException(status_code=400, detail="Invalid ISO week format")
        config = load_config(week=base_week)
        from weekly_report.src.metrics.discounts_sales import calculate_discount_category_country_breakdown
        return calculate_discount_category_country_breakdown(base_week, iso_week, category, config.data_root, segment)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading discounts category countries: {e}")
        raise HTTPException(status_code=500, detail="Failed to load discounts category countries")


@app.get("/api/discounts/category-countries-monthly")
async def get_discounts_category_countries_monthly(
    base_week: str = Query(...),
    month: str = Query(...),
    category: str = Query(...),
    segment: str = Query("all"),
):
    try:
        if not validate_iso_week(base_week):
            raise HTTPException(status_code=400, detail="Invalid ISO week format")
        config = load_config(week=base_week)
        from weekly_report.src.metrics.discounts_sales import calculate_discount_category_country_breakdown_month
        return calculate_discount_category_country_breakdown_month(base_week, month, category, config.data_root, segment)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading discounts category countries monthly: {e}")
        raise HTTPException(status_code=500, detail="Failed to load discounts category countries monthly")


@app.get("/api/discounts/category-series")
async def get_discounts_category_series(
    base_week: str = Query(...),
    category: str = Query(...),
    segment: str = Query("all"),
    expanded: bool = Query(False),
):
    try:
        if not validate_iso_week(base_week):
            raise HTTPException(status_code=400, detail="Invalid ISO week format")
        config = load_config(week=base_week)
        from weekly_report.src.metrics.discounts_sales import calculate_discount_category_series
        return calculate_discount_category_series(base_week, category, config.data_root, segment, expanded)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading discounts category series: {e}")
        raise HTTPException(status_code=500, detail="Failed to load discounts category series")


@app.get("/api/customer-quality/scorecard")
async def get_customer_quality_scorecard(
    base_week: str = Query(...),
    window_days: int = Query(180),
    as_of_date: Optional[str] = Query(None),
    baseline_months: int = Query(24),
):
    try:
        if not validate_iso_week(base_week):
            raise HTTPException(status_code=400, detail="Invalid ISO week format")
        config = load_config(week=base_week)
        from weekly_report.src.metrics.customer_discount_quality import (
            DiscountQualityConfig,
            build_quality_context,
            compute_quality_scorecard,
            compute_diagnostics,
        )
        cfg = DiscountQualityConfig(cohort_window_days=window_days)
        order_df, first_orders, meta = build_quality_context(base_week, str(config.data_root), as_of_date=as_of_date)
        if meta.get("error"):
            raise HTTPException(status_code=404, detail=meta["error"])
        as_of_dt = pd.to_datetime(meta.get("as_of_date"), errors="coerce")
        if pd.isna(as_of_dt):
            as_of_dt = pd.Timestamp.utcnow().normalize()
        scorecard = compute_quality_scorecard(order_df, first_orders, as_of_date=as_of_dt, window_days=window_days, baseline_months=baseline_months)
        diagnostics = compute_diagnostics(order_df)
        return {**scorecard, "meta": meta, "diagnostics": diagnostics}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading customer quality scorecard: {e}")
        raise HTTPException(status_code=500, detail="Failed to load customer quality scorecard")


@app.get("/api/customer-quality/discount-depth")
async def get_customer_quality_discount_depth(
    base_week: str = Query(...),
    window_days: int = Query(180),
    as_of_date: Optional[str] = Query(None),
):
    try:
        if not validate_iso_week(base_week):
            raise HTTPException(status_code=400, detail="Invalid ISO week format")
        config = load_config(week=base_week)
        from weekly_report.src.metrics.customer_discount_quality import (
            build_quality_context,
            compute_discount_depth,
        )
        order_df, first_orders, meta = build_quality_context(base_week, str(config.data_root), as_of_date=as_of_date)
        if meta.get("error"):
            raise HTTPException(status_code=404, detail=meta["error"])
        as_of_dt = pd.to_datetime(meta.get("as_of_date"), errors="coerce")
        if pd.isna(as_of_dt):
            as_of_dt = pd.Timestamp.utcnow().normalize()
        result = compute_discount_depth(order_df, first_orders, as_of_date=as_of_dt, window_days=window_days)
        return {**result, "meta": meta}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading customer quality discount depth: {e}")
        raise HTTPException(status_code=500, detail="Failed to load customer quality discount depth")


@app.get("/api/customer-quality/segments")
async def get_customer_quality_segments(
    base_week: str = Query(...),
    window_days: int = Query(180),
    as_of_date: Optional[str] = Query(None),
    threshold_low: float = Query(0.2),
    threshold_high: float = Query(0.8),
):
    try:
        if not validate_iso_week(base_week):
            raise HTTPException(status_code=400, detail="Invalid ISO week format")
        config = load_config(week=base_week)
        from weekly_report.src.metrics.customer_discount_quality import (
            build_quality_context,
            compute_segments,
        )
        order_df, first_orders, meta = build_quality_context(base_week, str(config.data_root), as_of_date=as_of_date)
        if meta.get("error"):
            raise HTTPException(status_code=404, detail=meta["error"])
        as_of_dt = pd.to_datetime(meta.get("as_of_date"), errors="coerce")
        if pd.isna(as_of_dt):
            as_of_dt = pd.Timestamp.utcnow().normalize()
        result = compute_segments(
            order_df,
            first_orders,
            as_of_date=as_of_dt,
            window_days=window_days,
            threshold_low=threshold_low,
            threshold_high=threshold_high,
        )
        return {**result, "meta": meta}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading customer quality segments: {e}")
        raise HTTPException(status_code=500, detail="Failed to load customer quality segments")


@app.get("/api/customer-quality/pathways")
async def get_customer_quality_pathways(
    base_week: str = Query(...),
    window_days: int = Query(180),
    as_of_date: Optional[str] = Query(None),
    threshold_low: float = Query(0.2),
    threshold_high: float = Query(0.8),
    baseline_months: int = Query(24),
):
    try:
        if not validate_iso_week(base_week):
            raise HTTPException(status_code=400, detail="Invalid ISO week format")
        config = load_config(week=base_week)
        from weekly_report.src.metrics.customer_discount_quality import (
            build_quality_context,
            compute_pathways,
        )
        order_df, first_orders, meta = build_quality_context(base_week, str(config.data_root), as_of_date=as_of_date)
        if meta.get("error"):
            raise HTTPException(status_code=404, detail=meta["error"])
        as_of_dt = pd.to_datetime(meta.get("as_of_date"), errors="coerce")
        if pd.isna(as_of_dt):
            as_of_dt = pd.Timestamp.utcnow().normalize()
        result = compute_pathways(
            order_df,
            first_orders,
            as_of_date=as_of_dt,
            window_days=window_days,
            threshold_low=threshold_low,
            threshold_high=threshold_high,
            baseline_months=baseline_months,
        )
        return {**result, "meta": meta}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading customer quality pathways: {e}")
        raise HTTPException(status_code=500, detail="Failed to load customer quality pathways")


def _parse_number(value: Any) -> float:
    """Robust number parser for budget values with locale artifacts.
    - Handles commas as thousands or decimal
    - Removes spaces, percent signs
    - Converts parentheses negatives
    """
    try:
        if pd.isna(value):
            return float('nan')
        if isinstance(value, (int, float)):
            return float(value)
        s = str(value).strip()
        if s == '':
            return float('nan')
        # parentheses negative
        if s.startswith('(') and s.endswith(')'):
            s = '-' + s[1:-1]
        # remove spaces and percents
        s = s.replace(' ', '').replace('%', '')
        # decide separators
        if ',' in s and '.' in s:
            # likely comma thousands, dot decimal
            s = s.replace(',', '')
        elif ',' in s and '.' not in s:
            # if groups of 3 before comma -> thousands
            parts = s.split(',')
            if all(len(p) == 3 for p in parts[1:]):
                s = ''.join(parts)
            else:
                s = s.replace(',', '.')
        return float(s)
    except Exception:
        return float('nan')


@app.get("/api/budget-debug")
async def get_budget_debug(
    week: str = Query(...),
    month: str = Query(...),
    metrics: str = Query("Returning Gross Revenue,New Gross Revenue")
):
    """Debug endpoint: show per-row values for selected month and metrics across filter stages."""
    try:
        if not validate_iso_week(week):
            raise HTTPException(status_code=400, detail="Invalid ISO week format")
        config = load_config(week=week)
        from weekly_report.src.adapters.budget import load_data
        df = load_data(config.raw_data_path, base_week=week)
        df.columns = df.columns.str.strip()
        if 'Month' not in df.columns:
            raise HTTPException(status_code=400, detail="Budget file missing 'Month' column")
        df['Month'] = df['Month'].astype(str).str.strip()
        df['Market'] = df['Market'].astype(str).str.strip() if 'Market' in df.columns else ''

        metric_list = [m.strip() for m in metrics.split(',') if m.strip()]
        present_metrics = [m for m in metric_list if m in df.columns]

        raw_subset = df[df['Month'] == month][['Month', 'Market', *present_metrics]].copy()

        total_aliases = {"total", "all", "all markets", "grand total", "totals"}
        filtered = raw_subset[~raw_subset['Market'].str.lower().isin(total_aliases)]
        filtered = filtered[filtered['Market'].str.len() > 0]

        # numeric stage
        numeric = filtered.copy()
        for col in present_metrics:
            numeric[col] = numeric[col].map(_parse_number)

        sums = {col: float(pd.to_numeric(numeric[col], errors='coerce').sum()) for col in present_metrics}

        return {
            'week': week,
            'month': month,
            'metrics': present_metrics,
            'raw_rows': raw_subset.to_dict(orient='records'),
            'after_filter_rows': filtered.to_dict(orient='records'),
            'after_numeric_rows': numeric.to_dict(orient='records'),
            'sums': sums,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"budget-debug failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/budget-general")
async def get_budget_general(week: str = Query(...)):
    """Aggregate budget metrics across all markets, summarized by Month.
    Returns a pivot-friendly structure with metrics as rows and months as columns,
    plus a Total column aggregating all months.
    When no budget data exists, returns 200 with empty structure (no 404) so dashboard load does not fail.
    """
    try:
        if not validate_iso_week(week):
            raise HTTPException(status_code=400, detail="Invalid ISO week format")
        from weekly_report.src.compute.budget import compute_budget_general
        result = compute_budget_general(week)
        if "error" in result:
            logger.debug(f"No budget data for {week}: {result['error']}")
            return {
                "week": week,
                "months": [],
                "metrics": [],
                "table": {},
                "totals": {},
                "ytd_totals": {},
                "error": result["error"],
            }
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error aggregating budget general data: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to aggregate budget general: {str(e)}")


@app.get("/api/actuals-general")
async def get_actuals_general(week: str = Query(...)):
    """Aggregate actuals across all markets by Month with same shape as budget-general.
    When no actuals data, returns 200 with empty structure so dashboard load does not fail.
    """
    try:
        if not validate_iso_week(week):
            raise HTTPException(status_code=400, detail="Invalid ISO week format")

        from weekly_report.src.compute.budget import compute_actuals_general

        result = compute_actuals_general(week)

        if "error" in result:
            logger.debug(f"No actuals data for {week}: {result['error']}")
            return {
                "week": week,
                "months": [],
                "metrics": [],
                "table": {},
                "totals": {},
                "ytd_totals": {},
                "error": result["error"],
            }

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error aggregating actuals general: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to aggregate actuals general: {str(e)}")


@app.get("/api/supabase/verify")
async def supabase_verify_endpoint():
    """
    Verify Supabase connection step-by-step. No guesswork: returns exact status for each step.
    Use this to confirm env vars, client creation, and a simple query work before running sync.
    """
    result = {
        "env_file_loaded": False,
        "SUPABASE_URL": "not_set",
        "SUPABASE_SERVICE_ROLE_KEY": "not_set",
        "key_length": 0,
        "client_created": False,
        "client_error": None,
        "query_ok": False,
        "query_error": None,
        "table_row_count": None,
    }
    if not _supabase_enabled():
        result["client_error"] = "Supabase is disabled (DISABLE_SUPABASE=true). No verification needed."
        return result
    # 1) Env file
    _env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    result["env_file_loaded"] = _env_path.exists()
    # 2) Env vars (values never returned, only set/not_set and key length)
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    result["SUPABASE_URL"] = "set" if (url and url.strip()) else "not_set"
    result["SUPABASE_SERVICE_ROLE_KEY"] = "set" if (key and key.strip()) else "not_set"
    result["key_length"] = len(key) if key else 0
    # 3) Client creation
    client = None
    try:
        from weekly_report.src.adapters.supabase_client import get_supabase_client
        client = get_supabase_client()
        result["client_created"] = client is not None
        if not client:
            result["client_error"] = "get_supabase_client() returned None (check env vars or supabase package)"
    except Exception as e:
        result["client_error"] = str(e)
    # 4) One simple query (proves connection and RLS)
    if result["client_created"] and client is not None:
        try:
            r = client.table("weekly_report_metrics").select("base_week", count="exact").limit(1).execute()
            result["query_ok"] = True
            result["table_row_count"] = r.count if getattr(r, "count", None) is not None else (len(r.data) if r.data else 0)
        except Exception as e:
            result["query_error"] = str(e)
    return result


@app.post("/api/sync-supabase")
async def sync_supabase_endpoint(
    week: str = Query(..., description="ISO week format: YYYY-WW"),
    num_weeks: int = Query(8, description="Number of weeks to analyze")
):
    """Trigger Supabase sync for the specified week."""
    try:
        if not _supabase_enabled():
            return {
                "success": False,
                "message": "Supabase is disabled (DISABLE_SUPABASE=true). Set DISABLE_SUPABASE=false to enable sync.",
            }
        if not validate_iso_week(week):
            raise HTTPException(status_code=400, detail="Invalid ISO week format")

        from weekly_report.src.sync.supabase_sync import sync_supabase_data

        result = sync_supabase_data(week, num_weeks=num_weeks)
        
        if not result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Sync failed")
            )
        
        return {
            "success": True,
            "week": week,
            "row_counts": result.get("row_counts", {}),
            "elapsed_seconds": result.get("elapsed_seconds", 0),
            "sync_id": result.get("sync_id")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Supabase sync failed: {e}")
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
