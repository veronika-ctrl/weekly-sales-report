"""Commercial full price share: exchanges out, team/investor discounts treated as full price.

The existing Full Price vs Sale slides stay as the financial view. This series
is the presentation view: start from the exchange-excluded daily export, then
move Investors, team, PR & friends net sales out of discounted and into full
price. Klaviyo, Customer Care, and other customer codes stay in the discount.
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
    "Exchanges are excluded. Investors, team, PR & friends discounts are counted as full price, "
    "so the remaining discount is commercial — mainly Klaviyo and Customer Care, plus other customer codes. "
    "The existing Full Price vs Sale slides are unchanged."
)

INVESTOR_GROUP_ID = "investors"


def investor_adjustments_from_daily(daily: pd.DataFrame) -> pd.DataFrame:
    """Sum investor/team net and discount amount by day.

    ``daily`` is the prepared discount-types frame (``_date``, ``group``,
    ``_gross_sales_usd``, ``_discount_amount_usd``). Net = gross − discount,
    floored at 0. Other groups are ignored.
    """
    empty = pd.DataFrame(columns=["_date", "investor_net", "investor_discount"])
    if daily is None or daily.empty or "_date" not in daily.columns or "group" not in daily.columns:
        return empty
    work = daily.copy()
    work["_gid"] = work["group"].map(_canonical_group_id)
    inv = work.loc[work["_gid"].eq(INVESTOR_GROUP_ID)]
    if inv.empty:
        return empty
    gross_col = "_gross_sales_usd" if "_gross_sales_usd" in inv.columns else None
    disc_col = "_discount_amount_usd" if "_discount_amount_usd" in inv.columns else None
    if gross_col is None or disc_col is None:
        return empty
    grouped = (
        inv.groupby("_date", as_index=False)[[gross_col, disc_col]]
        .sum()
        .rename(columns={gross_col: "gross", disc_col: "investor_discount"})
    )
    grouped["investor_net"] = (grouped["gross"] - grouped["investor_discount"]).clip(lower=0.0)
    grouped["investor_discount"] = grouped["investor_discount"].clip(lower=0.0)
    return grouped[["_date", "investor_net", "investor_discount"]]


def load_investor_daily_adjustments(data_root: Path) -> Dict[str, Any]:
    tables = load_discount_type_tables(data_root)
    daily, fx = _prepare_money(
        tables["daily"],
        "date",
        ["discount_amount_usd", "gross_sales_usd"],
        Path(data_root),
    )
    return {
        "df": investor_adjustments_from_daily(daily),
        "files_used": tables.get("files_used") or [],
        "fx": fx,
    }


def apply_investor_adjustment(pricing: pd.DataFrame, investor: pd.DataFrame) -> pd.DataFrame:
    """Move investor net from discounted into full price. Total is unchanged.

    The move is capped at that day's discounted net, and the discount amount
    removed is capped at that day's discount amount, so neither goes negative.
    """
    if pricing is None or pricing.empty:
        return pd.DataFrame()
    out = pricing.copy()
    out["_date"] = pd.to_datetime(out["_date"], errors="coerce").dt.normalize()
    out = out.dropna(subset=["_date"])
    for col in ("_full", "_discounted", "_total", "_discount"):
        if col not in out.columns:
            out[col] = 0.0
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0)

    if investor is None or investor.empty:
        out["investor_net"] = 0.0
        out["investor_discount"] = 0.0
    else:
        adj = investor.copy()
        adj["_date"] = pd.to_datetime(adj["_date"], errors="coerce").dt.normalize()
        adj = adj.dropna(subset=["_date"])
        adj = adj.groupby("_date", as_index=False)[["investor_net", "investor_discount"]].sum()
        out = out.merge(adj, on="_date", how="left")
        out["investor_net"] = pd.to_numeric(out["investor_net"], errors="coerce").fillna(0.0)
        out["investor_discount"] = pd.to_numeric(out["investor_discount"], errors="coerce").fillna(0.0)

    move = out[["investor_net", "_discounted"]].min(axis=1).clip(lower=0.0)
    removed = out[["investor_discount", "_discount"]].min(axis=1).clip(lower=0.0)
    out["_full"] = out["_full"] + move
    out["_discounted"] = out["_discounted"] - move
    out["_discount"] = out["_discount"] - removed
    out["_investor_net_moved"] = move
    out["_investor_discount_removed"] = removed
    return out


def _metrics(sub: pd.DataFrame) -> Dict[str, Any]:
    if sub is None or sub.empty:
        full = disc = total = moved = removed = 0.0
        damt: Optional[float] = None
    else:
        full = float(sub["_full"].sum() or 0.0)
        disc = float(sub["_discounted"].sum() or 0.0)
        total = float(sub["_total"].sum() or 0.0)
        damt_series = pd.to_numeric(sub["_discount"], errors="coerce")
        damt = float(damt_series.sum()) if damt_series.notna().any() else None
        moved = float(sub["_investor_net_moved"].sum() or 0.0) if "_investor_net_moved" in sub.columns else 0.0
        removed = (
            float(sub["_investor_discount_removed"].sum() or 0.0)
            if "_investor_discount_removed" in sub.columns
            else 0.0
        )
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
        "investor_net_moved": moved,
        "investor_discount_removed": removed,
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
    investor = load_investor_daily_adjustments(Path(data_root))
    pricing = history.get("df")
    if pricing is None:
        pricing = pd.DataFrame()
    adjusted = apply_investor_adjustment(pricing, investor.get("df"))
    periods = build_commercial_periods(
        adjusted,
        base_week,
        granularity=granularity,
        num_weeks=num_weeks,
        months=months,
    )
    has_last_year = any((p.get("last_year") or {}).get("total", 0) > 0 for p in periods)
    moved = float(sum(p.get("investor_net_moved") or 0.0 for p in periods))
    removed = float(sum(p.get("investor_discount_removed") or 0.0 for p in periods))
    files = list(history.get("files_used") or []) + list(investor.get("files_used") or [])
    hist = None
    if not adjusted.empty:
        hist = {
            "start": str(adjusted["_date"].min().date()),
            "end": str(adjusted["_date"].max().date()),
        }
    fx = history.get("fx") or investor.get("fx") or {"applied": False}
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
        "investor_net_moved": moved,
        "investor_discount_removed": removed,
        "periods": periods,
    }
