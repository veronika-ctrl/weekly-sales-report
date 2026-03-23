"""Professional PDF table builder for Table 1."""

from pathlib import Path
from typing import Dict, Any
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch, mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from typing import Dict, Any, Optional

from weekly_report.src.periods.calculator import get_week_date_range
from loguru import logger


def build_table1_pdf(
    metrics_data: Dict[str, Dict[str, Any]], 
    periods: Dict[str, str], 
    output_path: Path
) -> Path:
    """
    Create a professional PDF table matching the design exactly.
    
    Args:
        metrics_data: Dictionary with metrics for each period
        periods: Dictionary with period mappings
        output_path: Path where to save the PDF
        
    Returns:
        Path to the generated PDF file
    """
    
    logger.info(f"Building Table 1 PDF: {output_path}")
    
    # Get page size (A4 landscape)
    page_width, page_height = A4
    page_width, page_height = page_height, page_width  # Landscape
    
    # Create PDF document
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=(page_width, page_height),
        rightMargin=20*mm,
        leftMargin=20*mm,
        topMargin=20*mm,
        bottomMargin=20*mm
    )
    
    # Get styles
    styles = getSampleStyleSheet()
    
    # Create custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=20,
        alignment=TA_CENTER,
        textColor=HexColor('#1f2937'),
        fontName='Helvetica-Bold'
    )
    
    # Build content
    story = []
    
    # Title
    actual_week = periods.get('actual', 'N/A')
    title = Paragraph(f"Weekly Report - Table 1", title_style)
    story.append(title)
    story.append(Spacer(1, 10))
    
    # Get date range for actual period
    try:
        date_range = get_week_date_range(actual_week)
        period_display = date_range['display']
    except Exception as e:
        logger.warning(f"Could not get date range for {actual_week}: {e}")
        period_display = actual_week
    
    # Create the main table
    table_data = create_table_data(metrics_data, periods, period_display)
    
    # Create table with exact styling
    table = Table(table_data, colWidths=[120*mm, 30*mm, 30*mm, 30*mm, 30*mm])
    
    # Apply professional styling
    table.setStyle(TableStyle([
        # Header styling (light yellow background)
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#FFF9E6')),  # Light yellow
        ('TEXTCOLOR', (0, 0), (-1, 0), HexColor('#1f2937')),  # Dark gray text
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        
        # Data row styling
        ('BACKGROUND', (0, 1), (-1, -1), HexColor('#F5F5F5')),  # Light gray
        ('TEXTCOLOR', (0, 1), (-1, -1), HexColor('#1f2937')),  # Dark gray text
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),  # Metric names left-aligned
        ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),  # Numbers right-aligned
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        
        # Borders
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#CCCCCC')),  # Light gray borders
        ('LINEBELOW', (0, 0), (-1, 0), 1, HexColor('#999999')),  # Thicker line below header
        
        # Row striping for better readability
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [HexColor('#F5F5F5'), HexColor('#FFFFFF')]),
    ]))
    
    story.append(table)
    story.append(Spacer(1, 20))
    
    # Add footer info
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        alignment=TA_CENTER,
        textColor=HexColor('#6B7280'),
        fontName='Helvetica'
    )
    
    generated_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    footer = Paragraph(f"Generated on {generated_time} | Base Week: {actual_week}", footer_style)
    story.append(footer)
    
    # Build PDF
    doc.build(story)
    
    logger.info(f"Successfully generated Table 1 PDF: {output_path}")
    return output_path


def create_table_data(
    metrics_data: Dict[str, Dict[str, Any]], 
    periods: Dict[str, str],
    period_display: str
) -> list:
    """Create table data structure for the PDF."""
    
    # Define metric labels and keys
    metric_labels = [
        'Online Gross Revenue',
        'Returns', 
        'Return Rate %',
        'Online Net Revenue',
        'Retail Concept Store',
        'Retail Pop-ups, Outlets',
        'Retail Net Revenue',
        'Wholesale Net Revenue',
        'Total Net Revenue',
        'Returning Customers',
        'New customers',
        'Marketing Spend',
        'Online Cost of Sale(3)',
        'aMER'
    ]
    
    metric_keys = [
        'online_gross_revenue',
        'returns',
        'return_rate_pct', 
        'online_net_revenue',
        'retail_concept_store',
        'retail_popups_outlets',
        'retail_net_revenue',
        'wholesale_net_revenue',
        'total_net_revenue',
        'returning_customers',
        'new_customers',
        'marketing_spend',
        'online_cost_of_sale_3',
        'emer'
    ]
    
    # Create header row
    header = ['Metric', 'Actual', 'Last Week', 'Last Year', '2023', 'vs Last Week', 'vs Last Year', 'vs 2023']
    table_data = [header]
    
    # Add data rows
    for label, key in zip(metric_labels, metric_keys):
        row = [label]
        
        # Add values for each period
        actual_value = metrics_data.get('actual', {}).get(key, 0)
        last_week_value = metrics_data.get('last_week', {}).get(key, 0)
        last_year_value = metrics_data.get('last_year', {}).get(key, 0)
        year_2023_value = metrics_data.get('year_2023', {}).get(key, 0)
        
        row.append(format_metric_value(actual_value, key))
        row.append(format_metric_value(last_week_value, key))
        row.append(format_metric_value(last_year_value, key))
        row.append(format_metric_value(year_2023_value, key))
        
        # Add growth percentages
        row.append(format_growth_percentage(calculate_growth_percentage(actual_value, last_week_value)))
        row.append(format_growth_percentage(calculate_growth_percentage(actual_value, last_year_value)))
        row.append(format_growth_percentage(calculate_growth_percentage(actual_value, year_2023_value)))
        
        table_data.append(row)
    
    return table_data


def calculate_growth_percentage(current: float, previous: float) -> Optional[float]:
    """Calculate growth percentage between two values."""
    if previous == 0:
        return None
    return ((current - previous) / previous) * 100

def format_growth_percentage(value: Optional[float]) -> str:
    """Format growth percentage with parentheses for negative values."""
    if value is None:
        return '-'
    
    abs_value = abs(value)
    formatted = f"{abs_value:.1f}%"
    
    if value < 0:
        return f"({formatted})"
    else:
        return formatted


def create_sample_table1_pdf(output_path: Path) -> Path:
    """Create a sample Table 1 PDF for testing."""
    
    # Sample data
    sample_metrics = {
        'actual': {
            'online_gross_revenue': 1145000,
            'returns': 24000,
            'return_rate_pct': 2.1,
            'online_net_revenue': 1121000,
            'retail_concept_store': 55000,
            'retail_popups_outlets': 0,
            'retail_net_revenue': 55000,
            'wholesale_net_revenue': 0,
            'total_net_revenue': 1176000,
            'returning_customers': 418,
            'new_customers': 189,
            'marketing_spend': 359000,
            'online_cost_of_sale_3': 99000
        },
        'last_week': {
            'online_gross_revenue': 1100000,
            'returns': 22000,
            'return_rate_pct': 2.0,
            'online_net_revenue': 1078000,
            'retail_concept_store': 52000,
            'retail_popups_outlets': 0,
            'retail_net_revenue': 52000,
            'wholesale_net_revenue': 0,
            'total_net_revenue': 1130000,
            'returning_customers': 405,
            'new_customers': 175,
            'marketing_spend': 340000,
            'online_cost_of_sale_3': 95000
        },
        'last_year': {
            'online_gross_revenue': 980000,
            'returns': 19000,
            'return_rate_pct': 1.9,
            'online_net_revenue': 961000,
            'retail_concept_store': 45000,
            'retail_popups_outlets': 0,
            'retail_net_revenue': 45000,
            'wholesale_net_revenue': 0,
            'total_net_revenue': 1006000,
            'returning_customers': 380,
            'new_customers': 160,
            'marketing_spend': 320000,
            'online_cost_of_sale_3': 85000
        },
        'year_2023': {
            'online_gross_revenue': 850000,
            'returns': 15000,
            'return_rate_pct': 1.8,
            'online_net_revenue': 835000,
            'retail_concept_store': 40000,
            'retail_popups_outlets': 0,
            'retail_net_revenue': 40000,
            'wholesale_net_revenue': 0,
            'total_net_revenue': 875000,
            'returning_customers': 350,
            'new_customers': 140,
            'marketing_spend': 280000,
            'online_cost_of_sale_3': 75000
        }
    }
    
    sample_periods = {
        'actual': '2025-42',
        'last_week': '2025-41',
        'last_year': '2024-42',
        'year_2023': '2023-42'
    }
    
    return build_table1_pdf(sample_metrics, sample_periods, output_path)
