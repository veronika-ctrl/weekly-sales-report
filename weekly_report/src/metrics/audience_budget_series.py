"""
Map budget (wide budget-general or long-format CSV) to audience chart metrics per ISO week.
"""

from __future__ import annotations

import calendar
import re
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from loguru import logger

from weekly_report.src.compute.budget import _fetch_budget_dataframe, compute_budget_general
from weekly_report.src.metrics.online_kpis import _build_weeks
from weekly_report.src.periods.calculator import get_week_date_range, week_overlap_fraction_in_month

_SYNTH_KEY = "__audience_budget_month__"


def _norm_label(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def _parse_budget_month_to_ym(month_key: str) -> Optional[Tuple[int, int]]:
    """Parse a budget column / month label to (year, month)."""
    s = str(month_key).strip()
    if not s:
        return None
    m = re.match(r"^(\d{4})-(\d{2})(?:-\d{2})?$", s)
    if m:
        y, mo = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12:
            return y, mo
    for fmt in ("%B %Y", "%b %Y", "%Y-%m"):
        try:
            part = s[:7] if fmt == "%Y-%m" else s
            d = datetime.strptime(part, fmt)
            return d.year, d.month
        except ValueError:
            continue
    ts = pd.to_datetime(s, errors="coerce")
    if pd.notna(ts):
        t = pd.Timestamp(ts)
        return int(t.year), int(t.month)
    return None


_SV_MONTH_NAMES = (
    "januari",
    "februari",
    "mars",
    "april",
    "maj",
    "juni",
    "juli",
    "augusti",
    "september",
    "oktober",
    "november",
    "december",
)


def _resolve_month_key(months: List[str], end_y: int, end_m: int) -> Optional[str]:
    """Match calendar month to a budget pivot column name (English, Swedish, YYYY-MM)."""
    end_month_name = datetime(end_y, end_m, 1).strftime("%B")
    for raw in months:
        parsed = _parse_budget_month_to_ym(raw)
        if parsed == (end_y, end_m):
            return raw
        # Month-only columns (e.g. "March") — same calendar month name
        if str(raw).strip().lower() == end_month_name.lower():
            return raw
    if 1 <= end_m <= 12:
        sv = _SV_MONTH_NAMES[end_m - 1]
        for raw in months:
            s = str(raw).strip().lower()
            if s == sv or s.startswith(sv + " ") or s.startswith(sv + "."):
                y_match = re.search(r"\b(20\d{2})\b", str(raw))
                if y_match and int(y_match.group(1)) != end_y:
                    continue
                return raw
    want_prefix = f"{end_y}-{end_m:02d}"
    for raw in months:
        if want_prefix in raw or raw.startswith(want_prefix):
            return raw
    return None


_CUSTOMER_ORDER_WANTS = frozenset({"newcustomers", "returningcustomers", "totalcustomers", "totalorders"})


def _label_matches_budget_alias(want: str, ln: str) -> bool:
    """
    Avoid false positives from substring rules:
    - 'Returning Customers' must not match 'Share of Returning Customers' (share is a %, not a count).
    - 'New Net Revenue' must not match 'New Net Revenue per Customer' (ratio, not SEK).
    """
    if ln == want:
        return True
    if want in _CUSTOMER_ORDER_WANTS and "share" in ln:
        return False
    if want in ln or ln in want:
        if want in ln and ln.startswith(want) and len(ln) > len(want):
            tail = ln[len(want) :]
            if tail.startswith("per") or tail.startswith("share"):
                return False
        return True
    return False


def _get_cell(table: Dict[str, Dict[str, Any]], month_key: str, *aliases: str) -> float:
    if not table or not month_key:
        return 0.0
    for al in aliases:
        want = _norm_label(al)
        if not want:
            continue
        # Pass 1: exact label match only (prevents Share-of / per-customer rows winning).
        for label, row in table.items():
            ln = _norm_label(label)
            if ln != want:
                continue
            if not isinstance(row, dict):
                continue
            v = row.get(month_key)
            if v is None:
                continue
            try:
                x = float(v)
                if x == float("inf") or x == float("-inf"):
                    continue
                return x
            except (TypeError, ValueError):
                continue
        # Pass 2: legacy fuzzy (with guards).
        for label, row in table.items():
            ln = _norm_label(label)
            if not _label_matches_budget_alias(want, ln):
                continue
            if not isinstance(row, dict):
                continue
            v = row.get(month_key)
            if v is None:
                continue
            try:
                x = float(v)
                if x == float("inf") or x == float("-inf"):
                    continue
                return x
            except (TypeError, ValueError):
                continue
    return 0.0


def _normalize_share_pct(x: float) -> float:
    if 0 < x <= 1:
        return x * 100.0
    return x


def _normalize_cos_pct(x: float) -> float:
    if 0 < x <= 1:
        return x * 100.0
    return x


def _audience_metrics_from_table(table: Dict[str, Dict[str, Any]], month_key: str) -> Optional[Dict[str, Any]]:
    if not table or not month_key:
        return None

    def g(*aliases: str) -> float:
        return _get_cell(table, month_key, *aliases)

    new_c = g("New Customers")
    ret_c = g("Returning Customers")
    total_c = g("Total Customers")
    if total_c <= 0 and (new_c > 0 or ret_c > 0):
        total_c = new_c + ret_c
    total_orders = g("Total Orders")
    total_aov = g("Total AOV")
    if total_aov <= 0 and total_orders > 0:
        tg = g("Total Gross Revenue")
        if tg > 0:
            total_aov = tg / total_orders

    new_gross = g("New Gross Revenue")
    new_returns = g("New Returns")
    ret_gross = g("Returning Gross Revenue")
    ret_returns = g("Returning Returns")
    total_gross = g("Total Gross Revenue")

    rr_new = (new_returns / new_gross * 100.0) if new_gross > 0 else 0.0
    rr_ret = (ret_returns / ret_gross * 100.0) if ret_gross > 0 else 0.0
    ret_sum = new_returns + ret_returns
    rr_pct = (ret_sum / total_gross * 100.0) if total_gross > 0 else 0.0

    share_new = _normalize_share_pct(g("Share of New Customers"))
    share_ret = _normalize_share_pct(g("Share of Returning Customers"))
    if total_c > 0:
        if share_new <= 0 and new_c > 0:
            share_new = new_c / total_c * 100.0
        if share_ret <= 0 and ret_c > 0:
            share_ret = ret_c / total_c * 100.0

    cos_pct = _normalize_cos_pct(g("COS %"))
    # Budget files can contain signed values; normalize to absolute for comparison metrics.
    mkt = abs(g("Online Marketing Spend"))
    new_net = abs(g("New Net Revenue"))
    # aMER is a ratio — never trust an explicit row when we can derive from volumes (summed market
    # ratios or duplicate rows often inflate aMER; company plan = new net ÷ marketing spend).
    if mkt > 1e-9:
        amer = new_net / mkt
    else:
        amer = g("aMER") or g("AMER") or g("eMER") or g("emer") or g("OJ aMER")
        if not amer or abs(float(amer)) < 1e-9:
            amer = 0.0
    cac = (mkt / new_c) if new_c > 0 else 0.0

    aov_new = g("New AOV")
    aov_ret = g("Returning AOV")
    if aov_new <= 0 and new_c > 0:
        nn = g("New Net Revenue")
        if nn > 0:
            aov_new = nn / new_c
    if aov_ret <= 0 and ret_c > 0:
        rn = g("Returning Net Revenue")
        if rn > 0:
            aov_ret = rn / ret_c

    # Treat as miss only if nothing chart-relevant is non-zero (include total_aov — often the only budget row)
    if not any(
        abs(float(x or 0)) > 1e-9
        for x in (
            new_c,
            ret_c,
            total_c,
            total_orders,
            total_aov,
            total_gross,
            mkt,
            amer,
            cos_pct,
            cac,
            rr_new,
            rr_ret,
            rr_pct,
            share_new,
            share_ret,
            aov_new,
            aov_ret,
        )
    ):
        return None

    return {
        "total_aov": round(total_aov),
        "total_customers": int(round(total_c)),
        "total_orders": int(round(total_orders)),
        "new_customers": int(round(new_c)),
        "returning_customers": int(round(ret_c)),
        "aov_new_customer": round(aov_new, 2),
        "aov_returning_customer": round(aov_ret, 2),
        "new_customer_share_pct": round(share_new, 1),
        "returning_customer_share_pct": round(share_ret, 1),
        "return_rate_pct": round(rr_pct, 1),
        "return_rate_new_pct": round(rr_new, 1),
        "return_rate_returning_pct": round(rr_ret, 1),
        "cos_pct": round(cos_pct, 1),
        "cac": round(cac),
        "amer": round(amer, 2),
    }


def _iso_week_thursday_ymd(iso_week: str) -> Tuple[int, int]:
    """Calendar (year, month) of ISO week Thursday — primary month for monthly budget rates."""
    wr = get_week_date_range(iso_week)
    ws = datetime.strptime(wr["start"], "%Y-%m-%d").date()
    thu = ws + timedelta(days=3)
    return thu.year, thu.month


def _week_month_fractions_for_iso_week(months: List[str], iso_week: str) -> List[Tuple[str, float]]:
    """
    For each calendar month touched by Mon–Sun, fraction = days_in_week_in_month / days_in_month.
    Used to prorate monthly volume budgets across month boundaries (avoids dips when week-end month is empty).
    """
    if not months:
        return []
    wr = get_week_date_range(iso_week)
    ws = datetime.strptime(wr["start"], "%Y-%m-%d").date()
    we = datetime.strptime(wr["end"], "%Y-%m-%d").date()
    counts: Dict[Tuple[int, int], int] = defaultdict(int)
    d = ws
    while d <= we:
        counts[(d.year, d.month)] += 1
        d += timedelta(days=1)
    out: List[Tuple[str, float]] = []
    for (y, m), overlap in counts.items():
        _, dim = calendar.monthrange(y, m)
        mk = _resolve_month_key(months, y, m)
        if mk and dim > 0:
            out.append((mk, overlap / float(dim)))
    return out


def _apply_week_volume_proration(metrics: Dict[str, Any], frac: float) -> Dict[str, Any]:
    """
    Monthly budget rows are full-month; weekly actuals need the same week's share of that month
    (same as Top Markets week budget). Only volume counts are prorated; rates (AOV, return %, COS,
    aMER, shares) stay as monthly targets.
    """
    if frac <= 0 or frac > 1.0 + 1e-6:
        return metrics
    out = dict(metrics)
    for k in ("total_customers", "total_orders", "new_customers", "returning_customers"):
        if k in out and out[k] is not None:
            try:
                out[k] = int(round(float(out[k]) * frac))
            except (TypeError, ValueError):
                pass
    return out


def _try_long_format_audience_budget(
    base_week: str,
    iso_week: str,
    df: Optional[pd.DataFrame] = None,
) -> Optional[Dict[str, Any]]:
    """
    Budget CSV with columns like Market, Metric, Year, Month, Type, Value (same as MTD long layout).
    """
    if df is None:
        df = _fetch_budget_dataframe(base_week)
    if df is None or df.empty:
        return None
    lower = {str(c).strip().lower(): c for c in df.columns}
    m_col = lower.get("month")
    v_col = lower.get("value")
    met_col = lower.get("metric")
    if not m_col or not v_col or not met_col:
        return None

    try:
        end_s = get_week_date_range(iso_week)["end"]
        end_dt = datetime.strptime(end_s, "%Y-%m-%d")
    except Exception:
        return None

    ty, tm = end_dt.year, end_dt.month
    month_full = end_dt.strftime("%B")

    work = df.copy()
    work[m_col] = work[m_col].astype(str).str.strip()
    mask = work[m_col].str.lower() == month_full.lower()
    y_col = lower.get("year")
    if y_col:
        yv = pd.to_numeric(work[y_col], errors="coerce")
        mask &= yv == ty
    sub = work.loc[mask].copy()
    # If file uses a different budget year label (e.g. FY) than the ISO week’s calendar year, fall back
    if sub.empty and y_col:
        mask2 = work[m_col].str.lower() == month_full.lower()
        sub2 = work.loc[mask2].copy()
        if not sub2.empty:
            yv2 = pd.to_numeric(sub2[y_col], errors="coerce")
            avail = sorted({int(x) for x in yv2.dropna().tolist()})
            if avail:
                pick = ty if ty in avail else max([y for y in avail if y <= ty], default=max(avail))
                sub = sub2.loc[pd.to_numeric(sub2[y_col], errors="coerce") == pick].copy()

    if sub.empty:
        return None

    if "Type" in sub.columns:
        tv = sub["Type"].astype(str).str.strip().str.upper()
        picked = None
        for t in ("BUDGET", "ESTIMATE", "FORECAST", "PLAN"):
            cand = sub.loc[tv == t]
            if not cand.empty:
                picked = cand
                break
        if picked is not None:
            sub = picked.copy()
        else:
            for t in ("ACTUAL", "OUTCOME", "ACT"):
                cand = sub.loc[tv == t]
                if not cand.empty:
                    sub = cand.copy()
                    break
            else:
                sub = sub.copy()
    else:
        sub = sub.copy()

    mkt_col = lower.get("market")
    met_col_name = met_col
    if mkt_col and mkt_col in sub.columns and met_col_name:
        mv = sub[mkt_col].astype(str).str.strip().str.lower()
        tcdlp = sub.loc[mv == "total cdlp"]
        # Long CSV often has aMER / eMER on rows with no Market (not under Total CDLP).
        blank_mkt = mv.isna() | (mv == "") | (mv == "nan")
        met_lower = sub[met_col_name].astype(str).str.strip().str.lower()
        _GLOBAL_BUDGET_METRICS = frozenset({"amer", "emer", "oj amer", "cos %"})
        extra = sub.loc[blank_mkt & met_lower.isin(_GLOBAL_BUDGET_METRICS)].copy()
        if not tcdlp.empty:
            sub = pd.concat([tcdlp, extra], ignore_index=True)
            sub = sub.drop_duplicates(subset=[met_col_name], keep="first")
        elif not extra.empty:
            # No Total CDLP row for this month; merge global KPI rows into remaining slice.
            sub = pd.concat([sub, extra], ignore_index=True).drop_duplicates(
                subset=[met_col_name], keep="last"
            )

    sub[met_col] = sub[met_col].astype(str).str.strip()
    sub[v_col] = pd.to_numeric(sub[v_col], errors="coerce").fillna(0.0)
    grouped = sub.groupby(met_col, as_index=False)[v_col].sum()
    table: Dict[str, Dict[str, float]] = {}
    for _, row in grouped.iterrows():
        label = str(row[met_col]).strip()
        if label:
            table[label] = {_SYNTH_KEY: float(row[v_col])}
    if not table:
        return None
    return _audience_metrics_from_table(table, _SYNTH_KEY)


def build_audience_budget_metrics_for_week(
    budget_result: Dict[str, Any],
    iso_week: str,
    base_week: str,
    long_budget_df: Optional[pd.DataFrame] = None,
) -> Optional[Dict[str, Any]]:
    """
    One week's audience-shaped budget: wide budget-general first, else long-format CSV.
    Monthly rates use the ISO week's Thursday month; volume counts are prorated across every
    calendar month the Mon–Sun week touches (same idea as frontend weekMonthFractionsForIsoWeek).
    """
    try:
        end_s = get_week_date_range(iso_week)["end"]
        end_dt = datetime.strptime(end_s, "%Y-%m-%d")
    except Exception as e:
        logger.debug(f"audience budget: bad week {iso_week}: {e}")
        return None

    out: Optional[Dict[str, Any]] = None
    used_wide_table: Optional[Dict[str, Any]] = None
    wide_months: List[str] = []

    if budget_result and not budget_result.get("error"):
        table = budget_result.get("table") or {}
        if table:
            months = list(budget_result.get("months") or [])
            if not months:
                first_row = next(iter(table.values()), None)
                if isinstance(first_row, dict):
                    months = list(first_row.keys())
            try:
                thu_y, thu_m = _iso_week_thursday_ymd(iso_week)
            except Exception:
                thu_y, thu_m = end_dt.year, end_dt.month
            month_key = _resolve_month_key(months, thu_y, thu_m) if months else None
            if not month_key:
                month_key = _resolve_month_key(months, end_dt.year, end_dt.month) if months else None
            if month_key:
                out = _audience_metrics_from_table(table, month_key)
                if out is not None:
                    used_wide_table = table
                    first_row = next(iter(table.values()), None)
                    row_keys = list(first_row.keys()) if isinstance(first_row, dict) else []
                    seen = set()
                    wide_months = []
                    for x in months + row_keys:
                        if x not in seen:
                            seen.add(x)
                            wide_months.append(x)
            elif months:
                logger.debug(
                    f"audience budget: wide table but no month key for {iso_week} end={end_s}; "
                    f"sample months={months[:4]}"
                )

    if out is None:
        out = _try_long_format_audience_budget(base_week, iso_week, df=long_budget_df)
    if out is None:
        return None

    if used_wide_table is not None and wide_months:
        portions = _week_month_fractions_for_iso_week(wide_months, iso_week)
        if portions:
            for k, aliases in (
                ("total_customers", ("Total Customers",)),
                ("total_orders", ("Total Orders",)),
                ("new_customers", ("New Customers",)),
                ("returning_customers", ("Returning Customers",)),
            ):
                total = 0.0
                for mk, frac in portions:
                    total += _get_cell(used_wide_table, mk, *aliases) * frac
                out[k] = int(round(total))
        else:
            frac = week_overlap_fraction_in_month(iso_week)
            out = _apply_week_volume_proration(out, frac)
    else:
        frac = week_overlap_fraction_in_month(iso_week)
        out = _apply_week_volume_proration(out, frac)
    return out


def compute_audience_budget_series(base_week: str, num_weeks: int) -> Dict[str, Any]:
    if num_weeks < 1:
        num_weeks = 8
    weeks = _build_weeks(base_week, num_weeks)
    budget_result = compute_budget_general(base_week)
    long_df = _fetch_budget_dataframe(base_week)
    out_weeks: List[Dict[str, Any]] = []
    # aMER is a monthly plan ratio — same target for every week on the chart (report month = base_week).
    amer_ref: Optional[float] = None
    ref = build_audience_budget_metrics_for_week(budget_result, base_week, base_week, long_budget_df=long_df)
    if ref and isinstance(ref, dict) and ref.get("amer") is not None:
        try:
            amer_ref = float(ref["amer"])
        except (TypeError, ValueError):
            amer_ref = None
    for w in weeks:
        b = build_audience_budget_metrics_for_week(budget_result, w, base_week, long_budget_df=long_df)
        if b and amer_ref is not None:
            b = dict(b)
            b["amer"] = amer_ref
        out_weeks.append({"week": w, "budget": b})
    return {
        "base_week": base_week,
        "num_weeks": num_weeks,
        "weeks": out_weeks,
        "budget_general_error": budget_result.get("error"),
    }
