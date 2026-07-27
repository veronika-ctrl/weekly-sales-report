"""Excel export for Full Price vs Sale (fiscal YTD + monthly + weekly)."""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from weekly_report.src.metrics.discounts_sales import (
    calculate_full_price_vs_sale_monthly,
    calculate_full_price_vs_sale_weekly,
)


def _wd_pp_delta(cur: Optional[float], ly: Optional[float]) -> Optional[float]:
    if cur is None or ly is None:
        return None
    return cur - ly


def _ytd_summary_rows(ytd: Dict[str, Any]) -> List[Dict[str, Any]]:
    ly = ytd.get("last_year") or {}
    return [
        {
            "Metric": "Full price net (SEK)",
            "This FY YTD": ytd.get("full_price"),
            "Same period LY": ly.get("full_price"),
            "YoY %": ytd.get("yoy_full_price_pct"),
        },
        {
            "Metric": "Discounted net (SEK)",
            "This FY YTD": ytd.get("discounted"),
            "Same period LY": ly.get("discounted"),
            "YoY %": None,
        },
        {
            "Metric": "Total net (SEK)",
            "This FY YTD": ytd.get("total"),
            "Same period LY": ly.get("total"),
            "YoY %": ytd.get("yoy_total_pct"),
        },
        {
            "Metric": "Full price share %",
            "This FY YTD": ytd.get("full_price_pct"),
            "Same period LY": ly.get("full_price_pct"),
            "YoY %": None,
            "Δ pp": ytd.get("full_price_pct_delta"),
        },
        {
            "Metric": "Weighted discount %",
            "This FY YTD": ytd.get("weighted_discount_pct"),
            "Same period LY": ly.get("weighted_discount_pct"),
            "YoY %": None,
            "Δ wd pp": _wd_pp_delta(ytd.get("weighted_discount_pct"), ly.get("weighted_discount_pct")),
        },
    ]


def _monthly_rows(months_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for m in reversed(months_data):
        if (m.get("total") or 0) <= 0 and (m.get("last_year", {}).get("total") or 0) <= 0:
            continue
        ly = m.get("last_year") or {}
        rows.append(
            {
                "Month": m.get("month"),
                "Full price net (SEK)": m.get("full_price"),
                "Discounted net (SEK)": m.get("discounted"),
                "Total net (SEK)": m.get("total"),
                "Full price %": m.get("full_price_pct"),
                "LY full price net (SEK)": ly.get("full_price"),
                "LY discounted net (SEK)": ly.get("discounted"),
                "LY total net (SEK)": ly.get("total"),
                "LY full price %": ly.get("full_price_pct"),
                "Δ pp vs LY": m.get("full_price_pct_delta"),
                "YoY total %": m.get("yoy_total_pct"),
                "YoY full price %": m.get("yoy_full_price_pct"),
                "Weighted disc %": m.get("weighted_discount_pct"),
                "LY weighted disc %": ly.get("weighted_discount_pct"),
                "Δ wd pp": _wd_pp_delta(m.get("weighted_discount_pct"), ly.get("weighted_discount_pct")),
            }
        )
    return rows


def _weekly_rows(weeks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for w in weeks:
        ly = w.get("last_year") or {}
        rows.append(
            {
                "ISO week": w.get("week"),
                "Full price net (SEK)": w.get("full_price"),
                "Discounted net (SEK)": w.get("discounted"),
                "Total net (SEK)": w.get("total"),
                "Full price %": w.get("full_price_pct"),
                "LY ISO week": ly.get("week"),
                "LY full price net (SEK)": ly.get("full_price"),
                "LY discounted net (SEK)": ly.get("discounted"),
                "LY total net (SEK)": ly.get("total"),
                "LY full price %": ly.get("full_price_pct"),
                "Δ pp vs LY": w.get("full_price_pct_delta"),
                "YoY total %": w.get("yoy_total_pct"),
                "YoY full price %": w.get("yoy_full_price_pct"),
                "Weighted disc %": w.get("weighted_discount_pct"),
                "LY weighted disc %": ly.get("weighted_discount_pct"),
                "Δ wd pp": _wd_pp_delta(w.get("weighted_discount_pct"), ly.get("weighted_discount_pct")),
            }
        )
    return rows


def _meta_rows(monthly: Dict[str, Any], weekly: Dict[str, Any]) -> List[Dict[str, str]]:
    fx = monthly.get("fx") or {}
    ytd = monthly.get("ytd") or {}
    lines = [
        ("Generated (UTC)", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")),
        ("Base week", str(monthly.get("base_week") or weekly.get("base_week") or "")),
        ("Currency", str(monthly.get("currency") or "SEK")),
        ("Data source", "Shopify app revenue-over-time export (accumulated daily history)"),
        (
            "History range",
            f"{monthly.get('history_range', {}).get('start', '')} → {monthly.get('history_range', {}).get('end', '')}",
        ),
        ("Files used", ", ".join(monthly.get("files_used") or [])),
    ]
    if ytd:
        lines.extend(
            [
                ("Fiscal YTD label", str(ytd.get("label") or "")),
                ("Fiscal YTD period", f"{ytd.get('fy_start', '')} → {ytd.get('end', '')}"),
            ]
        )
    if fx.get("applied"):
        lines.append(
            (
                "FX conversion",
                f"{fx.get('source_currency', 'USD')} → {fx.get('target_currency', 'SEK')} via ECB daily rates",
            )
        )
    lines.extend(
        [
            ("", ""),
            ("Notes", ""),
            ("Full price %", "sum(Full Price) ÷ sum(Total) over the period (revenue-weighted)."),
            ("YoY total %", "Growth in total net sales vs same period last year."),
            ("YoY full price %", "Growth in absolute full-price revenue vs same period last year."),
            ("Δ pp", "Change in full price share vs last year (percentage points)."),
            ("Weighted disc %", "Discount depth on discounted sales only (requires Discount Amount column)."),
            ("Monthly latest month", "Month-to-date through the base week's end date."),
            ("Amounts", "All monetary values are in SEK (not thousands)."),
        ]
    )
    return [{"Field": k, "Value": v} for k, v in lines]


def build_full_price_vs_sale_excel(
    base_week: str,
    data_root: Path,
    *,
    months: int = 13,
    num_weeks: int = 8,
) -> BytesIO:
    """
    Build a multi-sheet Excel workbook for CFO reference.

    Sheets: About, YTD Summary, Monthly, Weekly.
    """
    monthly = calculate_full_price_vs_sale_monthly(base_week, months, data_root)
    weekly = calculate_full_price_vs_sale_weekly(base_week, num_weeks, data_root)

    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        pd.DataFrame(_meta_rows(monthly, weekly)).to_excel(writer, sheet_name="About", index=False)

        ytd = monthly.get("ytd")
        if ytd:
            ytd_header = pd.DataFrame(
                [
                    {"Field": "Fiscal YTD period", "Value": f"{ytd.get('fy_start')} → {ytd.get('end')}"},
                    {"Field": "Label", "Value": ytd.get("label")},
                ]
            )
            ytd_header.to_excel(writer, sheet_name="YTD Summary", index=False, startrow=0)
            pd.DataFrame(_ytd_summary_rows(ytd)).to_excel(writer, sheet_name="YTD Summary", index=False, startrow=4)
        else:
            pd.DataFrame([{"Note": "No fiscal YTD data available"}]).to_excel(writer, sheet_name="YTD Summary", index=False)

        pd.DataFrame(_monthly_rows(monthly.get("months_data") or [])).to_excel(writer, sheet_name="Monthly", index=False)
        pd.DataFrame(_weekly_rows(weekly.get("weeks") or [])).to_excel(writer, sheet_name="Weekly", index=False)

    buf.seek(0)
    return buf
