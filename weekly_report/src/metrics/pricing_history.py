"""Month-named Full Price vs Sale daily history.

Replaces the old all-orders ``*/discounts/*`` weekly exports and the old
``Full_Price_vs_Sale_W40`` / ``Exchanges_W40`` files. Those uploads are
**ignored** (not deleted) so production disk can be cleaned up later.

Read order:
  A) ``weekly_report/data/pricing_type/`` (repo-relative and/or under data_root)
  B) ``data/raw/*/full_price_vs_sale_excl_exchanges/`` — only month-named files
     (and later ISO-week continuation files). Never ``*/discounts/*``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from weekly_report.src.fx_rates import convert_revenue_over_time_to_sek
from weekly_report.src.periods.calculator import get_week_date_range

FILE_TYPE = "full_price_vs_sale_excl_exchanges"

# Required on upload and when ingesting a month file. Subscription Discount and
# Markdown Amount are optional (treated as 0 when missing) so older test CSVs
# still load.
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

EXCL_OPTIONAL_HEADERS: List[Tuple[str, List[str]]] = [
    ("Subscription Discount", ["Subscription Discount", "Subscription discount"]),
    ("Markdown Amount", ["Markdown Amount", "Markdown amount", "Markdown"]),
]

SALE_TYPE_COLS = (
    "_compare_at",
    "_discount_code",
    "_subscription",
    "_both",
    "_price_drop",
)

ATOMIC_MONEY_COLS = (
    "_full",
    "_compare_at",
    "_discount_code",
    "_subscription",
    "_both",
    "_price_drop",
    "_total",
    "_discount_amount",
    "_markdown",
    "_exchange_gross",
    "_exchange_discount",
    "_exchange_net",
)

_METRIC_SUM_COLS = [
    "_full",
    "_compare_at",
    "_discount_code",
    "_subscription",
    "_both",
    "_price_drop",
    "_discounted",
    "_total",
    "_discount_amount",
    "_markdown",
    "_discount",
    "_all_orders_discount",
    "_exchange_orders",
    "_exchange_gross",
    "_exchange_discount",
    "_exchange_net",
]

_MONTH_NUM = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

# january_2025, august_2026_full_exchanges, september_full_26, january_2026_ful_exchanges.
# Do not use \b after the year: "_" is a word char, so august_2026_full_* would miss.
_MONTH_YEAR_RE = re.compile(
    r"(?:^|[^a-z])"
    r"(january|february|march|april|may|june|july|august|september|october|november|december)"
    r"(?:[_-]+full)?"
    r"[_-]+"
    r"((?:20)?\d{2})"
    r"(?!\d)",
    re.IGNORECASE,
)

_NEW_WEEK_RE = re.compile(
    r"(?:week|iso)[_-]?(\d{4})[_-](\d{1,2})\b",
    re.IGNORECASE,
)
_ISO_WEEK_TOKEN_RE = re.compile(r"\b(\d{4})-(\d{2})\b")

# Old weekly / historical names that must never mix into the new calc.
_LEGACY_NAME_RES = (
    re.compile(r"full[_-]?price[_-]?vs[_-]?sale[_-]?w\d+", re.I),
    re.compile(r"exchanges[_-]?w\d+", re.I),
    re.compile(r"exchanges[_-]?historical", re.I),
    re.compile(r"full-price-vs-sale-\d{4}-", re.I),
    re.compile(r"full-price-vs-sale-excl-exchanges", re.I),
    re.compile(r"full_price_vs_sale_w\d+", re.I),
)


def _bundled_data_dir() -> Path:
    # weekly_report/src/metrics/this.py → weekly_report/data/
    return Path(__file__).resolve().parents[2] / "data"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def is_legacy_weekly_filename(name: str) -> bool:
    """True for old W36–W40 weekly Full Price / Exchanges uploads — stop using them."""
    n = Path(name).name
    return any(rx.search(n) for rx in _LEGACY_NAME_RES)


def parse_month_from_filename(name: str) -> Optional[Tuple[int, int]]:
    """Return (year, month) when the filename looks like a calendar month export."""
    if is_legacy_weekly_filename(name):
        return None
    m = _MONTH_YEAR_RE.search(Path(name).stem)
    if not m:
        return None
    month = _MONTH_NUM[m.group(1).lower()]
    raw = m.group(2)
    year = int(raw) if len(raw) == 4 else 2000 + int(raw)
    if year < 2000 or not (1 <= month <= 12):
        return None
    return year, month


def parse_iso_week_from_filename(name: str) -> Optional[str]:
    """ISO week for later weekly continuation files. Legacy weekly names return None."""
    if is_legacy_weekly_filename(name):
        return None
    if parse_month_from_filename(name):
        return None
    stem = Path(name).stem
    m = _NEW_WEEK_RE.search(stem)
    if m:
        y, w = int(m.group(1)), int(m.group(2))
        if 1 <= w <= 53:
            return f"{y}-{w:02d}"
    m = _ISO_WEEK_TOKEN_RE.search(stem)
    if m:
        y, w = int(m.group(1)), int(m.group(2))
        if 1 <= w <= 53:
            return f"{y}-{w:02d}"
    return None


def is_accepted_pricing_filename(name: str) -> bool:
    if Path(name).name.startswith("."):
        return False
    if is_legacy_weekly_filename(name):
        return False
    return parse_month_from_filename(name) is not None or parse_iso_week_from_filename(name) is not None


def _month_bounds(year: int, month: int) -> Tuple[pd.Timestamp, pd.Timestamp]:
    start = pd.Timestamp(year=year, month=month, day=1)
    end = (start + pd.offsets.MonthEnd(0)).normalize()
    return start.normalize(), end


def declared_date_window(name: str) -> Optional[Tuple[pd.Timestamp, pd.Timestamp, str]]:
    """Inclusive [start, end] the file is allowed to contribute, plus kind (month|week)."""
    month = parse_month_from_filename(name)
    if month:
        start, end = _month_bounds(*month)
        return start, end, "month"
    week = parse_iso_week_from_filename(name)
    if week:
        rng = get_week_date_range(week)
        return pd.Timestamp(rng["start"]).normalize(), pd.Timestamp(rng["end"]).normalize(), "week"
    return None


def pricing_type_dirs(data_root: Path) -> List[Path]:
    """Candidate directories for bundled / copied month files (source A)."""
    seen: List[Path] = []
    for d in (
        _bundled_data_dir() / "pricing_type",
        _repo_root() / "weekly_report" / "data" / "pricing_type",
        Path(data_root) / "pricing_type",
        Path(data_root) / "weekly_report" / "data" / "pricing_type",
    ):
        try:
            resolved = d.resolve()
        except OSError:
            continue
        if resolved.is_dir() and resolved not in seen:
            seen.append(resolved)
    return seen


def discover_pricing_files(data_root: Path) -> Tuple[List[Path], List[str]]:
    """Return (accepted files, ignored legacy/non-month names in the excl. slot)."""
    accepted: List[Path] = []
    ignored: List[str] = []
    seen: set = set()

    def _add(path: Path, *, require_month_or_week: bool) -> None:
        if not path.is_file() or path.name.startswith("."):
            return
        key = str(path.resolve()) if path.exists() else str(path)
        if key in seen:
            return
        if require_month_or_week and not is_accepted_pricing_filename(path.name):
            ignored.append(path.name)
            return
        if is_legacy_weekly_filename(path.name):
            ignored.append(path.name)
            return
        if require_month_or_week or is_accepted_pricing_filename(path.name):
            seen.add(key)
            accepted.append(path)

    for folder in pricing_type_dirs(data_root):
        for f in sorted(folder.iterdir(), key=lambda p: p.name.lower()):
            _add(f, require_month_or_week=True)

    raw_root = Path(data_root) / "raw"
    if raw_root.exists():
        for f in sorted(raw_root.glob(f"*/{FILE_TYPE}/*.*"), key=lambda p: p.name.lower()):
            # Slot B: month-named (and later ISO-week) files only. Never discounts/.
            _add(f, require_month_or_week=True)

    return accepted, ignored


def _pick_column(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    from weekly_report.src.metrics.discounts_sales import _pick_column as _pick

    return _pick(df, candidates)


def _to_number(s: pd.Series) -> pd.Series:
    from weekly_report.src.metrics.discounts_sales import _to_number as _num

    return _num(s)


def _read_csv_flexible(file_path: Path, nrows: Optional[int] = None) -> pd.DataFrame:
    from weekly_report.src.metrics.discounts_sales import _read_csv_flexible as _read

    return _read(file_path, nrows=nrows)


def _to_percentage(s: pd.Series) -> pd.Series:
    as_str = s.astype(str).str.replace("\u00a0", " ", regex=False).str.strip()
    as_str = as_str.str.replace("%", "", regex=False)
    as_str = as_str.str.replace(" ", "", regex=False).str.replace(",", ".", regex=False)
    as_str = as_str.replace({"nan": "", "none": "", "nat": ""}, regex=False)
    return pd.to_numeric(as_str, errors="coerce").fillna(0.0)


def missing_excl_exchanges_headers(df: pd.DataFrame) -> List[str]:
    missing: List[str] = []
    for canonical, aliases in EXCL_REQUIRED_HEADERS:
        if _pick_column(df, aliases) is None:
            missing.append(canonical)
    return missing


def inspect_excl_exchanges_upload(file_path: Path) -> Dict[str, Any]:
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
        "optional_headers_present": {
            canonical: _pick_column(df, aliases) is not None
            for canonical, aliases in EXCL_OPTIONAL_HEADERS
        },
        "legacy_weekly_name": is_legacy_weekly_filename(file_path.name),
        "accepted_pricing_filename": is_accepted_pricing_filename(file_path.name),
    }


def _empty_history() -> Dict[str, Any]:
    cols = ["_date", *_METRIC_SUM_COLS, "_full_price_share_pct"]
    return {
        "df": pd.DataFrame(columns=cols),
        "files_used": [],
        "ignored_files": [],
        "fx": {"applied": False},
        "currency": "SEK",
        "has_discount": False,
    }


def _num_col(df: pd.DataFrame, aliases: List[str]) -> pd.Series:
    col = _pick_column(df, aliases)
    if col is None:
        return pd.Series(0.0, index=df.index, dtype="float64")
    return _to_number(df[col])


def _normalize_pricing_frame(
    df: pd.DataFrame,
    *,
    mtime: float,
    filename: str,
) -> pd.DataFrame:
    date_col = _pick_column(df, ["Date", "Day", "Dag", "Datum"])
    if not date_col:
        return pd.DataFrame()

    window = declared_date_window(filename)
    share_col = _pick_column(df, ["Full Price Share %", "Full Price Share"])
    share = _to_percentage(df[share_col]) if share_col else pd.Series(0.0, index=df.index)

    sub = pd.DataFrame()
    sub["_date"] = pd.to_datetime(df[date_col], errors="coerce")
    sub["_full"] = _num_col(df, ["Full Price", "Full price", "Fullpris"])
    sub["_compare_at"] = _num_col(df, ["Compare-at Price Sale", "Compare-at price sale"])
    sub["_discount_code"] = _num_col(df, ["Discount Code / Auto Discount"])
    sub["_subscription"] = _num_col(df, ["Subscription Discount", "Subscription discount"])
    sub["_both"] = _num_col(df, ["Both"])
    sub["_price_drop"] = _num_col(df, ["Price Drop Sale", "Price drop sale"])
    sub["_total"] = _num_col(df, ["Total", "Totalt", "Sum"])
    sub["_discount_amount"] = _num_col(df, ["Discount Amount", "Discount amount"])
    sub["_markdown"] = _num_col(df, ["Markdown Amount", "Markdown amount", "Markdown"])
    sub["_full_price_share_pct"] = share
    sub["_exchange_orders"] = _num_col(df, ["Exchange Orders", "Exchange orders"])
    sub["_exchange_gross"] = _num_col(df, ["Exchange Gross Value", "Exchange Gross"])
    sub["_exchange_discount"] = _num_col(df, ["Exchange Discount"])
    sub["_exchange_net"] = _num_col(df, ["Exchange Net Revenue"])
    sub["_mtime"] = mtime
    sub["_source_file"] = filename
    sub = sub.dropna(subset=["_date"])
    sub["_date"] = pd.to_datetime(sub["_date"], errors="coerce").dt.normalize()
    sub = sub.dropna(subset=["_date"])

    if window is not None:
        start, end, kind = window
        sub = sub[(sub["_date"] >= start) & (sub["_date"] <= end)].copy()
        sub["_period_kind"] = kind
        sub["_priority"] = 2 if kind == "month" else 1
    else:
        # Last-Sunday / drop final 2 export days when we cannot name the period.
        uniq = sorted(sub["_date"].unique())
        if len(uniq) > 2:
            cutoff = pd.Timestamp(uniq[-3])
            sub = sub[sub["_date"] <= cutoff].copy()
        sub["_period_kind"] = "unknown"
        sub["_priority"] = 0

    return sub


def _recompute_derived(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["_discounted"] = (
        out["_compare_at"].fillna(0.0)
        + out["_discount_code"].fillna(0.0)
        + out["_subscription"].fillna(0.0)
        + out["_both"].fillna(0.0)
        + out["_price_drop"].fillna(0.0)
    )
    out["_discount"] = out["_discount_amount"].fillna(0.0) + out["_markdown"].fillna(0.0)
    out["_all_orders_discount"] = out["_discount_amount"].fillna(0.0) + out["_exchange_discount"].fillna(0.0)
    return out


def load_pricing_type_daily_history(data_root: Path) -> Dict[str, Any]:
    """Merge month-named (and later weekly) daily files; own-period dates win.

    Discounted is the explicit sum of sale-type columns (missing = 0), not
    Total − Full Price. Weighted-disc discount = Discount Amount + Markdown.
    """
    files, ignored = discover_pricing_files(data_root)
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
        try:
            mtime = f.stat().st_mtime
        except OSError:
            mtime = 0.0
        sub = _normalize_pricing_frame(df, mtime=mtime, filename=f.name)
        if sub.empty:
            continue
        frames.append(sub)
        files_used.append(f.name)

    if not frames:
        empty = _empty_history()
        empty["ignored_files"] = ignored
        return empty

    alld = pd.concat(frames, ignore_index=True)
    # Prefer the file whose declared month/week actually contains the date
    # (month beats week). Same kind → later mtime.
    alld = alld.sort_values(["_date", "_priority", "_mtime"]).drop_duplicates(
        subset=["_date"], keep="last"
    )
    alld, fx = convert_revenue_over_time_to_sek(
        alld, Path(data_root), extra_money_cols=ATOMIC_MONEY_COLS
    )
    alld = _recompute_derived(alld)
    keep = ["_date", *_METRIC_SUM_COLS, "_full_price_share_pct"]
    alld = alld[keep].sort_values("_date").reset_index(drop=True)
    return {
        "df": alld,
        "files_used": files_used,
        "ignored_files": ignored,
        "fx": fx,
        "currency": fx.get("target_currency", "SEK") if fx.get("applied") else "USD",
        "has_discount": True,
    }


def discounted_sales_sum(row: Dict[str, float]) -> float:
    """Compare-at + discount code + subscription + both + price drop (missing = 0)."""
    return float(
        (row.get("_compare_at") or 0.0)
        + (row.get("_discount_code") or 0.0)
        + (row.get("_subscription") or 0.0)
        + (row.get("_both") or 0.0)
        + (row.get("_price_drop") or 0.0)
    )
