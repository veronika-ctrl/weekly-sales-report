"""AOV Returning Customers per country metrics calculation."""
from typing import Dict, Any, List
import pandas as pd
from loguru import logger
from pathlib import Path

from weekly_report.src.metrics.table1 import load_all_raw_data


def calculate_aov_returning_customers_per_country_for_week(qlik_df: pd.DataFrame, week_str: str) -> Dict[str, Any]:
    """Calculate AOV for returning customers per country for a single week."""
    
    if qlik_df.empty:
        logger.warning(f"No Qlik data found for week {week_str}")
        return {
            'week': week_str,
            'countries': {}
        }
    
    # Filter for online sales and returning customers
    online_df = qlik_df[qlik_df['Sales Channel'] == 'Online'].copy()
    returning_customers_df = online_df[online_df['New/Returning Customer'] == 'Returning'].copy()
    
    if returning_customers_df.empty:
        logger.warning(f"No returning customer data found for week {week_str}")
        return {
            'week': week_str,
            'countries': {}
        }
    
    # Calculate AOV per country: Gross Revenue / Number of unique orders
    country_aov = returning_customers_df.groupby('Country').agg({
        'Gross Revenue': 'sum',
        'Order No': 'nunique'
    }).reset_index()
    
    country_aov.columns = ['Country', 'Gross Revenue', 'Orders']
    
    # Calculate AOV: Gross Revenue / Orders
    country_aov['AOV'] = country_aov['Gross Revenue'] / country_aov['Orders']
    country_aov['AOV'] = country_aov['AOV'].fillna(0)
    
    # Calculate Total AOV across all countries
    total_gross_revenue = returning_customers_df['Gross Revenue'].sum()
    total_orders = returning_customers_df['Order No'].nunique()
    total_aov = total_gross_revenue / total_orders if total_orders > 0 else 0
    
    logger.info(f"Total AOV for returning customers week {week_str}: Gross Revenue={total_gross_revenue}, Orders={total_orders}, AOV={total_aov}")
    
    # Define main countries (these will NOT be included in ROW)
    main_countries = ['United States', 'United Kingdom', 'Sweden', 'Germany', 'Australia', 'Canada', 'France']
    
    # Create result dict
    result = {
        'week': week_str,
        'countries': {}
    }
    
    # Add Total AOV first
    if total_orders > 0:
        result['countries']['Total'] = float(total_aov)
    
    # Calculate ROW AOV (all countries except the main 7)
    row_gross_revenue = 0
    row_orders = 0
    for _, row in country_aov.iterrows():
        country = row['Country']
        if pd.notna(country) and country != '-' and country not in main_countries:
            row_gross_revenue += row['Gross Revenue']
            row_orders += row['Orders']
    
    if row_orders > 0:
        row_aov = row_gross_revenue / row_orders
        result['countries']['ROW'] = float(row_aov)
    
    # Add each country's AOV
    for _, row in country_aov.iterrows():
        country = row['Country']
        if pd.notna(country) and country != '-':
            result['countries'][country] = float(row['AOV'])
    
    return result


def calculate_aov_returning_customers_per_country_for_weeks(base_week: str, num_weeks: int, data_root: Path) -> List[Dict[str, Any]]:
    """Calculate AOV for returning customers per country for multiple weeks."""
    
    results = []
    
    # Load Qlik data
    # data_root is ./data, so we need data_root/raw/{base_week}
    raw_data_path = data_root / "raw" / base_week
    logger.info(f"Loading Qlik data from {raw_data_path}")
    qlik_df = load_all_raw_data(raw_data_path).get('qlik', pd.DataFrame())
    
    if qlik_df.empty:
        logger.warning(f"No Qlik data found in {raw_data_path}")
        return []
    
    # Add iso_week column if not present
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
            week_qlik_df = qlik_df[qlik_df['iso_week'] == week_str].copy()
            
            if week_qlik_df.empty:
                logger.warning(f"No data for week {week_str}")
                continue
            
            # Calculate AOV for returning customers per country
            week_data = calculate_aov_returning_customers_per_country_for_week(week_qlik_df, week_str)
            
            # Get last year data
            last_year = target_year - 1
            last_year_week_str = f"{last_year}-{target_week_num:02d}"
            
            try:
                last_year_qlik_df = qlik_df[qlik_df['iso_week'] == last_year_week_str].copy()
                
                if not last_year_qlik_df.empty:
                    last_year_data = calculate_aov_returning_customers_per_country_for_week(
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

