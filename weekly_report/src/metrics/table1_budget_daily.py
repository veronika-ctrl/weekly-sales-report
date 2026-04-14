"""
Table 1 budget for calendar periods: spread monthly budget uniformly per day,
then sum over [start, end] so Week / MTD / YTD match the same date ranges as actuals.

Optional: long-format CSV with Date + Metric + Value rows (daily budget) to sum
exact daily amounts instead of uniform monthly spread.
"""

from __future__ import annotations

import calendar
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Callable, Dict, Optional, Tuple

import pandas as pd
from loguru import logger

from weekly_report.src.compute.budget import _parse_number
from weekly_report.src.periods.calculator import get_mtd_periods_for_week, get_week_date_range, get_ytd_periods_for_week

_MONTH_ACC_KEYS = (
    "online_gross_revenue",
    "returns",
    "online_net_revenue",
    "marketing_spend",
    "returning_customers",
    "new_customers",
    "new_net_revenue_new_seg",
)


def _norm_metric(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def _derive_emer_from_budget_components(
    emer_explicit: float,
    new_net_new_customers: float,
    marketing_spend: float,
) -> float:
    try:
        e = float(emer_explicit or 0)
    except (TypeError, ValueError):
        e = 0.0
    if abs(e) >= 1e-9:
        return e
    try:
        mkt = float(marketing_spend or 0)
        nn = float(new_net_new_customers or 0)
    except (TypeError, ValueError):
        return 0.0
    if abs(mkt) > 1e-9 and abs(nn) > 1e-9:
        return abs(nn) / abs(mkt)
    return e


def _finalize_table1_from_acc(acc: Dict[str, float]) -> Dict[str, Any]:
    gross = float(acc.get("online_gross_revenue", 0) or 0)
    ret = float(acc.get("returns", 0) or 0)
    mkt = float(acc.get("marketing_spend", 0) or 0)
    nn = float(acc.get("new_net_revenue_new_seg", 0) or 0)
    onet = float(acc.get("online_net_revenue", 0) or 0)
    rc = float(acc.get("returning_customers", 0) or 0)
    nc = float(acc.get("new_customers", 0) or 0)
    rr = (ret / gross * 100.0) if abs(gross) > 1e-12 else 0.0
    cos = (mkt / gross * 100.0) if abs(gross) > 1e-12 else 0.0
    emer = _derive_emer_from_budget_components(0.0, nn, mkt)
    return {
        "online_gross_revenue": gross,
        "returns": ret,
        "return_rate_pct": round(rr, 1),
        "online_net_revenue": onet,
        "retail_concept_store": 0.0,
        "retail_popups_outlets": 0.0,
        "retail_net_revenue": 0.0,
        "wholesale_net_revenue": 0.0,
        "total_net_revenue": onet,
        "returning_customers": int(round(rc)),
        "new_customers": int(round(nc)),
        "marketing_spend": mkt,
        "online_cost_of_sale_3": round(cos, 1),
        "emer": round(emer, 1),
        "new_net_revenue_new_seg": nn,
    }


def sum_table1_budget_uniform_daily(
    get_month_budget: Callable[[int, int], Dict[str, Any]],
    start_d: date,
    end_d: date,
) -> Dict[str, Any]:
    """
    Spread each calendar month's budget uniformly across its days,
    then sum additive components for [start_d, end_d] inclusive.
    """
    if start_d > end_d:
        return {}
    acc = {k: 0.0 for k in _MONTH_ACC_KEYS}
    d = start_d
    while d <= end_d:
        dim = calendar.monthrange(d.year, d.month)[1]
        mb = get_month_budget(d.year, d.month) or {}
        frac = 1.0 / float(dim) if dim else 0.0
        for k in _MONTH_ACC_KEYS:
            try:
                v = float(mb.get(k, 0) or 0)
            except (TypeError, ValueError):
                v = 0.0
            acc[k] += v * frac
        d += timedelta(days=1)
    return _finalize_table1_from_acc(acc)


def _add_long_metric_row_to_acc(label: str, v: float, acc: Dict[str, float]) -> None:
    """Map one budget metric label (long-format style) to additive accumulators only."""
    if pd.isna(v) or v == float("inf") or v == float("-inf"):
        return
    metric_norm = _norm_metric(label)
    if metric_norm in ("totalgrossrevenue", "onlinegrossrevenue"):
        acc["online_gross_revenue"] = acc.get("online_gross_revenue", 0.0) + float(v)
    elif metric_norm == "returns":
        acc["returns"] = acc.get("returns", 0.0) + float(v)
    elif metric_norm == "newnetrevenue":
        acc["new_net_revenue_new_seg"] = acc.get("new_net_revenue_new_seg", 0.0) + float(v)
    elif metric_norm in ("netrevenue", "onlinenetrevenue"):
        acc["online_net_revenue"] = acc.get("online_net_revenue", 0.0) + float(v)
    elif metric_norm == "returningcustomers":
        acc["returning_customers"] = acc.get("returning_customers", 0.0) + float(v)
    elif metric_norm == "newcustomers":
        acc["new_customers"] = acc.get("new_customers", 0.0) + float(v)
    elif metric_norm in ("onlinemarketingspend", "marketingspend"):
        acc["marketing_spend"] = acc.get("marketing_spend", 0.0) + float(v)


def _parse_row_date(val: Any) -> Optional[date]:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    s = str(val).strip()
    if not s:
        return None
    ts = pd.to_datetime(s, errors="coerce")
    if pd.notna(ts):
        return pd.Timestamp(ts).date()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            part = s[:10] if len(s) >= 10 else s
            return datetime.strptime(part, fmt).date()
        except ValueError:
            continue
    return None


def try_sum_explicit_daily_budget(
    df: pd.DataFrame,
    start_d: date,
    end_d: date,
) -> Optional[Dict[str, Any]]:
    """
    If CSV has Date + Metric + Value (long-format), aggregate additive metrics per day
    then sum over [start_d, end_d]. Rows with ratio-only metrics (return rate, COS %)
    without volume are ignored when building totals; ratios are derived from summed gross/returns/mkt/nn.
    """
    if df is None or df.empty or start_d > end_d:
        return None
    cmap = {str(c).strip().lower(): c for c in df.columns}
    date_col = None
    for cand in ("date", "day", "dag"):
        if cand in cmap:
            date_col = cmap[cand]
            break
    if date_col is None or "metric" not in cmap or "value" not in cmap:
        return None
    metric_col = cmap["metric"]
    value_col = cmap["value"]
    by_day: Dict[date, Dict[str, float]] = defaultdict(lambda: {k: 0.0 for k in _MONTH_ACC_KEYS})

    for _, row in df.iterrows():
        d = _parse_row_date(row.get(date_col))
        if d is None:
            continue
        label = row.get(metric_col)
        if label is None or (isinstance(label, float) and pd.isna(label)):
            continue
        label_s = str(label).strip()
        if not label_s:
            continue
        v = _parse_number(row.get(value_col))
        if pd.isna(v):
            continue
        acc = by_day[d]
        _add_long_metric_row_to_acc(label_s, float(v), acc)

    expected_days = (end_d - start_d).days + 1
    d = start_d
    while d <= end_d:
        da = by_day.get(d)
        if not da or not any(abs(float(da.get(k, 0) or 0)) > 1e-9 for k in _MONTH_ACC_KEYS):
            return None
        d += timedelta(days=1)

    acc_total = {k: 0.0 for k in _MONTH_ACC_KEYS}
    d = start_d
    while d <= end_d:
        day_acc = by_day.get(d)
        if day_acc:
            for k in _MONTH_ACC_KEYS:
                acc_total[k] += float(day_acc.get(k, 0) or 0)
        d += timedelta(days=1)

    if not any(abs(acc_total[k]) > 1e-9 for k in _MONTH_ACC_KEYS):
        return None
    ndays = (end_d - start_d).days + 1
    logger.info(f"Explicit daily budget: summed additive metrics over {ndays} days ({start_d}..{end_d})")
    return _finalize_table1_from_acc(acc_total)


def _month_has_signal(b: Dict[str, Any]) -> bool:
    for k in ("online_gross_revenue", "online_net_revenue", "marketing_spend"):
        try:
            if abs(float(b.get(k, 0) or 0)) > 1e-9:
                return True
        except (TypeError, ValueError):
            continue
    return False


def table1_budget_has_volume(d: Optional[Dict[str, Any]]) -> bool:
    """True if budget dict has meaningful volume (for API attachment)."""
    if not d:
        return False
    return _month_has_signal(d)


def _build_combined_month_getter(
    budget_table1_from_df: Callable[[Any, int, int], Dict[str, Any]],
    df: Optional[pd.DataFrame],
    budget_table1_from_general: Optional[Callable[[int, int], Dict[str, Any]]],
) -> Callable[[int, int], Dict[str, Any]]:
    """Prefer CSV month slice when it has volume; else budget-general."""

    def getter(y: int, m: int) -> Dict[str, Any]:
        b: Dict[str, Any] = {}
        if df is not None and not df.empty:
            b = budget_table1_from_df(df, y, m) or {}
        if not _month_has_signal(b) and budget_table1_from_general is not None:
            b = budget_table1_from_general(y, m) or {}
        return b

    return getter


def table1_budget_for_periods(
    base_week: str,
    budget_table1_from_df: Callable[[Any, int, int], Dict[str, Any]],
    df: Optional[pd.DataFrame],
    budget_table1_from_general: Optional[Callable[[int, int], Dict[str, Any]]],
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """
    Week / MTD / YTD budget dicts aligned to Table 1 actual date ranges:
    - Week: ISO Mon–Sun for base_week
    - MTD: calendar month start → base week end (same as mtd_actual)
    - YTD: fiscal YTD start → base week end (same as ytd_actual)
    """
    wr = get_week_date_range(base_week)
    ws = datetime.strptime(wr["start"], "%Y-%m-%d").date()
    we = datetime.strptime(wr["end"], "%Y-%m-%d").date()
    mtd_p = get_mtd_periods_for_week(base_week)["mtd_actual"]
    ms = datetime.strptime(mtd_p["start"], "%Y-%m-%d").date()
    me = datetime.strptime(mtd_p["end"], "%Y-%m-%d").date()
    ytd_p = get_ytd_periods_for_week(base_week)["ytd_actual"]
    ys = datetime.strptime(ytd_p["start"], "%Y-%m-%d").date()
    ye = datetime.strptime(ytd_p["end"], "%Y-%m-%d").date()

    getter = _build_combined_month_getter(budget_table1_from_df, df, budget_table1_from_general)

    def build_for_range(start: date, end: date) -> Dict[str, Any]:
        if df is not None and not df.empty:
            explicit = try_sum_explicit_daily_budget(df, start, end)
            if explicit and _month_has_signal(explicit):
                return explicit
        return sum_table1_budget_uniform_daily(getter, start, end)

    week_b = build_for_range(ws, we)
    mtd_b = build_for_range(ms, me)
    ytd_b = build_for_range(ys, ye)
    return week_b, mtd_b, ytd_b
