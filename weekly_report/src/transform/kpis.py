"""KPI transformation logic."""

from datetime import datetime
from typing import Dict

import pandas as pd
from loguru import logger


def transform_to_kpis(data_sources: Dict[str, pd.DataFrame], week: str) -> pd.DataFrame:
    """Transform raw data sources into weekly KPI data."""
    
    kpis = []
    
    # Extract KPIs from Qlik data
    if 'qlik' in data_sources:
        qlik_df = data_sources['qlik']
        
        # Calculate key metrics from Qlik data
        total_gross_revenue = qlik_df['Gross Revenue'].sum() if 'Gross Revenue' in qlik_df.columns else 0
        total_net_revenue = qlik_df['Net Revenue'].sum() if 'Net Revenue' in qlik_df.columns else 0
        total_returns = qlik_df['Returns'].sum() if 'Returns' in qlik_df.columns else 0
        
        kpis.extend([
            {'week': week, 'metric': 'gross_revenue', 'value': total_gross_revenue, 'source': 'qlik'},
            {'week': week, 'metric': 'net_revenue', 'value': total_net_revenue, 'source': 'qlik'},
            {'week': week, 'metric': 'returns', 'value': total_returns, 'source': 'qlik'},
        ])
    
    # Extract KPIs from Dema spend data
    if 'dema_spend' in data_sources:
        dema_spend_df = data_sources['dema_spend']
        
        # Calculate key metrics from spend data
        total_spend = dema_spend_df['Marketing spend'].sum() if 'Marketing spend' in dema_spend_df.columns else 0
        
        kpis.append({
            'week': week,
            'metric': 'total_spend',
            'value': total_spend,
            'source': 'dema_spend'
        })
    
    # Extract KPIs from Dema GM2 data
    if 'dema_gm2' in data_sources:
        dema_gm2_df = data_sources['dema_gm2']
        
        # Calculate key metrics from GM2 data
        total_gross_margin = dema_gm2_df['Gross margin 2 - Dema MTA'].sum() if 'Gross margin 2 - Dema MTA' in dema_gm2_df.columns else 0
        
        kpis.append({
            'week': week,
            'metric': 'gross_margin_2',
            'value': total_gross_margin,
            'source': 'dema_gm2'
        })
    
    # Extract KPIs from Shopify data
    if 'shopify' in data_sources:
        shopify_df = data_sources['shopify']
        
        # Calculate session metrics from Shopify data
        total_sessions = shopify_df['Sessions'].sum() if 'Sessions' in shopify_df.columns else 0
        
        kpis.append({
            'week': week,
            'metric': 'total_sessions',
            'value': total_sessions,
            'source': 'shopify'
        })
    
    # Create DataFrame
    kpi_df = pd.DataFrame(kpis)
    
    if not kpi_df.empty:
        # Add calculated metrics
        kpi_df = add_calculated_metrics(kpi_df)
        
        # Sort by metric name
        kpi_df = kpi_df.sort_values('metric').reset_index(drop=True)
    
    logger.info(f"Generated {len(kpi_df)} KPI records for week {week}")
    return kpi_df


def add_calculated_metrics(kpi_df: pd.DataFrame) -> pd.DataFrame:
    """Add calculated metrics to KPI data."""
    
    # Create a pivot table for easier calculations
    kpi_pivot = kpi_df.pivot_table(
        index='week', 
        columns='metric', 
        values='value', 
        aggfunc='sum'
    ).reset_index()
    
    calculated_metrics = []
    
    # Calculate return rate
    if 'returns' in kpi_pivot.columns and 'gross_sales' in kpi_pivot.columns:
        return_rate = (kpi_pivot['returns'] / kpi_pivot['gross_sales'] * 100).fillna(0)
        calculated_metrics.append({
            'week': kpi_pivot['week'].iloc[0],
            'metric': 'return_rate_pct',
            'value': return_rate.iloc[0],
            'source': 'calculated'
        })
    
    # Calculate profit margin
    if 'net_sales' in kpi_pivot.columns and 'cost_of_sales' in kpi_pivot.columns:
        profit_margin = ((kpi_pivot['net_sales'] - kpi_pivot['cost_of_sales']) / kpi_pivot['net_sales'] * 100).fillna(0)
        calculated_metrics.append({
            'week': kpi_pivot['week'].iloc[0],
            'metric': 'profit_margin_pct',
            'value': profit_margin.iloc[0],
            'source': 'calculated'
        })
    
    # Add calculated metrics to original data
    if calculated_metrics:
        calc_df = pd.DataFrame(calculated_metrics)
        kpi_df = pd.concat([kpi_df, calc_df], ignore_index=True)
    
    return kpi_df
