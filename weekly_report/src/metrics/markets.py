"""Markets calculation module for top markets analysis."""

import pandas as pd
from typing import Dict, List, Any
from pathlib import Path
from loguru import logger

from weekly_report.src.adapters import qlik
from weekly_report.src.periods.calculator import get_week_date_range
from weekly_report.src.metrics.table1 import load_all_raw_data


def calculate_top_markets_for_weeks(base_week: str, num_weeks: int, data_root: Path) -> Dict[str, Any]:
    """
    Calculate top markets based on average Online Gross Revenue over last N weeks.
    
    Args:
        base_week: ISO week format like '2025-42'
        num_weeks: Number of weeks to look back (default 8)
        data_root: Root data directory
        
    Returns:
        Dictionary with markets data and period info
    """
    
    logger.info(f"Calculating top markets for {num_weeks} weeks ending at {base_week}")
    
    # Parse base week
    match = base_week.split('-')
    year = int(match[0])
    week = int(match[1])
    
    # Generate list of weeks to analyze (current year)
    # Go back num_weeks from base_week, excluding week 53
    weeks_to_analyze = []
    i = 0
    while len(weeks_to_analyze) < num_weeks:
        week_num = week - i
        week_year = year
        if week_num < 1:
            # Need to go back to previous year
            prev_year = year - 1
            week_year = prev_year
            # Check if previous year had 53 weeks
            if _has_53_weeks(prev_year):
                week_num = 53 + week_num
            else:
                week_num = 52 + week_num
            
            # Exclude week 53
            if week_num == 53:
                # Skip week 53, use week 52 instead
                week_num = 52
                i += 1
                continue
        
        week_str = f"{week_year}-{week_num:02d}"
        if week_str not in weeks_to_analyze:
            weeks_to_analyze.append(week_str)
        i += 1
    
    # Generate list of last year weeks (same week numbers, previous year) for Y/Y baseline
    last_year_weeks = [get_last_year_week_for_yoy(w) for w in weeks_to_analyze]

    # Reverse to match chronological order (oldest first)
    weeks_to_analyze = weeks_to_analyze[::-1]
    last_year_weeks = last_year_weeks[::-1]
    
    logger.info(f"Analyzing weeks: {weeks_to_analyze}")
    logger.info(f"Last year weeks: {last_year_weeks}")
    
    # Load raw data: base_week folder has current-year weeks; last-year weeks need their own folders
    latest_data_path = data_root / "raw" / base_week
    
    try:
        logger.info(f"Loading raw data from {latest_data_path} for requested week {base_week}")
        all_raw_data = load_all_raw_data(latest_data_path)
    except Exception as e:
        logger.error(f"Failed to load raw data: {e}")
        raise
    
    # Use same pattern as category_sales: filter qlik by iso_week (already added by load_all_raw_data)
    # so multi-year data in one file works the same way as on Category Sales
    qlik_df = all_raw_data['qlik']
    if 'iso_week' not in qlik_df.columns and 'Date' in qlik_df.columns:
        qlik_df = qlik_df.copy()
        qlik_df['Date'] = pd.to_datetime(qlik_df['Date'], errors='coerce')
        iso_cal = qlik_df['Date'].dt.isocalendar()
        qlik_df['iso_week'] = iso_cal['year'].astype(str) + '-' + iso_cal['week'].astype(str).str.zfill(2)
    online_df = qlik_df[qlik_df['Sales Channel'] == 'Online'].copy() if 'Sales Channel' in qlik_df.columns else qlik_df.copy()
    
    country_weeks_data = {}
    
    def _add_week_revenue_from_df(week_str: str, df: pd.DataFrame) -> None:
        """Filter df by iso_week == week_str and add country revenue (same logic as category_sales)."""
        if 'iso_week' not in df.columns or 'Country' not in df.columns or 'Gross Revenue' not in df.columns:
            return
        week_df = df[df['iso_week'] == week_str]
        if week_df.empty:
            return
        country_revenue = week_df.groupby('Country')['Gross Revenue'].sum()
        for country, revenue in country_revenue.items():
            if country not in country_weeks_data:
                country_weeks_data[country] = {}
            country_weeks_data[country][week_str] = float(revenue)
    
    all_weeks = list(set(weeks_to_analyze + last_year_weeks))
    logger.info(f"Processing {len(all_weeks)} weeks total: {all_weeks}")
    
    # 1) Current-year weeks from base_week folder (same file has 2022-2026)
    for week_str in weeks_to_analyze:
        _add_week_revenue_from_df(week_str, online_df)
    
    # 2) Last-year weeks from same base_week folder (multi-year data)
    for week_str in last_year_weeks:
        _add_week_revenue_from_df(week_str, online_df)
    
    # 3) Last-year weeks: if data/raw/{last_year_week}/ exists, load and add (overwrites zeros)
    #    This is required for Y/Y GROWTH% on 2025-W50/51/52 (baseline 2024-W50/51/52) when base file has no 2024 data
    data_root_resolved = data_root.resolve()
    for week_str in last_year_weeks:
        week_path = data_root_resolved / "raw" / week_str
        if week_path.exists():
            try:
                ly_raw = load_all_raw_data(week_path)
                ly_qlik = ly_raw['qlik']
                if 'iso_week' not in ly_qlik.columns and 'Date' in ly_qlik.columns:
                    ly_qlik = ly_qlik.copy()
                    ly_qlik['Date'] = pd.to_datetime(ly_qlik['Date'], errors='coerce')
                    iso_cal = ly_qlik['Date'].dt.isocalendar()
                    ly_qlik['iso_week'] = iso_cal['year'].astype(str) + '-' + iso_cal['week'].astype(str).str.zfill(2)
                ly_online = ly_qlik[ly_qlik['Sales Channel'] == 'Online'].copy() if 'Sales Channel' in ly_qlik.columns else ly_qlik.copy()
                _add_week_revenue_from_df(week_str, ly_online)
                logger.info(f"Loaded last-year data for Y/Y from {week_path}")
            except Exception as e:
                logger.warning(f"Could not load last-year data for {week_str}: {e}")
        else:
            # No folder for this last-year week; Y/Y will show "-" for that week if base file had no data
            total_for_week = sum(country_weeks_data.get(c, {}).get(week_str, 0) for c in country_weeks_data)
            if total_for_week == 0:
                logger.info(f"Last-year week {week_str}: no data in base file and folder {week_path} not found (Y/Y will show '-' for this week)")
    
    # Calculate averages and sort (only for current year weeks)
    markets_list = []
    for country, weeks_data in country_weeks_data.items():
        # Calculate average only for current year weeks, including 0 for weeks without data
        current_year_values = [weeks_data.get(week, 0) for week in weeks_to_analyze]
        avg_revenue = sum(current_year_values) / len(weeks_to_analyze) if weeks_to_analyze else 0
        
        # Build weeks dict with both current and last year data
        combined_weeks = {}
        # Add current year weeks
        for week in weeks_to_analyze:
            combined_weeks[week] = weeks_data.get(week, 0)
        # Add last year weeks
        for week in last_year_weeks:
            combined_weeks[week] = weeks_data.get(week, 0)
        
        markets_list.append({
            'country': country,
            'weeks': combined_weeks,
            'average': avg_revenue
        })
    
    # Sort by average descending
    markets_list.sort(key=lambda x: x['average'], reverse=True)
    
    # Get top 13
    top_13 = markets_list[:13]
    
    # Calculate ROW (Rest of World) - sum of all others
    remaining_countries = markets_list[13:]
    row_weeks = {}
    row_total = 0
    
    # Include both current year and last year weeks for ROW
    for week_str in all_weeks:
        row_week_total = sum(c['weeks'].get(week_str, 0) for c in remaining_countries)
        row_weeks[week_str] = row_week_total
        if week_str in weeks_to_analyze:
            row_total += row_week_total
    
    row_average = row_total / len(weeks_to_analyze) if weeks_to_analyze else 0
    
    # Add ROW to markets list
    if row_average > 0:
        top_13.append({
            'country': 'ROW',
            'weeks': row_weeks,
            'average': row_average
        })
    
    # Calculate Total (sum of all countries including top 13 and ROW)
    total_weeks = {}
    total_sum = 0
    
    # Sum all countries for each week (use original markets_list to avoid double counting ROW)
    for week_str in all_weeks:
        week_total = sum(c['weeks'].get(week_str, 0) for c in markets_list)
        total_weeks[week_str] = week_total
        if week_str in weeks_to_analyze:
            total_sum += week_total
    
    # Calculate total average as average of the 8 weeks
    total_average = total_sum / len(weeks_to_analyze) if weeks_to_analyze else 0
    
    # Add Total to markets list
    top_13.append({
        'country': 'Total',
        'weeks': total_weeks,
        'average': total_average
    })
    
    # Get latest week date range for display
    latest_week = weeks_to_analyze[-1]  # Use last week instead of first
    date_range = get_week_date_range(latest_week)
    
    result = {
        'markets': top_13,
        'period_info': {
            'latest_week': latest_week,
            'latest_dates': date_range['display']
        }
    }
    
    logger.info(f"Calculated top markets: {len(top_13)} entries")
    return result


def _has_53_weeks(year: int) -> bool:
    """Check if a year has 53 ISO weeks."""
    from datetime import datetime

    jan_4 = datetime(year, 1, 4)
    return jan_4.weekday() >= 3


def get_last_year_week_for_yoy(week_str: str) -> str:
    """
    Return the same ISO week number in the previous year (baseline for Y/Y GROWTH%).
    E.g. 2025-50 -> 2024-50, 2026-01 -> 2025-01. Week 53 maps to 52 if previous year has no 53.
    """
    week_year, week_num = week_str.split('-')
    week_year_int = int(week_year)
    week_num_int = int(week_num)
    prev_year = week_year_int - 1
    if week_num_int == 53 and not _has_53_weeks(prev_year):
        return f"{prev_year}-52"
    return f"{prev_year}-{week_num_int:02d}"

