"""
Quarterly board scorecard for CFO reporting (calendar quarter, online ecom).

Focus: customer counts, net sales by segment, orders, AOV, full-price mix,
aMER, COS %, and CLV/CAC — with same-quarter-last-year comparisons.
"""

from __future__ import annotations

import calendar
import re
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from loguru import logger

from weekly_report.src.metrics.monthly_veronika_kpis import _aggregate_veronika_online_period
from weekly_report.src.metrics.table1 import load_all_raw_data
from weekly_report.src.periods.calculator import get_week_date_range, validate_iso_week

_YEAR_QUARTER_RE = re.compile(r"^\d{4}-Q[1-4]$", re.IGNORECASE)


def _quarter_bounds(year_quarter: str) -> Tuple[str, str, str]:
    """Return (start_iso, end_iso, label) for calendar quarter ``YYYY-Qn``."""
    yq = year_quarter.upper()
    if not _YEAR_QUARTER_RE.match(yq):
        raise ValueError(f"Invalid year_quarter (expected YYYY-Q1..Q4): {year_quarter!r}")
    y_str, q_str = yq.split("-")
    y = int(y_str)
    q = int(q_str[1])
    start_month = (q - 1) * 3 + 1
    end_month = start_month + 2
    last_day = calendar.monthrange(y, end_month)[1]
    start = date(y, start_month, 1).isoformat()
    end = date(y, end_month, last_day).isoformat()
    return start, end, f"{y}-Q{q}"


def _shift_years(iso_date: str, years: int) -> str:
    return (pd.Timestamp(iso_date) + pd.DateOffset(years=years)).strftime("%Y-%m-%d")


def _yoy_pct(current: Optional[float], last_year: Optional[float]) -> Optional[float]:
    if current is None or last_year is None or abs(last_year) <= 1e-9:
        return None
    return (current - last_year) / last_year * 100.0


def _yoy_pp(current: Optional[float], last_year: Optional[float]) -> Optional[float]:
    if current is None or last_year is None:
        return None
    return current - last_year


def _metric_row(
    key: str,
    label: str,
    value: Optional[float],
    last_year: Optional[float],
    fmt: str,
    *,
    use_pp: bool = False,
) -> Dict[str, Any]:
    delta = _yoy_pp(value, last_year) if use_pp else _yoy_pct(value, last_year)
    return {
        "key": key,
        "label": label,
        "value": value,
        "last_year": last_year,
        "yoy_pct": None if use_pp else (round(delta, 2) if delta is not None else None),
        "yoy_pp": round(delta, 2) if use_pp and delta is not None else None,
        "format": fmt,
    }


def _round_metric(v: Optional[float], fmt: str) -> Optional[float]:
    if v is None:
        return None
    if fmt == "integer":
        return int(round(v))
    if fmt == "pct":
        return round(v, 2)
    if fmt == "ratio":
        return round(v, 2)
    return round(v, 2)


def calculate_quarterly_veronika_board_kpis(
    year_quarter: str,
    base_week: str,
    data_root: Path,
) -> Dict[str, Any]:
    """
    Board-oriented quarterly KPIs with same-quarter-last-year comparison.

    When the selected quarter includes today (partial quarter), the period ends at
    the base week's last day and last year is cut to the same day-of-quarter.
    """
    if not validate_iso_week(base_week):
        raise ValueError(f"Invalid base_week: {base_week!r}")

    start_s, quarter_end_s, q_label = _quarter_bounds(year_quarter)
    week_rng = get_week_date_range(base_week)
    week_end_s = week_rng["end"]
    week_end = pd.Timestamp(week_end_s)
    quarter_end = pd.Timestamp(quarter_end_s)

    end_s = quarter_end_s
    is_partial = False
    if week_end < quarter_end:
        end_s = week_end_s
        is_partial = True

    ly_start_s = _shift_years(start_s, -1)
    ly_end_s = _shift_years(end_s, -1)

    raw_path = data_root / "raw" / base_week
    if not raw_path.is_dir():
        raise FileNotFoundError(f"Raw data folder not found: {raw_path}")

    all_data = load_all_raw_data(raw_path)
    cur = _aggregate_veronika_online_period(all_data, data_root, base_week, start_s, end_s)
    if cur.get("error") == "no_qlik_data":
        return _empty_quarterly_payload(
            q_label, base_week, start_s, end_s, quarter_end_s, is_partial, ly_start_s, ly_end_s,
            note="No Qlik data for this date range in the selected export.",
        )
    if cur.get("error") == "no_online_rows":
        return _empty_quarterly_payload(
            q_label, base_week, start_s, end_s, quarter_end_s, is_partial, ly_start_s, ly_end_s,
            note="No online rows for this quarter.",
        )

    ly = _aggregate_veronika_online_period(all_data, data_root, base_week, ly_start_s, ly_end_s)
    if ly.get("error"):
        ly = {k: None for k in (
            "new_customers", "returning_customers", "new_net", "returning_net",
            "unique_orders", "aov", "net", "full_price_share_pct", "full_price_net",
            "discounted_net", "amer", "cos_pct", "ltv_cac_ratio", "ltv_proxy_ttm", "cac",
        )}

    def _f(key: str, period: Dict[str, Any]) -> Optional[float]:
        v = period.get(key)
        return float(v) if v is not None else None

    metrics: List[Dict[str, Any]] = [
        _metric_row("new_customers", "New customers", _f("new_customers", cur), _f("new_customers", ly), "integer"),
        _metric_row("new_customer_net_sales", "New customer net sales (SEK)", _f("new_net", cur), _f("new_net", ly), "currency"),
        _metric_row("returning_customers", "Returning customers", _f("returning_customers", cur), _f("returning_customers", ly), "integer"),
        _metric_row("returning_customer_net_sales", "Returning customer net sales (SEK)", _f("returning_net", cur), _f("returning_net", ly), "currency"),
        _metric_row("orders", "Orders", _f("unique_orders", cur), _f("unique_orders", ly), "integer"),
        _metric_row("aov", "AOV — net sales ÷ orders (SEK)", _f("aov", cur), _f("aov", ly), "currency"),
        _metric_row("online_net_sales", "Total online net sales (SEK)", _f("net", cur), _f("net", ly), "currency"),
        _metric_row("amer", "aMER — new net ÷ marketing", _f("amer", cur), _f("amer", ly), "ratio"),
        _metric_row("cos_pct", "COS % — marketing ÷ gross", _f("cos_pct", cur), _f("cos_pct", ly), "pct", use_pp=True),
        _metric_row("ltv_cac_ratio", "CLV / CAC (LTV proxy ÷ nCAC)", _f("ltv_cac_ratio", cur), _f("ltv_cac_ratio", ly), "ratio"),
    ]
    for row in metrics:
        row["value"] = _round_metric(row["value"], row["format"])
        row["last_year"] = _round_metric(row["last_year"], row["format"])

    fp_share = cur.get("full_price_share_pct")
    fp_share_ly = ly.get("full_price_share_pct") if isinstance(ly, dict) else None
    full_price = {
        "share_pct": round(fp_share, 2) if fp_share is not None else None,
        "share_pct_last_year": round(fp_share_ly, 2) if fp_share_ly is not None else None,
        "share_pp_delta": _yoy_pp(fp_share, fp_share_ly),
        "full_price_net": round(cur["full_price_net"], 2) if cur.get("full_price_net") is not None else None,
        "discounted_net": round(cur["discounted_net"], 2) if cur.get("discounted_net") is not None else None,
        "total_net": round(cur["net"], 2) if cur.get("net") is not None else None,
        "full_price_net_last_year": round(ly["full_price_net"], 2) if ly.get("full_price_net") is not None else None,
        "discounted_net_last_year": round(ly["discounted_net"], 2) if ly.get("discounted_net") is not None else None,
        "yoy_full_price_net_pct": _yoy_pct(cur.get("full_price_net"), ly.get("full_price_net")),
        "yoy_discounted_net_pct": _yoy_pct(cur.get("discounted_net"), ly.get("discounted_net")),
    }

    notes: List[str] = []
    if is_partial:
        notes.append(
            f"Partial quarter: metrics cover {start_s} → {end_s} (through selected week {base_week}). "
            f"Last-year comparison uses the same day-of-quarter ({ly_start_s} → {ly_end_s})."
        )
    if cur.get("ttm_note"):
        notes.append(cur["ttm_note"])
    discounts_fp = cur.get("discounts_fp") or {}
    if fp_share is not None and discounts_fp.get("source") == "revenue_over_time":
        fx_note = " (USD→SEK via ECB daily rates)" if discounts_fp.get("fx_applied") else ""
        fp_amt = cur.get("full_price_net")
        disc_amt = cur.get("discounted_net")
        online_net = cur.get("net")
        notes.append(
            f"Full-price share: {fp_share:.2f}% (mix from Shopify app export{fx_note}). "
            f"E-com amounts: {fp_amt:,.0f} full + {disc_amt:,.0f} discounted = "
            f"{online_net:,.0f} SEK online net (Qlik, Sales channel = online)."
        )

    definitions = {
        "scope": (
            "Online channel only (Qlik Sales channel = online). Calendar quarter; "
            "partial quarters end on the selected data week's last day."
        ),
        "new_customers": "Distinct customer emails with New/Returning = new in the quarter.",
        "new_customer_net_sales": "Sum of online net revenue on new-customer rows in the quarter.",
        "returning_customers": "Distinct customer emails with New/Returning = returning in the quarter.",
        "returning_customer_net_sales": "Sum of online net revenue on returning-customer rows in the quarter.",
        "orders": "Distinct order numbers in the quarter (online).",
        "aov": "Total online net sales ÷ orders in the quarter.",
        "full_price_share_pct": (
            "Full-price mix % from the Shopify app revenue-over-time export (shop-wide daily file). "
            "Full-price and discounted SEK amounts are applied to Qlik online net only "
            "(full = online net × share %; discounted = remainder), so totals match the scorecard."
        ),
        "amer": "Online new-customer net revenue ÷ total DEMA marketing spend in the quarter (aMER / eMER).",
        "cos_pct": (
            "Marketing spend ÷ online gross revenue × 100 in the quarter. "
            "A lower COS % is better — a negative YoY change (pp) is favorable."
        ),
        "ltv_cac_ratio": (
            "TTM mean online net per distinct customer (ending quarter last day) ÷ quarterly nCAC "
            "(marketing ÷ new customers in quarter)."
        ),
        "yoy": "Same calendar quarter last year; for partial quarters, same day-of-quarter cutoff.",
    }

    return {
        "year_quarter": q_label,
        "base_week": base_week,
        "date_range": {
            "start": start_s,
            "end": end_s,
            "quarter_end": quarter_end_s,
            "is_partial": is_partial,
        },
        "last_year_date_range": {"start": ly_start_s, "end": ly_end_s},
        "definitions": definitions,
        "metrics": metrics,
        "full_price": full_price,
        "supporting": {
            "ltv_proxy_ttm": round(cur["ltv_proxy_ttm"], 2) if cur.get("ltv_proxy_ttm") is not None else None,
            "new_customer_acquisition_cost": round(cur["cac"], 2) if cur.get("cac") else None,
            "marketing_spend": round(cur["marketing"], 2),
            "online_gross_revenue": round(cur["gross"], 2),
        },
        "notes": notes,
    }


def _empty_quarterly_payload(
    q_label: str,
    base_week: str,
    start_s: str,
    end_s: str,
    quarter_end_s: str,
    is_partial: bool,
    ly_start_s: str,
    ly_end_s: str,
    note: str,
) -> Dict[str, Any]:
    logger.warning("Quarterly board: %s", note)
    return {
        "year_quarter": q_label,
        "base_week": base_week,
        "date_range": {"start": start_s, "end": end_s, "quarter_end": quarter_end_s, "is_partial": is_partial},
        "last_year_date_range": {"start": ly_start_s, "end": ly_end_s},
        "definitions": {},
        "metrics": [],
        "full_price": {},
        "supporting": {},
        "notes": [note],
    }
