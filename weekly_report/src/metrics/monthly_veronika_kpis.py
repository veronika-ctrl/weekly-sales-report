"""
Calendar-month KPIs for the Veronika monthly scorecard (online / ecom focused).

Data is read from ``data/raw/{base_week}/`` (same layout as weekly reports); rows are
filtered by **calendar** ``Date`` / ``Days`` falling inside the selected ``YYYY-MM`` month.
"""

from __future__ import annotations

import calendar
import re
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pandas as pd
from loguru import logger

from weekly_report.src.metrics.discounts_sales import _normalize_customer_segment
from weekly_report.src.metrics.table1 import filter_data_for_date_range, load_all_raw_data


_YEAR_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _month_bounds(year_month: str) -> Tuple[str, str, str]:
    """Return (start_iso, end_iso, label) for calendar month YYYY-MM."""
    if not _YEAR_MONTH_RE.match(year_month):
        raise ValueError(f"Invalid year_month (expected YYYY-MM): {year_month!r}")
    y_str, m_str = year_month.split("-")
    y, m = int(y_str), int(m_str)
    last = calendar.monthrange(y, m)[1]
    start = date(y, m, 1).isoformat()
    end = date(y, m, last).isoformat()
    label = f"{y}-{m:02d}"
    return start, end, label


def _is_amer_country(country: Any) -> bool:
    """Americas slice for corridor-style metrics (US, Canada, Mexico)."""
    if country is None or (isinstance(country, float) and pd.isna(country)):
        return False
    k = str(country).strip().lower()
    if not k:
        return False
    if k in ("us", "usa", "ca", "can", "mx", "mex"):
        return True
    if "united states" in k or k == "u.s.a" or k == "u.s.":
        return True
    if "canada" in k:
        return True
    if "mexico" in k or "méxico" in k:
        return True
    return False


def _pick_discount_col(df: pd.DataFrame) -> Optional[str]:
    for c in df.columns:
        cl = str(c).strip().lower()
        if cl in ("total discounts", "discounts", "discount amount", "total discount", "rabatter"):
            return c
    return None


def _filter_shopify_by_range(shopify_df: pd.DataFrame, start_dt: pd.Timestamp, end_dt: pd.Timestamp) -> pd.DataFrame:
    if shopify_df.empty:
        return shopify_df
    df = shopify_df.copy()
    day_col = "Day" if "Day" in df.columns else ("Dag" if "Dag" in df.columns else None)
    if not day_col:
        return pd.DataFrame()
    df[day_col] = pd.to_datetime(df[day_col], errors="coerce")
    return df[(df[day_col] >= start_dt) & (df[day_col] <= end_dt)]


def calculate_monthly_veronika_kpis(year_month: str, base_week: str, data_root: Path) -> Dict[str, Any]:
    """
    Aggregate Veronika KPIs for a calendar month.

    Args:
        year_month: Calendar month ``YYYY-MM``.
        base_week: ISO week folder under ``data/raw/`` where CSV exports live.
        data_root: Project ``data`` root (parent of ``raw``).

    Returns:
        JSON-serialisable dict with KPI values, definitions, and coverage notes.
    """
    from weekly_report.src.periods.calculator import validate_iso_week

    if not validate_iso_week(base_week):
        raise ValueError(f"Invalid base_week: {base_week!r}")
    start_s, end_s, ym_label = _month_bounds(year_month)
    start_dt = pd.to_datetime(start_s)
    end_dt = pd.to_datetime(end_s) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)  # end of day

    raw_path = data_root / "raw" / base_week
    if not raw_path.is_dir():
        raise FileNotFoundError(f"Raw data folder not found: {raw_path}")

    all_data = load_all_raw_data(raw_path)
    filtered = filter_data_for_date_range(all_data, start_s, end_s)
    qlik_m = filtered.get("qlik", pd.DataFrame()).copy()
    dema_m = filtered.get("dema_spend", pd.DataFrame()).copy()
    shop_m = _filter_shopify_by_range(all_data.get("shopify", pd.DataFrame()), start_dt, end_dt)

    qlik_m.columns = qlik_m.columns.astype(str).str.strip()
    if qlik_m.empty or "Sales Channel" not in qlik_m.columns:
        logger.warning("Monthly Veronika: no Qlik rows for month %s", ym_label)
        return _empty_payload(ym_label, base_week, start_s, end_s, note="No Qlik data for this date range in the selected export.")

    _sc = qlik_m["Sales Channel"].astype(str).str.strip()
    online = qlik_m.loc[_sc.str.lower().eq("online")].copy()
    if online.empty:
        return _empty_payload(ym_label, base_week, start_s, end_s, note="No online rows for this month.")

    if "Date" in online.columns:
        online["Date"] = pd.to_datetime(online["Date"], errors="coerce")

    gross = float(pd.to_numeric(online["Gross Revenue"], errors="coerce").fillna(0.0).sum())
    net = float(pd.to_numeric(online["Net Revenue"], errors="coerce").fillna(0.0).sum())

    seg_col = "New/Returning Customer"
    if seg_col in online.columns:
        seg = online[seg_col].map(_normalize_customer_segment)
    else:
        seg = pd.Series(pd.NA, index=online.index, dtype=object)
    email_col = "Customer E-mail" if "Customer E-mail" in online.columns else (
        "Customer Email" if "Customer Email" in online.columns else None
    )
    new_mask = seg.eq("new")
    ret_mask = seg.eq("returning")

    new_customers = int(online.loc[new_mask, email_col].nunique()) if email_col else 0
    returning_customers = int(online.loc[ret_mask, email_col].nunique()) if email_col else 0
    new_net = float(pd.to_numeric(online.loc[new_mask, "Net Revenue"], errors="coerce").fillna(0.0).sum())
    returning_net = float(pd.to_numeric(online.loc[ret_mask, "Net Revenue"], errors="coerce").fillna(0.0).sum())

    if not dema_m.empty and "Marketing spend" in dema_m.columns:
        marketing = float(pd.to_numeric(dema_m["Marketing spend"], errors="coerce").fillna(0.0).sum())
    elif not dema_m.empty and "Cost" in dema_m.columns:
        marketing = float(pd.to_numeric(dema_m["Cost"], errors="coerce").fillna(0.0).sum())
    else:
        marketing = 0.0

    sessions = 0
    if not shop_m.empty:
        if "Sessions" in shop_m.columns:
            sessions = int(pd.to_numeric(shop_m["Sessions"], errors="coerce").fillna(0).sum())
        elif "Sessioner" in shop_m.columns:
            sessions = int(pd.to_numeric(shop_m["Sessioner"], errors="coerce").fillna(0).sum())

    order_col = "Order No" if "Order No" in online.columns else None
    unique_orders = int(online[order_col].nunique()) if order_col else 0
    conversion_rate = (unique_orders / sessions * 100.0) if sessions > 0 else 0.0

    cac = (marketing / new_customers) if new_customers > 0 else 0.0
    cos_pct = (marketing / gross * 100.0) if gross > 0 else 0.0

    # Repeat purchase rate: share of online customers (month) with 2+ distinct orders
    repeat_purchase_rate_pct: Optional[float] = None
    if email_col and order_col:
        oc = online.dropna(subset=[email_col])
        per_c = oc.groupby(email_col)[order_col].nunique()
        buyers = int((per_c >= 1).sum())
        repeaters = int((per_c >= 2).sum())
        repeat_purchase_rate_pct = (repeaters / buyers * 100.0) if buyers > 0 else 0.0

    # Full-price share of ecom net revenue (rows with no discount amount)
    full_price_share_pct: Optional[float] = None
    dcol = _pick_discount_col(online)
    if dcol:
        disc = pd.to_numeric(online[dcol], errors="coerce").fillna(0.0)
        net_line = pd.to_numeric(online["Net Revenue"], errors="coerce").fillna(0.0)
        fp_net = float(net_line.loc[disc <= 0].sum())
        full_price_share_pct = (fp_net / net * 100.0) if net > 1e-9 else None

    # TTM LTV proxy: mean trailing-12-month online net per distinct customer (in export date range)
    ltv_proxy_ttm: Optional[float] = None
    ltv_cac_ratio: Optional[float] = None
    ttm_note: Optional[str] = None
    if email_col and "Date" in online.columns:
        full_online = all_data["qlik"].copy()
        full_online.columns = full_online.columns.astype(str).str.strip()
        _fsc = full_online["Sales Channel"].astype(str).str.strip()
        full_online = full_online.loc[_fsc.str.lower().eq("online")].copy()
        full_online["Date"] = pd.to_datetime(full_online["Date"], errors="coerce")
        ttm_start = (pd.Timestamp(end_s) - pd.DateOffset(months=11)).normalize()
        ttm_df = full_online[(full_online["Date"] >= ttm_start) & (full_online["Date"] <= pd.Timestamp(end_s))]
        if not ttm_df.empty and email_col in ttm_df.columns:
            cust_net = ttm_df.groupby(email_col)["Net Revenue"].apply(lambda s: pd.to_numeric(s, errors="coerce").fillna(0.0).sum())
            ltv_proxy_ttm = float(cust_net.mean()) if len(cust_net) > 0 else None
            min_d = full_online["Date"].min()
            if pd.notna(min_d) and min_d > ttm_start:
                ttm_note = (
                    f"TTM window starts {ttm_start.date()} but export only contains rows from {min_d.date()}; "
                    "LTV proxy is computed on available history only."
                )
            if ltv_proxy_ttm is not None and cac > 0:
                ltv_cac_ratio = ltv_proxy_ttm / cac

    # Americas slice
    amer_online = online
    amer_marketing = marketing
    amer_gross = gross
    amer_new_net = new_net
    if "Country" in online.columns:
        am_mask = online["Country"].map(_is_amer_country)
        amer_online = online.loc[am_mask]
        amer_gross = float(pd.to_numeric(amer_online["Gross Revenue"], errors="coerce").fillna(0.0).sum())
        # Boolean masks are aligned to full `online` index (subset .loc on amer_online would misalign).
        amer_new_net = float(
            pd.to_numeric(online.loc[new_mask & am_mask, "Net Revenue"], errors="coerce").fillna(0.0).sum()
        )
    if "Country" in dema_m.columns and not dema_m.empty:
        dm = dema_m.copy()
        am_d = dm["Country"].map(_is_amer_country)
        if "Marketing spend" in dm.columns:
            amer_marketing = float(pd.to_numeric(dm.loc[am_d, "Marketing spend"], errors="coerce").fillna(0.0).sum())
        elif "Cost" in dm.columns:
            amer_marketing = float(pd.to_numeric(dm.loc[am_d, "Cost"], errors="coerce").fillna(0.0).sum())

    cos_amer_pct = (amer_marketing / amer_gross * 100.0) if amer_gross > 0 else 0.0
    emer_amer = (amer_new_net / amer_marketing) if amer_marketing > 1e-9 else 0.0

    return {
        "year_month": ym_label,
        "base_week": base_week,
        "date_range": {"start": start_s, "end": end_s},
        "definitions": {
            "repeat_purchase_rate_pct": "Share of online customers (unique email) with ≥2 distinct orders in the month.",
            "ltv_proxy_ttm": "Mean online net revenue per distinct customer over trailing 12 months ending last day of month (export coverage).",
            "ltv_cac_ratio": "ltv_proxy_ttm ÷ monthly nCAC (marketing ÷ new customers in month).",
            "conversion_rate_pct": "Unique online orders ÷ Shopify sessions summed over the month.",
            "full_price_share_pct": "Share of online net revenue on rows with no discount amount column (if present).",
            "new_customer_acquisition_cost": "Total marketing spend in month ÷ distinct new online customers in month.",
            "returning_customer_revenue": "Sum of online net revenue where New/Returning = returning.",
            "cos_pct": "Marketing spend ÷ online gross revenue × 100 (month, global).",
            "cos_amer_pct": "Americas marketing ÷ Americas online gross × 100 (Country column on Qlik/Dema when present).",
            "emer_amer": "Americas online new-customer net revenue ÷ Americas marketing spend (month).",
            "corridor": "Compare COS % and eMER/aMER to your budget corridor for AMER in the monthly budget file (not auto-loaded here).",
        },
        "kpis": {
            "repeat_purchase_rate_pct": round(repeat_purchase_rate_pct, 2) if repeat_purchase_rate_pct is not None else None,
            "ltv_proxy_ttm": round(ltv_proxy_ttm, 2) if ltv_proxy_ttm is not None else None,
            "ltv_cac_ratio": round(ltv_cac_ratio, 2) if ltv_cac_ratio is not None else None,
            "conversion_rate_pct": round(conversion_rate, 2),
            "full_price_share_pct": round(full_price_share_pct, 2) if full_price_share_pct is not None else None,
            "new_customer_acquisition_cost": round(cac, 2),
            "returning_customer_revenue": round(returning_net, 2),
            "cos_pct": round(cos_pct, 2),
            "cos_amer_pct": round(cos_amer_pct, 2),
            "emer_amer": round(emer_amer, 2),
        },
        "supporting": {
            "online_gross_revenue": round(gross, 2),
            "online_net_revenue": round(net, 2),
            "marketing_spend": round(marketing, 2),
            "new_customers": new_customers,
            "returning_customers": returning_customers,
            "sessions": sessions,
            "unique_orders": unique_orders,
            "new_customers_net_revenue": round(new_net, 2),
        },
        "notes": [n for n in [ttm_note] if n],
    }


def _empty_payload(
    ym_label: str, base_week: str, start_s: str, end_s: str, note: str
) -> Dict[str, Any]:
    return {
        "year_month": ym_label,
        "base_week": base_week,
        "date_range": {"start": start_s, "end": end_s},
        "definitions": {},
        "kpis": {
            "repeat_purchase_rate_pct": None,
            "ltv_proxy_ttm": None,
            "ltv_cac_ratio": None,
            "conversion_rate_pct": 0.0,
            "full_price_share_pct": None,
            "new_customer_acquisition_cost": 0.0,
            "returning_customer_revenue": 0.0,
            "cos_pct": 0.0,
            "cos_amer_pct": 0.0,
            "emer_amer": 0.0,
        },
        "supporting": {},
        "notes": [note],
    }
