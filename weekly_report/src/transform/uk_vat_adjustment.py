"""Correct UK VAT that Shopify booked as revenue from 29 Sep 2026 to 9 Nov 2026 10:22.

Prices are VAT-inclusive. For each affected UK order (shipping country GB, created
in that window, tax still zero, positive amount) every revenue amount is divided
by 1.2. Order counts, units, customers, COGS, carrier cost, and marketing spend
are left unchanged.

The list of orders is ``weekly_report/data/adjustments/uk_vat_affected_orders.csv``.
This module is the only place that applies the correction. It runs at data load,
before caches and metrics. A second pass is a no-op: rows already flagged
``vat_adjusted`` and orders that now have tax booked are not divided again.

Qlik check: no extract containing order #100288154 is in this repository, so it
is not proven whether Qlik stored the VAT-inclusive amount. Top Markets and
Audience read Qlik gross and net, which is the revenue the reports overstated,
so Qlik is adjusted together with Shopify and Dema. Set ``QLIK_INCLUDES_UK_VAT``
to False if an export shows Qlik is already ex-VAT.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

import pandas as pd
from loguru import logger

VAT_FACTOR = 1.2
NOTE = "UK revenue adjusted for missing VAT (orders over £135, 29 Sep to 9 Nov 2026)."

# See module docstring. Reports read Qlik, and the missing export could not confirm ex-VAT.
QLIK_INCLUDES_UK_VAT = True

WINDOW_START = datetime(2026, 9, 29, 0, 0, tzinfo=ZoneInfo("Europe/Stockholm"))
WINDOW_END = datetime(2026, 11, 9, 10, 22, tzinfo=ZoneInfo("Europe/Stockholm"))
WINDOW_DATES = (WINDOW_START.date(), WINDOW_END.date())

_UK_LABELS = {
    "united kingdom",
    "uk",
    "u.k.",
    "gb",
    "g.b.",
    "great britain",
    "britain",
    "storbritannien",
    "united kingdom of great britain and northern ireland",
}

_ORDER_COLUMNS = (
    "Order No",
    "Order No.",
    "Order number",
    "Order Number",
    "Ordernummer",
    "Order name",
    "Order Name",
    "order_name",
    "Order ID",
    "Order Id",
    "Order Id.",
    "Order Ref",
    "Order",
    "Beställning",
    "Bestallning",
    "Name",
)

_COUNTRY_COLUMNS = (
    "Shipping Country",
    "Shipping country",
    "Ship Country",
    "Ship country",
    "Country",
    "Land",
    "Market",
    "Delivery Country",
    "Country/Region",
)

_DATE_COLUMNS = (
    "Created at",
    "Created At",
    "order_created_at",
    "Date",
    "Day",
    "Days",
    "Dag",
    "Datum",
)

_TAX_COLUMNS = (
    "Taxes",
    "Tax",
    "VAT",
    "VAT Amount",
    "Tax amount",
    "Total tax",
    "Returns VAT",
)

# Loaded in addition to the caller's Qlik columns so the match can run, then dropped.
QLIK_MATCH_COLUMNS = (
    "Order No",
    "Order Ref",
    "Order Id",
    "Order name",
    "Country",
    "Date",
    "Taxes",
    "VAT Amount",
    "Tax",
)

_REVENUE_PHRASES = (
    "gross revenue",
    "net revenue",
    "gross sales",
    "net sales",
    "discount",
    "returns",
    "return amount",
    "exchange",
    "shipping revenue",
    "freight revenue",
    "total sales",
    "revenue usd",
    "revenueusd",
    "revenue sek",
    "revenuesek",
    "revenue eur",
    "revenueeur",
    "revenue gbp",
    "revenuegbp",
    "revenue cfa",
    "revenue mta",
    "subtotal",
    "total sales",
)

_REVENUE_EXACT = {"shipping", "freight", "discounts", "returns", "subtotal"}

_EXCLUDE_TOKENS = (
    "cogs",
    "cost",
    "spend",
    "qty",
    "quantity",
    "units",
    "unit price",
    "sessions",
    "session",
    "tax",
    "vat",
    "budget",
    "margin",
    "profit",
    "gm2",
    "gm3",
    "gp2",
    "gp3",
    "customer",
    "count",
    "orders",
    "aov",
    "cac",
    "amer",
    "impressions",
    "clicks",
)

_lock = threading.Lock()
_orders_cache: Optional[Tuple[str, int, Dict[str, Dict[str, Any]]]] = None
_daily_shares: Dict[date, float] = {}
_share_weight: Dict[date, int] = {}


def affected_orders_csv_path() -> Path:
    override = (os.getenv("UK_VAT_AFFECTED_ORDERS_CSV") or "").strip()
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / "data" / "adjustments" / "uk_vat_affected_orders.csv"


def adjustment_cache_token() -> str:
    """Changes result-cache keys when the switch or the order list changes."""
    if not adjustment_enabled():
        return "ukvat:off"
    path = affected_orders_csv_path()
    if not path.exists():
        return "ukvat:on:missing"
    stat = path.stat()
    mtime = getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1e9))
    return f"ukvat:on:{stat.st_size}:{mtime}"


def _override_path() -> Path:
    root = Path(os.getenv("DATA_ROOT", "data"))
    return root / "uk_vat_adjustment.json"


def adjustment_enabled() -> bool:
    """ADJUST_UK_VAT defaults to true. A Settings toggle writes a local override."""
    path = _override_path()
    if path.is_file():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict) and "enabled" in payload:
                return bool(payload["enabled"])
        except (OSError, json.JSONDecodeError, TypeError):
            logger.warning("UK VAT override file is unreadable; using ADJUST_UK_VAT")
    raw = os.getenv("ADJUST_UK_VAT", "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def set_adjustment_enabled(enabled: bool, data_root: Optional[Path] = None) -> None:
    os.environ["ADJUST_UK_VAT"] = "true" if enabled else "false"
    root = Path(data_root) if data_root is not None else Path(os.getenv("DATA_ROOT", "data"))
    path = root / "uk_vat_adjustment.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"enabled": bool(enabled)}), encoding="utf-8")
    clear_runtime_state()


def clear_runtime_state() -> None:
    """Drop cached order ids and day shares. Tests and the Settings toggle use this."""
    global _orders_cache
    with _lock:
        _orders_cache = None
        _daily_shares.clear()
        _share_weight.clear()


def _normalize_order_id(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "<na>"}:
        return ""
    text = text.replace("#", "").replace(" ", "")
    if text.endswith(".0"):
        text = text[:-2]
    return text


def _norm_header(name: Any) -> str:
    return " ".join(str(name).strip().strip('"').strip("'").lower().replace("_", " ").split())


def _pick(df: pd.DataFrame, candidates: Sequence[str]) -> Optional[str]:
    if df is None or df.empty and (df is None or len(df.columns) == 0):
        return None
    lookup = {_norm_header(col): col for col in df.columns}
    for candidate in candidates:
        found = lookup.get(_norm_header(candidate))
        if found is not None:
            return str(found)
    return None


def _money(series: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")
    text = series.astype(str).str.replace("\u00a0", "", regex=False).str.replace(" ", "", regex=False)
    text = text.str.replace(",", ".", regex=False)
    return pd.to_numeric(text, errors="coerce")


def _has_word(header: str, token: str) -> bool:
    return f" {token} " in f" {header} "


def _is_revenue_column(name: Any) -> bool:
    header = _norm_header(name)
    if not header or header.startswith("_") or header in {"vat adjusted", "iso week"}:
        return False
    # Word match so "count" does not treat "discounts" as a count column.
    if any(_has_word(header, token) for token in _EXCLUDE_TOKENS):
        return False
    if header in _REVENUE_EXACT:
        return True
    return any(phrase in header for phrase in _REVENUE_PHRASES)


def _is_profit_column(name: Any) -> bool:
    header = _norm_header(name)
    if any(token in header for token in ("margin", "%", "pct", "percent")):
        return False
    return any(token in header for token in ("profit", "gm2", "gm 2", "gp2", "gp 2", "gp3", "gp 3"))


def _is_margin_column(name: Any) -> bool:
    header = _norm_header(name)
    return any(token in header for token in ("margin", "gm2 %", "gp2 %", "gp3 %")) or header.endswith(" pct") or "%" in header


def _is_uk(value: Any) -> bool:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return False
    return str(value).strip().lower() in _UK_LABELS


def _parse_created_at(value: Any) -> Optional[datetime]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, time.min)
    else:
        text = str(value).strip()
        if not text or text.lower() in {"nan", "none", "nat"}:
            return None
        parsed_ts = pd.to_datetime(text, errors="coerce", utc=False)
        if pd.isna(parsed_ts):
            return None
        parsed = parsed_ts.to_pydatetime()
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=WINDOW_START.tzinfo)
    else:
        parsed = parsed.astimezone(WINDOW_START.tzinfo)
    return parsed


def in_created_window(value: Any) -> bool:
    parsed = _parse_created_at(value)
    if parsed is None:
        return False
    return WINDOW_START <= parsed <= WINDOW_END


def load_affected_orders() -> Dict[str, Dict[str, Any]]:
    """Map normalised order id -> csv row. Empty when the file is missing or header-only."""
    global _orders_cache
    path = affected_orders_csv_path()
    if not path.is_file():
        return {}
    stat = path.stat()
    mtime = getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1e9))
    key = f"{path.resolve()}:{mtime}:{stat.st_size}"
    with _lock:
        if _orders_cache and _orders_cache[0] == key:
            return _orders_cache[2]
    frame = pd.read_csv(path, dtype=str).fillna("")
    orders: Dict[str, Dict[str, Any]] = {}
    if "order_name" not in frame.columns:
        with _lock:
            _orders_cache = (key, mtime, orders)
        return orders
    for record in frame.to_dict(orient="records"):
        order_id = _normalize_order_id(record.get("order_name"))
        if not order_id:
            continue
        try:
            gross = float(str(record.get("gross_sales") or "0").replace(",", "") or 0)
        except ValueError:
            gross = 0.0
        orders[order_id] = {
            "order_name": str(record.get("order_name") or ""),
            "order_created_at": str(record.get("order_created_at") or ""),
            "shipping_country": str(record.get("shipping_country") or ""),
            "gross_sales": gross,
            "taxes": str(record.get("taxes") or ""),
            "vat_factor": VAT_FACTOR,
        }
    with _lock:
        _orders_cache = (key, mtime, orders)
    return orders


def adjustment_active() -> bool:
    return adjustment_enabled() and bool(load_affected_orders()) and True


def _order_column(df: pd.DataFrame) -> Optional[str]:
    chosen = _pick(df, _ORDER_COLUMNS[:-1])
    if chosen:
        return chosen
    # Bare "Name" is the Shopify order name only on an orders export.
    if _pick(df, ("Created at",)) and _pick(df, ("Shipping Country", "Shipping country")):
        return _pick(df, ("Name",))
    return None


def _already_adjusted_mask(df: pd.DataFrame) -> pd.Series:
    if "vat_adjusted" not in df.columns:
        return pd.Series(False, index=df.index)
    flag = df["vat_adjusted"]
    if flag.dtype == bool:
        return flag.fillna(False)
    return flag.astype(str).str.strip().str.lower().isin({"1", "true", "yes", "t"})


def _taxed_order_ids(df: pd.DataFrame, order_ids: pd.Series) -> set:
    tax_col = _pick(df, _TAX_COLUMNS)
    if not tax_col:
        return set()
    tax = _money(df[tax_col]).fillna(0.0)
    return set(order_ids.loc[tax > 0.004].tolist())


def _revenue_columns(df: pd.DataFrame) -> List[str]:
    return [str(col) for col in df.columns if _is_revenue_column(col)]


def _register_shares(
    df: pd.DataFrame,
    affected: pd.Series,
    revenue_col: str,
) -> None:
    """UK-day share = overstatement / unadjusted UK revenue. Same ratio in any currency.

    Numerator uses affected rows dated inside the window (the original sale, not a
    later return). Denominator is all UK revenue that calendar day. ``1 - share``
    equals ``1 / 1.2`` when every UK pound that day is affected.
    """
    country_col = _pick(df, _COUNTRY_COLUMNS)
    date_col = _pick(df, _DATE_COLUMNS)
    if not country_col or not date_col or revenue_col not in df.columns:
        return
    dates = pd.to_datetime(df[date_col], errors="coerce")
    uk = df[country_col].map(_is_uk)
    revenue = _money(df[revenue_col]).fillna(0.0)
    work = pd.DataFrame(
        {
            "day": dates.dt.date,
            "uk": uk.fillna(False).to_numpy(),
            "affected": affected.fillna(False).to_numpy(),
            "revenue": revenue.to_numpy(),
        }
    )
    work = work.dropna(subset=["day"])
    if work.empty:
        return
    start, end = WINDOW_DATES
    in_window = work["day"].map(lambda day: start <= day <= end)
    with _lock:
        for day, part in work.groupby("day"):
            if not (start <= day <= end):
                continue
            uk_part = part.loc[part["uk"]]
            uk_total = float(uk_part["revenue"].sum())
            if uk_total == 0:
                continue
            affected_part = uk_part.loc[uk_part["affected"] & in_window.loc[uk_part.index]]
            overstatement = float(affected_part["revenue"].sum()) / 6.0
            share = overstatement / uk_total
            weight = int(len(uk_part))
            previous = _share_weight.get(day, -1)
            if weight >= previous:
                _daily_shares[day] = share
                _share_weight[day] = weight


def _primary_revenue_column(df: pd.DataFrame) -> Optional[str]:
    columns = _revenue_columns(df)
    if not columns:
        return None
    preferred = (
        "gross revenue",
        "gross sales",
        "net revenue",
        "net sales",
        "subtotal",
        "total sales",
    )
    lookup = {_norm_header(col): col for col in columns}
    for phrase in preferred:
        if phrase in lookup:
            return lookup[phrase]
    return columns[0]


def adjust_order_level(df: pd.DataFrame, *, source: str, register_shares: bool) -> pd.DataFrame:
    if df is None or df.empty or not adjustment_active():
        return df
    if source == "qlik" and not QLIK_INCLUDES_UK_VAT:
        return df
    order_col = _order_column(df)
    if not order_col:
        return adjust_day_level(df, recompute_margin=source in {"dema_gm2", "gm2"})
    orders = load_affected_orders()
    out = df.copy()
    order_ids = out[order_col].map(_normalize_order_id)
    affected = order_ids.isin(orders.keys()) & ~_already_adjusted_mask(out)
    taxed = _taxed_order_ids(out, order_ids)
    if taxed:
        affected = affected & ~order_ids.isin(taxed)
    money_cols = _revenue_columns(out)
    if not money_cols or not bool(affected.any()):
        return df
    revenue_col = _primary_revenue_column(out)
    if register_shares and revenue_col:
        _register_shares(out, affected, revenue_col)
    for column in money_cols:
        values = _money(out[column])
        out[column] = values
        out.loc[affected, column] = values.loc[affected] / VAT_FACTOR
    flag = _already_adjusted_mask(out)
    out["vat_adjusted"] = flag | affected
    logger.info(
        "UK VAT adjusted {} {} rows on {} ({} revenue columns)",
        source,
        int(affected.sum()),
        order_col,
        len(money_cols),
    )
    return out


def _shares() -> Dict[date, float]:
    with _lock:
        return dict(_daily_shares)


def adjust_day_level(df: pd.DataFrame, *, recompute_margin: bool) -> pd.DataFrame:
    """Scale UK revenue on each window day by ``1 - share``. Costs and spend stay put.

    GM2/GP2/GP3 are recomputed as adjusted revenue minus the original cost
    (original revenue minus original profit), not multiplied by the share.
    """
    if df is None or df.empty or not adjustment_enabled():
        return df
    shares = _shares()
    if not shares:
        return df
    country_col = _pick(df, _COUNTRY_COLUMNS)
    date_col = _pick(df, _DATE_COLUMNS)
    if not country_col or not date_col:
        return df
    out = df.copy()
    dates = pd.to_datetime(out[date_col], errors="coerce")
    days = dates.dt.date
    start, end = WINDOW_DATES
    in_window = days.map(lambda day: bool(day) and start <= day <= end if day == day else False)
    # ``day == day`` is False for NaT-like None already handled by bool(day).
    uk = out[country_col].map(_is_uk).fillna(False)
    factor = days.map(lambda day: 1.0 - shares.get(day, 0.0) if isinstance(day, date) else 1.0)
    mask = uk & in_window.fillna(False) & (factor < 0.999999) & ~_already_adjusted_mask(out)
    if not bool(mask.any()):
        return df
    money_cols = _revenue_columns(out)
    profit_cols = [str(col) for col in out.columns if _is_profit_column(col)]
    margin_cols = [str(col) for col in out.columns if _is_margin_column(col)]
    primary = _primary_revenue_column(out)
    old_revenue = _money(out[primary]).fillna(0.0) if primary else None
    old_profits = {col: _money(out[col]).fillna(0.0) for col in profit_cols}
    old_margins = {col: _money(out[col]) for col in margin_cols}
    for column in money_cols:
        values = _money(out[column])
        out[column] = values
        out.loc[mask, column] = values.loc[mask] * factor.loc[mask]
    if recompute_margin and primary and old_revenue is not None:
        new_revenue = _money(out[primary]).fillna(0.0)
        for column, old_profit in old_profits.items():
            cost = old_revenue - old_profit
            recomputed = new_revenue - cost
            out.loc[mask, column] = recomputed.loc[mask]
        new_profit = None
        if profit_cols:
            new_profit = _money(out[profit_cols[0]]).fillna(0.0)
        for column, old_margin in old_margins.items():
            if new_profit is not None:
                ratio = new_profit / new_revenue.replace(0, pd.NA)
            else:
                fraction = old_margin.where(old_margin.abs() <= 1.5, old_margin / 100.0)
                cost = old_revenue * (1.0 - fraction.fillna(0.0))
                ratio = (new_revenue - cost) / new_revenue.replace(0, pd.NA)
            sample = old_margin.dropna()
            as_percent = bool(len(sample) and float(sample.abs().median()) > 1.5)
            written = ratio * (100.0 if as_percent else 1.0)
            out.loc[mask, column] = written.loc[mask]
    flag = _already_adjusted_mask(out)
    out["vat_adjusted"] = flag | mask
    logger.info("UK VAT day-level adjusted {} rows", int(mask.sum()))
    return out


def adjust_qlik(df: pd.DataFrame) -> pd.DataFrame:
    if not QLIK_INCLUDES_UK_VAT:
        return df
    return adjust_order_level(df, source="qlik", register_shares=True)


def adjust_shopify(df: pd.DataFrame) -> pd.DataFrame:
    return adjust_order_level(df, source="shopify", register_shares=True)


def adjust_dema(df: pd.DataFrame) -> pd.DataFrame:
    """Day-level Dema revenue. Marketing spend and other cost columns are not scaled."""
    if _order_column(df):
        return adjust_order_level(df, source="dema", register_shares=False)
    return adjust_day_level(df, recompute_margin=False)


def adjust_dema_gm2(df: pd.DataFrame) -> pd.DataFrame:
    if _order_column(df):
        return adjust_order_level(df, source="dema_gm2", register_shares=False)
    return adjust_day_level(df, recompute_margin=True)


def adjust_other(df: pd.DataFrame) -> pd.DataFrame:
    """Other uploads: order-level when an order id exists, otherwise UK day share."""
    if _order_column(df):
        return adjust_order_level(df, source="other", register_shares=False)
    return adjust_day_level(df, recompute_margin=True)


def adjust_loaded_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Used by direct CSV readers that bypass the adapters (discounts, aMER inputs)."""
    if df is None or getattr(df, "empty", True):
        return df
    if _order_column(df):
        return adjust_order_level(df, source="frame", register_shares=False)
    if _pick(df, _COUNTRY_COLUMNS) and _pick(df, _DATE_COLUMNS) and _revenue_columns(df):
        return adjust_day_level(df, recompute_margin=_pick(df, ("Net gross profit 2", "GM2", "GP2", "GP3")) is not None)
    return df


def reporting_week_uses_adjustment(iso_week: str) -> bool:
    """True when a page opened on this ISO week can show 29 Sep–9 Nov 2026.

    Covers the week itself, an 8-week lookback, month-to-date, quarter-to-date,
    year-to-date, and the last-year column (so 2027-W40 still qualifies).
    """
    try:
        year_text, week_text = iso_week.split("-")
        year, week = int(year_text), int(week_text)
    except (ValueError, AttributeError):
        return False
    monday = _iso_monday(year, week)
    if monday is None:
        return False
    sunday = monday + timedelta(days=6)
    ranges = [
        (monday, sunday),
        (monday - timedelta(weeks=7), sunday),
        (_iso_monday(year - 1, week), _iso_monday(year - 1, week) + timedelta(days=6))
        if _iso_monday(year - 1, week)
        else None,
        (date(year, monday.month, 1), sunday),
        (date(year, ((monday.month - 1) // 3) * 3 + 1, 1), sunday),
        (date(year, 1, 1), sunday),
    ]
    start, end = WINDOW_DATES
    for item in ranges:
        if item is None or item[0] is None:
            continue
        if item[0] <= end and item[1] >= start:
            return True
    return False


def note_for_week(iso_week: Optional[str]) -> Optional[str]:
    if not iso_week or not adjustment_enabled():
        return None
    if reporting_week_uses_adjustment(iso_week):
        return NOTE
    return None


def _iso_monday(year: int, week: int) -> Optional[date]:
    if week < 1 or week > 53:
        return None
    try:
        return date.fromisocalendar(year, week, 1)
    except ValueError:
        return None


def adjustment_summary() -> Dict[str, Any]:
    """Settings payload: switch, order count, gross removed per ISO week and in total."""
    orders = load_affected_orders()
    weeks: Dict[str, Dict[str, float]] = {}
    for row in orders.values():
        created = _parse_created_at(row.get("order_created_at"))
        if created is None:
            label = "unknown"
        else:
            iso = created.isocalendar()
            label = f"{iso.year}-{iso.week:02d}"
        bucket = weeks.setdefault(label, {"orders": 0, "gross_removed": 0.0})
        bucket["orders"] += 1
        bucket["gross_removed"] += float(row.get("gross_sales") or 0.0) / 6.0
    week_rows = [
        {
            "week": week,
            "orders": int(values["orders"]),
            "gross_removed": round(values["gross_removed"], 2),
        }
        for week, values in sorted(weeks.items())
    ]
    return {
        "enabled": adjustment_enabled(),
        "qlik_adjusted": QLIK_INCLUDES_UK_VAT,
        "order_count": len(orders),
        "gross_removed": round(sum(row["gross_removed"] for row in week_rows), 2),
        "weeks": week_rows,
        "source": str(affected_orders_csv_path()),
        "note": NOTE,
        "reference": {
            "expected_orders": 178,
            "expected_gross_reduction_usd": 12368,
            "expected_net_reduction_usd": 11558,
        },
    }


def overlapping_base_weeks() -> List[str]:
    """Weeks whose stored metrics include the window or compare against it in 2027."""
    weeks: List[str] = []
    for year, start, end in ((2026, 40, 52), (2027, 40, 46)):
        for number in range(start, end + 1):
            label = f"{year}-{number:02d}"
            if reporting_week_uses_adjustment(label):
                weeks.append(label)
    return weeks


def invalidate_local_caches(data_root: Path) -> Dict[str, Any]:
    """Drop computed caches. Source parquet/CSV stays; the next load re-applies the rule.

    Parquet under the week folders is the uploaded source, not a derived result.
    Deleting it would remove the only copy of a week. Adjustment runs after the
    read, and ``vat_adjusted`` stops a second division if a file was already flagged.
    """
    from weekly_report.src.cache.manager import metrics_cache, raw_data_cache

    removed: List[str] = []
    cache_dir = Path(data_root) / "cache"
    if cache_dir.exists():
        for path in cache_dir.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".json", ".pkl", ".tmp", ".parquet"}:
                continue
            path.unlink()
            removed.append(str(path))
    raw_data_cache.clear()
    metrics_cache.clear()
    clear_runtime_state()
    return {
        "removed": removed,
        "removed_count": len(removed),
        "memory_caches_cleared": True,
        "source_parquet_kept": True,
        "weeks": overlapping_base_weeks(),
    }


def invalidate_supabase_overlapping() -> Dict[str, Any]:
    """Delete stored weekly metrics for weeks that include this VAT window.

    No-op when Supabase is not configured. Callers recompute on the next sync;
    this does not upload replacement figures.
    """
    weeks = overlapping_base_weeks()
    try:
        from weekly_report.src.adapters.supabase_client import get_supabase_client
    except Exception as exc:  # pragma: no cover - import guard
        return {"ran": False, "reason": str(exc), "weeks": weeks}
    client = get_supabase_client()
    if not client:
        return {
            "ran": False,
            "reason": "Supabase client is not configured (SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY).",
            "weeks": weeks,
        }
    deleted: List[str] = []
    errors: List[str] = []
    for week in weeks:
        try:
            client.table("weekly_report_metrics").delete().eq("base_week", week).execute()
            deleted.append(week)
        except Exception as exc:
            errors.append(f"{week}: {exc}")
    return {"ran": True, "deleted": deleted, "errors": errors, "weeks": weeks}


def iter_money_columns(columns: Iterable[Any]) -> List[str]:
    return [str(column) for column in columns if _is_revenue_column(column)]


def rows_from_orders_export(frame: pd.DataFrame) -> List[Dict[str, Any]]:
    """One row per order from a Shopify orders export or a Qlik extract.

    Shopify exports repeat line items. Order-level Name, Created at, Shipping
    Country, Subtotal and Taxes sit on the first line; later lines are ignored.
    """
    if frame is None or frame.empty:
        return []
    work = frame.copy()
    work.columns = [str(col).strip() for col in work.columns]
    order_col = _order_column(work)
    created_col = _pick(work, ("Created at", "Created At", "order_created_at", "Date", "Day"))
    country_col = _pick(work, _COUNTRY_COLUMNS)
    gross_col = _pick(
        work,
        ("Subtotal", "Gross sales", "Gross Sales", "Gross Revenue", "Total", "total_sales"),
    )
    tax_col = _pick(work, _TAX_COLUMNS)
    if not order_col or not created_col or not country_col or not gross_col:
        return []
    work["_order_key"] = work[order_col].map(_normalize_order_id)
    work = work.loc[work["_order_key"].ne("")].copy()
    if work.empty:
        return []
    first = work.groupby("_order_key", sort=False, as_index=False).head(1)
    rows: List[Dict[str, Any]] = []
    for record in first.to_dict(orient="records"):
        if not _is_uk(record.get(country_col)):
            continue
        if not in_created_window(record.get(created_col)):
            continue
        tax = _money(pd.Series([record.get(tax_col)])).iloc[0] if tax_col else 0.0
        if pd.isna(tax):
            tax = 0.0
        if float(tax) > 0.004:
            continue
        gross = _money(pd.Series([record.get(gross_col)])).iloc[0]
        if pd.isna(gross) or float(gross) <= 0:
            continue
        created = _parse_created_at(record.get(created_col))
        rows.append(
            {
                "order_name": str(record.get(order_col) or "").strip(),
                "order_created_at": created.strftime("%Y-%m-%d %H:%M:%S%z") if created else "",
                "shipping_country": "United Kingdom",
                "gross_sales": round(float(gross), 2),
                "taxes": 0,
                "vat_factor": VAT_FACTOR,
            }
        )
    rows.sort(key=lambda row: (row["order_created_at"], row["order_name"]))
    return rows


def write_affected_orders_csv(rows: Sequence[Mapping[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(
        list(rows),
        columns=["order_name", "order_created_at", "shipping_country", "gross_sales", "taxes", "vat_factor"],
    )
    frame.to_csv(path, index=False)
