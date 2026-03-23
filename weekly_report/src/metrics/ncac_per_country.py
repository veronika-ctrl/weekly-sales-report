"""nCAC (New Customer Acquisition Cost) per country metrics calculation."""
from typing import Dict, Any, List
import pandas as pd
from loguru import logger
from pathlib import Path

from weekly_report.src.metrics.table1 import load_all_raw_data


def calculate_ncac_per_country_for_week(
    dema_df: pd.DataFrame, 
    qlik_df: pd.DataFrame, 
    week_str: str
) -> Dict[str, Any]:
    """Calculate nCAC per country for a single week."""
    
    if dema_df.empty or qlik_df.empty:
        logger.warning(f"Missing DEMA or Qlik data for week {week_str}")
        return {
            'week': week_str,
            'countries': {}
        }
    
    # Calculate marketing spend per country (70% allocation for new customers)
    country_spend = dema_df.groupby('Country').agg({
        'Marketing spend': 'sum'
    }).reset_index()
    country_spend['New customer spend'] = country_spend['Marketing spend'] * 0.70
    
    # Count new customers per country from Qlik data
    new_customers_df = qlik_df[
        (qlik_df['Sales Channel'] == 'Online') & 
        (qlik_df['New/Returning Customer'] == 'New')
    ].copy()
    
    customers_per_country = new_customers_df.groupby('Country').agg(
        new_customers=('Customer E-mail', 'nunique')
    ).reset_index()
    
    # Merge spending and customers data
    merged_df = pd.merge(
        country_spend,
        customers_per_country,
        on='Country',
        how='outer'
    ).fillna(0)
    
    # Calculate nCAC = New customer spend / New customers
    merged_df['ncac'] = merged_df.apply(
        lambda row: row['New customer spend'] / row['new_customers'] if row['new_customers'] > 0 else 0,
        axis=1
    )
    
    # Create result dict
    result = {
        'week': week_str,
        'countries': {}
    }
    
    # Add each country's nCAC
    for _, row in merged_df.iterrows():
        country = row['Country']
        if pd.notna(country) and country != '-':
            result['countries'][country] = float(row['ncac'])
    
    # Calculate Total nCAC = Total New Customer Spend / Total New Customers
    total_new_customer_spend = merged_df['New customer spend'].sum()
    total_new_customers = merged_df['new_customers'].sum()
    if total_new_customers > 0:
        total_ncac = total_new_customer_spend / total_new_customers
    else:
        total_ncac = 0
    
    result['countries']['Total'] = float(total_ncac)
    
    # Calculate ROW (Rest of World) - aggregate of smaller countries
    # Main countries to exclude
    main_countries = ['United States', 'United Kingdom', 'Sweden', 'Germany', 'Australia', 'Canada', 'France']
    
    row_df = merged_df[~merged_df['Country'].isin(main_countries) & (merged_df['Country'] != 'Total') & (merged_df['Country'] != 'ROW')]
    
    logger.info(f"Week {week_str}: All countries in data: {merged_df['Country'].unique().tolist()}")
    logger.info(f"Week {week_str}: ROW countries: {row_df['Country'].unique().tolist()}")
    logger.info(f"Week {week_str}: ROW marketing spend: {row_df['New customer spend'].sum()}, ROW customers: {row_df['new_customers'].sum()}")
    
    row_marketing_spend = row_df['New customer spend'].sum()
    row_customers = row_df['new_customers'].sum()
    
    if row_customers > 0:
        row_ncac = row_marketing_spend / row_customers
    else:
        row_ncac = 0
    
    result['countries']['ROW'] = float(row_ncac)
    
    return result


def calculate_ncac_per_country_for_weeks(base_week: str, num_weeks: int, data_root: Path) -> List[Dict[str, Any]]:
    """Calculate nCAC per country for multiple weeks."""
    
    results = []
    
    # Load DEMA spend and Qlik data
    # data_root is ./data, so we need data_root/raw/{base_week}
    raw_data_path = data_root / "raw" / base_week
    logger.info(f"Loading DEMA spend and Qlik data from {raw_data_path}")
    raw_data = load_all_raw_data(raw_data_path)
    dema_df = raw_data.get('dema_spend', pd.DataFrame())
    qlik_df = raw_data.get('qlik', pd.DataFrame())
    
    if dema_df.empty or qlik_df.empty:
        logger.warning(f"No DEMA spend or Qlik data found in {raw_data_path}")
        return []
    
    # Add iso_week column if not present
    if 'iso_week' not in dema_df.columns:
        if 'Days' in dema_df.columns:
            iso_cal = pd.to_datetime(dema_df['Days']).dt.isocalendar()
            dema_df['iso_week'] = iso_cal['year'].astype(str) + '-' + iso_cal['week'].astype(str).str.zfill(2)
    
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
            week_dema_df = dema_df[dema_df['iso_week'] == week_str].copy()
            week_qlik_df = qlik_df[qlik_df['iso_week'] == week_str].copy()
            
            if week_dema_df.empty or week_qlik_df.empty:
                logger.warning(f"No data for week {week_str}")
                continue
            
            # Calculate nCAC per country
            week_data = calculate_ncac_per_country_for_week(week_dema_df, week_qlik_df, week_str)
            
            # Get last year data
            last_year = target_year - 1
            last_year_week_str = f"{last_year}-{target_week_num:02d}"
            
            try:
                last_year_dema_df = dema_df[dema_df['iso_week'] == last_year_week_str].copy()
                last_year_qlik_df = qlik_df[qlik_df['iso_week'] == last_year_week_str].copy()
                
                if not last_year_dema_df.empty and not last_year_qlik_df.empty:
                    last_year_data = calculate_ncac_per_country_for_week(
                        last_year_dema_df,
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

