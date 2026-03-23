"""PDF builder using ReportLab."""

from pathlib import Path
from typing import Dict, Any

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader

from weekly_report.src.pdf.layout import load_pdf_layout, PDFLayout
from weekly_report.src.config import Config
from loguru import logger


def build_pdfs(
    curated_data: Dict[str, Any],
    chart_files: Dict[str, Path],
    config: Config
) -> Dict[str, Path]:
    """Build PDF reports from curated data and charts."""
    
    # Load PDF layout
    layout = load_pdf_layout(config.template_path)
    
    # Create output directory
    config.reports_path.mkdir(parents=True, exist_ok=True)
    
    pdf_files = {}
    
    # Build general report
    general_pdf = build_general_pdf(curated_data, chart_files, layout, config)
    pdf_files['general'] = general_pdf
    
    # Build market report
    market_pdf = build_market_pdf(curated_data, chart_files, layout, config)
    pdf_files['market'] = market_pdf
    
    logger.info(f"Generated {len(pdf_files)} PDF reports")
    return pdf_files


def build_general_pdf(
    curated_data: Dict[str, Any],
    chart_files: Dict[str, Path],
    layout: PDFLayout,
    config: Config
) -> Path:
    """Build general report PDF."""
    
    output_path = config.reports_path / "general.pdf"
    
    # Get page size (A4 landscape)
    page_width, page_height = layout.get_page_size()
    
    # Create PDF document
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=(page_width, page_height),
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72
    )
    
    # Get styles
    styles = getSampleStyleSheet()
    
    # Create custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#1f77b4')
    )
    
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Heading2'],
        fontSize=18,
        spaceAfter=20,
        alignment=TA_LEFT,
        textColor=colors.HexColor('#333333')
    )
    
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['Normal'],
        fontSize=12,
        spaceAfter=12,
        alignment=TA_LEFT,
        textColor=colors.HexColor('#333333')
    )
    
    # Build content
    story = []
    
    # Title
    title = Paragraph(f"Weekly Report - Week {config.week}", title_style)
    story.append(title)
    story.append(Spacer(1, 20))
    
    # KPI Summary
    if 'kpis' in curated_data:
        kpi_df = curated_data['kpis']
        
        subtitle = Paragraph("Key Performance Indicators", subtitle_style)
        story.append(subtitle)
        
        # Create KPI table
        kpi_table_data = []
        for _, row in kpi_df.head(10).iterrows():
            kpi_table_data.append([
                row['metric'].replace('_', ' ').title(),
                f"{row['value']:,.0f}",
                row['source']
            ])
        
        # Add KPI table
        from reportlab.platypus import Table, TableStyle
        kpi_table = Table(kpi_table_data, colWidths=[200, 100, 100])
        kpi_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f77b4')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(kpi_table)
        story.append(Spacer(1, 20))
    
    # Charts
    if 'trend_sales' in chart_files:
        subtitle = Paragraph("Sales Trend", subtitle_style)
        story.append(subtitle)
        
        # Add chart image
        chart_img = Image(str(chart_files['trend_sales']), width=400, height=300)
        story.append(chart_img)
        story.append(Spacer(1, 20))
    
    if 'waterfall_contrib' in chart_files:
        subtitle = Paragraph("Revenue Waterfall", subtitle_style)
        story.append(subtitle)
        
        # Add chart image
        chart_img = Image(str(chart_files['waterfall_contrib']), width=400, height=300)
        story.append(chart_img)
        story.append(Spacer(1, 20))
    
    # Build PDF
    doc.build(story)
    
    logger.info(f"Generated general report: {output_path}")
    return output_path


def build_market_pdf(
    curated_data: Dict[str, Any],
    chart_files: Dict[str, Path],
    layout: PDFLayout,
    config: Config
) -> Path:
    """Build market report PDF."""
    
    output_path = config.reports_path / "market.pdf"
    
    # Get page size (A4 landscape)
    page_width, page_height = layout.get_page_size()
    
    # Create PDF document
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=(page_width, page_height),
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72
    )
    
    # Get styles
    styles = getSampleStyleSheet()
    
    # Create custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#1f77b4')
    )
    
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Heading2'],
        fontSize=18,
        spaceAfter=20,
        alignment=TA_LEFT,
        textColor=colors.HexColor('#333333')
    )
    
    # Build content
    story = []
    
    # Title
    title = Paragraph(f"Market Report - Week {config.week}", title_style)
    story.append(title)
    story.append(Spacer(1, 20))
    
    # Market Summary
    if 'markets' in curated_data:
        market_df = curated_data['markets']
        
        subtitle = Paragraph("Market Performance", subtitle_style)
        story.append(subtitle)
        
        # Create market table
        market_table_data = []
        for _, row in market_df.head(10).iterrows():
            market_table_data.append([
                row['country'],
                f"{row['revenue']:,.0f}",
                f"{row['units']:,.0f}",
                f"{row['orders']:,.0f}",
                f"{row['yoy_growth_pct']:.1f}%",
                f"{row['wow_growth_pct']:.1f}%"
            ])
        
        # Add market table
        from reportlab.platypus import Table, TableStyle
        market_table = Table(market_table_data, colWidths=[100, 100, 80, 80, 80, 80])
        market_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f77b4')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(market_table)
        story.append(Spacer(1, 20))
    
    # Charts
    if 'bar_yoy_wow' in chart_files:
        subtitle = Paragraph("Market Growth Comparison", subtitle_style)
        story.append(subtitle)
        
        # Add chart image
        chart_img = Image(str(chart_files['bar_yoy_wow']), width=400, height=300)
        story.append(chart_img)
        story.append(Spacer(1, 20))
    
    # Build PDF
    doc.build(story)
    
    logger.info(f"Generated market report: {output_path}")
    return output_path

