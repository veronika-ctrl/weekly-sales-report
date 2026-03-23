"""Conversion per country metrics calculation."""
from typing import Dict, Any, List
import pandas as pd
from loguru import logger
from pathlib import Path

from weekly_report.src.metrics.table1 import load_all_raw_data


def calculate_conversion_per_country_for_week(
    shopify_df: pd.DataFrame, 
    qlik_df: pd.DataFrame, 
    week_str: str
) -> Dict[str, Any]:
    """Calculate conversion per country for a single week."""
    
    if shopify_df.empty or qlik_df.empty:
        logger.warning(f"No data found for week {week_str}")
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
    
    # Get unique orders per country from Qlik data
    online_orders = qlik_df[qlik_df['Sales Channel'] == 'Online'].copy()
    
    # Group by country and count unique orders
    country_orders = online_orders.groupby('Country').agg({
        'Order No': 'nunique'
    }).reset_index()
    country_orders.columns = ['Country', 'Orders']
    
    # Get sessions per country from Shopify data
    country_sessions = shopify_df.groupby(country_col).agg({
        sessions_col: 'sum'
    }).reset_index()
    
    # Merge orders and sessions by country
    result = {
        'week': week_str,
        'countries': {}
    }
    
    # Create a mapping from country names
    orders_dict = dict(zip(country_orders['Country'], country_orders['Orders']))
    sessions_dict = dict(zip(country_sessions[country_col], country_sessions[sessions_col]))
    
    # Calculate conversion rate for each country
    for country in set(list(orders_dict.keys()) + list(sessions_dict.keys())):
        if pd.notna(country) and country != '-':
            orders = orders_dict.get(country, 0)
            sessions = sessions_dict.get(country, 0)
            
            # Calculate conversion rate: (Orders / Sessions) * 100
            if sessions > 0:
                conversion_rate = (orders / sessions) * 100
            else:
                conversion_rate = 0.0
            
            result['countries'][country] = {
                'conversion_rate': float(conversion_rate),
                'orders': int(orders),
                'sessions': int(sessions)
            }
    
    return result


def calculate_conversion_per_country_for_weeks(base_week: str, num_weeks: int, data_root: Path) -> List[Dict[str, Any]]:
    """Calculate conversion per country for multiple weeks."""
    
    results = []
    
    # Load Shopify data directly (not from cache) to ensure fresh data
    latest_data_path = data_root / "raw" / base_week
    logger.info(f"Loading Shopify data from {latest_data_path}")
    from weekly_report.src.adapters.shopify import load_data as load_shopify_data
    shopify_df = load_shopify_data(latest_data_path)
    
    if shopify_df.empty:
        logger.warning(f"No Shopify data found in {data_root}")
        return []
    
    # Load Qlik data
    latest_data_path = data_root / "raw" / base_week
    logger.info(f"Loading Qlik data from {latest_data_path}")
    qlik_df = load_all_raw_data(latest_data_path).get('qlik', pd.DataFrame())
    
    if qlik_df.empty:
        logger.warning(f"No Qlik data found in {data_root}")
        return []
    
    # Add iso_week column to both dataframes if not present
    if 'iso_week' not in shopify_df.columns:
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
    
    if 'iso_week' not in qlik_df.columns:
        if 'Date' in qlik_df.columns:
            iso_cal = pd.to_datetime(qlik_df['Date']).dt.isocalendar()
            qlik_df['iso_week'] = iso_cal['year'].astype(str) + '-' + iso_cal['week'].astype(str).str.zfill(2)
    
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
            week_shopify_df = shopify_df[shopify_df['iso_week'] == week_str].copy()
            week_qlik_df = qlik_df[qlik_df['iso_week'] == week_str].copy()
            
            if week_shopify_df.empty or week_qlik_df.empty:
                logger.warning(f"No data for week {week_str}")
                continue
            
            # Calculate conversion per country
            week_data = calculate_conversion_per_country_for_week(week_shopify_df, week_qlik_df, week_str)
            
            # Get last year data
            last_year = target_year - 1
            last_year_week_str = f"{last_year}-{target_week_num:02d}"
            
            try:
                last_year_shopify_df = shopify_df[shopify_df['iso_week'] == last_year_week_str].copy()
                last_year_qlik_df = qlik_df[qlik_df['iso_week'] == last_year_week_str].copy()
                
                if not last_year_shopify_df.empty and not last_year_qlik_df.empty:
                    last_year_data = calculate_conversion_per_country_for_week(
                        last_year_shopify_df, 
                        last_year_qlik_df, 
                        last_year_week_str
                    )
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

