"""Table generation functions."""

from pathlib import Path
from typing import Dict, Any

import pandas as pd
import plotly.graph_objects as go
from plotly.offline import plot
import kaleido

from weekly_report.src.viz.theme import (
    COLORS, TABLE_STYLE, EXPORT_SETTINGS, 
    format_currency, format_percentage, format_number
)
from loguru import logger


def kpi_table(kpi_data: pd.DataFrame, output_path: Path) -> Path:
    """Generate KPI summary table."""
    
    if kpi_data.empty:
        logger.warning("No KPI data found for table")
        return create_empty_table("No KPI Data", output_path)
    
    # Prepare table data
    table_data = kpi_data.copy()
    
    # Format values based on metric type
    for idx, row in table_data.iterrows():
        metric = row['metric']
        value = row['value']
        
        if 'pct' in metric or 'rate' in metric:
            table_data.loc[idx, 'formatted_value'] = format_percentage(value)
        elif 'sales' in metric or 'revenue' in metric or 'cost' in metric:
            table_data.loc[idx, 'formatted_value'] = format_currency(value)
        else:
            table_data.loc[idx, 'formatted_value'] = format_number(value)
    
    # Create table
    fig = go.Figure(data=[go.Table(
        header=dict(
            values=['Metric', 'Value', 'Source'],
            fill_color=TABLE_STYLE['header_color'],
            font=dict(color=TABLE_STYLE['header_text_color'], size=TABLE_STYLE['header_font_size']),
            align='left'
        ),
        cells=dict(
            values=[
                table_data['metric'].str.replace('_', ' ').str.title(),
                table_data['formatted_value'],
                table_data['source']
            ],
            fill_color=TABLE_STYLE['cell_color'],
            font=dict(color=TABLE_STYLE['cell_text_color'], size=TABLE_STYLE['cell_font_size']),
            align='left'
        )
    )])
    
    # Update layout
    fig.update_layout(
        title="KPI Summary",
        font=dict(family=TABLE_STYLE['font_family'], size=TABLE_STYLE['font_size']),
        title_font_size=TABLE_STYLE['title_font_size'],
        margin=dict(l=20, r=20, t=60, b=20),
        width=EXPORT_SETTINGS['width'],
        height=EXPORT_SETTINGS['height'],
    )
    
    # Export table
    output_file = output_path / "kpi_table.png"
    fig.write_image(str(output_file), scale=EXPORT_SETTINGS['scale'])
    
    logger.info(f"Generated KPI table: {output_file}")
    return output_file


def market_table(market_data: pd.DataFrame, output_path: Path) -> Path:
    """Generate market summary table."""
    
    if market_data.empty:
        logger.warning("No market data found for table")
        return create_empty_table("No Market Data", output_path)
    
    # Get top 10 markets
    top_markets = market_data.head(10)
    
    # Create table
    fig = go.Figure(data=[go.Table(
        header=dict(
            values=['Country', 'Revenue', 'Units', 'Orders', 'YoY Growth', 'WoW Growth'],
            fill_color=TABLE_STYLE['header_color'],
            font=dict(color=TABLE_STYLE['header_text_color'], size=TABLE_STYLE['header_font_size']),
            align='left'
        ),
        cells=dict(
            values=[
                top_markets['country'],
                top_markets['revenue'].apply(format_currency),
                top_markets['units'].apply(format_number),
                top_markets['orders'].apply(format_number),
                top_markets['yoy_growth_pct'].apply(format_percentage),
                top_markets['wow_growth_pct'].apply(format_percentage)
            ],
            fill_color=TABLE_STYLE['cell_color'],
            font=dict(color=TABLE_STYLE['cell_text_color'], size=TABLE_STYLE['cell_font_size']),
            align='left'
        )
    )])
    
    # Update layout
    fig.update_layout(
        title="Top Markets",
        font=dict(family=TABLE_STYLE['font_family'], size=TABLE_STYLE['font_size']),
        title_font_size=TABLE_STYLE['title_font_size'],
        margin=dict(l=20, r=20, t=60, b=20),
        width=EXPORT_SETTINGS['width'],
        height=EXPORT_SETTINGS['height'],
    )
    
    # Export table
    output_file = output_path / "market_table.png"
    fig.write_image(str(output_file), scale=EXPORT_SETTINGS['scale'])
    
    logger.info(f"Generated market table: {output_file}")
    return output_file


def create_empty_table(message: str, output_path: Path) -> Path:
    """Create an empty table with a message."""
    
    fig = go.Figure(data=[go.Table(
        header=dict(
            values=['Status'],
            fill_color=TABLE_STYLE['header_color'],
            font=dict(color=TABLE_STYLE['header_text_color'], size=TABLE_STYLE['header_font_size']),
            align='center'
        ),
        cells=dict(
            values=[[message]],
            fill_color=TABLE_STYLE['cell_color'],
            font=dict(color=TABLE_STYLE['cell_text_color'], size=TABLE_STYLE['cell_font_size']),
            align='center'
        )
    )])
    
    fig.update_layout(
        font=dict(family=TABLE_STYLE['font_family'], size=TABLE_STYLE['font_size']),
        margin=dict(l=20, r=20, t=20, b=20),
        width=EXPORT_SETTINGS['width'],
        height=EXPORT_SETTINGS['height'],
    )
    
    output_file = output_path / "empty_table.png"
    fig.write_image(str(output_file), scale=EXPORT_SETTINGS['scale'])
    
    return output_file

