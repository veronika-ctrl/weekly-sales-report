"""Sessions per country metrics calculation."""
from typing import Dict, Any, List
import pandas as pd
from loguru import logger
from pathlib import Path

from weekly_report.src.metrics.table1 import load_all_raw_data


def calculate_sessions_per_country_for_week(shopify_df: pd.DataFrame, week_str: str) -> Dict[str, Any]:
    """Calculate sessions per country for a single week."""
    
    if shopify_df.empty:
        logger.warning(f"No Shopify data found for week {week_str}")
        return {
            'week': week_str,
            'countries': {}
        }
    
    # Check if 'Session country' column exists (with space) or 'Country' column
    country_col = None
    if 'Session country' in shopify_df.columns:
        country_col = 'Session country'
    elif 'Sessionsland' in shopify_df.columns:
        country_col = 'Sessionsland'  # Swedish column name
    elif 'Country' in shopify_df.columns:
        country_col = 'Country'
    else:
        logger.warning(f"No country column found in Shopify data. Available columns: {shopify_df.columns.tolist()}")
        return {
            'week': week_str,
            'countries': {}
        }
    
    # Determine sessions column name
    sessions_col = None
    if 'Sessions' in shopify_df.columns:
        sessions_col = 'Sessions'
    elif 'Sessioner' in shopify_df.columns:
        sessions_col = 'Sessioner'  # Swedish column name
    else:
        logger.warning(f"No sessions column found in Shopify data. Available columns: {shopify_df.columns.tolist()}")
        return {
            'week': week_str,
            'countries': {}
        }
    
    # Group by country and sum sessions
    country_sessions = shopify_df.groupby(country_col).agg({
        sessions_col: 'sum'
    }).reset_index()
    
    # Create result dict
    result = {
        'week': week_str,
        'countries': {}
    }
    
    # Add each country's sessions
    for _, row in country_sessions.iterrows():
        country = row[country_col]
        if pd.notna(country) and country != '-':
            result['countries'][country] = float(row[sessions_col])
    
    return result


def calculate_sessions_per_country_for_weeks(base_week: str, num_weeks: int, data_root: Path) -> List[Dict[str, Any]]:
    """Calculate sessions per country for multiple weeks."""
    
    results = []
    
    # Load Shopify data directly (not from cache) to ensure fresh data
    latest_data_path = data_root / "raw" / base_week
    logger.info(f"Loading Shopify data from {latest_data_path}")
    from weekly_report.src.adapters.shopify import load_data as load_shopify_data
    shopify_df = load_shopify_data(latest_data_path)
    
    if shopify_df.empty:
        logger.warning(f"No Shopify data found in {data_root}")
        return []
    
    # Add iso_week column if not present
    if 'iso_week' not in shopify_df.columns:
        # Try to find date column
        date_col = None
        if 'Date' in shopify_df.columns:
            date_col = 'Date'
        elif 'Day' in shopify_df.columns:
            date_col = 'Day'
        elif 'Dag' in shopify_df.columns:
            date_col = 'Dag'  # Swedish column name
        
        if date_col:
            iso_cal = pd.to_datetime(shopify_df[date_col]).dt.isocalendar()
            shopify_df['iso_week'] = iso_cal['year'].astype(str) + '-' + iso_cal['week'].astype(str).str.zfill(2)
        else:
            logger.warning(f"No date column found in Shopify data. Available columns: {shopify_df.columns.tolist()}")
            return []
    
    # Parse base week
    year, week_num = base_week.split('-')
    year = int(year)
    week_num = int(week_num)
    
    for i in range(num_weeks):
        # Calculate target week
        target_week_num = week_num - num_weeks + 1 + i
        target_year = year
        
        # Handle year rollover
        if target_week_num <= 0:
            target_year -= 1
            target_week_num += 52
        
        week_str = f"{target_year}-{target_week_num:02d}"
        
        try:
            # Filter data for this week
            week_df = shopify_df[shopify_df['iso_week'] == week_str].copy()
            
            if week_df.empty:
                logger.warning(f"No data for week {week_str}")
                continue
            
            # Calculate sessions per country
            week_data = calculate_sessions_per_country_for_week(week_df, week_str)
            
            # Get last year data
            last_year = target_year - 1
            last_year_week_str = f"{last_year}-{target_week_num:02d}"
            
            try:
                last_year_df = shopify_df[shopify_df['iso_week'] == last_year_week_str].copy()
                
                if not last_year_df.empty:
                    last_year_data = calculate_sessions_per_country_for_week(last_year_df, last_year_week_str)
                    week_data['last_year'] = last_year_data
                else:
                    week_data['last_year'] = None
            except Exception as e:
                logger.warning(f"Could not load last year data for {last_year_week_str}: {e}")
                week_data['last_year'] = None
            
            results.append(week_data)
            
        except Exception as e:
            logger.error(f"Error processing week {week_str}: {e}")
            continue
    
    return results
