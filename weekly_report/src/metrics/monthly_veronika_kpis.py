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

from weekly_report.src.metrics.discounts_sales import (
    _normalize_customer_segment,
    calculate_full_price_share_for_date_range,
)
from weekly_report.src.metrics.table1 import filter_data_for_date_range, load_all_raw_data
from weekly_report.src.compute.budget import compute_budget_general
from weekly_report.src.compute.budget_table1_month import budget_table1_for_calendar_month


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


def _pick_discount_col(df: pd.DataFrame) -> Optional[str]:
    # Prefer exact known names first.
    exact = {
        "total discounts",
        "discounts",
        "discount amount",
        "total discount",
        "rabatter",
        "rabatt",
        "discount",
    }
    for c in df.columns:
        cl = str(c).strip().lower()
        if cl in exact:
            return c

    # Fallback: catch common variants from Qlik exports.
    for c in df.columns:
        cl = str(c).strip().lower()
        if ("discount" in cl or "rabatt" in cl) and "code" not in cl and "name" not in cl:
            return c
    return None


def _norm_col_name(col: Any) -> str:
    return str(col).strip().lower()


def _pick_col(df: pd.DataFrame, candidates: tuple[str, ...]) -> Optional[str]:
    if df.empty:
        return None
    norm_map = {_norm_col_name(c): str(c) for c in df.columns}
    for cand in candidates:
        hit = norm_map.get(_norm_col_name(cand))
        if hit:
            return hit
    return None


def _attach_budget_corridor_from_file(payload: Dict[str, Any], year_month: str, base_week: str) -> None:
    """
    Fill ``budget_plan`` (COS %, aMER) for the same calendar month from the budget CSV
    (``compute_budget_general`` / same logic as MTD Table 1 budget).
    """
    y_str, m_str = year_month.split("-")
    y, m = int(y_str), int(m_str)
    try:
        bg = compute_budget_general(base_week)
    except Exception as e:
        logger.warning("Monthly Veronika: compute_budget_general failed: {}", e)
        payload["budget_plan"] = None
        payload["budget_error"] = str(e)
        return
    err = bg.get("error")
    if err:
        payload["budget_plan"] = None
        payload["budget_error"] = str(err)
        return
    table = bg.get("table") or {}
    b = budget_table1_for_calendar_month(table, y, m)
    if not b:
        payload["budget_plan"] = None
        payload["budget_error"] = None
        return
    cos = b.get("online_cost_of_sale_3")
    emer = b.get("emer")
    payload["budget_plan"] = {
        "cos_pct": float(cos) if cos is not None else None,
        "amer": float(emer) if emer is not None else None,
    }
    payload["budget_error"] = None


def _detect_shopify_date_column(df: pd.DataFrame) -> Optional[str]:
    """Date column in Shopify exports (Day, Dag, Date, Month, etc.)."""
    if df.empty:
        return None
    cols = [str(c).strip() for c in df.columns]
    for key in ("Day", "Dag", "Date", "Month"):
        if key in cols:
            return key
    norm = {c.lower(): c for c in cols}
    for key in ("day", "dag", "date", "month", "visit date", "session date"):
        if key in norm:
            return norm[key]
    return None


def _shopify_sessions_in_range(
    shopify_df: pd.DataFrame, start_dt: pd.Timestamp, end_dt: pd.Timestamp
) -> int:
    """Sum Shopify session counts for rows whose date falls in [start_dt, end_dt]."""
    if shopify_df.empty:
        return 0
    df = shopify_df.copy()
    df.columns = df.columns.astype(str).str.strip()
    date_col = _detect_shopify_date_column(df)
    if not date_col:
        logger.warning(
            "Monthly Veronika: Shopify export has no Day/Dag/Date/Month column; sessions=0. Columns: {}",
            df.columns.tolist(),
        )
        return 0
    sess_col = None
    for key in ("Sessions", "Sessioner"):
        if key in df.columns:
            sess_col = key
            break
    if not sess_col:
        for c in df.columns:
            if "session" in str(c).lower() and "total" not in str(c).lower():
                sess_col = c
                break
    if not sess_col:
        logger.warning("Monthly Veronika: no sessions column in Shopify export")
        return 0
    dt = pd.to_datetime(df[date_col], errors="coerce")
    sess = pd.to_numeric(df[sess_col], errors="coerce").fillna(0.0)
    mask = dt.notna() & (dt >= start_dt) & (dt <= end_dt)
    total = int(round(float(sess.loc[mask].sum())))
    logger.info(
        "Monthly Veronika: Shopify sessions {}–{} via {} → {}",
        start_dt.date(),
        end_dt.date(),
        date_col,
        total,
    )
    return total


def _filter_shopify_by_range(shopify_df: pd.DataFrame, start_dt: pd.Timestamp, end_dt: pd.Timestamp) -> pd.DataFrame:
    if shopify_df.empty:
        return shopify_df
    df = shopify_df.copy()
    df.columns = df.columns.astype(str).str.strip()
    date_col = _detect_shopify_date_column(df)
    if not date_col:
        return pd.DataFrame()
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    return df[(df[date_col] >= start_dt) & (df[date_col] <= end_dt)]


def _shopify_full_price_share_pct(
    shopify_df: pd.DataFrame, start_dt: pd.Timestamp, end_dt: pd.Timestamp
) -> tuple[Optional[float], Optional[str]]:
    """
    Return (full_price_share_pct, method) for Shopify data in month window.

    Method priority:
    1) explicit class column (full/sale)
    2) explicit boolean flag column (is_full_price / is_discounted)
    3) discount amount column (<=0 full, >0 discounted)
    """
    sdf = _filter_shopify_by_range(shopify_df, start_dt, end_dt)
    if sdf.empty:
        return None, None

    net_col = _pick_col(
        sdf,
        (
            "Net sales",
            "Net sales amount",
            "Net sales (SEK)",
            "Nettoförsäljning",
            "Net Revenue",
            "Revenue net",
            "Sales net",
        ),
    )
    if not net_col:
        return None, None

    net_line = pd.to_numeric(sdf[net_col], errors="coerce").fillna(0.0)
    total = float(net_line.sum())
    if total <= 1e-9:
        return None, None

    # 1) Explicit class/type column
    cls_col = _pick_col(
        sdf,
        (
            "Price type",
            "price_type",
            "pricing_type",
            "discount_type",
            "sale_type",
            "full_price_or_sale",
            "price category",
        ),
    )
    if cls_col:
        cls = sdf[cls_col].astype(str).str.strip().str.lower()
        full_mask = (
            cls.str.contains(r"\bfull\b", na=False)
            | cls.str.contains(r"full.?price", na=False)
            | cls.str.contains(r"ordinarie", na=False)
            | cls.str.contains(r"ordinarie", na=False)
            | cls.str.contains(r"regular", na=False)
            | cls.str.contains(r"no.?discount", na=False)
        )
        if bool(full_mask.any()):
            fp = float(net_line.loc[full_mask].sum())
            return (fp / total * 100.0), f"class:{cls_col}"

    # 2) Explicit boolean flags
    is_full_col = _pick_col(sdf, ("is_full_price", "full_price", "is full price"))
    if is_full_col:
        vals = sdf[is_full_col].astype(str).str.strip().str.lower()
        full_mask = vals.isin({"1", "true", "t", "yes", "y", "full", "full_price"})
        if bool(full_mask.any()):
            fp = float(net_line.loc[full_mask].sum())
            return (fp / total * 100.0), f"flag:{is_full_col}"

    is_discounted_col = _pick_col(sdf, ("is_discounted", "discounted", "is discounted"))
    if is_discounted_col:
        vals = sdf[is_discounted_col].astype(str).str.strip().str.lower()
        disc_mask = vals.isin({"1", "true", "t", "yes", "y", "discounted", "sale"})
        fp = float(net_line.loc[~disc_mask].sum())
        return (fp / total * 100.0), f"flag_not_discounted:{is_discounted_col}"

    # 3) Discount amount heuristic (best fallback in Shopify app exports)
    disc_col = _pick_col(
        sdf,
        (
            "Discount amount",
            "Total discounts",
            "Discounts",
            "Rabatt",
            "Rabatter",
        ),
    )
    if disc_col:
        disc = pd.to_numeric(sdf[disc_col], errors="coerce").fillna(0.0)
        fp = float(net_line.loc[disc <= 0].sum())
        return (fp / total * 100.0), f"discount_col:{disc_col}"

    return None, None


def _shopify_full_price_diagnostics(
    shopify_df: pd.DataFrame, start_dt: pd.Timestamp, end_dt: pd.Timestamp
) -> Dict[str, Any]:
    """Return lightweight diagnostics for monthly full-price share column mapping."""
    out: Dict[str, Any] = {
        "rows_in_range": 0,
        "net_col": None,
        "class_col": None,
        "is_full_col": None,
        "is_discounted_col": None,
        "discount_col": None,
    }
    sdf = _filter_shopify_by_range(shopify_df, start_dt, end_dt)
    out["rows_in_range"] = int(len(sdf))
    if sdf.empty:
        return out

    out["net_col"] = _pick_col(
        sdf,
        (
            "Net sales",
            "Net sales amount",
            "Net sales (SEK)",
            "Nettoförsäljning",
            "Net Revenue",
            "Revenue net",
            "Sales net",
        ),
    )
    out["class_col"] = _pick_col(
        sdf,
        (
            "Price type",
            "price_type",
            "pricing_type",
            "discount_type",
            "sale_type",
            "full_price_or_sale",
            "price category",
        ),
    )
    out["is_full_col"] = _pick_col(sdf, ("is_full_price", "full_price", "is full price"))
    out["is_discounted_col"] = _pick_col(sdf, ("is_discounted", "discounted", "is discounted"))
    out["discount_col"] = _pick_col(
        sdf,
        (
            "Discount amount",
            "Total discounts",
            "Discounts",
            "Rabatt",
            "Rabatter",
        ),
    )
    return out


def _candidate_cols(df: pd.DataFrame, keywords: tuple[str, ...], limit: int = 8) -> list[str]:
    if df.empty:
        return []
    out: list[str] = []
    for c in df.columns:
        cl = str(c).strip().lower()
        if any(k in cl for k in keywords):
            out.append(str(c))
            if len(out) >= limit:
                break
    return out


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
    sessions = _shopify_sessions_in_range(all_data.get("shopify", pd.DataFrame()), start_dt, end_dt)
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

    order_col = "Order No" if "Order No" in online.columns else None
    unique_orders = int(online[order_col].nunique()) if order_col else 0
    conversion_rate = (unique_orders / sessions * 100.0) if sessions > 0 else 0.0

    cac = (marketing / new_customers) if new_customers > 0 else 0.0
    cos_pct = (marketing / gross * 100.0) if gross > 0 else 0.0
    # Same definition as Table 1 eMER / slide 1 aMER: online new-customer net ÷ total DEMA marketing (month, global)
    amer = (new_net / marketing) if marketing > 1e-9 else 0.0

    # Repeat purchase rate: share of online customers (month) with 2+ distinct orders
    repeat_purchase_rate_pct: Optional[float] = None
    if email_col and order_col:
        oc = online.dropna(subset=[email_col])
        per_c = oc.groupby(email_col)[order_col].nunique()
        buyers = int((per_c >= 1).sum())
        repeaters = int((per_c >= 2).sum())
        repeat_purchase_rate_pct = (repeaters / buyers * 100.0) if buyers > 0 else 0.0

    # Full-price share of ecom net revenue:
    # 1) Shopify order export in data/raw/{week}/discounts/ (compare-at price logic)
    # 2) Shopify app/order CSV in shopify/ folder (if it has net + price classification)
    # 3) Qlik discount column (rare — most Qlik exports lack discount fields)
    full_price_share_pct: Optional[float] = None
    full_price_share_method: Optional[str] = None
    qlik_fallback_discount_col: Optional[str] = None
    discounts_fp = calculate_full_price_share_for_date_range(base_week, data_root, start_s, end_s)
    if discounts_fp.get("full_price_share_pct") is not None:
        full_price_share_pct = float(discounts_fp["full_price_share_pct"])
        full_price_share_method = f"discounts:{discounts_fp.get('filename')}"
    else:
        shopify_full_share, shopify_method = _shopify_full_price_share_pct(
            all_data.get("shopify", pd.DataFrame()), start_dt, end_dt
        )
        if shopify_full_share is not None:
            full_price_share_pct = shopify_full_share
            full_price_share_method = f"shopify:{shopify_method}" if shopify_method else "shopify"
        else:
            dcol = _pick_discount_col(online)
            if dcol:
                disc = pd.to_numeric(online[dcol], errors="coerce").fillna(0.0)
                net_line = pd.to_numeric(online["Net Revenue"], errors="coerce").fillna(0.0)
                fp_net = float(net_line.loc[disc <= 0].sum())
                full_price_share_pct = (fp_net / net * 100.0) if net > 1e-9 else None
                full_price_share_method = f"qlik:{dcol}"
                qlik_fallback_discount_col = dcol

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

    payload = {
        "year_month": ym_label,
        "base_week": base_week,
        "date_range": {"start": start_s, "end": end_s},
        "definitions": {
            "repeat_purchase_rate_pct": "Share of online customers (unique email) with ≥2 distinct orders in the month.",
            "ltv_proxy_ttm": "Mean online net revenue per distinct customer over trailing 12 months ending last day of month (export coverage).",
            "ltv_cac_ratio": "ltv_proxy_ttm ÷ monthly nCAC (marketing ÷ new customers in month).",
            "conversion_rate_pct": "Unique online orders ÷ Shopify sessions summed over the month.",
            "full_price_share_pct": "Share of ecom net revenue at full price. Uses Shopify order export in data/raw/{week}/discounts/ (compare-at price > 0 = sale). Qlik has no discount columns in typical exports.",
            "new_customer_acquisition_cost": "Total marketing spend in month ÷ distinct new online customers in month.",
            "returning_customer_revenue": "Sum of online net revenue where New/Returning = returning.",
            "cos_pct": "Marketing spend ÷ online gross revenue × 100 (month, all markets).",
            "amer": "Online new-customer net revenue ÷ total DEMA marketing spend in the month (aMER, same as Table 1 eMER / all markets).",
            "corridor": "Budget plan COS % and aMER appear in budget_plan when a budget CSV is available (same month column as Table 1 MTD; aMER from the file or New Net ÷ Online Marketing if the cell is empty).",
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
            "amer": round(amer, 2),
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
    shop_diag = _shopify_full_price_diagnostics(all_data.get("shopify", pd.DataFrame()), start_dt, end_dt)
    payload["notes"].append(
        "full_price_diag:"
        f" shop_rows={shop_diag.get('rows_in_range', 0)}"
        f", shop_net_col={shop_diag.get('net_col')}"
        f", shop_class_col={shop_diag.get('class_col')}"
        f", shop_is_full_col={shop_diag.get('is_full_col')}"
        f", shop_is_discounted_col={shop_diag.get('is_discounted_col')}"
        f", shop_discount_col={shop_diag.get('discount_col')}"
        f", qlik_discount_col={qlik_fallback_discount_col}"
        f", source={full_price_share_method}"
    )
    payload["notes"].append(
        "full_price_diag_cols:"
        f" shop_candidates={_candidate_cols(all_data.get('shopify', pd.DataFrame()), ('net', 'sales', 'discount', 'rabatt', 'price', 'full'))}"
        f", qlik_candidates={_candidate_cols(online, ('discount', 'rabatt', 'price', 'net', 'gross', 'return'))}"
    )
    if full_price_share_method:
        payload["notes"].append(f"full_price_share_source={full_price_share_method}")
    elif discounts_fp.get("error") == "no_discounts_file":
        payload["notes"].append(
            f"full_price_share_missing: upload Shopify order-line export to data/raw/{base_week}/discounts/ "
            "(Settings → Discounts / sales export; needs Date, Net sales, and compare-at / Ordinarie pris). "
            "Current shopify/ folder is sessions-only; Qlik export has no discount column."
        )
    elif discounts_fp.get("error"):
        payload["notes"].append(
            f"full_price_share_missing: discounts file issue ({discounts_fp.get('error')}); "
            f"file={discounts_fp.get('filename')}"
        )
    _attach_budget_corridor_from_file(payload, year_month, base_week)
    return payload


def _empty_payload(
    ym_label: str, base_week: str, start_s: str, end_s: str, note: str
) -> Dict[str, Any]:
    p = {
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
            "amer": 0.0,
        },
        "supporting": {},
        "notes": [note],
    }
    _attach_budget_corridor_from_file(p, ym_label, base_week)
    return p
