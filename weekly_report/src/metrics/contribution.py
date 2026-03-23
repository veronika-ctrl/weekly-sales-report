"""
Calculate Contribution metrics for new and returning customers.
"""
from pathlib import Path
from typing import Dict, List, Any
import pandas as pd
from loguru import logger

from weekly_report.src.metrics.table1 import load_all_raw_data
from weekly_report.src.periods.calculator import get_week_date_range


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


def calculate_contribution_for_weeks(base_week: str, num_weeks: int, data_root: Path) -> Dict[str, Any]:
    """
    Calculate Contribution metrics for the last N weeks.
    
    Returns:
        Dict with 'contributions' (list of contribution data) and 'period_info' (metadata)
    """
    # Generate weeks to analyze (chronological, oldest first)
    weeks_to_analyze = _build_weeks(base_week, num_weeks)
    last_year_weeks = [_get_last_year_week_for_yoy(w) for w in weeks_to_analyze]
    
    logger.info(f"Calculating Contribution metrics for weeks: {weeks_to_analyze}")
    
    # Load data from the requested base_week (not the first of weeks_to_analyze)
    latest_data_path = data_root / "raw" / base_week
    
    qlik_df = pd.DataFrame()
    dema_df = pd.DataFrame()
    dema_gm2_df = pd.DataFrame()
    
    if latest_data_path.exists():
        try:
            all_raw_data = load_all_raw_data(latest_data_path)
            qlik_df = all_raw_data.get('qlik', pd.DataFrame())
            dema_df = all_raw_data.get('dema_spend', pd.DataFrame())
            dema_gm2_df = all_raw_data.get('dema_gm2', pd.DataFrame())
            
            # Pre-compute ISO week columns
            if not qlik_df.empty and 'Date' in qlik_df.columns:
                qlik_df['Date'] = pd.to_datetime(qlik_df['Date'], errors='coerce')
                iso_cal = qlik_df['Date'].dt.isocalendar()
                qlik_df['iso_week'] = iso_cal['year'].astype(str) + '-' + iso_cal['week'].astype(str).str.zfill(2)
            
            if not dema_df.empty and 'Days' in dema_df.columns:
                dema_df['Days'] = pd.to_datetime(dema_df['Days'], errors='coerce')
                iso_cal = dema_df['Days'].dt.isocalendar()
                dema_df['iso_week'] = iso_cal['year'].astype(str) + '-' + iso_cal['week'].astype(str).str.zfill(2)
            
            if not dema_gm2_df.empty and 'Days' in dema_gm2_df.columns:
                dema_gm2_df['Days'] = pd.to_datetime(dema_gm2_df['Days'], errors='coerce')
                iso_cal = dema_gm2_df['Days'].dt.isocalendar()
                dema_gm2_df['iso_week'] = iso_cal['year'].astype(str) + '-' + iso_cal['week'].astype(str).str.zfill(2)
                
        except Exception as e:
            logger.warning(f"Failed to load data for week {base_week}: {e}")
    
    # Calculate contributions for each week
    contributions_list = []
    
    for week_idx, week_str in enumerate(weeks_to_analyze):
        # Filter data for this week
        week_qlik_df = qlik_df[qlik_df['iso_week'] == week_str].copy() if not qlik_df.empty and 'iso_week' in qlik_df.columns else pd.DataFrame()
        week_dema_df = dema_df[dema_df['iso_week'] == week_str].copy() if not dema_df.empty and 'iso_week' in dema_df.columns else pd.DataFrame()
        week_dema_gm2_df = dema_gm2_df[dema_gm2_df['iso_week'] == week_str].copy() if not dema_gm2_df.empty and 'iso_week' in dema_gm2_df.columns else pd.DataFrame()
        
        if week_qlik_df.empty:
            logger.warning(f"Missing data for week {week_str} (using zeros)")
            week_contributions = calculate_week_contributions(pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), week_str)
        else:
            # Calculate contribution metrics
            week_contributions = calculate_week_contributions(week_qlik_df, week_dema_df, week_dema_gm2_df, week_str)
        
        # Add last year comparison
        last_year_week = last_year_weeks[week_idx]
        last_year_qlik_df = qlik_df[qlik_df['iso_week'] == last_year_week].copy() if not qlik_df.empty and 'iso_week' in qlik_df.columns else pd.DataFrame()
        last_year_dema_df = dema_df[dema_df['iso_week'] == last_year_week].copy() if not dema_df.empty and 'iso_week' in dema_df.columns else pd.DataFrame()
        last_year_dema_gm2_df = dema_gm2_df[dema_gm2_df['iso_week'] == last_year_week].copy() if not dema_gm2_df.empty and 'iso_week' in dema_gm2_df.columns else pd.DataFrame()
        
        if not last_year_qlik_df.empty:
            last_year_contributions = calculate_week_contributions(
                last_year_qlik_df,
                last_year_dema_df,
                last_year_dema_gm2_df,
                last_year_week
            )
            week_contributions['last_year'] = last_year_contributions
        else:
            week_contributions['last_year'] = calculate_week_contributions(pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), last_year_week)
        
        contributions_list.append(week_contributions)
    
    # Get latest week date range
    latest_week = weeks_to_analyze[-1]
    date_range = get_week_date_range(latest_week)
    
    return {
        'contributions': contributions_list,
        'period_info': {
            'latest_week': latest_week,
            'latest_dates': date_range
        }
    }


def calculate_week_contributions(qlik_df: pd.DataFrame, dema_df: pd.DataFrame, dema_gm2_df: pd.DataFrame, week_str: str) -> Dict[str, Any]:
    """Calculate contribution metrics for a single week."""
    if qlik_df.empty or 'Sales Channel' not in qlik_df.columns:
        return {
            'week': week_str,
            'gross_revenue_new': 0.0,
            'gross_revenue_returning': 0.0,
            'contribution_new': 0.0,
            'contribution_returning': 0.0,
            'contribution_total': 0.0
        }

    # Filter for online sales only
    online_df = qlik_df[qlik_df['Sales Channel'] == 'Online']
    
    # Gross Revenue by customer type
    new_customer_df = online_df[online_df['New/Returning Customer'] == 'New']
    returning_customer_df = online_df[online_df['New/Returning Customer'] == 'Returning']
    
    gross_revenue_new = new_customer_df['Gross Revenue'].sum()
    gross_revenue_returning = returning_customer_df['Gross Revenue'].sum()
    gross_revenue_total = online_df['Gross Revenue'].sum()
    
    # GM2 from dema_gm2: "Net gross margin 2" or "Gross margin 2 - Dema MTA" as percentage (0-1 or 0-100),
    # then GM2 SEK = gross_revenue * rate. No country needed in file.
    gm2_new = 0.0
    gm2_returning = 0.0
    gm2_total = 0.0

    if not dema_gm2_df.empty:
        logger.info(f"Week {week_str}: GM2 columns: {dema_gm2_df.columns.tolist()}")
        logger.info(f"Week {week_str}: GM2 rows: {len(dema_gm2_df)}")

        margin_col = None
        if "Net gross margin 2" in dema_gm2_df.columns:
            margin_col = "Net gross margin 2"
        elif "Net gross margin 2 - Dema MTA" in dema_gm2_df.columns:
            margin_col = "Net gross margin 2 - Dema MTA"
        elif "Gross margin 2 - Dema MTA" in dema_gm2_df.columns:
            margin_col = "Gross margin 2 - Dema MTA"

        if margin_col:
            # Detect if values are in percent (e.g. 62.11) or decimal (e.g. 0.6211)
            sample = dema_gm2_df[margin_col].dropna()
            as_pct = sample.max() > 1 if len(sample) else False  # >1 => assume 0-100%

            def _rate_to_ratio(val: float) -> float:
                if pd.isna(val):
                    return 0.0
                v = float(val)
                return (v / 100.0) if as_pct else v

            if "New vs Returning Customer" in dema_gm2_df.columns:
                new_rows = dema_gm2_df[dema_gm2_df["New vs Returning Customer"] == "New"]
                returning_rows = dema_gm2_df[dema_gm2_df["New vs Returning Customer"] == "Returning"]
                pct_new = new_rows[margin_col].mean() if len(new_rows) else 0.0
                pct_returning = returning_rows[margin_col].mean() if len(returning_rows) else 0.0
                ratio_new = _rate_to_ratio(pct_new)
                ratio_returning = _rate_to_ratio(pct_returning)
                gm2_new = gross_revenue_new * ratio_new
                gm2_returning = gross_revenue_returning * ratio_returning
                gm2_total = gm2_new + gm2_returning
                logger.info(
                    f"Week {week_str}: GM2 rate New: {pct_new}{'%' if as_pct else ''}, Returning: {pct_returning}{'%' if as_pct else ''}; "
                    f"GM2 SEK New: {gm2_new}, Returning: {gm2_returning}"
                )
            else:
                pct_total = dema_gm2_df[margin_col].mean()
                ratio_total = _rate_to_ratio(pct_total)
                gm2_new = gross_revenue_new * ratio_total
                gm2_returning = gross_revenue_returning * ratio_total
                gm2_total = gm2_new + gm2_returning
                logger.info(f"Week {week_str}: GM2 rate total: {pct_total}{'%' if as_pct else ''}; GM2 SEK New: {gm2_new}, Returning: {gm2_returning}")
        else:
            logger.warning(
                f"Week {week_str}: GM2 has no margin column (expected 'Net gross margin 2', "
                f"'Net gross margin 2 - Dema MTA', or 'Gross margin 2 - Dema MTA')"
            )

    if gm2_total == 0 and not dema_gm2_df.empty:
        logger.info(f"Week {week_str}: Gross Revenue New: {gross_revenue_new}, Gross Revenue Returning: {gross_revenue_returning}")
    
    logger.info(f"Week {week_str}: GM2 New: {gm2_new}, GM2 Returning: {gm2_returning}")
    
    # Get marketing spend
    marketing_spend = dema_df['Marketing spend'].sum() if not dema_df.empty and 'Marketing spend' in dema_df.columns else 0
    
    # Calculate GM3 (Contribution)
    # Marketing spend allocation: 70% new, 30% returning
    marketing_new = marketing_spend * 0.7
    marketing_returning = marketing_spend * 0.3
    
    contribution_new = gm2_new - marketing_new
    contribution_returning = gm2_returning - marketing_returning
    contribution_total = gm2_total - marketing_spend
    
    logger.info(f"Week {week_str}: Contribution New: {contribution_new}, Contribution Returning: {contribution_returning}")
    
    return {
        'week': week_str,
        'gross_revenue_new': float(gross_revenue_new),
        'gross_revenue_returning': float(gross_revenue_returning),
        'contribution_new': float(contribution_new),
        'contribution_returning': float(contribution_returning),
        'contribution_total': float(contribution_total)
    }

