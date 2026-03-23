"""Total Contribution per country metrics calculation."""
from typing import Dict, Any, List
import pandas as pd
from loguru import logger
from pathlib import Path

from weekly_report.src.metrics.table1 import load_all_raw_data


def calculate_total_contribution_per_country_for_week(
    qlik_df: pd.DataFrame,
    dema_df: pd.DataFrame,
    dema_gm2_df: pd.DataFrame,
    week_str: str
) -> Dict[str, Any]:
    """Calculate total contribution per country for all customers for a single week."""
    
    if qlik_df.empty or dema_gm2_df.empty or dema_df.empty:
        logger.warning(f"Missing data for week {week_str}")
        return {
            'week': week_str,
            'countries': {}
        }
    
    # Filter for online sales only
    online_df = qlik_df[qlik_df['Sales Channel'] == 'Online'].copy()
    
    if online_df.empty:
        logger.warning(f"No online sales found for week {week_str}")
        return {
            'week': week_str,
            'countries': {}
        }
    
    # Get total marketing spend per country (100% allocation)
    country_spend = dema_df.groupby('Country').agg({
        'Marketing spend': 'sum'
    }).reset_index()
    country_spend['Total marketing spend'] = country_spend['Marketing spend'] * 1.0
    
    # Get gross revenue per country for all online customers
    country_revenue = online_df.groupby('Country').agg({
        'Gross Revenue': 'sum'
    }).reset_index()
    country_revenue.columns = ['Country', 'gross_revenue']
    
    # Get overall GM2 (average across all customers)
    logger.info(f"Week {week_str}: GM2 columns: {dema_gm2_df.columns.tolist()}")
    
    if 'Country' in dema_gm2_df.columns:
        # GM2 has country dimension
        logger.info(f"Week {week_str}: GM2 countries: {dema_gm2_df['Country'].unique().tolist()}")
        country_gm2 = dema_gm2_df.groupby('Country').agg({
            'Gross margin 2 - Dema MTA': 'mean'
        }).reset_index()
        country_gm2.columns = ['Country', 'gm2_pct']
        logger.info(f"Week {week_str}: GM2 per country:\n{country_gm2}")
    else:
        # GM2 doesn't have country dimension - use overall average
        logger.info(f"Week {week_str}: No country dimension in GM2, using overall average")
        overall_gm2_pct = dema_gm2_df['Gross margin 2 - Dema MTA'].mean() if 'Gross margin 2 - Dema MTA' in dema_gm2_df.columns else 0
        
        # Create a dummy country_gm2 with the overall percentage for all countries
        country_gm2 = country_revenue[['Country']].copy()
        country_gm2['gm2_pct'] = overall_gm2_pct
        logger.info(f"Week {week_str}: Using overall GM2%: {overall_gm2_pct} for all countries")
    
    # Merge all data
    merged_df = pd.merge(
        pd.merge(country_revenue, country_gm2, on='Country', how='outer'),
        country_spend,
        on='Country',
        how='outer'
    ).fillna(0)
    
    logger.info(f"Week {week_str}: After merge, shape: {merged_df.shape}")
    logger.info(f"Week {week_str}: After merge, countries: {merged_df['Country'].unique().tolist()}")
    
    # Calculate GM2 in SEK per country = Gross Revenue * GM2 percentage
    merged_df['gm2_sek'] = merged_df['gross_revenue'] * merged_df['gm2_pct']
    
    # Calculate Total Contribution = GM2 - Total Marketing spend
    merged_df['total_contribution'] = merged_df['gm2_sek'] - merged_df['Total marketing spend']
    
    # Debug logging
    logger.info(f"Week {week_str}: Merged data shape: {merged_df.shape}")
    logger.info(f"Week {week_str}: Sample countries: {merged_df[['Country', 'gross_revenue', 'gm2_pct', 'total_contribution']].head().to_dict()}")
    
    # Create result dict
    result = {
        'week': week_str,
        'countries': {}
    }
    
    # Add each country's total contribution
    for _, row in merged_df.iterrows():
        country = row['Country']
        if pd.notna(country) and country != '-':
            result['countries'][country] = float(row['total_contribution'])
    
    # Calculate Total Contribution (aggregate of all countries)
    total_gm2_sek = merged_df['gm2_sek'].sum()
    total_marketing_spend = merged_df['Total marketing spend'].sum()
    total_contribution = total_gm2_sek - total_marketing_spend
    
    result['countries']['Total'] = float(total_contribution)
    
    # Calculate ROW (Rest of World) - aggregate of smaller countries
    main_countries = ['United States', 'United Kingdom', 'Sweden', 'Germany', 'Australia', 'Canada', 'France']
    
    row_df = merged_df[~merged_df['Country'].isin(main_countries) & (merged_df['Country'] != 'Total') & (merged_df['Country'] != 'ROW')]
    
    logger.info(f"Week {week_str} Total Contribution: All countries: {merged_df['Country'].unique().tolist()}")
    logger.info(f"Week {week_str} Total Contribution: ROW countries: {row_df['Country'].unique().tolist()}")
    
    row_gm2_sek = row_df['gm2_sek'].sum()
    row_marketing_spend = row_df['Total marketing spend'].sum()
    row_contribution = row_gm2_sek - row_marketing_spend
    
    logger.info(f"Week {week_str} Total Contribution: ROW gm2_sek: {row_gm2_sek}, marketing: {row_marketing_spend}, contribution: {row_contribution}")
    
    result['countries']['ROW'] = float(row_contribution)
    
    return result


def calculate_total_contribution_per_country_for_weeks(base_week: str, num_weeks: int, data_root: Path) -> List[Dict[str, Any]]:
    """Calculate total contribution per country for multiple weeks."""
    
    results = []
    
    # Load data
    latest_data_path = data_root / "raw" / base_week
    logger.info(f"Loading data from {latest_data_path}")
    raw_data = load_all_raw_data(latest_data_path)
    qlik_df = raw_data.get('qlik', pd.DataFrame())
    dema_df = raw_data.get('dema_spend', pd.DataFrame())
    dema_gm2_df = raw_data.get('dema_gm2', pd.DataFrame())
    
    if qlik_df.empty or dema_df.empty or dema_gm2_df.empty:
        logger.warning(f"Missing required data in {data_root}")
        return []
    
    # Add iso_week columns if not present
    if 'iso_week' not in qlik_df.columns and 'Date' in qlik_df.columns:
        iso_cal = pd.to_datetime(qlik_df['Date']).dt.isocalendar()
        qlik_df['iso_week'] = iso_cal['year'].astype(str) + '-' + iso_cal['week'].astype(str).str.zfill(2)
    
    if 'iso_week' not in dema_df.columns and 'Days' in dema_df.columns:
        iso_cal = pd.to_datetime(dema_df['Days']).dt.isocalendar()
        dema_df['iso_week'] = iso_cal['year'].astype(str) + '-' + iso_cal['week'].astype(str).str.zfill(2)
    
    if 'iso_week' not in dema_gm2_df.columns and 'Days' in dema_gm2_df.columns:
        iso_cal = pd.to_datetime(dema_gm2_df['Days']).dt.isocalendar()
        dema_gm2_df['iso_week'] = iso_cal['year'].astype(str) + '-' + iso_cal['week'].astype(str).str.zfill(2)
    
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
            week_dema_df = dema_df[dema_df['iso_week'] == week_str].copy()
            week_dema_gm2_df = dema_gm2_df[dema_gm2_df['iso_week'] == week_str].copy()
            
            if week_qlik_df.empty or week_dema_df.empty or week_dema_gm2_df.empty:
                logger.warning(f"Missing data for week {week_str}")
                continue
            
            # Calculate total contribution per country
            week_data = calculate_total_contribution_per_country_for_week(
                week_qlik_df,
                week_dema_df,
                week_dema_gm2_df,
                week_str
            )
            
            # Get last year data
            last_year = target_year - 1
            last_year_week_str = f"{last_year}-{target_week_num:02d}"
            
            try:
                last_year_qlik_df = qlik_df[qlik_df['iso_week'] == last_year_week_str].copy()
                last_year_dema_df = dema_df[dema_df['iso_week'] == last_year_week_str].copy()
                last_year_dema_gm2_df = dema_gm2_df[dema_gm2_df['iso_week'] == last_year_week_str].copy()
                
                if not last_year_qlik_df.empty and not last_year_dema_df.empty and not last_year_dema_gm2_df.empty:
                    last_year_data = calculate_total_contribution_per_country_for_week(
                        last_year_qlik_df,
                        last_year_dema_df,
                        last_year_dema_gm2_df,
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

