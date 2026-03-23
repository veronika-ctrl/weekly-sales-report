"""Top products metrics calculation."""
from typing import Dict, Any, List
import pandas as pd
from loguru import logger
from pathlib import Path

from weekly_report.src.metrics.table1 import load_all_raw_data


def calculate_top_products_for_week(qlik_df: pd.DataFrame, week_str: str, top_n: int = 30, customer_type: str = 'new') -> Dict[str, Any]:
    """Calculate top N products for a single week."""
    
    # Filter for online sales and specified customer type
    customer_filter = 'New' if customer_type == 'new' else 'Returning'
    online_df = qlik_df[
        (qlik_df['Sales Channel'] == 'Online') & 
        (qlik_df['New/Returning Customer'] == customer_filter)
    ].copy()
    
    # Convert Sales Qty to numeric, handling errors
    online_df['Sales Qty'] = pd.to_numeric(online_df['Sales Qty'], errors='coerce').fillna(0)
    
    # Group by Gender, Product Category, Product, and Color
    product_sales = online_df.groupby(['Gender', 'Product Category', 'Product', 'Color']).agg({
        'Gross Revenue': 'sum',
        'Sales Qty': 'sum'
    }).reset_index()
    
    # Filter out rows with invalid data
    product_sales = product_sales[
        (product_sales['Gender'] != '-') & 
        (product_sales['Gender'].notna()) &
        (product_sales['Product Category'] != '-') & 
        (product_sales['Product Category'].notna()) &
        (product_sales['Product'] != '-') & 
        (product_sales['Product'].notna())
    ]
    
    # Sort by Gross Revenue descending
    product_sales = product_sales.sort_values('Gross Revenue', ascending=False)
    
    # Take top N
    top_products = product_sales.head(top_n)
    
    # Calculate total for top N
    top_total_revenue = top_products['Gross Revenue'].sum()
    top_total_qty = top_products['Sales Qty'].sum()
    
    # Calculate grand total (all products)
    grand_total_revenue = online_df['Gross Revenue'].sum()
    grand_total_qty = online_df['Sales Qty'].sum()
    
    # Format results
    products = []
    for idx, row in top_products.iterrows():
        products.append({
            'rank': len(products) + 1,
            'gender': str(row['Gender']).upper(),
            'category': str(row['Product Category']),
            'product': str(row['Product']),
            'color': str(row['Color']) if pd.notna(row['Color']) and str(row['Color']) != '-' else '',
            'gross_revenue': float(row['Gross Revenue']),
            'sales_qty': int(row['Sales Qty'])
        })
    
    return {
        'week': week_str,
        'products': products,
        'top_total': {
            'gross_revenue': float(top_total_revenue),
            'sales_qty': int(top_total_qty),
            'sob': float((top_total_revenue / grand_total_revenue * 100) if grand_total_revenue > 0 else 0)
        },
        'grand_total': {
            'gross_revenue': float(grand_total_revenue),
            'sales_qty': int(grand_total_qty),
            'sob': 100.0
        }
    }


def calculate_top_products_for_weeks(base_week: str, num_weeks: int, data_root: Path, top_n: int = 30, customer_type: str = 'new') -> List[Dict[str, Any]]:
    """Calculate top products for multiple weeks."""
    
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
            week_df = qlik_df[qlik_df['iso_week'] == week_str].copy()
            
            if week_df.empty:
                logger.warning(f"No data for week {week_str}")
                continue
            
            # Calculate top products
            week_data = calculate_top_products_for_week(week_df, week_str, top_n, customer_type)
            
            results.append(week_data)
            
        except Exception as e:
            logger.error(f"Error processing week {week_str}: {e}")
            continue
    
    return results

