"""Product transformation logic."""

from typing import Dict

import pandas as pd
from loguru import logger


def transform_to_products(data_sources: Dict[str, pd.DataFrame], week: str) -> pd.DataFrame:
    """Transform raw data sources into product analysis data."""
    
    products = []
    
    # Extract product data from Qlik (has Product columns)
    if 'qlik' in data_sources:
        qlik_df = data_sources['qlik']
        
        # Group by product to get product metrics
        if 'Product' in qlik_df.columns and 'Gross Revenue' in qlik_df.columns:
            product_metrics = qlik_df.groupby('Product').agg({
                'Gross Revenue': 'sum',
                'Net Revenue': 'sum',
                'Returns': 'sum',
                'Sales Qty': 'sum'
            }).reset_index()
            
            product_metrics.columns = ['product_key', 'revenue', 'net_revenue', 'returns', 'units']
            product_metrics['orders'] = 0  # Placeholder
            product_metrics['refunds'] = product_metrics['returns']
            product_metrics['avg_order_value'] = 0
            product_metrics['refund_rate'] = 0
            
            # Add week and source
            product_metrics['week'] = week
            product_metrics['source'] = 'qlik'
            
            products.extend(product_metrics.to_dict('records'))
    
    # Extract product data from other sources if available
    if 'other' in data_sources:
        other_df = data_sources['other']
        
        # If other data has product information, process it
        if 'product_key' in other_df.columns:
            other_products = other_df.groupby('product_key').size().reset_index(name='count')
            other_products['week'] = week
            other_products['source'] = 'other'
            other_products['revenue'] = 0  # Placeholder
            other_products['units'] = other_products['count']
            other_products['orders'] = other_products['count']
            other_products['refunds'] = 0
            other_products['avg_order_value'] = 0
            other_products['refund_rate'] = 0
            
            products.extend(other_products.to_dict('records'))
    
    # Create DataFrame
    product_df = pd.DataFrame(products)
    
    if not product_df.empty:
        # Add YoY and WoW calculations (placeholder for now)
        product_df = add_period_comparisons(product_df)
        
        # Sort by revenue descending
        product_df = product_df.sort_values('revenue', ascending=False).reset_index(drop=True)
    
    logger.info(f"Generated {len(product_df)} product records for week {week}")
    return product_df


def add_period_comparisons(product_df: pd.DataFrame) -> pd.DataFrame:
    """Add year-over-year and week-over-week comparisons."""
    
    # For now, we'll add placeholder columns
    # In a real implementation, you'd load historical data and calculate actual comparisons
    
    product_df['yoy_growth_pct'] = 0.0  # Placeholder
    product_df['wow_growth_pct'] = 0.0  # Placeholder
    product_df['yoy_trend'] = 'stable'  # Placeholder
    product_df['wow_trend'] = 'stable'  # Placeholder
    
    return product_df
