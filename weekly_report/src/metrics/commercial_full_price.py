"""Full price share vs discount: exchanges out, every discount code stays discounted.

AfterShip exchanges are already absent from the exchange-excluded daily export.
Team, investor, PR & friends orders stay in discounted, and their discount
amount stays in the weighted discount. Klaviyo, Customer Care, and that internal
group are also listed on their own.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from weekly_report.src.metrics.discount_types import (
    _canonical_group_id,
    _prepare_money,
    load_discount_type_tables,
)
from weekly_report.src.metrics.discounts_sales import _build_display_weeks, _iso_week_series
from weekly_report.src.metrics.pricing_history import load_pricing_type_daily_history
from weekly_report.src.periods.calculator import get_week_date_range

NOTE = (
    "Exchanges are excluded. All discount codes, including internal team, investor, PR & friends "
    "discounts, are counted as discounted."
)

INVESTOR_GROUP_ID = "investors"
KLAVIYO_GROUP_ID = "klaviyo"
CUSTOMER_CARE_GROUP_ID = "customer_care"
TRIGGER_GROUP_COLUMNS = (
    (KLAVIYO_GROUP_ID, "klaviyo_discount"),
    (CUSTOMER_CARE_GROUP_ID, "customer_care_discount"),
    (INVESTOR_GROUP_ID, "internal_discount"),
)
TRIGGER_DISCOUNT_COLUMNS = tuple(column for _gid, column in TRIGGER_GROUP_COLUMNS)


def _prepared_discount_daily(data_root: Path) -> Dict[str, Any]:
    """Load the discount-type daily file once and convert money columns once."""
    tables = load_discount_type_tables(data_root)
    daily, fx = _prepare_money(
        tables["daily"],
        "date",
        ["discount_amount_usd", "gross_sales_usd"],
        Path(data_root),
    )
    return {
        "daily": daily,
        "files_used": tables.get("files_used") or [],
        "fx": fx,
    }


def trigger_discounts_from_daily(daily: pd.DataFrame) -> pd.DataFrame:
    """Sum Klaviyo, Customer Care, and internal discount amounts by day.

    Amounts are the discount-type export's discount, not net sales. They are
    not removed from discounted sales.
    """
    empty = pd.DataFrame(columns=["_date", *TRIGGER_DISCOUNT_COLUMNS])
    if daily is None or daily.empty or "_date" not in daily.columns or "group" not in daily.columns:
        return empty
    if "_discount_amount_usd" not in daily.columns:
        return empty
    work = daily.copy()
    work["_gid"] = work["group"].map(_canonical_group_id)
    wanted = {gid for gid, _column in TRIGGER_GROUP_COLUMNS}
    work = work.loc[work["_gid"].isin(wanted)]
    if work.empty:
        return empty
    for gid, column in TRIGGER_GROUP_COLUMNS:
        work[column] = work["_discount_amount_usd"].where(work["_gid"].eq(gid), 0.0)
    grouped = work.groupby("_date", as_index=False)[list(TRIGGER_DISCOUNT_COLUMNS)].sum()
    for col in TRIGGER_DISCOUNT_COLUMNS:
        grouped[col] = pd.to_numeric(grouped[col], errors="coerce").fillna(0.0).clip(lower=0.0)
    grouped["_date"] = pd.to_datetime(grouped["_date"], errors="coerce").dt.normalize()
    return grouped.dropna(subset=["_date"])[["_date", *TRIGGER_DISCOUNT_COLUMNS]]


def attach_trigger_discounts(adjusted: pd.DataFrame, triggers: pd.DataFrame) -> pd.DataFrame:
    """Left-join Klaviyo, Customer Care, and internal discount amounts onto pricing days.

    Both sides are collapsed to one row per date first, so a day that appears
    twice cannot double-count the discount.
    """
    if adjusted is None or adjusted.empty:
        return pd.DataFrame() if adjusted is None else adjusted.copy()
    out = adjusted.copy()
    out["_date"] = pd.to_datetime(out["_date"], errors="coerce").dt.normalize()
    out = out.dropna(subset=["_date"])
    value_cols = [col for col in out.columns if col != "_date"]
    for col in value_cols:
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0)
    if value_cols:
        out = out.groupby("_date", as_index=False)[value_cols].sum()
    else:
        out = out.drop_duplicates(subset=["_date"])

    if triggers is None or triggers.empty:
        for col in TRIGGER_DISCOUNT_COLUMNS:
            out[col] = 0.0
        return out

    trig = triggers.copy()
    trig["_date"] = pd.to_datetime(trig["_date"], errors="coerce").dt.normalize()
    for col in TRIGGER_DISCOUNT_COLUMNS:
        if col not in trig.columns:
            trig[col] = 0.0
        trig[col] = pd.to_numeric(trig[col], errors="coerce").fillna(0.0)
    trig = trig.dropna(subset=["_date"])
    trig = trig.groupby("_date", as_index=False)[list(TRIGGER_DISCOUNT_COLUMNS)].sum()
    out = out.drop(columns=[col for col in TRIGGER_DISCOUNT_COLUMNS if col in out.columns])
    out = out.merge(trig, on="_date", how="left")
    for col in TRIGGER_DISCOUNT_COLUMNS:
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0)
    return out


def _sum_optional(sub: pd.DataFrame, column: str) -> float:
    if sub is None or sub.empty or column not in sub.columns:
        return 0.0
    return float(pd.to_numeric(sub[column], errors="coerce").fillna(0.0).sum() or 0.0)


def _metrics(sub: pd.DataFrame) -> Dict[str, Any]:
    if sub is None or sub.empty:
        full = disc = total = 0.0
        damt: Optional[float] = None
    else:
        full = float(sub["_full"].sum() or 0.0)
        disc = float(sub["_discounted"].sum() or 0.0)
        total = float(sub["_total"].sum() or 0.0)
        damt_series = pd.to_numeric(sub["_discount"], errors="coerce")
        damt = float(damt_series.sum()) if damt_series.notna().any() else None
    klaviyo = _sum_optional(sub, "klaviyo_discount")
    customer_care = _sum_optional(sub, "customer_care_discount")
    internal = _sum_optional(sub, "internal_discount")
    pct = (full / total * 100.0) if total > 0 else None
    weighted = None
    if damt is not None and (disc + damt) > 0:
        weighted = damt / (disc + damt) * 100.0
    return {
        "full_price": full,
        "discounted": disc,
        "total": total,
        "full_price_pct": pct,
        "discount_amount": damt,
        "weighted_discount_pct": weighted,
        "klaviyo_discount": klaviyo,
        "customer_care_discount": customer_care,
        "internal_discount": internal,
    }


def _yoy(cur: Dict[str, Any], prev: Dict[str, Any]) -> Dict[str, Any]:
    yoy_total = (cur["total"] - prev["total"]) / prev["total"] * 100.0 if prev["total"] > 0 else None
    fp_delta = (
        cur["full_price_pct"] - prev["full_price_pct"]
        if cur["full_price_pct"] is not None and prev["full_price_pct"] is not None
        else None
    )
    yoy_full = (
        (cur["full_price"] - prev["full_price"]) / prev["full_price"] * 100.0
        if prev["full_price"] > 0
        else None
    )
    return {
        "yoy_total_pct": yoy_total,
        "yoy_full_price_pct": yoy_full,
        "full_price_pct_delta": fp_delta,
    }


def _window(df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    if df.empty:
        return df
    mask = (df["_date"] >= start) & (df["_date"] <= end)
    return df.loc[mask]


def build_commercial_periods(
    adjusted: pd.DataFrame,
    base_week: str,
    *,
    granularity: str = "week",
    num_weeks: int = 8,
    months: int = 13,
) -> List[Dict[str, Any]]:
    """Oldest → newest periods. Latest month is month-to-date through the week end."""
    df = adjusted.copy() if adjusted is not None else pd.DataFrame()
    if not df.empty:
        df["_date"] = pd.to_datetime(df["_date"], errors="coerce").dt.normalize()
        df = df.dropna(subset=["_date"])
        df["_week"] = _iso_week_series(df["_date"])

    week_end = pd.to_datetime(get_week_date_range(base_week)["end"], errors="coerce")
    if pd.isna(week_end):
        raise ValueError(f"Invalid base week: {base_week}")
    week_end = pd.Timestamp(week_end).normalize()

    periods: List[Dict[str, Any]] = []
    if granularity == "month":
        end_period = week_end.to_period("M")
        count = max(1, int(months or 13))
        month_keys = list(reversed([(end_period - i) for i in range(count)]))
        for mp in month_keys:
            is_latest = mp == end_period
            start = mp.start_time.normalize()
            end = week_end if is_latest else mp.end_time.normalize()
            ly_p = mp - 12
            ly_end = (week_end - pd.DateOffset(years=1)).normalize() if is_latest else ly_p.end_time.normalize()
            cur = _metrics(_window(df, start, end))
            ly = _metrics(_window(df, ly_p.start_time.normalize(), ly_end))
            periods.append(
                {
                    "key": mp.strftime("%Y-%m"),
                    "month": mp.strftime("%Y-%m"),
                    "start": str(start.date()),
                    "end": str(pd.Timestamp(end).date()),
                    **cur,
                    "last_year": {"month": ly_p.strftime("%Y-%m"), **ly},
                    **_yoy(cur, ly),
                }
            )
        return periods

    expected = _build_display_weeks(base_week, num_weeks)
    for w in expected:
        rng = get_week_date_range(w)
        start = pd.Timestamp(rng["start"]).normalize()
        end = pd.Timestamp(rng["end"]).normalize()
        y_str, ww = w.split("-")
        ly_w = f"{int(y_str) - 1}-{ww}"
        ly_rng = get_week_date_range(ly_w)
        cur = _metrics(df.loc[df["_week"].eq(w)] if not df.empty and "_week" in df.columns else df.iloc[0:0])
        ly = _metrics(
            df.loc[df["_week"].eq(ly_w)] if not df.empty and "_week" in df.columns else df.iloc[0:0]
        )
        periods.append(
            {
                "key": w,
                "week": w,
                "start": str(start.date()),
                "end": str(end.date()),
                **cur,
                "last_year": {"week": ly_w, "start": ly_rng["start"], "end": ly_rng["end"], **ly},
                **_yoy(cur, ly),
            }
        )
    return periods


def calculate_commercial_full_price(
    base_week: str,
    data_root: Path,
    *,
    granularity: str = "week",
    num_weeks: int = 8,
    months: int = 13,
) -> Dict[str, Any]:
    if granularity not in ("week", "month"):
        raise ValueError("granularity must be 'week' or 'month'")
    history = load_pricing_type_daily_history(Path(data_root))
    prepared = _prepared_discount_daily(Path(data_root))
    triggers = trigger_discounts_from_daily(prepared["daily"])
    pricing = history.get("df")
    if pricing is None:
        pricing = pd.DataFrame()
    adjusted = attach_trigger_discounts(pricing, triggers)
    periods = build_commercial_periods(
        adjusted,
        base_week,
        granularity=granularity,
        num_weeks=num_weeks,
        months=months,
    )
    has_last_year = any((p.get("last_year") or {}).get("total", 0) > 0 for p in periods)
    files = list(history.get("files_used") or []) + list(prepared.get("files_used") or [])
    hist = None
    if not adjusted.empty:
        hist = {
            "start": str(adjusted["_date"].min().date()),
            "end": str(adjusted["_date"].max().date()),
        }
    discount_range = None
    daily = prepared.get("daily")
    if daily is not None and not daily.empty and "_date" in daily.columns:
        dates = pd.to_datetime(daily["_date"], errors="coerce").dropna()
        if not dates.empty:
            discount_range = {"start": str(dates.min().date()), "end": str(dates.max().date())}
    fx = history.get("fx") or prepared.get("fx") or {"applied": False}
    currency = history.get("currency") or ("SEK" if fx.get("applied") else "USD")
    return {
        "base_week": base_week,
        "granularity": granularity,
        "num_weeks": num_weeks,
        "months": months,
        "note": NOTE,
        "source": "commercial_full_price",
        "currency": currency,
        "fx": fx,
        "has_last_year": has_last_year,
        "has_discount": bool(history.get("has_discount")),
        "files_used": files,
        "history_range": hist,
        "discount_range": discount_range,
        "discount_files": list(prepared.get("files_used") or []),
        "periods": periods,
    }
