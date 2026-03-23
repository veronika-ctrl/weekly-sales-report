"""
Calculate Online KPIs for the last 8 weeks.
"""
from pathlib import Path
from typing import Dict, List, Any
import pandas as pd
from loguru import logger

from weekly_report.src.metrics.table1 import load_all_raw_data
from weekly_report.src.periods.calculator import get_week_date_range


def get_iso_week_from_date(date_str: str) -> str:
    """Convert date string to ISO week format."""
    try:
        date = pd.to_datetime(date_str)
        year, week, _ = date.isocalendar()
        return f"{year}-{week:02d}"
    except Exception as e:
        logger.warning(f"Could not parse date {date_str}: {e}")
        return None


def filter_data_by_iso_week(df: pd.DataFrame, iso_week: str, date_column: str = 'Date') -> pd.DataFrame:
    """Filter dataframe by ISO week (iso_week column must already exist)."""
    if df.empty or 'iso_week' not in df.columns:
        return df
    
    filtered = df[df['iso_week'] == iso_week].copy()
    return filtered


def _has_53_weeks(year: int) -> bool:
    """Check if a year has 53 ISO weeks."""
    from datetime import datetime
    jan_4 = datetime(year, 1, 4)
    return jan_4.weekday() >= 3


def _get_last_year_week_for_yoy(week_str: str) -> str:
    """Return same ISO week number in previous year; week 53 maps to 52 if needed."""
    y_str, w_str = week_str.split("-")
    year = int(y_str)
    week = int(w_str)
    prev_year = year - 1
    if week == 53 and not _has_53_weeks(prev_year):
        week = 52
    return f"{prev_year}-{week:02d}"


def _build_weeks(base_week: str, num_weeks: int) -> List[str]:
    """Build last N ISO weeks ending at base_week, excluding week 53."""
    year, week = map(int, base_week.split("-"))
    weeks: List[str] = []
    i = 0
    while len(weeks) < num_weeks:
        week_num = week - i
        week_year = year
        if week_num < 1:
            prev_year = year - 1
            week_year = prev_year
            week_num = (53 if _has_53_weeks(prev_year) else 52) + week_num
            if week_num == 53:
                week_num = 52
                i += 1
                continue
        week_str = f"{week_year}-{week_num:02d}"
        if week_str not in weeks:
            weeks.append(week_str)
        i += 1
    weeks = weeks[::-1]  # oldest first
    return weeks


def calculate_online_kpis_for_weeks(base_week: str, num_weeks: int, data_root: Path) -> Dict[str, Any]:
    """
    Calculate Online KPIs for the last N weeks.
    
    Returns:
        Dict with 'kpis' (list of KPI data) and 'period_info' (metadata)
    """
    # Generate weeks to analyze (chronological, oldest first)
    weeks_to_analyze = _build_weeks(base_week, num_weeks)
    last_year_weeks = [_get_last_year_week_for_yoy(w) for w in weeks_to_analyze]
    
    logger.info(f"Calculating Online KPIs for weeks: {weeks_to_analyze}")
    logger.info(f"Last year weeks: {last_year_weeks}")
    
    # Collect all weeks
    all_weeks = list(set(weeks_to_analyze + last_year_weeks))
    
    # Load data from the requested base_week (not the first of weeks_to_analyze)
    latest_data_path = data_root / "raw" / base_week
    
    qlik_df = pd.DataFrame()
    shopify_df = pd.DataFrame()
    dema_df = pd.DataFrame()
    
    if latest_data_path.exists():
        try:
            # Load all raw data using cached loader (loads once, caches in memory)
            logger.info(f"Loading raw data from {latest_data_path}")
            all_raw_data = load_all_raw_data(latest_data_path)
            
            qlik_df = all_raw_data.get('qlik', pd.DataFrame())
            dema_df = all_raw_data.get('dema_spend', pd.DataFrame())
            
            # Shopify data is loaded separately as it's not in load_all_raw_data
            from weekly_report.src.adapters.shopify import load_data as load_shopify_data
            shopify_df = load_shopify_data(latest_data_path)
            logger.info(f"Loaded Shopify data: {shopify_df.shape}, columns: {shopify_df.columns.tolist() if not shopify_df.empty else 'empty'}")
            
            # Pre-compute ISO week column for all dataframes to avoid repeated computation
            if not qlik_df.empty and 'Date' in qlik_df.columns:
                qlik_df['Date'] = pd.to_datetime(qlik_df['Date'], errors='coerce')
                iso_cal = qlik_df['Date'].dt.isocalendar()
                qlik_df['iso_week'] = iso_cal['year'].astype(str) + '-' + iso_cal['week'].astype(str).str.zfill(2)
                logger.info(f"Pre-computed ISO weeks for Qlik data: {qlik_df.shape}")
            
            if not dema_df.empty and 'Days' in dema_df.columns:
                dema_df['Days'] = pd.to_datetime(dema_df['Days'], errors='coerce')
                iso_cal = dema_df['Days'].dt.isocalendar()
                dema_df['iso_week'] = iso_cal['year'].astype(str) + '-' + iso_cal['week'].astype(str).str.zfill(2)
                logger.info(f"Pre-computed ISO weeks for DEMA data: {dema_df.shape}")
            
            if not shopify_df.empty and 'Day' in shopify_df.columns:
                shopify_df['Day'] = pd.to_datetime(shopify_df['Day'], errors='coerce')
                iso_cal = shopify_df['Day'].dt.isocalendar()
                shopify_df['iso_week'] = iso_cal['year'].astype(str) + '-' + iso_cal['week'].astype(str).str.zfill(2)
                logger.info(f"Pre-computed ISO weeks for Shopify data: {shopify_df.shape}")
            elif not shopify_df.empty and 'Dag' in shopify_df.columns:
                # Handle Swedish column names
                shopify_df['Day'] = pd.to_datetime(shopify_df['Dag'], errors='coerce')
                iso_cal = shopify_df['Day'].dt.isocalendar()
                shopify_df['iso_week'] = iso_cal['year'].astype(str) + '-' + iso_cal['week'].astype(str).str.zfill(2)
                # Normalize column names: 'Sessioner' -> 'Sessions'
                if 'Sessioner' in shopify_df.columns:
                    shopify_df['Sessions'] = shopify_df['Sessioner']
                logger.info(f"Pre-computed ISO weeks for Shopify data (Swedish columns): {shopify_df.shape}")
            else:
                logger.warning(f"Shopify data missing 'Day' or 'Dag' column. Available columns: {shopify_df.columns.tolist()}")
                
        except Exception as e:
            logger.warning(f"Failed to load data for week {base_week}: {e}")
    
    # Calculate KPIs for each week
    kpis_list = []
    
    for week_idx, week_str in enumerate(weeks_to_analyze):
        # Filter data for this week (iso_week column already computed)
        week_qlik_df = filter_data_by_iso_week(qlik_df, week_str, 'Date')
        
        # Filter Shopify data by week (iso_week column already computed)
        week_shopify_df = shopify_df.copy()
        if not shopify_df.empty and 'iso_week' in shopify_df.columns:
            week_shopify_df = shopify_df[shopify_df['iso_week'] == week_str].copy()
            logger.debug(f"Filtered Shopify data for week {week_str}: {len(week_shopify_df)} rows (from {len(shopify_df)} total)")
        elif not shopify_df.empty:
            logger.warning(f"Shopify data exists but missing 'iso_week' column for week {week_str}. Available columns: {shopify_df.columns.tolist()}")
        else:
            logger.warning(f"No Shopify data available for week {week_str}")
        
        # Filter DEMA data by week (iso_week column already computed)
        week_dema_df = dema_df.copy()
        if not dema_df.empty and 'iso_week' in dema_df.columns:
            week_dema_df = dema_df[dema_df['iso_week'] == week_str].copy()
        
        if week_qlik_df.empty:
            logger.warning(f"Missing data for week {week_str} (using zeros)")
            week_kpis = calculate_week_kpis(pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), week_str)
        else:
            # Calculate KPIs
            week_kpis = calculate_week_kpis(week_qlik_df, week_shopify_df, week_dema_df, week_str)
        
        # Add last year comparison
        last_year_week = last_year_weeks[week_idx]
        last_year_qlik_df = filter_data_by_iso_week(qlik_df, last_year_week, 'Date')
        
        # Filter Shopify data for last year
        last_year_shopify_df = shopify_df.copy()
        if not shopify_df.empty and 'iso_week' in shopify_df.columns:
            last_year_shopify_df = shopify_df[shopify_df['iso_week'] == last_year_week].copy()
        
        # Filter DEMA data for last year
        last_year_dema_df = dema_df.copy()
        if not dema_df.empty and 'iso_week' in dema_df.columns:
            last_year_dema_df = dema_df[dema_df['iso_week'] == last_year_week].copy()
        
        if not last_year_qlik_df.empty:
            last_year_kpis = calculate_week_kpis(
                last_year_qlik_df,
                last_year_shopify_df,  # Use filtered shopify data for last year
                last_year_dema_df,  # Use filtered dema data for last year
                last_year_week
            )
            week_kpis['last_year'] = last_year_kpis
        else:
            week_kpis['last_year'] = calculate_week_kpis(pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), last_year_week)
        
        kpis_list.append(week_kpis)
    
    # Get latest week date range
    latest_week = weeks_to_analyze[-1]
    date_range = get_week_date_range(latest_week)
    
    return {
        'kpis': kpis_list,
        'period_info': {
            'latest_week': latest_week,
            'latest_dates': date_range
        }
    }


def calculate_week_kpis(qlik_df: pd.DataFrame, shopify_df: pd.DataFrame, dema_df: pd.DataFrame, week_str: str) -> Dict[str, Any]:
    """Calculate KPIs for a single week."""
    
    # Handle missing/empty Qlik data
    if qlik_df.empty or 'Sales Channel' not in qlik_df.columns:
        return {
            'week': week_str,
            'aov_new_customer': 0.0,
            'aov_returning_customer': 0.0,
            'cos': 0.0,
            'marketing_spend': float(dema_df['Marketing spend'].sum()) if (not dema_df.empty and 'Marketing spend' in dema_df.columns) else 0.0,
            'conversion_rate': 0.0,
            'new_customers': 0,
            'returning_customers': 0,
            'sessions': int(shopify_df['Sessions'].sum()) if (not shopify_df.empty and 'Sessions' in shopify_df.columns) else 0,
            'new_customer_cac': 0.0,
            'total_orders': 0,
            'return_rate_pct': 0.0,
        }

    # Filter for online sales only
    online_df = qlik_df[qlik_df['Sales Channel'] == 'Online']
    
    # Calculate metrics
    gross_revenue = online_df['Gross Revenue'].sum()
    net_revenue = online_df['Net Revenue'].sum()
    
    # New/Returning customers
    new_customers = online_df[online_df['New/Returning Customer'] == 'New']['Customer E-mail'].nunique()
    returning_customers = online_df[online_df['New/Returning Customer'] == 'Returning']['Customer E-mail'].nunique()
    
    # New customer revenue
    new_customer_df = online_df[online_df['New/Returning Customer'] == 'New']
    new_customer_revenue = new_customer_df['Net Revenue'].sum()
    
    # Returning customer revenue
    returning_customer_df = online_df[online_df['New/Returning Customer'] == 'Returning']
    returning_customer_revenue = returning_customer_df['Net Revenue'].sum()
    
    # Calculate AOVs
    aov_new_customer = new_customer_revenue / new_customers if new_customers > 0 else 0
    aov_returning_customer = returning_customer_revenue / returning_customers if returning_customers > 0 else 0
    
    # Sessions from Shopify
    if shopify_df.empty:
        logger.warning(f"Shopify data is empty for week {week_str}")
        sessions = 0
    elif 'Sessions' in shopify_df.columns:
        sessions = shopify_df['Sessions'].sum()
        logger.debug(f"Calculated sessions for week {week_str}: {sessions}")
    elif 'Sessioner' in shopify_df.columns:
        # Handle Swedish column name
        sessions = shopify_df['Sessioner'].sum()
        logger.debug(f"Calculated sessions for week {week_str} (Swedish column): {sessions}")
    else:
        logger.warning(f"Shopify data missing 'Sessions' or 'Sessioner' column for week {week_str}. Available columns: {shopify_df.columns.tolist()}")
        sessions = 0
    
    # Conversion rate
    unique_orders = online_df['Order No'].nunique()
    conversion_rate = (unique_orders / sessions * 100) if sessions > 0 else 0
    logger.debug(f"Conversion rate for week {week_str}: {conversion_rate}% (orders: {unique_orders}, sessions: {sessions})")
    
    # COS (Cost of Sale) - from DEMA spend
    if not dema_df.empty and 'Marketing spend' in dema_df.columns:
        marketing_spend = dema_df['Marketing spend'].sum()
    elif not dema_df.empty and 'Cost' in dema_df.columns:
        marketing_spend = dema_df['Cost'].sum()
    else:
        marketing_spend = 0
    
    # Calculate CoS as percentage: marketing spend / gross sales * 100
    cos = (marketing_spend / gross_revenue * 100) if gross_revenue > 0 else 0
    
    # New Customer CAC (Customer Acquisition Cost)
    new_customer_cac = marketing_spend / new_customers if new_customers > 0 else 0
    
    # Total Orders
    total_orders = online_df['Order No'].nunique()

    # Return rate % = returns / gross. Prefer "Returns" column when present and > 0; else use Gross - Net.
    net_revenue = online_df['Net Revenue'].sum() if 'Net Revenue' in online_df.columns else 0.0
    returns_from_col = online_df['Returns'].sum() if 'Returns' in online_df.columns else 0.0
    if gross_revenue <= 0:
        returns_amount = 0.0
    elif returns_from_col and float(returns_from_col) > 0:
        returns_amount = float(returns_from_col)
    else:
        returns_amount = max(0.0, float(gross_revenue - net_revenue))
    return_rate_pct = (returns_amount / gross_revenue * 100) if gross_revenue > 0 else 0.0

    return {
        'week': week_str,
        'aov_new_customer': float(aov_new_customer),
        'aov_returning_customer': float(aov_returning_customer),
        'cos': float(cos),
        'marketing_spend': float(marketing_spend),
        'conversion_rate': float(conversion_rate),
        'new_customers': int(new_customers),
        'returning_customers': int(returning_customers),
        'sessions': int(sessions),
        'new_customer_cac': float(new_customer_cac),
        'total_orders': int(total_orders),
        'return_rate_pct': round(return_rate_pct, 1),
    }

