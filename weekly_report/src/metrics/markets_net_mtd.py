"""Top markets: online net revenue by Week / Month / YTD with YoY and budget (per-market from budget file when available).

Budgets are built from monthly online net in the file by spreading each calendar month uniformly per day,
then summing over the same date ranges as actuals:
- Week: ISO Mon–Sun (7 days).
- Month: MTD (calendar month start → week end), same as Summary MTD.
- YTD: fiscal YTD (Apr 1 → week end), same as Summary YTD — not the full Apr–Mar year total.
"""

from __future__ import annotations

import calendar as _cal
import unicodedata
from datetime import date, datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

from loguru import logger
from pathlib import Path

from weekly_report.src.compute.budget import _is_row_dimension_budget_label
from weekly_report.src.metrics.markets import calculate_top_markets_for_weeks
from weekly_report.src.metrics.table1 import filter_data_for_date_range, filter_data_for_period, load_all_raw_data
from weekly_report.src.periods.calculator import (
    get_mtd_periods_for_week,
    get_periods_for_week,
    get_week_date_range,
    get_ytd_periods_for_week,
)


def _online_net_by_country(qlik_df: pd.DataFrame) -> Dict[str, float]:
    """Sum Net Revenue for Sales Channel Online, by Country (stripped string keys)."""
    if qlik_df is None or qlik_df.empty:
        return {}
    df = qlik_df.copy()
    df.columns = df.columns.str.strip()
    ch = "Sales Channel"
    net = "Net Revenue"
    co = "Country"
    if ch not in df.columns or net not in df.columns or co not in df.columns:
        logger.warning("markets_net_mtd: missing Sales Channel / Net Revenue / Country on Qlik frame")
        return {}
    df[ch] = df[ch].astype(str).str.strip()
    df[co] = df[co].astype(str).str.strip()
    online = df[df[ch].str.lower().eq("online")]
    if online.empty:
        return {}
    g = online.groupby(co, dropna=False)[net].sum()
    return {str(k): float(v) for k, v in g.items() if k is not None and str(k).strip() != ""}


def _yoy_pct(actual: float, last_year: float) -> Optional[float]:
    if last_year == 0:
        return None
    return (actual - last_year) / last_year * 100.0


def _allocate_budget_by_mix(
    total_budget: Optional[float],
    country_values: Dict[str, float],
    ordered_countries: List[str],
) -> Dict[str, Optional[float]]:
    out: Dict[str, Optional[float]] = {c: None for c in ordered_countries}
    if total_budget is None:
        return out
    tb = float(total_budget)
    if tb == 0.0:
        for c in ordered_countries:
            out[c] = 0.0
        return out
    s = sum(country_values.get(c, 0.0) for c in ordered_countries)
    if s <= 0:
        for c in ordered_countries:
            out[c] = 0.0
        return out
    for c in ordered_countries:
        out[c] = tb * (country_values.get(c, 0.0) / s)
    return out


def _build_period_block(
    actual_by_c: Dict[str, float],
    ly_by_c: Dict[str, float],
    budget_total: Optional[float],
    detail_names: List[str],
) -> Dict[str, Dict[str, Any]]:
    detail_set = set(detail_names)
    total_act = sum(actual_by_c.values())
    total_ly = sum(ly_by_c.values())

    def slice_for(names: List[str], src: Dict[str, float]) -> Dict[str, float]:
        return {n: float(src.get(n, 0.0)) for n in names}

    act_detail = slice_for(detail_names, actual_by_c)
    ly_detail = slice_for(detail_names, ly_by_c)
    row_act = sum(v for k, v in actual_by_c.items() if k not in detail_set)
    row_ly = sum(v for k, v in ly_by_c.items() if k not in detail_set)

    ordered = detail_names + ["ROW", "Total"]
    act_map = {**act_detail, "ROW": row_act, "Total": total_act}
    ly_map = {**ly_detail, "ROW": row_ly, "Total": total_ly}

    bud_map = _allocate_budget_by_mix(budget_total, act_map, detail_names + ["ROW"])
    bud_map["Total"] = float(budget_total) if budget_total is not None else None

    block: Dict[str, Dict[str, Any]] = {}
    for c in ordered:
        act = act_map[c]
        lyv = ly_map[c]
        bud = bud_map.get(c)
        yoy = _yoy_pct(act, lyv)
        vsb = None if bud is None else (act - bud)
        block[c] = {
            "actual": act,
            "last_year": lyv,
            "budget": bud,
            "yoy_pct": yoy,
            "vs_budget": vsb,
        }
    return block


_swedish_m = {
    "januari": 1, "februari": 2, "mars": 3, "april": 4, "maj": 5, "juni": 6,
    "juli": 7, "augusti": 8, "september": 9, "oktober": 10, "november": 11, "december": 12,
}
_english_m = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}


def _month_key_matches(m_key: str, target_year: int, target_month: int) -> bool:
    if not m_key or not str(m_key).strip():
        return False
    s = str(m_key).strip()
    try:
        if len(s) >= 10 and s[4] == "-" and s[7] == "-":
            dt = datetime.strptime(s[:10], "%Y-%m-%d")
            return dt.year == target_year and dt.month == target_month
    except Exception:
        pass
    try:
        xf = float(s.replace(",", ".").replace(" ", ""))
        if 35000 <= xf <= 65000:
            base = datetime(1899, 12, 30)
            dt = base + timedelta(days=int(xf))
            return dt.year == target_year and dt.month == target_month
    except (ValueError, TypeError, OverflowError):
        pass
    for fmt in ("%B %Y", "%b %Y", "%Y-%m", "%b-%y", "%b-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            if fmt == "%Y-%m" and len(s) >= 7:
                dt = datetime.strptime(s[:7], "%Y-%m")
            elif fmt in ("%d/%m/%Y", "%Y/%m/%d") and len(s) >= 10:
                dt = datetime.strptime(s[:10], fmt)
            else:
                dt = datetime.strptime(s, fmt)
            return dt.year == target_year and dt.month == target_month
        except Exception:
            continue
    try:
        anchor = datetime(target_year, target_month, 1)
        if s.lower() == anchor.strftime("%B %Y").lower():
            return True
    except Exception:
        pass
    parts = s.replace(".", " ").lower().split()
    if len(parts) >= 2 and parts[-1].isdigit():
        yr = int(parts[-1])
        mo = _swedish_m.get(parts[0]) or _english_m.get(parts[0])
        if mo is not None and mo == target_month and yr == target_year:
            return True
    return False


def _lookup_month_net(inner: Dict[str, float], target_year: int, target_month: int) -> float:
    for mk, val in inner.items():
        if _month_key_matches(mk, target_year, target_month):
            return float(val)
    return 0.0


def _budget_market_slug(name: str) -> str:
    s = unicodedata.normalize("NFKD", str(name).lower().strip())
    return "".join(c for c in s if c.isalnum())


_BUDGET_MARKET_ALIAS_GROUPS = (
    frozenset({"unitedstates", "usa", "us"}),
    frozenset({"unitedkingdom", "uk", "greatbritain", "britain", "gb"}),
    frozenset({"uae", "unitedarabemirates", "emirates"}),
    frozenset({"sweden", "se", "sverige"}),
    frozenset({"germany", "de", "deutschland"}),
    # Switzerland: not a separate budget line — share ROW bucket (see _ROW_BUCKET_ONLY_COUNTRY_SLUGS).
    frozenset({"australia", "au"}),
    frozenset({"france", "fr"}),
    frozenset({"canada", "ca"}),
    frozenset({"netherlands", "nl", "holland", "thenetherlands"}),
    frozenset({"austria", "at", "osterreich"}),
    frozenset({"spain", "es", "espana"}),
    frozenset({"italy", "it", "italia"}),
)

# Budget CSV has no CH/Switzerland row; always split that country's budget from the file ROW line.
_ROW_BUCKET_ONLY_COUNTRY_SLUGS = frozenset(
    {"switzerland", "ch", "schweiz", "suisse", "svizzera"},
)
_SLUG_TO_GROUP: Dict[str, frozenset] = {}
for _g in _BUDGET_MARKET_ALIAS_GROUPS:
    for _x in _g:
        _SLUG_TO_GROUP[_x] = _g


# Budget CSV uses short codes; Qlik uses full country names. Order = preferred key if several exist in file.
_BUDGET_CSV_KEYS_BY_COUNTRY_SLUG: Dict[str, Tuple[str, ...]] = {
    "unitedstates": ("US", "USA", "United States"),
    "usa": ("US", "USA", "United States"),
    "us": ("US", "USA", "United States"),
    "unitedkingdom": ("UK", "GB", "United Kingdom"),
    "uk": ("UK", "GB", "United Kingdom"),
    "greatbritain": ("UK", "GB", "United Kingdom"),
    "britain": ("UK", "GB", "United Kingdom"),
    "gb": ("UK", "GB", "United Kingdom"),
    "sweden": ("SE", "Sweden"),
    "se": ("SE", "Sweden"),
    "germany": ("DE", "Germany"),
    "de": ("DE", "Germany"),
    "australia": ("AU", "Australia"),
    "au": ("AU", "Australia"),
    "canada": ("CA", "Canada"),
    "ca": ("CA", "Canada"),
    "france": ("FR", "France"),
    "fr": ("FR", "France"),
    "row": ("ROW", "RoW", "Rest of World", "Others", "Other"),
}


def _match_budget_key_candidates(
    by_market: Dict[str, Dict[str, float]], candidates: Tuple[str, ...]
) -> Optional[str]:
    for cand in candidates:
        if cand in by_market:
            return cand
    for cand in candidates:
        cl = cand.strip().lower()
        for k in by_market:
            if k.strip().lower() == cl:
                return k
    return None


def _resolve_budget_market_key(country: str, by_market: Dict[str, Dict[str, float]]) -> Optional[str]:
    if country in by_market:
        return country
    cl = country.strip().lower()
    for k in by_market:
        if k.strip().lower() == cl:
            return k

    cslug = _budget_market_slug(country)
    if cslug in _ROW_BUCKET_ONLY_COUNTRY_SLUGS:
        return None

    csv_keys = _BUDGET_CSV_KEYS_BY_COUNTRY_SLUG.get(cslug)
    if csv_keys:
        hit = _match_budget_key_candidates(by_market, csv_keys)
        if hit is not None:
            return hit

    cgrp = _SLUG_TO_GROUP.get(cslug)
    if cgrp:
        for k in by_market:
            if _budget_market_slug(k) in cgrp:
                return k

    # Avoid matching 2-letter ISO codes as substrings (e.g. "fr" inside "switzerland" → France).
    if len(cslug) >= 5:
        hits: List[str] = []
        for k in by_market:
            sk = _budget_market_slug(k)
            if not sk:
                continue
            if cslug == sk:
                hits.append(k)
            elif len(cslug) >= len(sk) and cslug in sk:
                hits.append(k)
            elif len(sk) >= 4 and sk in cslug:
                hits.append(k)
        if len(hits) == 1:
            return hits[0]
    return None


def _sum_daily_online_net_uniform(
    by_market: Dict[str, Dict[str, float]],
    market_key: str,
    start_d: date,
    end_d: date,
) -> float:
    """Spread each calendar month's online net budget evenly per day, sum over [start_d, end_d] inclusive."""
    if market_key not in by_market or start_d > end_d:
        return 0.0
    acc = 0.0
    d = start_d
    while d <= end_d:
        dim = _cal.monthrange(d.year, d.month)[1]
        mnet = _market_net_for_calendar_month(by_market, market_key, d.year, d.month)
        acc += float(mnet) / float(dim) if dim else 0.0
        d += timedelta(days=1)
    return acc


def _file_budget_sum_all_market_keys(
    base_week: str, bmm: Dict[str, Dict[str, float]], period: str
) -> float:
    """Sum of per-market file budgets for the period (all keys incl. ROW); group rollup from CSV."""
    if not bmm:
        return 0.0
    if period == "week":
        return sum(_budget_week_for_market_key(base_week, k, bmm) for k in bmm)
    if period == "month":
        return sum(_budget_mtd_for_market_key(base_week, k, bmm) for k in bmm)
    return sum(_budget_ytd_for_market_key(base_week, k, bmm) for k in bmm)


def _market_net_for_calendar_month(by_market: Dict[str, Dict[str, float]], market_key: str, y: int, m: int) -> float:
    inner = by_market.get(market_key)
    if not inner:
        return 0.0
    return _lookup_month_net(inner, y, m)


def _budget_week_for_market_key(
    base_week: str, market_key: str, by_market: Dict[str, Dict[str, float]]
) -> float:
    """Online net budget for the ISO week: uniform daily spread, summed over Mon–Sun."""
    if market_key not in by_market:
        return 0.0
    week_range = get_week_date_range(base_week)
    ws = datetime.strptime(week_range["start"], "%Y-%m-%d").date()
    we = datetime.strptime(week_range["end"], "%Y-%m-%d").date()
    return _sum_daily_online_net_uniform(by_market, market_key, ws, we)


def _budget_mtd_for_market_key(
    base_week: str, market_key: str, by_market: Dict[str, Dict[str, float]]
) -> float:
    """Online net budget for MTD actual dates (month start → week end), uniform daily spread."""
    if market_key not in by_market:
        return 0.0
    mtd_p = get_mtd_periods_for_week(base_week)["mtd_actual"]
    ms = datetime.strptime(mtd_p["start"], "%Y-%m-%d").date()
    me = datetime.strptime(mtd_p["end"], "%Y-%m-%d").date()
    return _sum_daily_online_net_uniform(by_market, market_key, ms, me)


def _budget_ytd_for_market_key(
    base_week: str, market_key: str, by_market: Dict[str, Dict[str, float]]
) -> float:
    """Online net budget for fiscal YTD elapsed (ytd_actual start → end), uniform daily spread."""
    if market_key not in by_market:
        return 0.0
    try:
        ytd_rng = get_ytd_periods_for_week(base_week)["ytd_actual"]
        ys = datetime.strptime(ytd_rng["start"], "%Y-%m-%d").date()
        ye = datetime.strptime(ytd_rng["end"], "%Y-%m-%d").date()
    except Exception:
        return 0.0
    return _sum_daily_online_net_uniform(by_market, market_key, ys, ye)


def _pool_share_of_file_row_budget(
    pool: List[str],
    detail_names: List[str],
    actual_by_c: Dict[str, float],
    ly_by_c: Optional[Dict[str, float]],
) -> float:
    """
    Fraction of the file ROW budget to assign to named pool countries (UAE, NL, …);
    the rest stays with table ROW via reconciliation (total − sum detail).

    Uses last-year mix first (pool LY vs Qlik ROW LY) so the split is independent from
    current-period actuals. Falls back to current period; if still no signal, 50%.
    """
    if not pool:
        return 1.0
    detail_set = set(detail_names)
    if ly_by_c:
        row_ly = sum(float(v) for k, v in ly_by_c.items() if k not in detail_set)
        pool_ly = sum(float(ly_by_c.get(c, 0.0)) for c in pool)
        dly = pool_ly + row_ly
        if dly > 0:
            return pool_ly / dly
    row_act = sum(float(v) for k, v in actual_by_c.items() if k not in detail_set)
    pool_act = sum(float(actual_by_c.get(c, 0.0)) for c in pool)
    denom = pool_act + row_act
    if denom > 0:
        return pool_act / denom
    return 0.5


def _detail_budget_map_with_row_bucket_split(
    base_week: str,
    actual_by_c: Dict[str, float],
    detail_names: List[str],
    by_market: Dict[str, Dict[str, float]],
    period: str,
    ly_by_c: Optional[Dict[str, float]] = None,
) -> Dict[str, float]:
    """
    Explicit markets (US, UK, …) use file rows. The file ROW line is split between (a) countries
    in the pool without a own budget line and (b) table ROW (long tail): pool gets
    row_file × (pool actuals / (pool + ROW actuals)), with LY fallback for the ratio; within
    the pool, split by each country's share of pool actuals (LY mix if pool actuals are zero).
    """
    row_keys = [k for k in by_market if _is_row_dimension_budget_label(k)]
    if period == "week":
        row_total = sum(_budget_week_for_market_key(base_week, k, by_market) for k in row_keys)

        def key_b(mk: str) -> float:
            return _budget_week_for_market_key(base_week, mk, by_market)

    elif period == "month":
        row_total = sum(_budget_mtd_for_market_key(base_week, k, by_market) for k in row_keys)

        def key_b(mk: str) -> float:
            return _budget_mtd_for_market_key(base_week, mk, by_market)

    else:
        row_total = sum(_budget_ytd_for_market_key(base_week, k, by_market) for k in row_keys)

        def key_b(mk: str) -> float:
            return _budget_ytd_for_market_key(base_week, mk, by_market)

    out: Dict[str, float] = {}
    pool: List[str] = []
    for c in detail_names:
        mk = _resolve_budget_market_key(c, by_market)
        if mk is not None and not _is_row_dimension_budget_label(mk):
            out[c] = key_b(mk)
        else:
            pool.append(c)

    if not pool or row_total <= 0:
        for c in pool:
            out[c] = 0.0
        return out

    pool_share = _pool_share_of_file_row_budget(pool, detail_names, actual_by_c, ly_by_c)
    pool_budget_total = row_total * pool_share

    if pool_budget_total <= 0:
        for c in pool:
            out[c] = 0.0
        return out

    # Prefer LY mix so distributed budgets are not mechanically tied to current actuals.
    if ly_by_c:
        pool_ly = sum(float(ly_by_c.get(c, 0.0)) for c in pool)
        if pool_ly > 0:
            for c in pool:
                out[c] = pool_budget_total * (float(ly_by_c.get(c, 0.0)) / pool_ly)
            return out

    pool_act = sum(float(actual_by_c.get(c, 0.0)) for c in pool)
    if pool_act > 0:
        for c in pool:
            out[c] = pool_budget_total * (float(actual_by_c.get(c, 0.0)) / pool_act)
    else:
        eq = pool_budget_total / len(pool)
        for c in pool:
            out[c] = eq
    return out


def _market_week_budget_from_file(
    base_week: str, country: str, by_market: Dict[str, Dict[str, float]]
) -> float:
    mk = _resolve_budget_market_key(country, by_market)
    if mk is None:
        return 0.0
    return _budget_week_for_market_key(base_week, mk, by_market)


def _market_ytd_budget_from_file(
    base_week: str, country: str, by_market: Dict[str, Dict[str, float]]
) -> float:
    mk = _resolve_budget_market_key(country, by_market)
    if mk is None:
        return 0.0
    return _budget_ytd_for_market_key(base_week, mk, by_market)


def _build_period_block_from_file(
    actual_by_c: Dict[str, float],
    ly_by_c: Dict[str, float],
    budget_total: Optional[float],
    detail_names: List[str],
    budget_detail_fn: Optional[Callable[[str], float]] = None,
    detail_budget_map: Optional[Dict[str, float]] = None,
) -> Dict[str, Dict[str, Any]]:
    """Per-country budget from file; ROW = total − sum(detail); Total = authoritative. ROW absorbs file ROW share left for long-tail."""
    if detail_budget_map is None and budget_detail_fn is None:
        raise ValueError("budget_detail_fn or detail_budget_map is required")
    detail_set = set(detail_names)
    total_act = sum(actual_by_c.values())
    total_ly = sum(ly_by_c.values())
    act_detail = {n: float(actual_by_c.get(n, 0.0)) for n in detail_names}
    ly_detail = {n: float(ly_by_c.get(n, 0.0)) for n in detail_names}
    row_act = sum(v for k, v in actual_by_c.items() if k not in detail_set)
    row_ly = sum(v for k, v in ly_by_c.items() if k not in detail_set)

    ordered = detail_names + ["ROW", "Total"]
    act_map = {**act_detail, "ROW": row_act, "Total": total_act}
    ly_map = {**ly_detail, "ROW": row_ly, "Total": total_ly}

    sum_detail_b = 0.0
    bud_map: Dict[str, Optional[float]] = {}
    for c in detail_names:
        if detail_budget_map is not None:
            b = float(detail_budget_map.get(c, 0.0))
        else:
            b = float(budget_detail_fn(c))  # type: ignore[misc]
        bud_map[c] = b
        sum_detail_b += b

    if budget_total is not None:
        row_b = max(0.0, float(budget_total) - sum_detail_b)
        bud_map["ROW"] = row_b
        bud_map["Total"] = float(budget_total)
    else:
        bud_map["ROW"] = None
        bud_map["Total"] = None

    block: Dict[str, Dict[str, Any]] = {}
    for c in ordered:
        act = act_map[c]
        lyv = ly_map[c]
        bud = bud_map.get(c)
        yoy = _yoy_pct(act, lyv)
        vsb = None if bud is None else (act - bud)
        block[c] = {
            "actual": act,
            "last_year": lyv,
            "budget": bud,
            "yoy_pct": yoy,
            "vs_budget": vsb,
        }
    return block


def calculate_top_markets_net_revenue_mtd(
    base_week: str,
    data_root: Path,
    num_weeks: int = 8,
    budget_online_net: Optional[Dict[str, Optional[float]]] = None,
    budget_by_market_month: Optional[Dict[str, Dict[str, float]]] = None,
) -> Dict[str, Any]:
    """
    Same market ordering as /api/markets/top. Online net revenue Week / MTD / YTD with YoY.

    Month column: actuals are MTD (month start -> week end); month budget is the plan for the same calendar
    dates (daily sum). YTD budget is the plan for the same fiscal YTD dates as actuals (daily sum), not the
    full-year total.

    If budget_by_market_month is non-empty (from budget CSV with Market dimension), budgets use those
    values. Countries without a matching line share the file's ROW bucket by actual mix; the table ROW
    line still reconciles to the group month total for the month block. Otherwise totals in
    budget_online_net are split by mix.
    """
    budget_online_net = budget_online_net or {}
    use_file = bool(budget_by_market_month and any(budget_by_market_month.values()))

    top = calculate_top_markets_for_weeks(base_week, num_weeks, data_root)
    markets_def = top.get("markets") or []
    detail_names = [m["country"] for m in markets_def if m["country"] not in ("ROW", "Total")]
    if not markets_def:
        return {
            "markets": [],
            "period_info": top.get("period_info") or {},
            "date_ranges": {},
        }

    all_raw = load_all_raw_data(data_root / "raw" / base_week)

    fw = filter_data_for_period(all_raw, base_week)
    net_w = _online_net_by_country(fw["qlik"])
    ly_week = get_periods_for_week(base_week)["last_year"]
    fwly = filter_data_for_period(all_raw, ly_week)
    net_wly = _online_net_by_country(fwly["qlik"])

    mtd_p = get_mtd_periods_for_week(base_week)
    m_a = filter_data_for_date_range(all_raw, mtd_p["mtd_actual"]["start"], mtd_p["mtd_actual"]["end"])
    m_ly = filter_data_for_date_range(all_raw, mtd_p["mtd_last_year"]["start"], mtd_p["mtd_last_year"]["end"])
    net_m = _online_net_by_country(m_a["qlik"])
    net_mly = _online_net_by_country(m_ly["qlik"])

    ytd_p = get_ytd_periods_for_week(base_week)
    y_a = filter_data_for_date_range(all_raw, ytd_p["ytd_actual"]["start"], ytd_p["ytd_actual"]["end"])
    y_ly = filter_data_for_date_range(all_raw, ytd_p["ytd_last_year"]["start"], ytd_p["ytd_last_year"]["end"])
    net_y = _online_net_by_country(y_a["qlik"])
    net_yly = _online_net_by_country(y_ly["qlik"])

    bw_summary = budget_online_net.get("week")
    bw = bw_summary
    bm = budget_online_net.get("mtd")
    by = budget_online_net.get("ytd")
    bmm = budget_by_market_month or {}

    def _sf(x: Any) -> float:
        try:
            return float(x) if x is not None else 0.0
        except (TypeError, ValueError):
            return 0.0

    week_from_mtd_summary = False
    week_from_file_rollup = False
    week_file_rollup_overrode_summary = False
    file_week_rollup = _file_budget_sum_all_market_keys(base_week, bmm, "week")
    file_mtd_rollup = _file_budget_sum_all_market_keys(base_week, bmm, "month")
    month_from_file_rollup = False
    month_file_rollup_overrode_summary = False
    bm_month_before_file_max = _sf(bm)
    bm_month_for_block: Optional[float] = float(bm) if bm is not None else None

    # File mode: group total must be >= sum of all CSV keys (incl. ROW + markets not in top list).
    # Summary week/MTD often equals only named markets → remainder for table ROW was 0; YTD still used fuller total.
    if use_file and file_week_rollup > 0:
        cur_w = _sf(bw)
        if file_week_rollup > cur_w + 1e-6:
            week_file_rollup_overrode_summary = cur_w > 1e-6
        bw = max(cur_w, file_week_rollup)
        if _sf(bw_summary) < 1e-6:
            week_from_file_rollup = True
        elif week_file_rollup_overrode_summary:
            week_from_file_rollup = True

    if _sf(bw) < 1e-6:
        try:
            if bm is not None and float(bm) > 0:
                mtd_p = get_mtd_periods_for_week(base_week)["mtd_actual"]
                ms = datetime.strptime(mtd_p["start"], "%Y-%m-%d").date()
                me = datetime.strptime(mtd_p["end"], "%Y-%m-%d").date()
                wr = get_week_date_range(base_week)
                ws = datetime.strptime(wr["start"], "%Y-%m-%d").date()
                we = datetime.strptime(wr["end"], "%Y-%m-%d").date()
                overlap_start = max(ws, ms)
                overlap_end = min(we, me)
                if overlap_start <= overlap_end:
                    mtd_days = (me - ms).days + 1
                    wdays = (overlap_end - overlap_start).days + 1
                    if mtd_days > 0 and wdays > 0:
                        bw = float(bm) * (wdays / mtd_days)
                        week_from_mtd_summary = True
                        week_from_file_rollup = False
                        week_file_rollup_overrode_summary = False
        except (TypeError, ValueError):
            pass

    if use_file and file_mtd_rollup > 0:
        cur_m = _sf(bm_month_for_block)
        if file_mtd_rollup > cur_m + 1e-6:
            month_file_rollup_overrode_summary = cur_m > 1e-6
        bm_month_for_block = max(cur_m, file_mtd_rollup)
        if bm_month_before_file_max < 1e-6:
            month_from_file_rollup = True
        elif month_file_rollup_overrode_summary:
            month_from_file_rollup = True

    if use_file:
        week_map = _detail_budget_map_with_row_bucket_split(
            base_week, net_w, detail_names, bmm, "week", net_wly
        )
        month_map = _detail_budget_map_with_row_bucket_split(
            base_week, net_m, detail_names, bmm, "month", net_mly
        )
        ytd_map = _detail_budget_map_with_row_bucket_split(
            base_week, net_y, detail_names, bmm, "ytd", net_yly
        )
        week_b = _build_period_block_from_file(net_w, net_wly, bw, detail_names, detail_budget_map=week_map)
        month_b = _build_period_block_from_file(
            net_m, net_mly, bm_month_for_block, detail_names, detail_budget_map=month_map
        )
        ytd_b = _build_period_block_from_file(net_y, net_yly, by, detail_names, detail_budget_map=ytd_map)
    else:
        week_b = _build_period_block(net_w, net_wly, bw, detail_names)
        month_b = _build_period_block(net_m, net_mly, bm_month_for_block, detail_names)
        ytd_b = _build_period_block(net_y, net_yly, by, detail_names)

    out_rows: List[Dict[str, Any]] = []
    for m in markets_def:
        c = m["country"]
        out_rows.append(
            {
                "country": c,
                "week": week_b.get(c, {}),
                "month": month_b.get(c, {}),
                "ytd": ytd_b.get(c, {}),
            }
        )

    wr = get_week_date_range(base_week)
    date_ranges = {
        "week_actual": {"start": wr["start"], "end": wr["end"], "display": wr.get("display", base_week)},
        "mtd_actual": {k: mtd_p["mtd_actual"][k] for k in ("start", "end", "display")},
        "mtd_last_year": {k: mtd_p["mtd_last_year"][k] for k in ("start", "end", "display")},
        "ytd_actual": {
            "start": ytd_p["ytd_actual"]["start"],
            "end": ytd_p["ytd_actual"]["end"],
            "display": f"{ytd_p['ytd_actual']['start']} to {ytd_p['ytd_actual']['end']}",
        },
        "ytd_last_year": {
            "start": ytd_p["ytd_last_year"]["start"],
            "end": ytd_p["ytd_last_year"]["end"],
            "display": f"{ytd_p['ytd_last_year']['start']} to {ytd_p['ytd_last_year']['end']}",
        },
    }

    expl: List[str] = [
        "Budgets use monthly online net from the file, spread uniformly per calendar day, then summed over the same "
        "dates as actuals. Week = 7-day ISO window; Month = MTD (1st → week end); YTD = fiscal YTD (Apr 1 → week end). "
        "vs budget is actual − budget in SEK (absolute), not a percentage.",
        "Week — Per country: daily spread of each month’s online net, summed for Mon–Sun. Group Total is at least the "
        "larger of the summary week online-net budget and the sum of all market + ROW lines from the file (file mode). "
        "If the summary week line is empty, it can be inferred from the MTD summary × (ISO week days overlapping MTD ÷ MTD days).",
        "Month — Per country: same daily-spread logic for the MTD date range. Group MTD total matches Summary MTD online "
        "net budget when available, and is at least the file rollup of per-market MTD slices (file mode).",
        "YTD — Per country: daily spread summed for fiscal YTD elapsed (same start/end as YTD actuals), aligned with Summary YTD budget.",
        "Countries without a own line in the file share the file ROW budget: part by pool vs long-tail actual mix "
        "(last year if the current period has no volume), then split within the pool by online net share.",
    ]
    if week_from_mtd_summary:
        expl.append(
            "Note: This week's group budget was inferred from the MTD online net budget × (days of the ISO week that "
            "fall inside the MTD range ÷ MTD days), because the summary week line was empty or zero."
        )
    if week_from_file_rollup and _sf(bw_summary) < 1e-6:
        expl.append(
            "Note: This week's group budget is the sum of per-market (and ROW) week slices from the budget file "
            "because the summary week budget was empty or zero."
        )
    elif week_file_rollup_overrode_summary:
        expl.append(
            "Note: Week group Total was set to at least the sum of all budget-file lines (including ROW) "
            "because that sum exceeded the summary week budget — otherwise the ROW row would show no budget "
            "while named markets used the file."
        )
    if month_from_file_rollup and bm_month_before_file_max < 1e-6:
        expl.append(
            "Note: This month's group budget is the sum of per-market MTD slices from the budget file "
            "because the summary MTD budget was empty or zero."
        )
    elif month_file_rollup_overrode_summary:
        expl.append(
            "Note: Month group Total was set to at least the sum of all budget-file MTD lines (including ROW) "
            "because that sum exceeded the summary MTD budget — so ROW matches the long-tail remainder."
        )

    return {
        "markets": out_rows,
        "period_info": top.get("period_info") or {},
        "date_ranges": date_ranges,
        "budget_source": "file_per_market" if use_file else "mix_allocation",
        "budget_explanation": expl,
    }
