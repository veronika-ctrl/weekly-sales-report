"""Monthly Women's overview and top-selling products vs the same month last year.

Uses the last completed calendar month for the selected ISO week, so the first
week of the next month reviews the month that just closed.
"""

from __future__ import annotations

import calendar
import gc
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from loguru import logger

from weekly_report.src.adapters.qlik import (
    load_qlik_columns,
    qlik_resident_section,
    qlik_source_files,
)
from weekly_report.src.metrics.result_cache import ResultCache
from weekly_report.src.periods.calculator import get_week_date_range
from weekly_report.src.storage.disk import list_qlik_weeks

_MONTHLY_QLIK_COLUMNS = (
    "Date",
    "Sales Channel",
    "Gender",
    "Product Category",
    "Product",
    "Color",
    "Gross Revenue",
    "Sales Qty",
)

NOTE = (
    "Last completed calendar month vs the same month last year. "
    "Open this in the first week of the next month to review the month that just closed."
)

_women_cache = ResultCache("women-monthly")
_products_cache = ResultCache("top-products-monthly")


def resolve_qlik_week_for_monthly(base_week: str, data_root: Path) -> str:
    """Prefer the selected ISO week; if it has no Qlik, use the newest week that does.

    Monday of a new ISO week (2026-45) must not 500. The last completed month is
    still on the previous week's Qlik file.
    """
    try:
        qlik_source_files(Path(data_root) / "raw" / base_week)
        return base_week
    except FileNotFoundError:
        pass
    weeks = list_qlik_weeks(data_root)
    if weeks:
        logger.info(
            "monthly women/products: no Qlik in %s, using latest week %s",
            base_week,
            weeks[0],
        )
        return weeks[0]
    return base_week


def last_completed_calendar_month(week_end: date) -> Tuple[date, date]:
    """Inclusive start/end of the last calendar month fully closed by week_end."""
    last_of_this_month = date(week_end.year, week_end.month, calendar.monthrange(week_end.year, week_end.month)[1])
    if week_end >= last_of_this_month:
        start = date(week_end.year, week_end.month, 1)
        return start, last_of_this_month
    prev_last = date(week_end.year, week_end.month, 1) - timedelta(days=1)
    start = date(prev_last.year, prev_last.month, 1)
    return start, prev_last


def month_range_for_week(base_week: str) -> Tuple[date, date]:
    week_end = datetime.strptime(get_week_date_range(base_week)["end"], "%Y-%m-%d").date()
    return last_completed_calendar_month(week_end)


def prior_months(end_month_start: date, count: int) -> List[Tuple[date, date]]:
    """Oldest → newest list of `count` calendar months ending at end_month_start."""
    months: List[Tuple[date, date]] = []
    y, m = end_month_start.year, end_month_start.month
    for _ in range(max(1, count)):
        start = date(y, m, 1)
        end = date(y, m, calendar.monthrange(y, m)[1])
        months.append((start, end))
        if m == 1:
            y, m = y - 1, 12
        else:
            m -= 1
    months.reverse()
    return months


def _month_label(start: date) -> str:
    return start.strftime("%b '%y")


def _yoy_pct(current: float, last_year: float) -> Optional[float]:
    if abs(float(last_year or 0)) < 1e-9:
        return None
    return ((float(current) - float(last_year)) / abs(float(last_year))) * 100.0


def _slice_dates(df: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    if df is None or df.empty or "Date" not in df.columns:
        return pd.DataFrame()
    dates = pd.to_datetime(df["Date"], errors="coerce")
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end) + pd.Timedelta(days=1) - pd.Timedelta(nanoseconds=1)
    return df.loc[(dates >= start_ts) & (dates <= end_ts)].copy()


def _online(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty or "Sales Channel" not in df.columns:
        return pd.DataFrame()
    channel = df["Sales Channel"].astype(str).str.strip().str.lower()
    return df.loc[channel.eq("online")].copy()


def _apply_gender(df: pd.DataFrame, gender_filter: Optional[str]) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    if not gender_filter:
        return df
    gender = df["Gender"].astype(str).str.strip().str.upper() if "Gender" in df.columns else pd.Series("", index=df.index)
    if gender_filter == "women":
        return df.loc[gender.eq("WOMEN")].copy()
    if gender_filter == "men":
        return df.loc[~gender.eq("WOMEN")].copy()
    return df


def _qty_series(df: pd.DataFrame) -> pd.Series:
    if "Sales Qty" in df.columns:
        return pd.to_numeric(df["Sales Qty"], errors="coerce").fillna(0.0)
    return pd.Series(0.0, index=df.index)


def _gross_qty(df: pd.DataFrame) -> Tuple[float, int]:
    if df is None or df.empty:
        return 0.0, 0
    gross = float(pd.to_numeric(df.get("Gross Revenue", 0.0), errors="coerce").fillna(0.0).sum())
    qty = int(round(float(_qty_series(df).sum())))
    return gross, qty


def _category_rows(df: pd.DataFrame, ly_df: pd.DataFrame) -> List[Dict[str, Any]]:
    def by_cat(frame: pd.DataFrame) -> pd.DataFrame:
        if frame is None or frame.empty or "Product Category" not in frame.columns:
            return pd.DataFrame(columns=["category", "gross_revenue", "sales_qty"])
        work = frame.copy()
        work["_gross"] = pd.to_numeric(work.get("Gross Revenue", 0.0), errors="coerce").fillna(0.0)
        work["_qty"] = _qty_series(work)
        work["_cat"] = work["Product Category"].astype(str).str.strip()
        work = work.loc[work["_cat"].ne("") & work["_cat"].ne("-") & work["_cat"].ne("nan")]
        grouped = work.groupby("_cat", dropna=False).agg(gross_revenue=("_gross", "sum"), sales_qty=("_qty", "sum")).reset_index()
        grouped = grouped.rename(columns={"_cat": "category"})
        return grouped

    cur = by_cat(df)
    ly = by_cat(ly_df)
    ly_map = {str(r.category): r for r in ly.itertuples(index=False)} if not ly.empty else {}
    total = float(cur["gross_revenue"].sum()) if not cur.empty else 0.0
    rows: List[Dict[str, Any]] = []
    for r in cur.sort_values("gross_revenue", ascending=False).itertuples(index=False):
        ly_r = ly_map.get(str(r.category))
        ly_gross = float(ly_r.gross_revenue) if ly_r is not None else 0.0
        ly_qty = int(round(float(ly_r.sales_qty))) if ly_r is not None else 0
        rows.append(
            {
                "category": str(r.category),
                "gross_revenue": float(r.gross_revenue),
                "sales_qty": int(round(float(r.sales_qty))),
                "last_year_gross_revenue": ly_gross,
                "last_year_sales_qty": ly_qty,
                "yoy_pct": _yoy_pct(float(r.gross_revenue), ly_gross),
                "share_pct": (float(r.gross_revenue) / total * 100.0) if total > 0 else 0.0,
            }
        )
    return rows


def _product_agg(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["gender", "category", "product", "color", "gross_revenue", "sales_qty"])
    work = df.copy()
    work["_gross"] = pd.to_numeric(work.get("Gross Revenue", 0.0), errors="coerce").fillna(0.0)
    work["_qty"] = _qty_series(work)
    work["_gender"] = work["Gender"].astype(str).str.strip().str.upper() if "Gender" in work.columns else ""
    work["_category"] = work["Product Category"].astype(str).str.strip() if "Product Category" in work.columns else ""
    work["_product"] = work["Product"].astype(str).str.strip() if "Product" in work.columns else ""
    work["_color"] = work["Color"].astype(str).str.strip() if "Color" in work.columns else ""
    work["_color"] = work["_color"].replace({"-": "", "nan": "", "None": ""})
    work = work.loc[
        work["_gender"].ne("-")
        & work["_gender"].ne("")
        & work["_category"].ne("-")
        & work["_category"].ne("")
        & work["_product"].ne("-")
        & work["_product"].ne("")
    ]
    grouped = (
        work.groupby(["_gender", "_category", "_product", "_color"], dropna=False)
        .agg(gross_revenue=("_gross", "sum"), sales_qty=("_qty", "sum"))
        .reset_index()
        .rename(columns={"_gender": "gender", "_category": "category", "_product": "product", "_color": "color"})
    )
    return grouped.sort_values("gross_revenue", ascending=False)


def _top_products(cur_df: pd.DataFrame, ly_df: pd.DataFrame, top_n: int) -> Tuple[List[Dict[str, Any]], Dict[str, Any], Dict[str, Any]]:
    cur = _product_agg(cur_df)
    ly = _product_agg(ly_df)
    ly_map = {
        (str(r.gender), str(r.category), str(r.product), str(r.color)): r
        for r in ly.itertuples(index=False)
    } if not ly.empty else {}
    grand_gross, grand_qty = _gross_qty(cur_df)
    ly_grand_gross, ly_grand_qty = _gross_qty(ly_df)
    top = cur.head(top_n)
    products: List[Dict[str, Any]] = []
    for idx, row in enumerate(top.itertuples(index=False), start=1):
        key = (str(row.gender), str(row.category), str(row.product), str(row.color))
        ly_r = ly_map.get(key)
        ly_gross = float(ly_r.gross_revenue) if ly_r is not None else 0.0
        ly_qty = int(round(float(ly_r.sales_qty))) if ly_r is not None else 0
        gross = float(row.gross_revenue)
        products.append(
            {
                "rank": idx,
                "gender": str(row.gender),
                "category": str(row.category),
                "product": str(row.product),
                "color": str(row.color),
                "gross_revenue": gross,
                "sales_qty": int(round(float(row.sales_qty))),
                "last_year_gross_revenue": ly_gross,
                "last_year_sales_qty": ly_qty,
                "yoy_pct": _yoy_pct(gross, ly_gross),
                "sob": (gross / grand_gross * 100.0) if grand_gross > 0 else 0.0,
            }
        )
    top_gross = float(sum(p["gross_revenue"] for p in products))
    top_qty = int(sum(p["sales_qty"] for p in products))
    ly_top_gross = float(sum(p["last_year_gross_revenue"] for p in products))
    ly_top_qty = int(sum(p["last_year_sales_qty"] for p in products))
    top_total = {
        "gross_revenue": top_gross,
        "sales_qty": top_qty,
        "sob": (top_gross / grand_gross * 100.0) if grand_gross > 0 else 0.0,
        "last_year_gross_revenue": ly_top_gross,
        "last_year_sales_qty": ly_top_qty,
        "yoy_pct": _yoy_pct(top_gross, ly_top_gross),
    }
    grand_total = {
        "gross_revenue": grand_gross,
        "sales_qty": grand_qty,
        "sob": 100.0,
        "last_year_gross_revenue": ly_grand_gross,
        "last_year_sales_qty": ly_grand_qty,
        "yoy_pct": _yoy_pct(grand_gross, ly_grand_gross),
    }
    return products, top_total, grand_total


def _trend_points(
    qlik: pd.DataFrame,
    months: List[Tuple[date, date]],
    gender_filter: Optional[str],
) -> List[Dict[str, Any]]:
    points: List[Dict[str, Any]] = []
    for start, end in months:
        ly_start, ly_end = date(start.year - 1, start.month, 1), date(
            start.year - 1, start.month, calendar.monthrange(start.year - 1, start.month)[1]
        )
        cur = _apply_gender(_online(_slice_dates(qlik, start, end)), gender_filter)
        ly = _apply_gender(_online(_slice_dates(qlik, ly_start, ly_end)), gender_filter)
        gross, qty = _gross_qty(cur)
        ly_gross, ly_qty = _gross_qty(ly)
        points.append(
            {
                "month": start.strftime("%Y-%m"),
                "label": _month_label(start),
                "start": start.isoformat(),
                "end": end.isoformat(),
                "gross_revenue": gross,
                "sales_qty": qty,
                "last_year_gross_revenue": ly_gross,
                "last_year_sales_qty": ly_qty,
                "yoy_pct": _yoy_pct(gross, ly_gross),
            }
        )
    return points


def _cell_date(raw: object) -> Optional[date]:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    text = str(raw).strip()
    if not text or text.lower() in {"nan", "nat", "none", "natype"}:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        pass
    parsed = pd.to_datetime(raw, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date()


def _keep_online_between(start: date, end: date):
    """Drop retail and out-of-window rows while the Excel sheet is still streaming."""

    def keep(values: Dict[str, object]) -> bool:
        channel = str(values.get("Sales Channel") or "").strip().lower()
        if channel != "online":
            return False
        parsed = _cell_date(values.get("Date"))
        if parsed is None:
            return False
        return start <= parsed <= end

    return keep


def _load_qlik(qlik_week: str, data_root: Path, months: List[Tuple[date, date]]) -> pd.DataFrame:
    """Column-stream the weekly Qlik file. FileNotFound → empty; other errors propagate."""
    raw_path = Path(data_root) / "raw" / qlik_week
    keep_row = None
    if months:
        oldest = months[0][0]
        newest = months[-1][1]
        ly_oldest = date(oldest.year - 1, oldest.month, 1)
        keep_row = _keep_online_between(ly_oldest, newest)
    try:
        frame = load_qlik_columns(raw_path, _MONTHLY_QLIK_COLUMNS, keep_row=keep_row)
    except FileNotFoundError as exc:
        logger.warning("monthly women/products: no Qlik for %s: %s", qlik_week, exc)
        return pd.DataFrame()
    if frame is None or frame.empty:
        return pd.DataFrame()
    frame.columns = frame.columns.astype(str).str.strip()
    return frame


def _trim_online_window(qlik: pd.DataFrame, months: List[Tuple[date, date]]) -> pd.DataFrame:
    """Keep Online rows in the 13-month window plus last year. Drop the rest before copies."""
    online = _online(qlik)
    if online.empty or not months:
        return online
    oldest = months[0][0]
    newest = months[-1][1]
    ly_oldest = date(oldest.year - 1, oldest.month, 1)
    return _slice_dates(online, ly_oldest, newest)


def _window_meta(base_week: str, months: int) -> Dict[str, Any]:
    start, end = month_range_for_week(base_week)
    windows = prior_months(start, months)
    return {
        "base_week": base_week,
        "focus_month": start.strftime("%Y-%m"),
        "focus_label": _month_label(start),
        "focus_start": start.isoformat(),
        "focus_end": end.isoformat(),
        "months": windows,
        "note": NOTE,
    }


def _payload_from_online(
    online: pd.DataFrame,
    base_week: str,
    months: int,
    top_n: int,
    gender_filter: Optional[str],
    kind: str,
) -> Dict[str, Any]:
    meta = _window_meta(base_week, months)
    start = date.fromisoformat(meta["focus_start"])
    end = date.fromisoformat(meta["focus_end"])
    ly_start, ly_end = date(start.year - 1, start.month, 1), date(
        start.year - 1, start.month, calendar.monthrange(start.year - 1, start.month)[1]
    )
    cur = _apply_gender(_slice_dates(online, start, end), gender_filter)
    ly = _apply_gender(_slice_dates(online, ly_start, ly_end), gender_filter)
    all_cur = _slice_dates(online, start, end)
    gross, qty = _gross_qty(cur)
    ly_gross, ly_qty = _gross_qty(ly)
    online_gross, _ = _gross_qty(all_cur)
    products, top_total, grand_total = _top_products(cur, ly, top_n)
    payload: Dict[str, Any] = {
        "base_week": base_week,
        "focus_month": meta["focus_month"],
        "focus_label": meta["focus_label"],
        "focus_start": meta["focus_start"],
        "focus_end": meta["focus_end"],
        "note": meta["note"],
        "trend": _trend_points(online, meta["months"], gender_filter),
        "top_total": top_total,
        "grand_total": grand_total,
    }
    if kind == "women_overview":
        payload["headline"] = {
            "gross_revenue": gross,
            "sales_qty": qty,
            "last_year_gross_revenue": ly_gross,
            "last_year_sales_qty": ly_qty,
            "yoy_pct": _yoy_pct(gross, ly_gross),
            "online_share_pct": (gross / online_gross * 100.0) if online_gross > 0 else 0.0,
            "online_gross_revenue": online_gross,
        }
        payload["categories"] = _category_rows(cur, ly)
        payload["top_products"] = products
    else:
        payload["gender_filter"] = gender_filter
        payload["products"] = products
    return payload


def _compute_monthly(
    base_week: str,
    data_root: Path,
    months: int,
    top_n: int,
    gender_filter: Optional[str],
    kind: str,
) -> Dict[str, Any]:
    qlik_week = resolve_qlik_week_for_monthly(base_week, data_root)
    meta = _window_meta(base_week, months)
    with qlik_resident_section():
        qlik = _load_qlik(qlik_week, data_root, meta["months"])
        try:
            online = _trim_online_window(qlik, meta["months"])
            del qlik
            gc.collect()
            return _payload_from_online(online, base_week, months, top_n, gender_filter, kind)
        finally:
            gc.collect()


def calculate_women_monthly(base_week: str, data_root: Path, months: int = 13, top_n: int = 15) -> Dict[str, Any]:
    qlik_week = resolve_qlik_week_for_monthly(base_week, data_root)
    raw = Path(data_root) / "raw" / qlik_week
    rows = _women_cache.get_or_compute(
        Path(data_root),
        raw,
        qlik_week,
        months,
        lambda: [_compute_monthly(base_week, Path(data_root), months, top_n, "women", "women_overview")],
        extra=f"top{top_n}|sel{base_week}",
    )
    return rows[0]


def calculate_top_products_monthly(
    base_week: str,
    data_root: Path,
    gender_filter: str = "men",
    months: int = 13,
    top_n: int = 30,
) -> Dict[str, Any]:
    if gender_filter not in ("men", "women"):
        raise ValueError("gender_filter must be 'men' or 'women'")
    qlik_week = resolve_qlik_week_for_monthly(base_week, data_root)
    raw = Path(data_root) / "raw" / qlik_week
    rows = _products_cache.get_or_compute(
        Path(data_root),
        raw,
        qlik_week,
        months,
        lambda: [_compute_monthly(base_week, Path(data_root), months, top_n, gender_filter, "top_products")],
        extra=f"{gender_filter}|top{top_n}|sel{base_week}",
    )
    return rows[0]
