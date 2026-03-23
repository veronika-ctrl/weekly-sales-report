"""Category sales metrics calculation."""
from typing import Dict, Any, List
import pandas as pd
from loguru import logger
from pathlib import Path
from datetime import datetime

from weekly_report.src.metrics.table1 import load_all_raw_data


def _has_53_weeks(year: int) -> bool:
    """Check if a year has 53 ISO weeks."""
    jan_4 = datetime(year, 1, 4)
    return jan_4.weekday() >= 3


def calculate_category_sales_for_weeks(base_week: str, num_weeks: int, data_root: Path) -> List[Dict[str, Any]]:
    """Calculate category sales for multiple weeks."""
    
    results = []
    
    # Load all raw data once from base week directory
    # data_root is ./data, so we need data_root/raw/{base_week}
    raw_data_path = data_root / "raw" / base_week
    logger.info(f"Loading raw data from {raw_data_path}")
    raw_data = load_all_raw_data(raw_data_path)
    qlik_df = raw_data.get('qlik', pd.DataFrame())
    
    if qlik_df.empty:
        logger.warning(f"No Qlik data found in {raw_data_path}")
        return []
    
    # Add iso_week column if not present
    if 'iso_week' not in qlik_df.columns and 'Date' in qlik_df.columns:
        iso_cal = pd.to_datetime(qlik_df['Date']).dt.isocalendar()
        qlik_df['iso_week'] = iso_cal['year'].astype(str) + '-' + iso_cal['week'].astype(str).str.zfill(2)
    
    # Filter for online sales only
    online_df = qlik_df[qlik_df['Sales Channel'] == 'Online'].copy()
    
    # Parse base week
    year, week_num = base_week.split('-')
    year = int(year)
    week_num = int(week_num)
    
    # Generate list of weeks to process (excluding week 53)
    weeks_to_process = []
    i = 0
    while len(weeks_to_process) < num_weeks:
        target_week_num = week_num - i
        target_year = year
        
        if target_week_num < 1:
            # Need to go back to previous year
            target_year = year - 1
            # Check if previous year had 53 weeks
            if _has_53_weeks(target_year):
                target_week_num = 53 + target_week_num
            else:
                target_week_num = 52 + target_week_num
            
            # Exclude week 53
            if target_week_num == 53:
                target_week_num = 52
                i += 1
                continue
        
        week_str = f"{target_year}-{target_week_num:02d}"
        if week_str not in weeks_to_process:
            weeks_to_process.append(week_str)
        i += 1
    
    # Reverse to match chronological order (oldest first)
    weeks_to_process = weeks_to_process[::-1]
    
    # Get all unique categories and genders
    all_categories = set()
    all_genders = set(['MEN', 'WOMEN'])
    
    for week_str in weeks_to_process:
        # Filter data for this week
        week_df = online_df[online_df['iso_week'] == week_str].copy()
        
        if not week_df.empty:
            # Collect unique categories
            for cat in week_df['Product Category'].dropna().unique():
                if str(cat) != '-':
                    all_categories.add(str(cat))
    
    # Group by Gender and Product Category for each week
    for week_str in weeks_to_process:
        
        try:
            # Filter data for this week
            week_df = online_df[online_df['iso_week'] == week_str].copy()
            
            if week_df.empty:
                continue
            
            # Group by Gender and Product Category (include NaN values)
            grouped = week_df.groupby(['Gender', 'Product Category'], dropna=False).agg({
                'Gross Revenue': 'sum'
            }).reset_index()
            
            # Create result dict for this week
            week_result = {
                'week': week_str,
                'categories': {}
            }
            
            # Process each gender-category combination
            for _, row in grouped.iterrows():
                gender_raw = row['Gender']
                category_raw = row['Product Category']
                revenue = float(row['Gross Revenue'])
                
                # Skip rows with no revenue
                if revenue == 0:
                    continue
                
                # Check if gender or category is invalid
                gender_is_invalid = (pd.isna(gender_raw) or str(gender_raw).upper() == '-')
                category_is_invalid = (pd.isna(category_raw) or str(category_raw) == '-')
                
                # Handle invalid categories by grouping them under MEN
                if category_is_invalid:
                    # Add to a special "Other" category for Men
                    key = "MEN_OTHER"
                    if key not in week_result['categories']:
                        week_result['categories'][key] = 0
                    week_result['categories'][key] += revenue
                    continue
                
                # Convert to strings for normal processing
                gender = str(gender_raw).upper()
                category = str(category_raw)
                
                # Include ALL genders except WOMEN in MEN category
                if gender != 'WOMEN':
                    key = f"MEN_{category}"
                    if key not in week_result['categories']:
                        week_result['categories'][key] = 0
                    week_result['categories'][key] += revenue
                elif gender == 'WOMEN':
                    key = f"{gender}_{category}"
                    week_result['categories'][key] = revenue
            
            # Get last year data (same week number, previous year)
            week_year, week_week_num = week_str.split('-')
            week_year = int(week_year)
            week_week_num = int(week_week_num)
            
            last_year = week_year - 1
            
            # Check if last year had 53 weeks and we're trying to match week 53
            if week_week_num == 53 and not _has_53_weeks(last_year):
                # If last year doesn't have week 53, use week 52
                last_year_week_str = f"{last_year}-52"
            else:
                last_year_week_str = f"{last_year}-{week_week_num:02d}"
            
            try:
                last_year_df = online_df[online_df['iso_week'] == last_year_week_str].copy()
                
                if not last_year_df.empty:
                    last_year_grouped = last_year_df.groupby(['Gender', 'Product Category'], dropna=False).agg({
                        'Gross Revenue': 'sum'
                    }).reset_index()
                    
                    last_year_result = {
                        'week': last_year_week_str,
                        'categories': {}
                    }
                    
                    for _, row in last_year_grouped.iterrows():
                        gender_raw = row['Gender']
                        category_raw = row['Product Category']
                        revenue = float(row['Gross Revenue'])
                        
                        # Skip rows with no revenue
                        if revenue == 0:
                            continue
                        
                        # Check if gender or category is invalid
                        gender_is_invalid = (pd.isna(gender_raw) or str(gender_raw).upper() == '-')
                        category_is_invalid = (pd.isna(category_raw) or str(category_raw) == '-')
                        
                        # Handle invalid categories by grouping them under MEN
                        if category_is_invalid:
                            # Add to a special "Other" category for Men
                            key = "MEN_OTHER"
                            if key not in last_year_result['categories']:
                                last_year_result['categories'][key] = 0
                            last_year_result['categories'][key] += revenue
                            continue
                        
                        # Convert to strings for normal processing
                        gender = str(gender_raw).upper()
                        category = str(category_raw)
                        
                        # Include ALL genders except WOMEN in MEN category
                        if gender != 'WOMEN':
                            key = f"MEN_{category}"
                            if key not in last_year_result['categories']:
                                last_year_result['categories'][key] = 0
                            last_year_result['categories'][key] += revenue
                        elif gender == 'WOMEN':
                            key = f"{gender}_{category}"
                            last_year_result['categories'][key] = revenue
                    
                    week_result['last_year'] = last_year_result
                else:
                    week_result['last_year'] = None
            except Exception as e:
                logger.warning(f"Could not load last year data for {last_year_week_str}: {e}")
                week_result['last_year'] = None
            
            results.append(week_result)
            
        except Exception as e:
            logger.error(f"Error processing week {week_str}: {e}")
            continue
    
    return results

