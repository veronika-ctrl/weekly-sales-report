"""Full Price vs Sale excluding AfterShip exchanges — daily Shopify export.

Separate dataset from the all-orders revenue-over-time history in ``*/discounts/*``.
Stored under ``data/raw/{week}/full_price_vs_sale_excl_exchanges/``.
Newest uploaded file wins per calendar date (upsert-by-date).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from weekly_report.src.fx_rates import convert_revenue_over_time_to_sek
from weekly_report.src.metrics.discounts_sales import (
    _build_display_weeks,
    _iso_week_series,
    _pick_column,
    _read_csv_flexible,
    _to_number,
    load_revenue_over_time_history,
)
from weekly_report.src.periods.calculator import get_week_date_range

FILE_TYPE = "full_price_vs_sale_excl_exchanges"

EXCL_REQUIRED_HEADERS: List[Tuple[str, List[str]]] = [
    ("Date", ["Date", "Day", "Dag", "Datum"]),
    ("Full Price", ["Full Price", "Full price", "Fullpris"]),
    ("Compare-at Price Sale", ["Compare-at Price Sale", "Compare-at price sale"]),
    ("Discount Code / Auto Discount", ["Discount Code / Auto Discount"]),
    ("Both", ["Both"]),
    ("Price Drop Sale", ["Price Drop Sale", "Price drop sale"]),
    ("Total", ["Total", "Totalt", "Sum"]),
    ("Discount Amount", ["Discount Amount", "Discount amount"]),
    ("Full Price Share %", ["Full Price Share %", "Full Price Share"]),
    ("Exchange Orders", ["Exchange Orders", "Exchange orders"]),
    ("Exchange Gross Value", ["Exchange Gross Value", "Exchange Gross"]),
    ("Exchange Discount", ["Exchange Discount"]),
    ("Exchange Net Revenue", ["Exchange Net Revenue"]),
]

# Monetary columns converted USD→SEK. Share % and exchange order counts are excluded.
EXCL_MONEY_COLS = (
    "_full",
    "_compare_at",
    "_discount_code",
    "_both",
    "_price_drop",
    "_total",
    "_discount",
    "_exchange_gross",
    "_exchange_discount",
    "_exchange_net",
)

_METRIC_SUM_COLS = [
    "_full",
    "_compare_at",
    "_discount_code",
    "_both",
    "_price_drop",
    "_total",
    "_discount",
    "_exchange_orders",
    "_exchange_gross",
    "_exchange_discount",
    "_exchange_net",
]


def _to_percentage(s: pd.Series) -> pd.Series:
    """Parse share percentages from ``45.2``, ``45.2%``, blanks → 0."""
    as_str = s.astype(str).str.replace("\u00a0", " ", regex=False).str.strip()
    as_str = as_str.str.replace("%", "", regex=False)
    as_str = as_str.str.replace(" ", "", regex=False).str.replace(",", ".", regex=False)
    as_str = as_str.replace({"nan": "", "none": "", "nat": ""}, regex=False)
    return pd.to_numeric(as_str, errors="coerce").fillna(0.0)


def missing_excl_exchanges_headers(df: pd.DataFrame) -> List[str]:
    """Return canonical names of required headers that are missing."""
    missing: List[str] = []
    for canonical, aliases in EXCL_REQUIRED_HEADERS:
        if _pick_column(df, aliases) is None:
            missing.append(canonical)
    return missing


def inspect_excl_exchanges_upload(file_path: Path) -> Dict[str, Any]:
    """Validate headers and report the imported calendar date range (cheap CSV read)."""
    df = _read_csv_flexible(file_path)
    df.columns = [str(c).strip().replace('"', "") for c in df.columns]
    missing = missing_excl_exchanges_headers(df)
    date_col = _pick_column(df, ["Date", "Day", "Dag", "Datum"])
    first_date = last_date = None
    row_count = int(len(df))
    if date_col and not missing:
        dates = pd.to_datetime(df[date_col], errors="coerce").dropna()
        if not dates.empty:
            first_date = str(dates.min().date())
            last_date = str(dates.max().date())
    return {
        "missing_headers": missing,
        "columns": [str(c).strip() for c in df.columns],
        "first_date": first_date,
        "last_date": last_date,
        "row_count": row_count,
        "date_column": date_col,
    }


def _empty_history() -> Dict[str, Any]:
    cols = ["_date", *_METRIC_SUM_COLS, "_full_price_share_pct"]
    return {
        "df": pd.DataFrame(columns=cols),
        "files_used": [],
        "fx": {"applied": False},
        "currency": "SEK",
    }


def _normalize_excl_frame(df: pd.DataFrame, mtime: float) -> pd.DataFrame:
    date_col = _pick_column(df, ["Date", "Day", "Dag", "Datum"])
    if not date_col:
        return pd.DataFrame()

    def _num(aliases: List[str]) -> pd.Series:
        col = _pick_column(df, aliases)
        if col is None:
            return pd.Series(0.0, index=df.index, dtype="float64")
        return _to_number(df[col])

    share_col = _pick_column(df, ["Full Price Share %", "Full Price Share"])
    share = _to_percentage(df[share_col]) if share_col else pd.Series(0.0, index=df.index)

    sub = pd.DataFrame()
    sub["_date"] = pd.to_datetime(df[date_col], errors="coerce")
    sub["_full"] = _num(["Full Price", "Full price", "Fullpris"])
    sub["_compare_at"] = _num(["Compare-at Price Sale", "Compare-at price sale"])
    sub["_discount_code"] = _num(["Discount Code / Auto Discount"])
    sub["_both"] = _num(["Both"])
    sub["_price_drop"] = _num(["Price Drop Sale", "Price drop sale"])
    sub["_total"] = _num(["Total", "Totalt", "Sum"])
    sub["_discount"] = _num(["Discount Amount", "Discount amount"])
    sub["_full_price_share_pct"] = share
    sub["_exchange_orders"] = _num(["Exchange Orders", "Exchange orders"])
    sub["_exchange_gross"] = _num(["Exchange Gross Value", "Exchange Gross"])
    sub["_exchange_discount"] = _num(["Exchange Discount"])
    sub["_exchange_net"] = _num(["Exchange Net Revenue"])
    sub["_mtime"] = mtime
    # Keep zero-sales dates; only drop unparseable dates.
    sub = sub.dropna(subset=["_date"])
    return sub


def load_full_price_vs_sale_excl_exchanges_history(data_root: Path) -> Dict[str, Any]:
    """Merge every uploaded excl-exchanges daily file; newest file wins per date."""
    raw_root = Path(data_root) / "raw"
    files = sorted(
        [f for f in raw_root.glob(f"*/{FILE_TYPE}/*.*") if not f.name.startswith(".")],
        key=lambda f: f.stat().st_mtime,
    )

    frames: List[pd.DataFrame] = []
    files_used: List[str] = []
    for f in files:
        try:
            df = _read_csv_flexible(f)
        except Exception:
            continue
        df.columns = [str(c).strip().replace('"', "") for c in df.columns]
        if missing_excl_exchanges_headers(df):
            continue
        sub = _normalize_excl_frame(df, f.stat().st_mtime)
        if sub.empty:
            continue
        frames.append(sub)
        files_used.append(f.name)

    if not frames:
        return _empty_history()

    alld = pd.concat(frames, ignore_index=True)
    alld = alld.sort_values(["_date", "_mtime"]).drop_duplicates(subset=["_date"], keep="last")
    keep = ["_date", *_METRIC_SUM_COLS, "_full_price_share_pct"]
    alld = alld[keep].sort_values("_date").reset_index(drop=True)

    extra = [c for c in EXCL_MONEY_COLS if c not in ("_full", "_discounted", "_total", "_discount")]
    alld, fx = convert_revenue_over_time_to_sek(alld, Path(data_root), extra_money_cols=extra)
    return {
        "df": alld,
        "files_used": files_used,
        "fx": fx,
        "currency": fx.get("target_currency", "SEK") if fx.get("applied") else "USD",
    }


def _share(num: float, den: Optional[float]) -> Optional[float]:
    if den is None or den <= 0:
        return None
    return float(num) / float(den) * 100.0


def _full_price_share(full: float, total: float, fallback: Optional[float] = None) -> Optional[float]:
    if total > 0:
        return full / total * 100.0
    if fallback is not None:
        return float(fallback)
    return None


def compare_incl_excl(
    *,
    excl_full: float,
    excl_total: float,
    excl_discount: float,
    exchange_gross: float,
    exchange_discount: float,
    incl_full: Optional[float],
    incl_total: Optional[float],
    incl_discount: Optional[float],
) -> Dict[str, Any]:
    """Comparison metrics between all-orders and exchange-excluded figures."""
    excl_share = _full_price_share(excl_full, excl_total)
    incl_share = (
        _full_price_share(float(incl_full), float(incl_total))
        if incl_full is not None and incl_total is not None
        else None
    )
    pp_diff = (
        excl_share - incl_share if excl_share is not None and incl_share is not None else None
    )

    non_exchange_gross_est = excl_total + excl_discount
    gross_context = non_exchange_gross_est + exchange_gross
    exchange_gross_share_pct = _share(exchange_gross, gross_context)

    if incl_discount is not None and incl_discount > 0:
        disc_den: Optional[float] = float(incl_discount)
    else:
        disc_den = excl_discount + exchange_discount
    exchange_discount_share_pct = _share(exchange_discount, disc_den)

    return {
        "full_price_share_incl_pct": incl_share,
        "full_price_share_excl_pct": excl_share,
        "full_price_share_pp_diff": pp_diff,
        "total_incl": None if incl_total is None else float(incl_total),
        "total_excl": float(excl_total),
        "discount_incl": None if incl_discount is None else float(incl_discount),
        "discount_excl": float(excl_discount),
        "exchange_gross_share_pct": exchange_gross_share_pct,
        "exchange_discount_share_pct": exchange_discount_share_pct,
        "non_exchange_gross_est": float(non_exchange_gross_est),
        "gross_context": float(gross_context),
    }


def _incl_lookup(incl_df: pd.DataFrame) -> Dict[pd.Timestamp, Dict[str, Optional[float]]]:
    if incl_df is None or incl_df.empty:
        return {}
    out: Dict[pd.Timestamp, Dict[str, Optional[float]]] = {}
    for _, row in incl_df.iterrows():
        key = pd.Timestamp(row["_date"]).normalize()
        damt = row["_discount"] if "_discount" in row and pd.notna(row["_discount"]) else None
        out[key] = {
            "full": float(row["_full"] or 0.0),
            "total": float(row["_total"] or 0.0),
            "discount": None if damt is None else float(damt),
        }
    return out


def _metrics_from_sum(sums: Dict[str, float], share_fallback: Optional[float] = None) -> Dict[str, Any]:
    full = float(sums.get("_full", 0.0) or 0.0)
    total = float(sums.get("_total", 0.0) or 0.0)
    discount = float(sums.get("_discount", 0.0) or 0.0)
    return {
        "full_price": full,
        "compare_at_price_sale": float(sums.get("_compare_at", 0.0) or 0.0),
        "discount_code_auto": float(sums.get("_discount_code", 0.0) or 0.0),
        "both": float(sums.get("_both", 0.0) or 0.0),
        "price_drop_sale": float(sums.get("_price_drop", 0.0) or 0.0),
        "total": total,
        "discount_amount": discount,
        "full_price_share_pct": _full_price_share(full, total, share_fallback),
        "exchange_orders": int(round(float(sums.get("_exchange_orders", 0.0) or 0.0))),
        "exchange_gross_value": float(sums.get("_exchange_gross", 0.0) or 0.0),
        "exchange_discount": float(sums.get("_exchange_discount", 0.0) or 0.0),
        "exchange_net_revenue": float(sums.get("_exchange_net", 0.0) or 0.0),
    }


def _row_sums(sub: pd.DataFrame) -> Dict[str, float]:
    if sub.empty:
        return {c: 0.0 for c in _METRIC_SUM_COLS}
    return {c: float(pd.to_numeric(sub[c], errors="coerce").fillna(0.0).sum()) for c in _METRIC_SUM_COLS}


def _incl_window_totals(
    lookup: Dict[pd.Timestamp, Dict[str, Optional[float]]],
    dates: List[pd.Timestamp],
) -> Dict[str, Optional[float]]:
    full = 0.0
    total = 0.0
    discount = 0.0
    has_discount = False
    matched = 0
    for d in dates:
        row = lookup.get(pd.Timestamp(d).normalize())
        if not row:
            continue
        matched += 1
        full += float(row["full"] or 0.0)
        total += float(row["total"] or 0.0)
        if row["discount"] is not None:
            has_discount = True
            discount += float(row["discount"])
    if matched == 0:
        return {"full": None, "total": None, "discount": None}
    return {
        "full": full,
        "total": total,
        "discount": discount if has_discount else None,
    }


def _attach_comparison(
    metrics: Dict[str, Any],
    incl: Dict[str, Optional[float]],
) -> Dict[str, Any]:
    metrics["comparison"] = compare_incl_excl(
        excl_full=metrics["full_price"],
        excl_total=metrics["total"],
        excl_discount=metrics["discount_amount"],
        exchange_gross=metrics["exchange_gross_value"],
        exchange_discount=metrics["exchange_discount"],
        incl_full=incl.get("full"),
        incl_total=incl.get("total"),
        incl_discount=incl.get("discount"),
    )
    return metrics


def calculate_full_price_vs_sale_excl_exchanges(
    base_week: str,
    data_root: Path,
    num_weeks: int = 8,
    months: int = 13,
    granularity: str = "week",
) -> Dict[str, Any]:
    """Daily + period totals for the exchange-excluded export, with all-orders comparison."""
    history = load_full_price_vs_sale_excl_exchanges_history(data_root)
    df = history["df"]
    incl_hist = load_revenue_over_time_history(data_root)
    incl_lookup = _incl_lookup(incl_hist.get("df"))

    base: Dict[str, Any] = {
        "base_week": base_week,
        "num_weeks": num_weeks,
        "months": months,
        "granularity": granularity,
        "source": FILE_TYPE,
        "files_used": history["files_used"],
        "currency": history.get("currency", "SEK"),
        "fx": history.get("fx"),
        "all_orders_files_used": incl_hist.get("files_used", []),
    }
    if df.empty:
        return {**base, "days": [], "weeks": [], "months_data": [], "period": None, "history_range": None}

    df = df.copy()
    df["_date"] = pd.to_datetime(df["_date"], errors="coerce")
    df = df.dropna(subset=["_date"])
    df["_date"] = df["_date"].dt.normalize()
    df["_week"] = _iso_week_series(df["_date"])

    week_end = pd.to_datetime(get_week_date_range(base_week)["end"], errors="coerce")
    if pd.isna(week_end):
        return {**base, "error": "Invalid base_week date range", "days": [], "weeks": [], "months_data": [], "period": None}

    expected_weeks: List[str] = []
    month_keys: List[Any] = []
    end_period = None
    if granularity == "month":
        end_period = week_end.to_period("M")
        count = max(1, int(months or 13))
        month_keys = [(end_period - i) for i in range(count)]
        window_start = month_keys[-1].start_time.normalize()
        window_end = week_end.normalize()
        period_label = f"{window_start.date()} → {window_end.date()} (last {count} months)"
    else:
        expected_weeks = _build_display_weeks(base_week, num_weeks)
        window_start = pd.to_datetime(get_week_date_range(expected_weeks[0])["start"]).normalize()
        window_end = week_end.normalize()
        period_label = f"{window_start.date()} → {window_end.date()} (last {num_weeks} weeks)"

    window = df[(df["_date"] >= window_start) & (df["_date"] <= window_end)].copy()
    if window.empty:
        return {
            **base,
            "history_range": {
                "start": str(df["_date"].min().date()),
                "end": str(df["_date"].max().date()),
            },
            "days": [],
            "weeks": [],
            "months_data": [],
            "period": None,
        }

    days_out: List[Dict[str, Any]] = []
    for _, row in window.sort_values("_date").iterrows():
        sums = {c: float(row[c] or 0.0) for c in _METRIC_SUM_COLS}
        fallback = float(row["_full_price_share_pct"]) if pd.notna(row.get("_full_price_share_pct")) else 0.0
        metrics = _metrics_from_sum(sums, share_fallback=fallback)
        day_key = pd.Timestamp(row["_date"]).normalize()
        incl_row = incl_lookup.get(day_key)
        incl = (
            {"full": incl_row["full"], "total": incl_row["total"], "discount": incl_row["discount"]}
            if incl_row
            else {"full": None, "total": None, "discount": None}
        )
        _attach_comparison(metrics, incl)
        days_out.append({"date": str(day_key.date()), "week": str(row["_week"]), **metrics})

    period_sums = _row_sums(window)
    period_metrics = _metrics_from_sum(period_sums)
    period_dates = [pd.Timestamp(d).normalize() for d in window["_date"].tolist()]
    _attach_comparison(period_metrics, _incl_window_totals(incl_lookup, period_dates))
    period = {
        "label": period_label,
        "start": str(window_start.date()),
        "end": str(window_end.date()),
        **period_metrics,
    }

    weeks_out: List[Dict[str, Any]] = []
    if granularity != "month":
        for w in expected_weeks:
            sub = window[window["_week"] == w]
            metrics = _metrics_from_sum(_row_sums(sub))
            dates = [pd.Timestamp(d).normalize() for d in sub["_date"].tolist()]
            _attach_comparison(metrics, _incl_window_totals(incl_lookup, dates))
            weeks_out.append({"week": w, **metrics})

    months_out: List[Dict[str, Any]] = []
    if granularity == "month":
        for mp in month_keys:
            is_latest = mp == end_period
            start = mp.start_time.normalize()
            end = week_end.normalize() if is_latest else mp.end_time.normalize()
            sub = window[(window["_date"] >= start) & (window["_date"] <= end)]
            metrics = _metrics_from_sum(_row_sums(sub))
            dates = [pd.Timestamp(d).normalize() for d in sub["_date"].tolist()]
            _attach_comparison(metrics, _incl_window_totals(incl_lookup, dates))
            months_out.append(
                {
                    "month": mp.strftime("%Y-%m"),
                    "start": str(start.date()),
                    "end": str(end.date()),
                    **metrics,
                }
            )

    return {
        **base,
        "history_range": {
            "start": str(df["_date"].min().date()),
            "end": str(df["_date"].max().date()),
        },
        "days": days_out,
        "weeks": weeks_out,
        "months_data": months_out,
        "period": period,
    }


def excl_exchanges_history_info(data_root: Path) -> Dict[str, Any]:
    """Summarize accumulated excl-exchanges files across week folders."""
    history = load_full_price_vs_sale_excl_exchanges_history(data_root)
    df = history.get("df")
    raw_root = Path(data_root) / "raw"
    files = []
    for f in sorted(raw_root.glob(f"*/{FILE_TYPE}/*.*"), key=lambda p: p.stat().st_mtime):
        if f.name.startswith("."):
            continue
        files.append(
            {
                "name": f.name,
                "week": f.parent.parent.name,
                "uploaded_at": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            }
        )
    rng = None
    if df is not None and not df.empty:
        rng = {"start": str(df["_date"].min().date()), "end": str(df["_date"].max().date())}
    return {
        "files": files,
        "count": len(files),
        "matched_files": history.get("files_used", []),
        "range": rng,
        "currency": history.get("currency", "SEK"),
        "fx": history.get("fx"),
    }
