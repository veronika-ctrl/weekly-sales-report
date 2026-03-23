"""Chart generation functions."""

from pathlib import Path
from typing import Dict, Any

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.offline import plot
import kaleido

from weekly_report.src.viz.theme import (
    COLORS, CHART_STYLE, EXPORT_SETTINGS, 
    get_chart_colors, format_currency, format_percentage
)
from loguru import logger


def trend_sales(kpi_data: pd.DataFrame, output_path: Path) -> Path:
    """Generate trend sales chart."""
    
    # Filter for sales-related metrics
    if kpi_data.empty or 'metric' not in kpi_data.columns:
        logger.warning("No KPI data found for trend chart")
        return create_empty_chart("No Sales Data", output_path)
    
    sales_metrics = kpi_data[kpi_data['metric'].isin(['gross_revenue', 'net_revenue', 'total_revenue'])]
    
    if sales_metrics.empty:
        logger.warning("No sales data found for trend chart")
        return create_empty_chart("No Sales Data", output_path)
    
    # Create line chart
    fig = go.Figure()
    
    colors = get_chart_colors(len(sales_metrics['metric'].unique()))
    
    for i, metric in enumerate(sales_metrics['metric'].unique()):
        metric_data = sales_metrics[sales_metrics['metric'] == metric]
        
        fig.add_trace(go.Scatter(
            x=metric_data['week'],
            y=metric_data['value'],
            mode='lines+markers',
            name=metric.replace('_', ' ').title(),
            line=dict(color=colors[i], width=3),
            marker=dict(size=8)
        ))
    
    # Update layout
    fig.update_layout(
        title="Sales Trend",
        xaxis_title="Week",
        yaxis_title="Sales (SEK)",
        font=dict(family=CHART_STYLE['font_family'], size=CHART_STYLE['font_size']),
        title_font_size=CHART_STYLE['title_font_size'],
        margin=CHART_STYLE['margin'],
        plot_bgcolor=CHART_STYLE['background_color'],
        paper_bgcolor=CHART_STYLE['background_color'],
        width=EXPORT_SETTINGS['width'],
        height=EXPORT_SETTINGS['height'],
    )
    
    # Format y-axis
    fig.update_layout(yaxis=dict(tickformat=".0f"))
    
    # Export chart
    output_file = output_path / "trend_sales.png"
    fig.write_image(str(output_file), scale=EXPORT_SETTINGS['scale'])
    
    logger.info(f"Generated trend sales chart: {output_file}")
    return output_file


def bar_yoy_wow(market_data: pd.DataFrame, output_path: Path) -> Path:
    """Generate YoY/WoW comparison bar chart."""
    
    if market_data.empty:
        logger.warning("No market data found for YoY/WoW chart")
        return create_empty_chart("No Market Data", output_path)
    
    # Get top 10 markets by revenue
    top_markets = market_data.head(10)
    
    # Create bar chart
    fig = go.Figure()
    
    colors = get_chart_colors(2)
    
    # Add YoY bars
    fig.add_trace(go.Bar(
        name="YoY Growth",
        x=top_markets['country'],
        y=top_markets['yoy_growth_pct'],
        marker_color=colors[0],
        text=top_markets['yoy_growth_pct'].apply(format_percentage),
        textposition='auto',
    ))
    
    # Add WoW bars
    fig.add_trace(go.Bar(
        name="WoW Growth",
        x=top_markets['country'],
        y=top_markets['wow_growth_pct'],
        marker_color=colors[1],
        text=top_markets['wow_growth_pct'].apply(format_percentage),
        textposition='auto',
    ))
    
    # Update layout
    fig.update_layout(
        title="Market Growth Comparison",
        xaxis_title="Country",
        yaxis_title="Growth (%)",
        font=dict(family=CHART_STYLE['font_family'], size=CHART_STYLE['font_size']),
        title_font_size=CHART_STYLE['title_font_size'],
        margin=CHART_STYLE['margin'],
        plot_bgcolor=CHART_STYLE['background_color'],
        paper_bgcolor=CHART_STYLE['background_color'],
        barmode='group',
        width=EXPORT_SETTINGS['width'],
        height=EXPORT_SETTINGS['height'],
    )
    
    # Export chart
    output_file = output_path / "bar_yoy_wow.png"
    fig.write_image(str(output_file), scale=EXPORT_SETTINGS['scale'])
    
    logger.info(f"Generated YoY/WoW chart: {output_file}")
    return output_file


def waterfall_contrib(kpi_data: pd.DataFrame, output_path: Path) -> Path:
    """Generate waterfall contribution chart."""
    
    # Filter for key metrics
    key_metrics = kpi_data[kpi_data['metric'].isin([
        'gross_revenue', 'net_revenue', 'returns', 'total_spend'
    ])]
    
    if key_metrics.empty:
        logger.warning("No key metrics found for waterfall chart")
        return create_empty_chart("No Key Metrics", output_path)
    
    # Create waterfall chart
    fig = go.Figure()
    
    # Prepare data for waterfall
    metrics = key_metrics['metric'].tolist()
    values = key_metrics['value'].tolist()
    
    # Create waterfall bars
    for i, (metric, value) in enumerate(zip(metrics, values)):
        color = COLORS['success'] if value > 0 else COLORS['warning']
        
        fig.add_trace(go.Bar(
            x=[metric.replace('_', ' ').title()],
            y=[value],
            marker_color=color,
            text=format_currency(value),
            textposition='auto',
            showlegend=False,
        ))
    
    # Update layout
    fig.update_layout(
        title="Revenue Waterfall",
        xaxis_title="Metrics",
        yaxis_title="Amount (SEK)",
        font=dict(family=CHART_STYLE['font_family'], size=CHART_STYLE['font_size']),
        title_font_size=CHART_STYLE['title_font_size'],
        margin=CHART_STYLE['margin'],
        plot_bgcolor=CHART_STYLE['background_color'],
        paper_bgcolor=CHART_STYLE['background_color'],
        width=EXPORT_SETTINGS['width'],
        height=EXPORT_SETTINGS['height'],
    )
    
    # Export chart
    output_file = output_path / "waterfall_contrib.png"
    fig.write_image(str(output_file), scale=EXPORT_SETTINGS['scale'])
    
    logger.info(f"Generated waterfall chart: {output_file}")
    return output_file


def create_empty_chart(title: str, output_path: Path) -> Path:
    """Create an empty chart with a message."""
    
    fig = go.Figure()
    
    fig.add_annotation(
        text=title,
        xref="paper", yref="paper",
        x=0.5, y=0.5,
        showarrow=False,
        font=dict(size=16, color=COLORS['muted'])
    )
    
    fig.update_layout(
        xaxis=dict(showgrid=False, showticklabels=False),
        yaxis=dict(showgrid=False, showticklabels=False),
        plot_bgcolor=CHART_STYLE['background_color'],
        paper_bgcolor=CHART_STYLE['background_color'],
        width=EXPORT_SETTINGS['width'],
        height=EXPORT_SETTINGS['height'],
    )
    
    output_file = output_path / "empty_chart.png"
    fig.write_image(str(output_file), scale=EXPORT_SETTINGS['scale'])
    
    return output_file
