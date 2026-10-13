"""Full Price vs Sale excluding AfterShip exchanges — daily Shopify export.

History comes from month-named files in ``pricing_type/`` and
``data/raw/{week}/full_price_vs_sale_excl_exchanges/``. Old weekly names and
``*/discounts/*`` are ignored (not mixed with the new calc).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from weekly_report.src.metrics.discounts_sales import (
    _build_display_weeks,
    _iso_week_series,
)
from weekly_report.src.metrics.pricing_history import (
    EXCL_OPTIONAL_HEADERS,
    EXCL_REQUIRED_HEADERS,
    FILE_TYPE,
    _METRIC_SUM_COLS,
    discover_pricing_files,
    inspect_excl_exchanges_upload,
    is_legacy_weekly_filename,
    load_pricing_type_daily_history,
    missing_excl_exchanges_headers,
)
from weekly_report.src.periods.calculator import get_week_date_range

# Re-export for upload routes and existing tests.
__all__ = [
    "EXCL_OPTIONAL_HEADERS",
    "EXCL_REQUIRED_HEADERS",
    "FILE_TYPE",
    "calculate_full_price_vs_sale_excl_exchanges",
    "compare_incl_excl",
    "excl_exchanges_history_info",
    "inspect_excl_exchanges_upload",
    "is_legacy_weekly_filename",
    "load_full_price_vs_sale_excl_exchanges_history",
    "missing_excl_exchanges_headers",
]


def load_full_price_vs_sale_excl_exchanges_history(data_root: Path) -> Dict[str, Any]:
    """Month-named excl-exchanges daily history (own-month dates win)."""
    return load_pricing_type_daily_history(data_root)


def _share(num: float, den: Optional[float]) -> Optional[float]:
    if den is None or den <= 0:
        return None
    return float(num) / float(den) * 100.0


def _complement_share(share: Optional[float]) -> Optional[float]:
    if share is None:
        return None
    return 100.0 - float(share)


def _discount_rate(discount: Optional[float], total: Optional[float]) -> Optional[float]:
    """Discount amount as a share of estimated gross (net + discount)."""
    if discount is None or total is None:
        return None
    return _share(float(discount), float(discount) + float(total))


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
    excl_discounted: Optional[float] = None,
    incl_discounted: Optional[float] = None,
) -> Dict[str, Any]:
    """Comparison metrics between all-orders and exchange-excluded figures.

    All-orders discount is reconstructed from the same excl. file as
    Discount Amount + Exchange Discount (no separate ``*/discounts/*`` history).

    100% sales mix (share of sales, not share of discount)::

        denom = excl_total + exchange_gross
        full  = excl_full / denom
        exch  = exchange_gross / denom
        promo = (excl_total - excl_full) / denom

    Tables use the explicit discounted sum of sale-type columns when provided.
    """
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

    sales_mix_denom = float(excl_total) + float(exchange_gross)
    sales_mix_full_price_pct = _share(excl_full, sales_mix_denom)
    sales_mix_exchange_pct = _share(exchange_gross, sales_mix_denom)
    # Mix identity uses Total − Full so the three slices sum to 100%.
    sales_mix_promo_pct = _share(float(excl_total) - float(excl_full), sales_mix_denom)

    if incl_discount is not None and incl_discount > 0:
        disc_den: Optional[float] = float(incl_discount)
    else:
        disc_den = excl_discount + exchange_discount
    exchange_discount_share_pct = _share(exchange_discount, disc_den)
    promotional_discount_share_pct = (
        100.0 - exchange_discount_share_pct if exchange_discount_share_pct is not None else None
    )

    excl_discounted_share = _complement_share(excl_share)
    incl_discounted_share = _complement_share(incl_share)
    discounted_pp_diff = (
        excl_discounted_share - incl_discounted_share
        if excl_discounted_share is not None and incl_discounted_share is not None
        else None
    )

    excl_discount_rate = _discount_rate(excl_discount, excl_total)
    incl_discount_rate = _discount_rate(incl_discount, incl_total)
    discount_rate_pp_diff = (
        excl_discount_rate - incl_discount_rate
        if excl_discount_rate is not None and incl_discount_rate is not None
        else None
    )

    full_incl = None if incl_full is None else float(incl_full)
    full_excl = float(excl_full)
    if incl_discounted is not None:
        discounted_incl: Optional[float] = float(incl_discounted)
    elif full_incl is not None and incl_total is not None:
        discounted_incl = float(incl_total) - full_incl
    else:
        discounted_incl = None
    if excl_discounted is not None:
        discounted_excl = float(excl_discounted)
    else:
        discounted_excl = float(excl_total) - full_excl

    return {
        "full_price_share_incl_pct": incl_share,
        "full_price_share_excl_pct": excl_share,
        "full_price_share_pp_diff": pp_diff,
        "discounted_share_incl_pct": incl_discounted_share,
        "discounted_share_excl_pct": excl_discounted_share,
        "discounted_share_pp_diff": discounted_pp_diff,
        "discount_rate_incl_pct": incl_discount_rate,
        "discount_rate_excl_pct": excl_discount_rate,
        "discount_rate_pp_diff": discount_rate_pp_diff,
        "full_incl": full_incl,
        "full_excl": full_excl,
        "discounted_incl": discounted_incl,
        "discounted_excl": discounted_excl,
        "total_incl": None if incl_total is None else float(incl_total),
        "total_excl": float(excl_total),
        "discount_incl": None if incl_discount is None else float(incl_discount),
        "discount_excl": float(excl_discount),
        "exchange_gross_share_pct": exchange_gross_share_pct,
        "exchange_discount_share_pct": exchange_discount_share_pct,
        "promotional_discount_share_pct": promotional_discount_share_pct,
        "non_exchange_gross_est": float(non_exchange_gross_est),
        "gross_context": float(gross_context),
        "sales_mix_denom": float(sales_mix_denom),
        "sales_mix_full_price_pct": sales_mix_full_price_pct,
        "sales_mix_exchange_pct": sales_mix_exchange_pct,
        "sales_mix_promo_pct": sales_mix_promo_pct,
    }


def _metrics_from_sum(sums: Dict[str, float], share_fallback: Optional[float] = None) -> Dict[str, Any]:
    full = float(sums.get("_full", 0.0) or 0.0)
    total = float(sums.get("_total", 0.0) or 0.0)
    compare_at = float(sums.get("_compare_at", 0.0) or 0.0)
    discount_code = float(sums.get("_discount_code", 0.0) or 0.0)
    subscription = float(sums.get("_subscription", 0.0) or 0.0)
    both = float(sums.get("_both", 0.0) or 0.0)
    price_drop = float(sums.get("_price_drop", 0.0) or 0.0)
    discounted = float(
        sums.get("_discounted", compare_at + discount_code + subscription + both + price_drop) or 0.0
    )
    discount_amount = float(sums.get("_discount_amount", 0.0) or 0.0)
    markdown = float(sums.get("_markdown", 0.0) or 0.0)
    promo_discount = float(sums.get("_discount", discount_amount + markdown) or 0.0)
    exchange_discount = float(sums.get("_exchange_discount", 0.0) or 0.0)
    all_orders_discount = float(
        sums.get("_all_orders_discount", discount_amount + exchange_discount) or 0.0
    )
    return {
        "full_price": full,
        "compare_at_price_sale": compare_at,
        "discount_code_auto": discount_code,
        "subscription_discount": subscription,
        "both": both,
        "price_drop_sale": price_drop,
        "discounted": discounted,
        "total": total,
        "discount_amount": promo_discount,
        "markdown_amount": markdown,
        "all_orders_discount": all_orders_discount,
        "full_price_share_pct": _full_price_share(full, total, share_fallback),
        "exchange_orders": int(round(float(sums.get("_exchange_orders", 0.0) or 0.0))),
        "exchange_gross_value": float(sums.get("_exchange_gross", 0.0) or 0.0),
        "exchange_discount": exchange_discount,
        "exchange_net_revenue": float(sums.get("_exchange_net", 0.0) or 0.0),
    }


def _row_sums(sub: pd.DataFrame) -> Dict[str, float]:
    if sub.empty:
        return {c: 0.0 for c in _METRIC_SUM_COLS}
    return {c: float(pd.to_numeric(sub[c], errors="coerce").fillna(0.0).sum()) for c in _METRIC_SUM_COLS}


def _attach_comparison(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Incl. vs excl. from the same daily file (no old all-orders discounts slot)."""
    excl_discount = float(metrics["discount_amount"] or 0.0)
    exchange_discount = float(metrics["exchange_discount"] or 0.0)
    all_orders_discount = float(metrics.get("all_orders_discount") or (excl_discount + exchange_discount))
    discounted = float(metrics.get("discounted") or 0.0)
    metrics["comparison"] = compare_incl_excl(
        excl_full=metrics["full_price"],
        excl_total=metrics["total"],
        excl_discount=excl_discount,
        exchange_gross=metrics["exchange_gross_value"],
        exchange_discount=exchange_discount,
        incl_full=metrics["full_price"],
        incl_total=metrics["total"],
        incl_discount=all_orders_discount,
        excl_discounted=discounted,
        incl_discounted=discounted,
    )
    return metrics


def calculate_full_price_vs_sale_excl_exchanges(
    base_week: str,
    data_root: Path,
    num_weeks: int = 8,
    months: int = 13,
    granularity: str = "week",
) -> Dict[str, Any]:
    """Daily + period totals for the exchange-excluded export.

    Comparison vs all-orders uses Discount Amount + Exchange Discount from the
    same file. Old ``*/discounts/*`` history is not read.
    """
    history = load_full_price_vs_sale_excl_exchanges_history(data_root)
    df = history["df"]

    base: Dict[str, Any] = {
        "base_week": base_week,
        "num_weeks": num_weeks,
        "months": months,
        "granularity": granularity,
        "source": FILE_TYPE,
        "files_used": history["files_used"],
        "ignored_files": history.get("ignored_files", []),
        "currency": history.get("currency", "SEK"),
        "fx": history.get("fx"),
        "all_orders_files_used": [],
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
        _attach_comparison(metrics)
        days_out.append({"date": str(day_key.date()), "week": str(row["_week"]), **metrics})

    period_sums = _row_sums(window)
    period_metrics = _metrics_from_sum(period_sums)
    _attach_comparison(period_metrics)
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
            _attach_comparison(metrics)
            weeks_out.append({"week": w, **metrics})

    months_out: List[Dict[str, Any]] = []
    if granularity == "month":
        for mp in month_keys:
            is_latest = mp == end_period
            start = mp.start_time.normalize()
            end = week_end.normalize() if is_latest else mp.end_time.normalize()
            sub = window[(window["_date"] >= start) & (window["_date"] <= end)]
            metrics = _metrics_from_sum(_row_sums(sub))
            _attach_comparison(metrics)
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
    """Summarize accepted month-named files vs ignored legacy weekly names."""
    history = load_full_price_vs_sale_excl_exchanges_history(data_root)
    df = history.get("df")
    accepted, ignored = discover_pricing_files(data_root)
    files = []
    for f in accepted:
        week = f.parent.parent.name if f.parent.name == FILE_TYPE else "pricing_type"
        try:
            uploaded = datetime.fromtimestamp(f.stat().st_mtime).isoformat()
        except OSError:
            uploaded = None
        files.append(
            {
                "name": f.name,
                "week": week,
                "uploaded_at": uploaded,
            }
        )
    rng = None
    if df is not None and not df.empty:
        rng = {"start": str(df["_date"].min().date()), "end": str(df["_date"].max().date())}
    return {
        "files": files,
        "count": len(files),
        "matched_files": history.get("files_used", []),
        "ignored_files": history.get("ignored_files", ignored),
        "range": rng,
        "currency": history.get("currency", "SEK"),
        "fx": history.get("fx"),
        "note": (
            "Old weekly Full Price vs Sale / Exchanges files (W36–W40 names, "
            "Exchanges_Historical_Data, and anything in */discounts/*) are ignored. "
            "Keep the 22 month-named files in 2026-41; those old weekly files can be "
            "deleted on Render after deploy to free disk."
        ),
    }
