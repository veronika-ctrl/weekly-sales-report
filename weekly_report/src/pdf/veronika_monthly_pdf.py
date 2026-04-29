"""One-page PDF for Veronika calendar-month KPIs."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Union

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from loguru import logger


def build_veronika_monthly_pdf(payload: Dict[str, Any], output: Union[Path, BytesIO]) -> None:
    """
    Build a single-page landscape PDF from ``calculate_monthly_veronika_kpis`` JSON payload.

    Args:
        payload: Result dict from ``calculate_monthly_veronika_kpis``.
        output: File path or binary buffer (``BytesIO``).
    """
    page_w, page_h = A4[1], A4[0]
    doc_target: Union[str, BytesIO] = str(output) if isinstance(output, Path) else output
    doc = SimpleDocTemplate(
        doc_target,
        pagesize=(page_w, page_h),
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "VTitle",
        parent=styles["Heading1"],
        fontSize=18,
        alignment=TA_CENTER,
        spaceAfter=8,
        textColor=colors.HexColor("#1f2937"),
    )
    sub = ParagraphStyle(
        "VSub",
        parent=styles["Normal"],
        fontSize=10,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#4b5563"),
        spaceAfter=14,
    )
    lab = ParagraphStyle("VLab", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#374151"))
    val = ParagraphStyle("VVal", parent=styles["Normal"], fontSize=11, textColor=colors.HexColor("#111827"))

    ym = payload.get("year_month", "")
    bw = payload.get("base_week", "")
    dr = payload.get("date_range", {})
    kpis = payload.get("kpis", {})

    story: list = []
    story.append(Paragraph("Veronika — Monthly KPIs (calendar month)", title))
    story.append(
        Paragraph(
            f"{ym} &nbsp;·&nbsp; Data folder: <b>{bw}</b> &nbsp;·&nbsp; {dr.get('start', '')} → {dr.get('end', '')}",
            sub,
        )
    )

    rows = [
        [
            Paragraph("<b>KPI</b>", lab),
            Paragraph("<b>Value</b>", val),
        ],
        [
            Paragraph("Repeat purchase rate (% of online buyers with 2+ orders)", lab),
            Paragraph(_fmt_pct(kpis.get("repeat_purchase_rate_pct")), val),
        ],
        [
            Paragraph("LTV / CAC — ratio (TTM mean net per customer ÷ monthly nCAC)", lab),
            Paragraph(_fmt_num(kpis.get("ltv_cac_ratio")), val),
        ],
        [
            Paragraph("LTV proxy — TTM mean online net / customer (SEK)", lab),
            Paragraph(_fmt_num(kpis.get("ltv_proxy_ttm")), val),
        ],
        [
            Paragraph("Conversion rate (orders ÷ sessions, %)", lab),
            Paragraph(_fmt_pct(kpis.get("conversion_rate_pct")), val),
        ],
        [
            Paragraph("Full-price share of ecom net (%)", lab),
            Paragraph(_fmt_pct(kpis.get("full_price_share_pct")), val),
        ],
        [
            Paragraph("New customer acquisition cost (SEK)", lab),
            Paragraph(_fmt_num(kpis.get("new_customer_acquisition_cost")), val),
        ],
        [
            Paragraph("Returning customer revenue (SEK)", lab),
            Paragraph(_fmt_num(kpis.get("returning_customer_revenue")), val),
        ],
        [
            Paragraph("COS % — marketing ÷ online gross", lab),
            Paragraph(_fmt_pct(kpis.get("cos_pct")), val),
        ],
        [
            Paragraph("COS % — Americas (marketing ÷ online gross, AMER countries)", lab),
            Paragraph(_fmt_pct(kpis.get("cos_amer_pct")), val),
        ],
        [
            Paragraph("eMER / aMER — Americas (new net ÷ marketing)", lab),
            Paragraph(_fmt_num(kpis.get("emer_amer")), val),
        ],
    ]

    tbl = Table([[a, b] for a, b in rows], colWidths=[page_w * 0.58, page_w * 0.28])
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#9ca3af")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fafaf9")]),
            ]
        )
    )
    story.append(tbl)
    story.append(Spacer(1, 10))
    notes = payload.get("notes") or []
    if notes:
        story.append(Paragraph("<b>Notes</b>", lab))
        for n in notes:
            story.append(Paragraph(str(n), lab))
    story.append(Spacer(1, 6))
    story.append(
        Paragraph(
            "<i>Corridor vs budget: compare to your monthly budget file for AMER COS / aMER targets.</i>",
            lab,
        )
    )

    doc.build(story)
    logger.info(f"Veronika monthly PDF built for {ym}")


def _fmt_num(v: Any) -> str:
    if v is None:
        return "—"
    try:
        x = float(v)
    except (TypeError, ValueError):
        return "—"
    if abs(x) >= 1000:
        return f"{x:,.0f}"
    return f"{x:.2f}"


def _fmt_pct(v: Any) -> str:
    if v is None:
        return "—"
    try:
        return f"{float(v):.2f}%"
    except (TypeError, ValueError):
        return "—"
