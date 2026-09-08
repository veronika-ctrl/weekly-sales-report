"""
Adjusted aMER reporting — a separate module from weekly Dema/Shopify/Qlik reports.

Data source (scheduled Dema agent, semicolon CSV, one trio per ISO week):

    Revenue_by_channel_W##.csv
        Channel;ChannelGroup;Country;Day;Revenue_MTA;Revenue_CFA;Revenue_New_MTA;Revenue_Returning_MTA
    Marketing_spend_W##.csv
        Channel;ChannelGroup;Country;Day;Marketing spend
    Net_GM2_W##.csv
        Channel;ChannelGroup;Country;Day;Net gross profit 2;Net sales;Net gross margin 2;Marketing spend

Join is a mandatory FULL OUTER JOIN on Channel;ChannelGroup;Country;Day. Unmatched
revenue or spend is treated as 0. Never left-join from revenue: paid spend without
revenue would disappear and inflate ratios.

Headline Adjusted aMER uses Revenue_CFA. New-customer Adjusted aMER uses
Revenue_New_MTA because CFA is not split by new/returning. Those two ratios are
not the same methodology.

Unattributed is never folded into organic. Unknown ChannelGroups land in a visible
``other`` bucket rather than being dropped.

Existing weekly ``dema_spend`` / ``dema_gm2`` / Shopify sessions uploads are a
different grain (no ChannelGroup; GM2 W36 is country-level spend only) and are
NOT reused here.

Taxonomy (case-insensitive, spaces/hyphens → underscore)
========================================================
Live W36 ``dema_spend`` Channel values (no ChannelGroup in that file):
    Facebook, TikTok, Google, CJ
When the agent file omits ChannelGroup we infer from Channel using that live set.

PAID_GROUPS — paid media whose CFA revenue is the Adjusted aMER numerator
    and whose spend is the denominator:
        sem, google, google_ads, shopping, paid_search, pmax, performance_max
        meta, meta_paid, facebook, instagram, paid_social
        tiktok, tiktok_paid
        affiliate, affiliates, cj
        display
ORGANIC_GROUPS (spec):
        organic, email, social_organic, referral, direct
        (+ seo, organic_search, organic_social as aliases)
UNATTRIBUTED_GROUPS (spec):
        backfilled, unknown
        (+ unattributed as alias)
Anything else → bucket ``other`` (shown, not dropped, not folded into organic).

Shopify recruited vs dropped does NOT use Dema files. It needs a customer-order
export (customer id + order date). Sessions/Qlik cannot substitute.
"""

from __future__ import annotations

import calendar
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd
from loguru import logger

from weekly_report.src.metrics.discounts_sales import _read_csv_flexible
from weekly_report.src.periods.calculator import get_week_date_range, validate_iso_week

# ---------------------------------------------------------------------------
# Upload slots (Settings). Distinct from weekly dema_spend / dema_gm2 / shopify.
# ---------------------------------------------------------------------------
AMER_REVENUE_TYPE = "amer_revenue"
AMER_SPEND_TYPE = "amer_spend"
AMER_GM2_TYPE = "amer_gm2"
SHOPIFY_CUSTOMERS_TYPE = "shopify_customers"

AMER_DEMA_FILE_TYPES: Tuple[str, ...] = (AMER_REVENUE_TYPE, AMER_SPEND_TYPE, AMER_GM2_TYPE)
AMER_ALL_FILE_TYPES: Tuple[str, ...] = AMER_DEMA_FILE_TYPES + (SHOPIFY_CUSTOMERS_TYPE,)

PROVISIONAL_DAYS = 42  # ~6 weeks; periods younger than this are restated, not locked.
CUSTOMER_HISTORY_START = date(2022, 1, 1)

# ---------------------------------------------------------------------------
# ChannelGroup taxonomy
# ---------------------------------------------------------------------------
# Matched after _norm_group(). Confirmed from live W36 Channel names (Facebook,
# TikTok, Google, CJ) plus the spec placeholders for organic / unattributed.
PAID_GROUPS = frozenset(
    {
        "sem",
        "google",
        "google_ads",
        "shopping",
        "paid_search",
        "pmax",
        "performance_max",
        "meta",
        "meta_paid",
        "facebook",
        "instagram",
        "paid_social",
        "tiktok",
        "tiktok_paid",
        "affiliate",
        "affiliates",
        "cj",
        "display",
    }
)
ORGANIC_GROUPS = frozenset(
    {
        "organic",
        "email",
        "social_organic",
        "referral",
        "direct",
        "seo",
        "organic_search",
        "organic_social",
    }
)
UNATTRIBUTED_GROUPS = frozenset(
    {
        "backfilled",
        "unknown",
        "unattributed",
    }
)

# Channel → ChannelGroup when the agent file has Channel but no ChannelGroup.
# Keys are _norm_group() of Channel. Values are canonical group labels.
CHANNEL_TO_GROUP = {
    "facebook": "meta",
    "fb": "meta",
    "instagram": "meta",
    "ig": "meta",
    "meta": "meta",
    "tiktok": "tiktok",
    "tt": "tiktok",
    "google": "sem",
    "google_ads": "sem",
    "adwords": "sem",
    "shopping": "sem",
    "pmax": "sem",
    "performance_max": "sem",
    "cj": "affiliate",
    "commission_junction": "affiliate",
    "awin": "affiliate",
    "affiliate": "affiliate",
    "email": "email",
    "klaviyo": "email",
    "direct": "direct",
    "organic": "organic",
    "seo": "organic",
    "referral": "referral",
    "unknown": "unknown",
    "backfilled": "backfilled",
}

JOIN_KEYS = ("Channel", "ChannelGroup", "Country", "Day")

_YEAR_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _norm_group(value: Any) -> str:
    s = str(value or "").strip().strip('"').strip("'").lower()
    s = re.sub(r"[\s\-]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def classify_channel_group(group: Any) -> str:
    """Return paid | organic | unattributed | other."""
    g = _norm_group(group)
    if not g:
        return "other"
    if g in PAID_GROUPS:
        return "paid"
    if g in ORGANIC_GROUPS:
        return "organic"
    if g in UNATTRIBUTED_GROUPS:
        return "unattributed"
    return "other"


def infer_channel_group(channel: Any, channel_group: Any = None) -> str:
    """Prefer the file's ChannelGroup; if blank, map Channel from the live W36 set."""
    g = _norm_group(channel_group)
    if g:
        return g
    mapped = CHANNEL_TO_GROUP.get(_norm_group(channel))
    if mapped:
        return mapped
    return "other"


def _pick_column(df: pd.DataFrame, candidates: Sequence[str]) -> Optional[str]:
    if df is None:
        return None
    norm_map = {_norm_group(c): str(c) for c in df.columns}
    for cand in candidates:
        hit = norm_map.get(_norm_group(cand))
        if hit:
            return hit
    return None


def _to_number(series: pd.Series) -> pd.Series:
    """Parse numbers; tolerate European decimals and thousands separators."""
    if series is None:
        return pd.Series(dtype=float)
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")

    as_str = (
        series.astype(str)
        .str.replace("\u00a0", " ", regex=False)
        .str.replace(" ", "", regex=False)
        .str.replace("%", "", regex=False)
    )
    as_str = as_str.str.replace(r"^\((.*)\)$", r"-\1", regex=True)

    def _one(s: str) -> float:
        if s in ("", "nan", "None", "NULL", "null", "N/A", "n/a", "-", "—"):
            return float("nan")
        if "," in s and "." in s:
            if s.rfind(",") > s.rfind("."):
                s = s.replace(".", "").replace(",", ".")
            else:
                s = s.replace(",", "")
        elif "," in s:
            parts = s.split(",")
            if len(parts) > 1 and all(len(p) == 3 for p in parts[1:]):
                s = "".join(parts)
            else:
                s = s.replace(",", ".")
        try:
            return float(s)
        except ValueError:
            return float("nan")

    return as_str.map(_one)


def safe_ratio(numerator: Any, denominator: Any) -> Optional[float]:
    """Guard divide-by-zero: return None (JSON null / UI em dash), never Inf."""
    try:
        n = float(numerator)
        d = float(denominator)
    except (TypeError, ValueError):
        return None
    if not pd.notna(n) or not pd.notna(d) or d == 0:
        return None
    return n / d


def is_provisional(period_end: date, as_of: date, days: int = PROVISIONAL_DAYS) -> bool:
    """True when the period is younger than ~6 weeks relative to the pull date."""
    return (as_of - period_end).days < days


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _parse_day(series: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(series, errors="coerce", utc=False)
    if parsed.isna().all():
        parsed = pd.to_datetime(series, errors="coerce", dayfirst=True)
    return parsed


def _list_csv_files(folder: Path) -> List[Path]:
    if not folder.exists():
        return []
    return sorted(
        (f for f in folder.glob("*.*") if f.suffix.lower() == ".csv" and not f.name.startswith(".")),
        key=lambda p: p.stat().st_mtime,
    )


def _latest_csv(folder: Path) -> Optional[Path]:
    files = _list_csv_files(folder)
    return files[-1] if files else None


def find_week_amer_files(raw_week_path: Path) -> Dict[str, Optional[Path]]:
    return {
        AMER_REVENUE_TYPE: _latest_csv(raw_week_path / AMER_REVENUE_TYPE),
        AMER_SPEND_TYPE: _latest_csv(raw_week_path / AMER_SPEND_TYPE),
        AMER_GM2_TYPE: _latest_csv(raw_week_path / AMER_GM2_TYPE),
    }


def missing_amer_types(files: Dict[str, Optional[Path]]) -> List[str]:
    return [k for k, v in files.items() if v is None]


def _load_one_csv(path: Path) -> pd.DataFrame:
    df = _read_csv_flexible(path)
    df.columns = [str(c).strip().strip('"').strip("'") for c in df.columns]
    df["_source_file"] = path.name
    df["_source_mtime"] = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return df


def _standardize_keys(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    channel = _pick_column(out, ["Channel"])
    group = _pick_column(out, ["ChannelGroup", "Channel Group", "Channel_Group"])
    country = _pick_column(out, ["Country"])
    day = _pick_column(out, ["Day", "Days", "Date"])
    rename: Dict[str, str] = {}
    if channel:
        rename[channel] = "Channel"
    if group:
        rename[group] = "ChannelGroup"
    if country:
        rename[country] = "Country"
    if day:
        rename[day] = "Day"
    out = out.rename(columns=rename)
    if "Channel" not in out.columns:
        out["Channel"] = "unknown"
    if "Country" not in out.columns:
        out["Country"] = "unknown"
    if "Day" not in out.columns:
        out["Day"] = pd.NaT
    raw_group = out["ChannelGroup"] if "ChannelGroup" in out.columns else None
    inferred = [
        infer_channel_group(ch, g)
        for ch, g in zip(
            out["Channel"].tolist(),
            (raw_group.tolist() if raw_group is not None else [None] * len(out)),
        )
    ]
    out["ChannelGroup"] = inferred
    out["Channel"] = out["Channel"].astype(str).str.strip()
    out["Country"] = out["Country"].astype(str).str.strip()
    out["Day"] = _parse_day(out["Day"]).dt.normalize()
    out["bucket"] = out["ChannelGroup"].map(classify_channel_group)
    return out


def _take_numeric(df: pd.DataFrame, candidates: Sequence[str], dest: str) -> pd.DataFrame:
    col = _pick_column(df, candidates)
    if col is None:
        df[dest] = 0.0
    else:
        df[dest] = _to_number(df[col]).fillna(0.0)
    return df


def load_revenue_frame(path: Path) -> pd.DataFrame:
    df = _standardize_keys(_load_one_csv(path))
    df = _take_numeric(df, ["Revenue_CFA", "Revenue CFA", "RevenueCFA"], "revenue_cfa")
    df = _take_numeric(df, ["Revenue_MTA", "Revenue MTA", "RevenueMTA"], "revenue_mta")
    df = _take_numeric(df, ["Revenue_New_MTA", "Revenue New MTA", "Revenue_New MTA"], "revenue_new_mta")
    df = _take_numeric(
        df,
        ["Revenue_Returning_MTA", "Revenue Returning MTA", "Revenue_Returning MTA"],
        "revenue_returning_mta",
    )
    return df[
        [
            *JOIN_KEYS,
            "bucket",
            "revenue_cfa",
            "revenue_mta",
            "revenue_new_mta",
            "revenue_returning_mta",
            "_source_file",
            "_source_mtime",
        ]
    ]


def load_spend_frame(path: Path) -> pd.DataFrame:
    df = _standardize_keys(_load_one_csv(path))
    df = _take_numeric(df, ["Marketing spend", "Marketing Spend", "Spend"], "marketing_spend")
    return df[[*JOIN_KEYS, "bucket", "marketing_spend", "_source_file", "_source_mtime"]]


def load_gm2_frame(path: Path) -> pd.DataFrame:
    df = _standardize_keys(_load_one_csv(path))
    df = _take_numeric(
        df,
        ["Net gross profit 2", "Net GM2", "Net gross profit2", "Gross margin 2 - Dema MTA"],
        "net_gross_profit_2",
    )
    df = _take_numeric(df, ["Net sales", "Net Sales"], "net_sales")
    df = _take_numeric(
        df,
        ["Net gross margin 2", "Net GM2 %", "Net gross margin2"],
        "net_gross_margin_2_row",
    )
    df = _take_numeric(df, ["Marketing spend", "Marketing Spend", "Spend"], "gm2_marketing_spend")
    return df[
        [
            *JOIN_KEYS,
            "bucket",
            "net_gross_profit_2",
            "net_sales",
            "net_gross_margin_2_row",
            "gm2_marketing_spend",
            "_source_file",
            "_source_mtime",
        ]
    ]


def full_outer_join_amer(
    revenue: pd.DataFrame,
    spend: pd.DataFrame,
    gm2: pd.DataFrame,
) -> pd.DataFrame:
    """FULL OUTER JOIN on Channel;ChannelGroup;Country;Day. Unmatched metrics = 0."""
    empty_rev = pd.DataFrame(
        columns=[
            *JOIN_KEYS,
            "bucket",
            "revenue_cfa",
            "revenue_mta",
            "revenue_new_mta",
            "revenue_returning_mta",
            "_source_mtime",
        ]
    )
    empty_spend = pd.DataFrame(columns=[*JOIN_KEYS, "bucket", "marketing_spend", "_source_mtime"])
    empty_gm2 = pd.DataFrame(
        columns=[
            *JOIN_KEYS,
            "bucket",
            "net_gross_profit_2",
            "net_sales",
            "net_gross_margin_2_row",
            "gm2_marketing_spend",
            "_source_mtime",
        ]
    )
    rev = revenue if revenue is not None and not revenue.empty else empty_rev
    sp = spend if spend is not None and not spend.empty else empty_spend
    g = gm2 if gm2 is not None and not gm2.empty else empty_gm2

    keys = list(JOIN_KEYS)
    rev_s = rev.rename(columns={"bucket": "bucket_rev", "_source_mtime": "_mtime_rev"})
    sp_s = sp.rename(columns={"bucket": "bucket_spend", "_source_mtime": "_mtime_spend"}).drop(
        columns=[c for c in sp.columns if c.startswith("_source_file")],
        errors="ignore",
    )
    g_s = g.rename(columns={"bucket": "bucket_gm2", "_source_mtime": "_mtime_gm2"}).drop(
        columns=[c for c in g.columns if c.startswith("_source_file")],
        errors="ignore",
    )

    joined = rev_s.merge(sp_s, on=keys, how="outer")
    joined = joined.merge(g_s, on=keys, how="outer")

    joined["bucket"] = (
        joined["bucket_rev"]
        .combine_first(joined.get("bucket_spend"))
        .combine_first(joined.get("bucket_gm2"))
        .fillna("other")
    )
    mtimes = []
    for c in ("_mtime_rev", "_mtime_spend", "_mtime_gm2"):
        if c in joined.columns:
            mtimes.append(pd.to_datetime(joined[c], utc=True, errors="coerce"))
    if mtimes:
        joined["_as_of"] = pd.concat(mtimes, axis=1).max(axis=1, skipna=True)
    else:
        joined["_as_of"] = pd.NaT

    for col in (
        "revenue_cfa",
        "revenue_mta",
        "revenue_new_mta",
        "revenue_returning_mta",
        "marketing_spend",
        "net_gross_profit_2",
        "net_sales",
        "net_gross_margin_2_row",
        "gm2_marketing_spend",
    ):
        if col not in joined.columns:
            joined[col] = 0.0
        joined[col] = pd.to_numeric(joined[col], errors="coerce").fillna(0.0)

    joined["Day"] = pd.to_datetime(joined["Day"], errors="coerce").dt.normalize()
    return joined


def _filter_days(df: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    if df.empty:
        return df
    s = pd.Timestamp(start)
    e = pd.Timestamp(end)
    return df[(df["Day"] >= s) & (df["Day"] <= e)].copy()


def _share(part: float, whole: float) -> Optional[float]:
    return safe_ratio(part, whole)


def aggregate_amer_metrics(df: pd.DataFrame) -> Dict[str, Any]:
    """Weekly or monthly headline aggregates. GM2 is sum/sum, never a row-level average."""
    empty = {
        "paidRevenue": 0.0,
        "organicRevenue": 0.0,
        "unattributedRevenue": 0.0,
        "otherRevenue": 0.0,
        "totalRevenue": 0.0,
        "newCustomerPaidRevenue": 0.0,
        "paidSpend": 0.0,
        "blendedMER": None,
        "adjustedAMER": None,
        "newCustomerAdjustedAMER": None,
        "organicRevShare": None,
        "paidRevShare": None,
        "unattributedShare": None,
        "otherRevShare": None,
        "netGM2": None,
        "netGrossProfit2": 0.0,
        "netSales": 0.0,
    }
    if df is None or df.empty:
        return empty

    paid = df["bucket"] == "paid"
    organic = df["bucket"] == "organic"
    unattr = df["bucket"] == "unattributed"
    other = df["bucket"] == "other"

    paid_revenue = float(df.loc[paid, "revenue_cfa"].sum())
    organic_revenue = float(df.loc[organic, "revenue_cfa"].sum())
    unattr_revenue = float(df.loc[unattr, "revenue_cfa"].sum())
    other_revenue = float(df.loc[other, "revenue_cfa"].sum())
    total_revenue = paid_revenue + organic_revenue + unattr_revenue
    new_paid = float(df.loc[paid, "revenue_new_mta"].sum())
    paid_spend = float(df.loc[paid, "marketing_spend"].sum())
    gp2 = float(df["net_gross_profit_2"].sum())
    net_sales = float(df["net_sales"].sum())

    total_cfa_all = total_revenue + other_revenue
    return {
        "paidRevenue": paid_revenue,
        "organicRevenue": organic_revenue,
        "unattributedRevenue": unattr_revenue,
        "otherRevenue": other_revenue,
        "totalRevenue": total_revenue,
        "newCustomerPaidRevenue": new_paid,
        "paidSpend": paid_spend,
        "blendedMER": safe_ratio(total_revenue, paid_spend),
        "adjustedAMER": safe_ratio(paid_revenue, paid_spend),
        "newCustomerAdjustedAMER": safe_ratio(new_paid, paid_spend),
        "organicRevShare": _share(organic_revenue, total_revenue),
        "paidRevShare": _share(paid_revenue, total_revenue),
        "unattributedShare": _share(unattr_revenue, total_revenue),
        "otherRevShare": _share(other_revenue, total_cfa_all),
        "netGM2": safe_ratio(gp2, net_sales),
        "netGrossProfit2": gp2,
        "netSales": net_sales,
    }


def _period_as_of(df: pd.DataFrame) -> Optional[datetime]:
    if df is None or df.empty or "_as_of" not in df.columns:
        return None
    series = pd.to_datetime(df["_as_of"], utc=True, errors="coerce").dropna()
    if series.empty:
        return None
    ts = series.max()
    if isinstance(ts, pd.Timestamp):
        return ts.to_pydatetime()
    return None


def _with_provisional(
    metrics: Dict[str, Any], period_end: date, as_of: date, as_of_dt: Optional[datetime]
) -> Dict[str, Any]:
    out = dict(metrics)
    out["provisional"] = is_provisional(period_end, as_of)
    out["as_of"] = _iso(as_of_dt) if as_of_dt else as_of.isoformat()
    out["period_end"] = period_end.isoformat()
    return out


def monthly_channel_rows(df: pd.DataFrame, as_of: date) -> List[Dict[str, Any]]:
    """Calendar-month rollup, Channel and ChannelGroup broken out (weeks may straddle months)."""
    if df is None or df.empty:
        return []
    work = df.dropna(subset=["Day"]).copy()
    work["year_month"] = work["Day"].dt.strftime("%Y-%m")
    grouped = work.groupby(["year_month", "Channel", "ChannelGroup", "bucket"], dropna=False)
    rows: List[Dict[str, Any]] = []
    for (year_month, channel, group, bucket), part in grouped:
        y_str, m_str = str(year_month).split("-")
        last = calendar.monthrange(int(y_str), int(m_str))[1]
        period_end = date(int(y_str), int(m_str), last)
        spend = float(part["marketing_spend"].sum())
        cfa = float(part["revenue_cfa"].sum())
        new_mta = float(part["revenue_new_mta"].sum())
        as_of_dt = _period_as_of(part)
        as_of_d = as_of_dt.date() if as_of_dt else as_of
        rows.append(
            {
                "year_month": str(year_month),
                "channel": str(channel),
                "channel_group": str(group),
                "bucket": str(bucket),
                "revenue_cfa": cfa,
                "revenue_new_mta": new_mta,
                "paidSpend": spend,
                "adjustedAMER": safe_ratio(cfa, spend),
                "newCustomerAdjustedAMER": safe_ratio(new_mta, spend),
                "provisional": is_provisional(period_end, as_of_d),
                "as_of": _iso(as_of_dt) if as_of_dt else as_of_d.isoformat(),
            }
        )
    rows.sort(key=lambda r: (r["year_month"], r["channel_group"], r["channel"]))
    return rows


def monthly_headline_rows(df: pd.DataFrame, as_of: date) -> List[Dict[str, Any]]:
    if df is None or df.empty:
        return []
    work = df.dropna(subset=["Day"]).copy()
    work["year_month"] = work["Day"].dt.strftime("%Y-%m")
    out: List[Dict[str, Any]] = []
    for year_month, part in work.groupby("year_month"):
        y_str, m_str = str(year_month).split("-")
        last = calendar.monthrange(int(y_str), int(m_str))[1]
        period_end = date(int(y_str), int(m_str), last)
        metrics = aggregate_amer_metrics(part)
        as_of_dt = _period_as_of(part)
        as_of_d = as_of_dt.date() if as_of_dt else as_of
        row = _with_provisional(metrics, period_end, as_of_d, as_of_dt)
        row["year_month"] = str(year_month)
        out.append(row)
    out.sort(key=lambda r: r["year_month"])
    return out


def observed_taxonomy(df: pd.DataFrame) -> Dict[str, Any]:
    groups: List[Dict[str, Any]] = []
    if df is not None and not df.empty:
        g = (
            df.groupby(["ChannelGroup", "bucket"], dropna=False)["Channel"]
            .apply(lambda s: sorted({str(x) for x in s.dropna()}))
            .reset_index(name="channels")
        )
        for _, row in g.iterrows():
            groups.append(
                {
                    "group": str(row["ChannelGroup"]),
                    "bucket": str(row["bucket"]),
                    "channels": list(row["channels"]),
                }
            )
        groups.sort(key=lambda r: (r["bucket"], r["group"]))
    return {
        "paid_groups": sorted(PAID_GROUPS),
        "organic_groups": sorted(ORGANIC_GROUPS),
        "unattributed_groups": sorted(UNATTRIBUTED_GROUPS),
        "observed_groups": groups,
        "notes": (
            "PAID inferred from live W36 Channel values Facebook→meta, TikTok→tiktok, "
            "Google→sem, CJ→affiliate, plus SEM/affiliate/display aliases. ORGANIC and "
            "UNATTRIBUTED follow the spec. Unknown ChannelGroups are bucketed as other "
            "and shown separately — they are not dropped and not folded into organic. "
            "totalRevenue = paid + organic + unattributed (other is extra)."
        ),
    }


def _scan_customer_files(data_root: Path) -> List[Path]:
    raw = Path(data_root) / "raw"
    if not raw.exists():
        return []
    files = [
        f
        for f in raw.glob(f"*/{SHOPIFY_CUSTOMERS_TYPE}/*.*")
        if f.suffix.lower() == ".csv" and not f.name.startswith(".")
    ]
    files.sort(key=lambda p: p.stat().st_mtime)
    return files


def load_shopify_customer_orders(data_root: Path) -> pd.DataFrame:
    """Load accumulated Shopify customer-order history (customer id + order date)."""
    frames: List[pd.DataFrame] = []
    for path in _scan_customer_files(data_root):
        try:
            df = _load_one_csv(path)
        except Exception as exc:
            logger.warning(f"Skipping Shopify customer file {path}: {exc}")
            continue
        cust = _pick_column(
            df,
            [
                "Customer ID",
                "customer_id",
                "Customer id",
                "Customer",
                "Email",
                "Customer Email",
                "customer_email",
            ],
        )
        day = _pick_column(
            df,
            [
                "Created at",
                "Order Date",
                "Order date",
                "Processed at",
                "Day",
                "Date",
                "created_at",
            ],
        )
        if not cust or not day:
            logger.warning(
                f"Shopify customer file {path.name} missing customer/date columns: {list(df.columns)}"
            )
            continue
        part = pd.DataFrame(
            {
                "customer_id": df[cust].astype(str).str.strip(),
                "order_date": _parse_day(df[day]),
            }
        )
        part = part[part["customer_id"].ne("") & part["customer_id"].ne("nan")]
        part = part.dropna(subset=["order_date"])
        frames.append(part)
    if not frames:
        return pd.DataFrame(columns=["customer_id", "order_date"])
    out = pd.concat(frames, ignore_index=True)
    out["order_date"] = pd.to_datetime(out["order_date"], errors="coerce").dt.normalize()
    out = out.dropna(subset=["order_date"])
    cutoff = pd.Timestamp(CUSTOMER_HISTORY_START)
    return out[out["order_date"] >= cutoff].drop_duplicates(["customer_id", "order_date"])


def recruited_vs_dropped(orders: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Recruited in month M = earliest order since 2022-01-01 falls in M.
    Dropped in month M = most recent order was in the calendar month exactly 12
    months before M, with no order since (implied by last-order month).
    Recomputed independently for each month (forward).
    """
    if orders is None or orders.empty:
        return []
    work = orders.copy()
    work["order_month"] = work["order_date"].dt.to_period("M")
    first = work.groupby("customer_id")["order_month"].min().rename("first_month")
    last = work.groupby("customer_id")["order_month"].max().rename("last_month")
    span = pd.concat([first, last], axis=1)

    months = sorted({str(p) for p in work["order_month"].unique()})
    extra = []
    for p in span["last_month"].dropna().unique():
        extra.append(str(p + 12))
    all_months = sorted(set(months) | set(extra))

    recruited_counts = first.value_counts()
    rows: List[Dict[str, Any]] = []
    for ym in all_months:
        period = pd.Period(ym, freq="M")
        recruited = int(recruited_counts.get(period, 0))
        drop_src = period - 12
        dropped = int((span["last_month"] == drop_src).sum())
        rows.append(
            {
                "year_month": str(period),
                "recruited": recruited,
                "dropped": dropped,
                "net": recruited - dropped,
            }
        )
    return rows


def calculate_adjusted_amer(base_week: str, data_root: Path) -> Dict[str, Any]:
    """Build the Adjusted aMER payload for the report page and API."""
    if not validate_iso_week(base_week):
        raise ValueError(f"Invalid ISO week format: {base_week}")

    data_root = Path(data_root)
    week_range = get_week_date_range(base_week)
    week_path = data_root / "raw" / base_week
    files = find_week_amer_files(week_path)
    missing = missing_amer_types(files)

    warnings: List[Dict[str, str]] = []
    footnotes = [
        "Headline Adjusted aMER = paid Revenue_CFA ÷ paid marketing spend.",
        "New-customer Adjusted aMER = paid Revenue_New_MTA ÷ paid marketing spend. "
        "CFA is not split by new/returning, so this ratio is MTA-based and is not the same methodology.",
        "Unattributed revenue is kept separate and is never folded into organic.",
        "Net GM2 = sum(Net gross profit 2) ÷ sum(Net sales) after aggregate — row-level margins are not averaged.",
        "Periods younger than ~6 weeks are provisional: newer agent pulls overwrite stored values.",
    ]

    if missing:
        labels = {
            AMER_REVENUE_TYPE: "Revenue_by_channel_W##.csv",
            AMER_SPEND_TYPE: "Marketing_spend_W##.csv",
            AMER_GM2_TYPE: "Net_GM2_W##.csv",
        }
        pretty = ", ".join(labels[m] for m in missing)
        warnings.append(
            {
                "code": "missing_agent_files",
                "message": (
                    f"No Dema agent file(s) for week {base_week}: {pretty}. "
                    "Check the scheduled agent. Stale files from other weeks are not used "
                    "for this week's headline numbers."
                ),
            }
        )

    revenue = load_revenue_frame(files[AMER_REVENUE_TYPE]) if files[AMER_REVENUE_TYPE] else pd.DataFrame()
    spend = load_spend_frame(files[AMER_SPEND_TYPE]) if files[AMER_SPEND_TYPE] else pd.DataFrame()
    gm2 = load_gm2_frame(files[AMER_GM2_TYPE]) if files[AMER_GM2_TYPE] else pd.DataFrame()

    joined = full_outer_join_amer(revenue, spend, gm2)

    file_mtimes = [datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc) for p in files.values() if p]
    as_of_dt = max(file_mtimes) if file_mtimes else datetime.now(timezone.utc)
    as_of_d = as_of_dt.date()

    week_df = _filter_days(joined, week_range["start"], week_range["end"]) if missing == [] else pd.DataFrame()
    week_end = date.fromisoformat(week_range["end"])
    week_metrics = (
        _with_provisional(
            aggregate_amer_metrics(week_df), week_end, as_of_d, _period_as_of(week_df) or as_of_dt
        )
        if missing == []
        else None
    )

    monthly = monthly_headline_rows(joined, as_of_d) if not joined.empty else []
    by_channel = monthly_channel_rows(joined, as_of_d) if not joined.empty else []

    customer_files = _scan_customer_files(data_root)
    customer_orders = load_shopify_customer_orders(data_root) if customer_files else pd.DataFrame()
    if not customer_files:
        recruited = {
            "available": False,
            "message": (
                "Upload a Shopify customer-order export (customer id + order date) in Settings "
                "under Adjusted aMER. Sessions and Qlik cannot substitute for recruited vs dropped."
            ),
            "months": [],
        }
    else:
        recruited = {
            "available": True,
            "message": None,
            "months": recruited_vs_dropped(customer_orders),
            "order_count": int(len(customer_orders)),
            "customer_count": int(customer_orders["customer_id"].nunique()) if not customer_orders.empty else 0,
        }

    return {
        "base_week": base_week,
        "week_range": week_range,
        "as_of": _iso(as_of_dt),
        "warnings": warnings,
        "missing_files": {k: files[k] is None for k in AMER_DEMA_FILE_TYPES},
        "files": {
            k: {"filename": p.name, "uploaded_at": _iso(datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc))}
            if p
            else None
            for k, p in files.items()
        },
        "taxonomy": observed_taxonomy(joined if not joined.empty else pd.DataFrame()),
        "week": week_metrics,
        "monthly": monthly,
        "monthly_by_channel": by_channel,
        "recruited_vs_dropped": recruited,
        "footnotes": footnotes,
    }
