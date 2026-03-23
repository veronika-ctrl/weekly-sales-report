"""Market transformation logic."""

from typing import Dict

import pandas as pd
from loguru import logger


def transform_to_markets(data_sources: Dict[str, pd.DataFrame], week: str) -> pd.DataFrame:
    """Transform raw data sources into market analysis data."""
    
    markets = []
    
    # Extract market data from Qlik (has Country column)
    if 'qlik' in data_sources:
        qlik_df = data_sources['qlik']
        
        # Group by country to get market metrics
        if 'Country' in qlik_df.columns and 'Gross Revenue' in qlik_df.columns:
            market_metrics = qlik_df.groupby('Country').agg({
                'Gross Revenue': 'sum',
                'Net Revenue': 'sum',
                'Returns': 'sum'
            }).reset_index()
            
            market_metrics.columns = ['country', 'revenue', 'net_revenue', 'returns']
            market_metrics['units'] = 0  # Placeholder
            market_metrics['orders'] = 0  # Placeholder
            market_metrics['refunds'] = market_metrics['returns']
            market_metrics['avg_order_value'] = 0
            market_metrics['refund_rate'] = 0
            
            # Add week and source
            market_metrics['week'] = week
            market_metrics['source'] = 'qlik'
            
            markets.extend(market_metrics.to_dict('records'))
    
    # Extract market data from other sources if available
    if 'other' in data_sources:
        other_df = data_sources['other']
        
        # If other data has country information, process it
        if 'country' in other_df.columns:
            other_markets = other_df.groupby('country').size().reset_index(name='count')
            other_markets['week'] = week
            other_markets['source'] = 'other'
            other_markets['revenue'] = 0  # Placeholder
            other_markets['units'] = other_markets['count']
            other_markets['orders'] = other_markets['count']
            other_markets['refunds'] = 0
            other_markets['avg_order_value'] = 0
            other_markets['refund_rate'] = 0
            
            markets.extend(other_markets.to_dict('records'))
    
    # Create DataFrame
    market_df = pd.DataFrame(markets)
    
    if not market_df.empty:
        # Add YoY and WoW calculations (placeholder for now)
        market_df = add_period_comparisons(market_df)
        
        # Sort by revenue descending
        market_df = market_df.sort_values('revenue', ascending=False).reset_index(drop=True)
    
    logger.info(f"Generated {len(market_df)} market records for week {week}")
    return market_df


def add_period_comparisons(market_df: pd.DataFrame) -> pd.DataFrame:
    """Add year-over-year and week-over-week comparisons."""
    
    # For now, we'll add placeholder columns
    # In a real implementation, you'd load historical data and calculate actual comparisons
    
    market_df['yoy_growth_pct'] = 0.0  # Placeholder
    market_df['wow_growth_pct'] = 0.0  # Placeholder
    market_df['yoy_trend'] = 'stable'  # Placeholder
    market_df['wow_trend'] = 'stable'  # Placeholder
    
    return market_df
