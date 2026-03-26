"""Discounts metrics (discounted vs full price) based on uploaded Discounts data."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from weekly_report.src.periods.calculator import get_week_date_range


def _read_csv_flexible(file_path: Path, nrows: Optional[int] = None) -> pd.DataFrame:
    """
    Read CSV robustly.
    Important: pandas can "succeed" with the wrong separator and return a single giant column.
    We treat that as a parse failure and retry with other separators.
    """
    # Try common separators/encodings
    for sep in [";", ","]:
        for enc in ["utf-8", "latin-1"]:
            try:
                df = pd.read_csv(file_path, sep=sep, encoding=enc, nrows=nrows, quotechar='"')
                # Detect wrong-separator parse (single column with delimiter characters in header)
                if len(df.columns) == 1:
                    header = str(df.columns[0])
                    if (sep == ";" and "," in header) or (sep == "," and ";" in header):
                        raise ValueError("Likely wrong separator (single column header contains other delimiter)")
                return df
            except Exception:
                pass
    # Fallback
    return pd.read_csv(file_path, nrows=nrows, quotechar='"')


def _normalize_col(col: str) -> str:
    return str(col).strip().strip('"').strip("'").lower()


def _pick_column(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    norm_to_actual = {_normalize_col(c): c for c in df.columns}
    for cand in candidates:
        if _normalize_col(cand) in norm_to_actual:
            return norm_to_actual[_normalize_col(cand)]
    return None


def _iso_week_series(dt: pd.Series) -> pd.Series:
    iso = dt.dt.isocalendar()
    return iso["year"].astype(int).astype(str) + "-" + iso["week"].astype(int).map(lambda w: f"{w:02d}")


def _build_display_weeks(base_week: str, n: int) -> List[str]:
    """Build last N ISO weeks ending at base_week, skipping week 53 (business reporting expects 52-week years)."""
    y_str, w_str = base_week.split("-")
    y = int(y_str)
    w = int(w_str)
    out: List[str] = []
    cur_y, cur_w = y, w
    while len(out) < n:
        if cur_w == 53:
            cur_w = 52
        out.append(f"{cur_y}-{cur_w:02d}")
        cur_w -= 1
        if cur_w < 1:
            cur_y -= 1
            cur_w = 52
    return sorted(out)

def _parse_iso_week(w: str) -> Optional[Tuple[int, int]]:
    try:
        y_str, ww = str(w).split("-")
        return int(y_str), int(ww)
    except Exception:
        return None


def _sort_iso_weeks(weeks: List[str]) -> List[str]:
    parsed: List[Tuple[int, int, str]] = []
    for w in weeks:
        p = _parse_iso_week(w)
        if not p:
            continue
        y, ww = p
        # Skip week 53 for reporting consistency
        if ww == 53:
            continue
        parsed.append((y, ww, f"{y}-{ww:02d}"))
    parsed.sort(key=lambda t: (t[0], t[1]))
    return [t[2] for t in parsed]


def _to_number(s: pd.Series) -> pd.Series:
    # Handle Swedish decimals/formatting
    as_str = s.astype(str).str.replace("\u00a0", " ", regex=False).str.replace(" ", "", regex=False)
    # If values include comma decimals, convert to dot; if include both, strip thousands
    as_str = as_str.str.replace(",", ".", regex=False)
    return pd.to_numeric(as_str, errors="coerce").fillna(0.0)


def calculate_discount_sales_for_weeks(base_week: str, num_weeks: int, data_root: Path) -> Dict[str, Any]:
    """
    Returns discounted vs full price net sales per ISO week for last N weeks.

    Business rule:
    - If 'Produktvariantens ordinare pris' > 0 => discounted (net sales)
    - If == 0 => full price (net sales)
    """
    raw_path = Path(data_root) / "raw" / base_week / "discounts"
    files = [f for f in raw_path.glob("*.*") if not f.name.startswith(".")]
    if not files:
        return {"base_week": base_week, "num_weeks": num_weeks, "weeks": []}

    latest_file = max(files, key=lambda f: f.stat().st_mtime)
    df = _read_csv_flexible(latest_file)
    df.columns = [c.strip().replace('"', "") for c in df.columns]

    # Column detection (supports Swedish/English variants)
    date_col = _pick_column(df, ["Date", "Day", "Dag"])
    net_sales_col = _pick_column(
        df,
        [
            "Net Revenue",
            "Nettoförsäljning",
            "Nettoförsäljning (SEK)",
            "Net sales",
            "Net sales amount",
            "Net amount",
        ],
    )
    ordinary_price_col = _pick_column(
        df,
        [
            "Produktvariantens ordinare pris",
            "Produktvariantens ordinarie pris",
            "Ordinarie pris",
            "Ordinare pris",
            "Variant regular price",
            "Regular price",
            "Compare at price",
        ],
    )

    if not date_col or not net_sales_col or not ordinary_price_col:
        return {
            "base_week": base_week,
            "num_weeks": num_weeks,
            "error": "Missing required columns",
            "detected": {
                "date": date_col,
                "net_sales": net_sales_col,
                "ordinary_price": ordinary_price_col,
                "columns": df.columns.tolist(),
                "filename": latest_file.name,
            },
            "weeks": [],
        }

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])

    df["_week"] = _iso_week_series(df[date_col])
    df["_net_sales"] = _to_number(df[net_sales_col])
    df["_ordinary_price"] = _to_number(df[ordinary_price_col])

    df["_is_discounted"] = df["_ordinary_price"] > 0

    expected_weeks = _build_display_weeks(base_week, num_weeks)
    df = df[df["_week"].isin(expected_weeks)]

    grouped = (
        df.groupby(["_week", "_is_discounted"], dropna=False)["_net_sales"]
        .sum()
        .reset_index()
    )

    by_week: Dict[str, Dict[str, float]] = {w: {"discounted": 0.0, "full_price": 0.0} for w in expected_weeks}
    for _, row in grouped.iterrows():
        w = str(row["_week"])
        is_disc = bool(row["_is_discounted"])
        val = float(row["_net_sales"] or 0.0)
        if w not in by_week:
            continue
        if is_disc:
            by_week[w]["discounted"] += val
        else:
            by_week[w]["full_price"] += val

    weeks_out = [{"week": w, **by_week[w]} for w in expected_weeks]
    return {
        "base_week": base_week,
        "num_weeks": num_weeks,
        "filename": latest_file.name,
        "columns_used": {
            "date": date_col,
            "net_sales": net_sales_col,
            "ordinary_price": ordinary_price_col,
        },
        "weeks": weeks_out,
    }


def calculate_discounts_summary_metrics(base_week: str, data_root: Path, include_ytd: bool = True) -> Dict[str, Any]:
    """
    Products Summary metrics derived from Discounts file:
    - Net Revenue Overall
    - Net Revenue Full Price
    - Net Revenue Sale
    For periods: actual, last_week, last_year, year_2024 and YTD equivalents.
    """
    raw_path = Path(data_root) / "raw" / base_week / "discounts"
    files = [f for f in raw_path.glob("*.*") if not f.name.startswith(".")]
    if not files:
        return {"periods": {}}

    latest_file = max(files, key=lambda f: f.stat().st_mtime)
    df = _read_csv_flexible(latest_file)
    df.columns = [c.strip().replace('"', "") for c in df.columns]

    date_col = _pick_column(df, ["Date", "Day", "Dag", "Datum"])
    net_sales_col = _pick_column(df, ["Nettoförsäljning", "Net Revenue", "Net sales", "Net amount"])
    price_col = _pick_column(df, ["Produktvariantpris", "Produktvariantpris (SEK)", "Variant price", "Price"])
    ordinary_price_col = _pick_column(
        df,
        [
            "Produktvariantens ordinare pris",
            "Produktvariantens ordinarie pris",
            "Ordinarie pris",
            "Regular price",
            "Compare at price",
        ],
    )
    if not date_col or not net_sales_col or not ordinary_price_col or not price_col:
        return {
            "periods": {},
            "error": "Missing required columns",
            "detected": {
                "date": date_col,
                "net_sales": net_sales_col,
                "price": price_col,
                "ordinary_price": ordinary_price_col,
                "columns": df.columns.tolist(),
                "filename": latest_file.name,
            },
        }

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])
    df["_net_sales"] = _to_number(df[net_sales_col])
    df["_price"] = _to_number(df[price_col])
    df["_ordinary_price"] = _to_number(df[ordinary_price_col])
    df["_is_sale"] = df["_ordinary_price"] > 0

    # Discount bucket (0..70, rounded to nearest 10).
    # Full-price rows (ordinary_price <= 0) are treated as 0%.
    def _discount_bucket(row) -> int:
        op = float(row["_ordinary_price"] or 0.0)
        p = float(row["_price"] or 0.0)
        if op <= 0:
            return 0
        pct = max(0.0, min(100.0, (op - p) / op * 100.0))
        bucket = int(round(pct / 10.0) * 10)
        if bucket < 0:
            bucket = 0
        if bucket > 70:
            bucket = 70
        return bucket

    df["_discount_bucket"] = df.apply(_discount_bucket, axis=1)

    def _sum_for_range(start: str, end: str) -> Dict[str, float]:
        start_dt = pd.to_datetime(start, errors="coerce")
        end_dt = pd.to_datetime(end, errors="coerce")
        if pd.isna(start_dt) or pd.isna(end_dt):
            return {
                "net_revenue_overall": 0.0,
                "net_revenue_full_price": 0.0,
                "net_revenue_sale": 0.0,
            }
        m = (df[date_col] >= start_dt) & (df[date_col] <= end_dt)
        sub = df.loc[m]
        overall = float(sub["_net_sales"].sum() or 0.0)
        sale_df = sub.loc[sub["_is_sale"]]
        sale = float(sale_df["_net_sales"].sum() or 0.0)
        full = float(sub.loc[~sub["_is_sale"], "_net_sales"].sum() or 0.0)

        out = {
            "net_revenue_overall": overall,
            "net_revenue_full_price": full,
            "net_revenue_sale": sale,
        }

        # Add discount-% buckets 0..70 over ALL revenue, so buckets sum to net_revenue_overall.
        # (Full price is bucket 0 via _discount_bucket.)
        for b in range(0, 71, 10):
            out[f"net_revenue_sale_{b}"] = float(sub.loc[sub["_discount_bucket"] == b, "_net_sales"].sum() or 0.0)
        return out

    # Weekly periods
    y_str, w_str = base_week.split("-")
    year = int(y_str)
    week = int(w_str)

    def _prev_week(iso_week: str) -> str:
        y, w = _parse_iso_week(iso_week) or (year, week)
        if w > 1:
            return f"{y}-{w-1:02d}"
        return f"{y-1}-52"

    periods_weeks = {
        "actual": base_week,
        "last_week": _prev_week(base_week),
        "last_year": f"{year-1}-{week:02d}",
        "year_2024": f"2024-{week:02d}",
    }

    periods: Dict[str, Dict[str, float]] = {}
    for key, iso in periods_weeks.items():
        dr = get_week_date_range(iso)
        periods[key] = _sum_for_range(dr["start"], dr["end"])

    if include_ytd:
        # Fiscal year starts April 1st. Determine fiscal year start for the selected base week.
        week_end = get_week_date_range(base_week)["end"]
        week_end_dt = pd.to_datetime(week_end).date()
        fy_start_year = year if week_end_dt.month >= 4 else year - 1

        # Actual YTD
        ytd_actual_start = f"{fy_start_year}-04-01"
        ytd_actual_end = week_end

        # Last year FYTD: same *calendar end date* minus 1 year (keeps dates aligned),
        # with fiscal year start being April 1st of the previous fiscal year.
        week_end_ts = pd.to_datetime(week_end)
        ytd_last_year_start = f"{fy_start_year-1}-04-01"
        ytd_last_year_end = (week_end_ts - pd.DateOffset(years=1)).strftime("%Y-%m-%d")

        # FYTD 2024 baseline: fiscal year ending 2024 (Apr 1, 2023 → Mar 31, 2024).
        # Use the same calendar month/day as the actual FYTD end, but mapped into FY2024.
        # - If actual end is Apr–Dec, map into 2023 (still within FY2024)
        # - If actual end is Jan–Mar, map into 2024
        fytd_2024_start = "2023-04-01"
        fytd_2024_end_year = 2023 if week_end_dt.month >= 4 else 2024
        fytd_2024_end = week_end_ts.replace(year=fytd_2024_end_year).strftime("%Y-%m-%d")

        periods["ytd_actual"] = _sum_for_range(ytd_actual_start, ytd_actual_end)
        periods["ytd_last_year"] = _sum_for_range(ytd_last_year_start, ytd_last_year_end)
        periods["ytd_2024"] = _sum_for_range(fytd_2024_start, fytd_2024_end)

        # Month-to-date (calendar month)
        mtd_start = week_end_ts.replace(day=1).strftime("%Y-%m-%d")
        mtd_end = week_end

        # Same month-to-date last year (clamp end-of-month)
        ly_end_ts = pd.to_datetime(mtd_end) - pd.DateOffset(years=1)
        ly_start_ts = ly_end_ts.replace(day=1)
        mtd_last_year_start = ly_start_ts.strftime("%Y-%m-%d")
        mtd_last_year_end = ly_end_ts.strftime("%Y-%m-%d")

        # Baseline month-to-date for 2024 (use same month/day as current end date, but in 2024)
        base_2024_end_ts = week_end_ts.replace(year=2024)
        base_2024_start_ts = base_2024_end_ts.replace(day=1)
        mtd_2024_start = base_2024_start_ts.strftime("%Y-%m-%d")
        mtd_2024_end = base_2024_end_ts.strftime("%Y-%m-%d")

        periods["mtd_actual"] = _sum_for_range(mtd_start, mtd_end)
        periods["mtd_last_year"] = _sum_for_range(mtd_last_year_start, mtd_last_year_end)
        periods["mtd_2024"] = _sum_for_range(mtd_2024_start, mtd_2024_end)

    return {"periods": periods}


def calculate_discounts_ltm_metrics(base_week: str, data_root: Path) -> Dict[str, Any]:
    """
    Last-12-months metrics derived from Discounts file:
    - ltm_actual: last 12 months ending at base week end date
    - ltm_last_year: previous 12 months (same window shifted back 1 year)
    """
    raw_path = Path(data_root) / "raw" / base_week / "discounts"
    files = [f for f in raw_path.glob("*.*") if not f.name.startswith(".")]
    if not files:
        return {"periods": {}}

    latest_file = max(files, key=lambda f: f.stat().st_mtime)
    df = _read_csv_flexible(latest_file)
    df.columns = [c.strip().replace('"', "") for c in df.columns]

    date_col = _pick_column(df, ["Date", "Day", "Dag", "Datum"])
    net_sales_col = _pick_column(df, ["Nettoförsäljning", "Net Revenue", "Net sales", "Net amount"])
    price_col = _pick_column(df, ["Produktvariantpris", "Produktvariantpris (SEK)", "Variant price", "Price"])
    ordinary_price_col = _pick_column(
        df,
        [
            "Produktvariantens ordinare pris",
            "Produktvariantens ordinarie pris",
            "Ordinarie pris",
            "Regular price",
            "Compare at price",
        ],
    )
    if not date_col or not net_sales_col or not ordinary_price_col or not price_col:
        return {
            "periods": {},
            "error": "Missing required columns",
            "detected": {
                "date": date_col,
                "net_sales": net_sales_col,
                "price": price_col,
                "ordinary_price": ordinary_price_col,
                "columns": df.columns.tolist(),
                "filename": latest_file.name,
            },
        }

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])
    df["_net_sales"] = _to_number(df[net_sales_col])
    df["_price"] = _to_number(df[price_col])
    df["_ordinary_price"] = _to_number(df[ordinary_price_col])
    df["_is_sale"] = df["_ordinary_price"] > 0

    def _discount_bucket(row) -> int:
        op = float(row["_ordinary_price"] or 0.0)
        p = float(row["_price"] or 0.0)
        if op <= 0:
            return 0
        pct = max(0.0, min(100.0, (op - p) / op * 100.0))
        bucket = int(round(pct / 10.0) * 10)
        if bucket < 0:
            bucket = 0
        if bucket > 70:
            bucket = 70
        return bucket

    df["_discount_bucket"] = df.apply(_discount_bucket, axis=1)

    def _sum_for_range(start_dt: pd.Timestamp, end_dt: pd.Timestamp) -> Dict[str, float]:
        m = (df[date_col] >= start_dt) & (df[date_col] <= end_dt)
        sub = df.loc[m]
        overall = float(sub["_net_sales"].sum() or 0.0)
        sale_df = sub.loc[sub["_is_sale"]]
        sale = float(sale_df["_net_sales"].sum() or 0.0)
        full = float(sub.loc[~sub["_is_sale"], "_net_sales"].sum() or 0.0)
        out = {
            "net_revenue_overall": overall,
            "net_revenue_full_price": full,
            "net_revenue_sale": sale,
        }
        for b in range(0, 71, 10):
            out[f"net_revenue_sale_{b}"] = float(sale_df.loc[sale_df["_discount_bucket"] == b, "_net_sales"].sum() or 0.0)
        return out

    week_end = pd.to_datetime(get_week_date_range(base_week)["end"])
    # Define "last 12 months" as the previous 12 calendar months, inclusive of end date.
    start = (week_end - pd.DateOffset(months=12)) + pd.Timedelta(days=1)
    prev_end = week_end - pd.DateOffset(years=1)
    prev_start = start - pd.DateOffset(years=1)

    periods = {
        "ltm_actual": _sum_for_range(start, week_end),
        "ltm_last_year": _sum_for_range(prev_start, prev_end),
    }
    return {"periods": periods}


def calculate_discounts_monthly_metrics(base_week: str, data_root: Path, months: int = 12, segment: str = "all") -> Dict[str, Any]:
    """
    Monthly aggregates for the last N calendar months ending at the selected base week's end date.

    Returns:
      {
        "months": ["2026-01", "2025-12", ...],
        "current": { "2026-01": {...metrics}, ... },
        "last_year": { "2026-01": {...metrics_for_2025-01}, ... }
      }
    """
    raw_path = Path(data_root) / "raw" / base_week / "discounts"
    files = [f for f in raw_path.glob("*.*") if not f.name.startswith(".")]
    if not files:
        return {"months": [], "current": {}, "last_year": {}}

    latest_file = max(files, key=lambda f: f.stat().st_mtime)
    df = _read_csv_flexible(latest_file)
    df.columns = [c.strip().replace('"', "") for c in df.columns]

    date_col = _pick_column(df, ["Date", "Day", "Dag", "Datum"])
    net_sales_col = _pick_column(df, ["Nettoförsäljning", "Net Revenue", "Net sales", "Net amount"])
    price_col = _pick_column(df, ["Produktvariantpris", "Produktvariantpris (SEK)", "Variant price", "Price"])
    ordinary_price_col = _pick_column(
        df,
        [
            "Produktvariantens ordinare pris",
            "Produktvariantens ordinarie pris",
            "Ordinarie pris",
            "Regular price",
            "Compare at price",
        ],
    )
    if not date_col or not net_sales_col or not ordinary_price_col or not price_col:
        return {
            "months": [],
            "current": {},
            "last_year": {},
            "error": "Missing required columns",
            "detected": {
                "date": date_col,
                "net_sales": net_sales_col,
                "price": price_col,
                "ordinary_price": ordinary_price_col,
                "columns": df.columns.tolist(),
                "filename": latest_file.name,
            },
        }

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])
    df["_net_sales"] = _to_number(df[net_sales_col])
    df["_price"] = _to_number(df[price_col])
    df["_ordinary_price"] = _to_number(df[ordinary_price_col])
    df["_is_sale"] = df["_ordinary_price"] > 0

    # Optional: filter to customer segment (new / returning)
    seg = (segment or "all").strip().lower()
    if seg not in ("all", "new", "returning"):
        return {"months": [], "current": {}, "last_year": {}, "error": f"Invalid segment: {segment}"}
    if seg != "all":
        customer_col = _pick_column(
            df,
            [
                "Ny eller återkommande kund",
                "Ny eller återkommande kund (New/Returning)",
                "New or returning customer",
                "New/Returning Customer",
            ],
        )
        if not customer_col:
            return {
                "months": [],
                "current": {},
                "last_year": {},
                "error": "Missing customer segment column",
                "detected": {
                    "customer_type": None,
                    "columns": df.columns.tolist(),
                    "filename": latest_file.name,
                },
            }
        df["_customer_segment"] = df[customer_col].map(_normalize_customer_segment)
        df = df[df["_customer_segment"] == seg]

    def _discount_bucket(row) -> int:
        op = float(row["_ordinary_price"] or 0.0)
        p = float(row["_price"] or 0.0)
        if op <= 0:
            return 0
        pct = max(0.0, min(100.0, (op - p) / op * 100.0))
        bucket = int(round(pct / 10.0) * 10)
        if bucket < 0:
            bucket = 0
        if bucket > 70:
            bucket = 70
        return bucket

    df["_discount_bucket"] = df.apply(_discount_bucket, axis=1)
    df["_month"] = df[date_col].dt.to_period("M").astype(str)

    week_end = pd.to_datetime(get_week_date_range(base_week)["end"], errors="coerce")
    if pd.isna(week_end):
        return {"months": [], "current": {}, "last_year": {}, "error": "Invalid base_week date range"}

    end_period = week_end.to_period("M")
    min_dt = pd.to_datetime(df[date_col].min(), errors="coerce")
    min_period = min_dt.to_period("M") if not pd.isna(min_dt) else end_period

    # months=0 means "all available months"
    requested = int(months or 0)
    if requested <= 0:
        total = int(end_period.ordinal - min_period.ordinal + 1)
        month_keys = [(end_period - i).strftime("%Y-%m") for i in range(max(1, total))]
    else:
        requested = max(1, requested)
        # Cap to available range so we don't return long runs of empty months.
        max_available = int(end_period.ordinal - min_period.ordinal + 1)
        count = min(requested, max(1, max_available))
        month_keys = [(end_period - i).strftime("%Y-%m") for i in range(count)]

    def _sum_for_month(month_key: str, end_dt: Optional[pd.Timestamp] = None) -> Dict[str, float]:
        sub = df.loc[df["_month"] == month_key]
        # For the current (latest) month, optionally clamp to the base week's end date (MTD semantics).
        if end_dt is not None:
            sub = sub.loc[sub[date_col] <= end_dt]
        overall = float(sub["_net_sales"].sum() or 0.0)
        sale_df = sub.loc[sub["_is_sale"]]
        sale = float(sale_df["_net_sales"].sum() or 0.0)
        full = float(sub.loc[~sub["_is_sale"], "_net_sales"].sum() or 0.0)

        out: Dict[str, float] = {
            "net_revenue_overall": overall,
            "net_revenue_full_price": full,
            "net_revenue_sale": sale,
        }
        for b in range(0, 71, 10):
            out[f"net_revenue_sale_{b}"] = float(sub.loc[sub["_discount_bucket"] == b, "_net_sales"].sum() or 0.0)
        return out

    current: Dict[str, Dict[str, float]] = {}
    last_year: Dict[str, Dict[str, float]] = {}

    latest_month_key = end_period.strftime("%Y-%m")
    latest_end_dt = week_end
    latest_end_dt_ly = week_end - pd.DateOffset(years=1)

    for mk in month_keys:
        is_latest_month = mk == latest_month_key
        current_end = latest_end_dt if is_latest_month else None
        current[mk] = _sum_for_month(mk, end_dt=current_end)

        # Same month last year. For the latest month, clamp to the same day-of-month cutoff last year.
        ly_period = pd.Period(mk, freq="M") - 12
        ly_key = ly_period.strftime("%Y-%m")
        ly_end = latest_end_dt_ly if is_latest_month else None
        last_year[mk] = _sum_for_month(ly_key, end_dt=ly_end)

    return {"months": month_keys, "current": current, "last_year": last_year, "segment": seg}


def _normalize_customer_segment(val: Any) -> Optional[str]:
    """Map raw customer type values to 'new' / 'returning'."""
    if val is None:
        return None
    s = str(val).strip().strip('"').strip("'").lower()
    if not s:
        return None
    if "new" in s or "ny" in s:
        return "new"
    if "return" in s or "åter" in s or "ater" in s:
        return "returning"
    return None


def calculate_discount_sales_yoy_for_weeks(
    base_week: str,
    num_weeks: int,
    data_root: Path,
    segment: str = "all",
    all_weeks: bool = False,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Returns discounted vs full price net sales per ISO week for last N weeks,
    plus last year's values for the same ISO week numbers.
    """
    raw_path = Path(data_root) / "raw" / base_week / "discounts"
    files = [f for f in raw_path.glob("*.*") if not f.name.startswith(".")]
    if not files:
        return {"base_week": base_week, "num_weeks": num_weeks, "weeks": []}

    latest_file = max(files, key=lambda f: f.stat().st_mtime)
    df = _read_csv_flexible(latest_file)
    df.columns = [c.strip().replace('"', "") for c in df.columns]

    date_col = _pick_column(df, ["Date", "Day", "Dag", "Datum"])
    net_sales_col = _pick_column(df, ["Nettoförsäljning", "Net Revenue", "Net sales", "Net amount"])
    ordinary_price_col = _pick_column(
        df,
        [
            "Produktvariantens ordinare pris",
            "Produktvariantens ordinarie pris",
            "Ordinarie pris",
            "Regular price",
            "Compare at price",
        ],
    )

    if not date_col or not net_sales_col or not ordinary_price_col:
        return {
            "base_week": base_week,
            "num_weeks": num_weeks,
            "error": "Missing required columns",
            "detected": {
                "date": date_col,
                "net_sales": net_sales_col,
                "ordinary_price": ordinary_price_col,
                "columns": df.columns.tolist(),
                "filename": latest_file.name,
            },
            "weeks": [],
        }

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])
    df["_week"] = _iso_week_series(df[date_col])
    df["_net_sales"] = _to_number(df[net_sales_col])
    df["_ordinary_price"] = _to_number(df[ordinary_price_col])
    df["_is_discounted"] = df["_ordinary_price"] > 0

    # Optional: filter to customer segment
    seg = (segment or "all").strip().lower()
    if seg not in ("all", "new", "returning"):
        return {"base_week": base_week, "num_weeks": num_weeks, "error": f"Invalid segment: {segment}", "weeks": []}
    if seg != "all":
        customer_col = _pick_column(
            df,
            [
                "Ny eller återkommande kund",
                "Ny eller återkommande kund (New/Returning)",
                "New or returning customer",
                "New/Returning Customer",
            ],
        )
        if not customer_col:
            return {
                "base_week": base_week,
                "num_weeks": num_weeks,
                "error": "Missing required columns",
                "detected": {
                    "date": date_col,
                    "net_sales": net_sales_col,
                    "ordinary_price": ordinary_price_col,
                    "customer_type": None,
                    "columns": df.columns.tolist(),
                    "filename": latest_file.name,
                },
                "weeks": [],
            }
        df["_customer_segment"] = df[customer_col].map(_normalize_customer_segment)
        df = df[df["_customer_segment"] == seg]

    if all_weeks:
        # Restrict to data available up to selected base_week end date (if provided)
        if end_date:
            end_dt = pd.to_datetime(end_date, errors="coerce")
            if pd.notna(end_dt):
                df = df[df[date_col] <= end_dt]
        expected_weeks = _sort_iso_weeks(df["_week"].dropna().unique().tolist())
    else:
        expected_weeks = _build_display_weeks(base_week, num_weeks)

    expected_last_year = []
    for w in expected_weeks:
        y_str, ww = w.split("-")
        expected_last_year.append(f"{int(y_str) - 1}-{ww}")

    df = df[df["_week"].isin(set(expected_weeks + expected_last_year))]

    grouped = (
        df.groupby(["_week", "_is_discounted"], dropna=False)["_net_sales"]
        .sum()
        .reset_index()
    )

    def _init_map(weeks: List[str]) -> Dict[str, Dict[str, float]]:
        return {w: {"discounted": 0.0, "full_price": 0.0} for w in weeks}

    cur_map = _init_map(expected_weeks)
    ly_map = _init_map(expected_last_year)

    for _, row in grouped.iterrows():
        w = str(row["_week"])
        is_disc = bool(row["_is_discounted"])
        val = float(row["_net_sales"] or 0.0)
        target = cur_map if w in cur_map else (ly_map if w in ly_map else None)
        if target is None:
            continue
        if is_disc:
            target[w]["discounted"] += val
        else:
            target[w]["full_price"] += val

    weeks_out = []
    for w in expected_weeks:
        y_str, ww = w.split("-")
        ly_w = f"{int(y_str) - 1}-{ww}"
        weeks_out.append(
            {
                "week": w,
                "discounted": cur_map[w]["discounted"],
                "full_price": cur_map[w]["full_price"],
                "last_year": {
                    "week": ly_w,
                    "discounted": ly_map.get(ly_w, {}).get("discounted", 0.0),
                    "full_price": ly_map.get(ly_w, {}).get("full_price", 0.0),
                },
            }
        )

    return {
        "base_week": base_week,
        "num_weeks": num_weeks,
        "segment": seg,
        "filename": latest_file.name,
        "columns_used": {
            "date": date_col,
            "net_sales": net_sales_col,
            "ordinary_price": ordinary_price_col,
        },
        "weeks": weeks_out,
    }


def _normalize_gender(val: Any) -> str:
    if val is None:
        return "MEN"
    s = str(val).strip().strip('"').strip("'").lower()
    if not s or s == "-":
        return "MEN"
    if "women" in s or "woman" in s or "dam" in s or "dame" in s:
        return "WOMEN"
    if "men" in s or "man" in s or "herr" in s:
        return "MEN"
    if "unisex" in s:
        return "MEN"
    # Default: treat unknown as MEN (consistent with Category Sales behavior)
    return "MEN"


def calculate_discount_category_price_sales_for_weeks(
    base_week: str,
    num_weeks: int,
    data_root: Path,
    segment: str = "all",
) -> Dict[str, Any]:
    """
    Category net sales per ISO week (last N weeks) split by Full Price vs Sale,
    with last year's values for the same ISO week numbers.
    Returned structure mirrors /api/category-sales (categories dict per week) but with:
      - FULL_{category}
      - SALE_{category}
    """
    raw_path = Path(data_root) / "raw" / base_week / "discounts"
    files = [f for f in raw_path.glob("*.*") if not f.name.startswith(".")]
    if not files:
        return {"base_week": base_week, "num_weeks": num_weeks, "category_sales": []}

    latest_file = max(files, key=lambda f: f.stat().st_mtime)
    df = _read_csv_flexible(latest_file)
    df.columns = [c.strip().replace('"', "") for c in df.columns]

    date_col = _pick_column(df, ["Date", "Day", "Dag", "Datum"])
    net_sales_col = _pick_column(df, ["Nettoförsäljning", "Net Revenue", "Net sales", "Net amount"])
    ordinary_price_col = _pick_column(
        df,
        [
            "Produktvariantens ordinare pris",
            "Produktvariantens ordinarie pris",
            "Ordinarie pris",
            "Regular price",
            "Compare at price",
        ],
    )
    category_col = _pick_column(df, ["Produkttyp", "Product type", "Kategori", "Category"])

    if not date_col or not net_sales_col or not ordinary_price_col or not category_col:
        return {
            "base_week": base_week,
            "num_weeks": num_weeks,
            "error": "Missing required columns",
            "detected": {
                "date": date_col,
                "net_sales": net_sales_col,
                "ordinary_price": ordinary_price_col,
                "category": category_col,
                "columns": df.columns.tolist(),
                "filename": latest_file.name,
            },
            "category_sales": [],
        }

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])
    df["_week"] = _iso_week_series(df[date_col])
    df["_net_sales"] = _to_number(df[net_sales_col])
    df["_ordinary_price"] = _to_number(df[ordinary_price_col])
    df["_is_sale"] = df["_ordinary_price"] > 0
    df["_category"] = df[category_col].astype(str)

    # Optional: filter to customer segment
    seg = (segment or "all").strip().lower()
    if seg not in ("all", "new", "returning"):
        return {"base_week": base_week, "num_weeks": num_weeks, "error": f"Invalid segment: {segment}", "category_sales": []}
    customer_col = None
    if seg != "all":
        customer_col = _pick_column(
            df,
            [
                "Ny eller återkommande kund",
                "Ny eller återkommande kund (New/Returning)",
                "New or returning customer",
                "New/Returning Customer",
            ],
        )
        if not customer_col:
            return {
                "base_week": base_week,
                "num_weeks": num_weeks,
                "segment": seg,
                "error": "Missing customer segment column",
                "detected": {"customer_type": None, "columns": df.columns.tolist(), "filename": latest_file.name},
                "category_sales": [],
            }
        df["_customer_segment"] = df[customer_col].map(_normalize_customer_segment)
        df = df[df["_customer_segment"] == seg]

    expected_weeks = _build_display_weeks(base_week, num_weeks)
    expected_last_year = [f"{int(w.split('-')[0]) - 1}-{w.split('-')[1]}" for w in expected_weeks]
    df = df[df["_week"].isin(set(expected_weeks + expected_last_year))]

    grouped = (
        df.groupby(["_week", "_category", "_is_sale"], dropna=False)["_net_sales"]
        .sum()
        .reset_index()
    )

    def _init_map(weeks: List[str]) -> Dict[str, Dict[str, float]]:
        return {w: {} for w in weeks}

    cur_map = _init_map(expected_weeks)
    ly_map = _init_map(expected_last_year)

    for _, row in grouped.iterrows():
        w = str(row["_week"])
        cat = str(row["_category"])
        is_sale = bool(row["_is_sale"])
        val = float(row["_net_sales"] or 0.0)
        target = cur_map if w in cur_map else (ly_map if w in ly_map else None)
        if target is None:
            continue
        key = f"{'SALE' if is_sale else 'FULL'}_{cat}"
        target[w][key] = float(target[w].get(key, 0.0) + val)

    category_sales: List[Dict[str, Any]] = []
    for w in expected_weeks:
        y_str, ww = w.split("-")
        ly_w = f"{int(y_str) - 1}-{ww}"
        category_sales.append(
            {
                "week": w,
                "categories": cur_map.get(w, {}),
                "last_year": {"week": ly_w, "categories": ly_map.get(ly_w, {})},
            }
        )

    latest_range = get_week_date_range(base_week)
    return {
        "base_week": base_week,
        "num_weeks": num_weeks,
        "granularity": "week",
        "segment": seg,
        "filename": latest_file.name,
        "columns_used": {
            "date": date_col,
            "net_sales": net_sales_col,
            "ordinary_price": ordinary_price_col,
            "category": category_col,
            "customer_type": customer_col,
        },
        "period_info": {"latest_week": base_week, "latest_dates": f"{latest_range.get('start')} - {latest_range.get('end')}"},
        "category_sales": category_sales,
    }


def calculate_discount_category_price_sales_for_months(
    base_week: str,
    months: int,
    data_root: Path,
    segment: str = "all",
) -> Dict[str, Any]:
    """
    Category net sales per calendar month (last N months) split by Full Price vs Sale,
    with last year's values for the same months.

    For the latest month, values are Month-to-date (clamped to base week's end date),
    and LY is clamped to the same cutoff date last year.
    """
    raw_path = Path(data_root) / "raw" / base_week / "discounts"
    files = [f for f in raw_path.glob("*.*") if not f.name.startswith(".")]
    if not files:
        return {"base_week": base_week, "months": months, "granularity": "month", "category_sales": []}

    latest_file = max(files, key=lambda f: f.stat().st_mtime)
    df = _read_csv_flexible(latest_file)
    df.columns = [c.strip().replace('"', "") for c in df.columns]

    date_col = _pick_column(df, ["Date", "Day", "Dag", "Datum"])
    net_sales_col = _pick_column(df, ["Nettoförsäljning", "Net Revenue", "Net sales", "Net amount"])
    ordinary_price_col = _pick_column(
        df,
        [
            "Produktvariantens ordinare pris",
            "Produktvariantens ordinarie pris",
            "Ordinarie pris",
            "Regular price",
            "Compare at price",
        ],
    )
    category_col = _pick_column(df, ["Produkttyp", "Product type", "Kategori", "Category"])

    if not date_col or not net_sales_col or not ordinary_price_col or not category_col:
        return {
            "base_week": base_week,
            "months": months,
            "granularity": "month",
            "error": "Missing required columns",
            "detected": {
                "date": date_col,
                "net_sales": net_sales_col,
                "ordinary_price": ordinary_price_col,
                "category": category_col,
                "columns": df.columns.tolist(),
                "filename": latest_file.name,
            },
            "category_sales": [],
        }

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])
    df["_net_sales"] = _to_number(df[net_sales_col])
    df["_ordinary_price"] = _to_number(df[ordinary_price_col])
    df["_is_sale"] = df["_ordinary_price"] > 0
    df["_category"] = df[category_col].astype(str)
    df["_month"] = df[date_col].dt.to_period("M").astype(str)  # YYYY-MM

    # Optional: filter to customer segment (new / returning)
    seg = (segment or "all").strip().lower()
    if seg not in ("all", "new", "returning"):
        return {"base_week": base_week, "months": months, "granularity": "month", "error": f"Invalid segment: {segment}", "category_sales": []}
    customer_col = None
    if seg != "all":
        customer_col = _pick_column(
            df,
            [
                "Ny eller återkommande kund",
                "Ny eller återkommande kund (New/Returning)",
                "New or returning customer",
                "New/Returning Customer",
            ],
        )
        if not customer_col:
            return {
                "base_week": base_week,
                "months": months,
                "granularity": "month",
                "segment": seg,
                "error": "Missing customer segment column",
                "detected": {"customer_type": None, "columns": df.columns.tolist(), "filename": latest_file.name},
                "category_sales": [],
            }
        df["_customer_segment"] = df[customer_col].map(_normalize_customer_segment)
        df = df[df["_customer_segment"] == seg]

    week_end = pd.to_datetime(get_week_date_range(base_week)["end"], errors="coerce")
    if pd.isna(week_end):
        return {"base_week": base_week, "months": months, "granularity": "month", "error": "Invalid base_week date range", "category_sales": []}

    end_period = week_end.to_period("M")
    min_dt = pd.to_datetime(df[date_col].min(), errors="coerce")
    min_period = min_dt.to_period("M") if not pd.isna(min_dt) else end_period

    requested = int(months or 0)
    requested = max(1, requested)
    max_available = int(end_period.ordinal - min_period.ordinal + 1)
    count = min(requested, max(1, max_available))
    month_keys = [(end_period - i).strftime("%Y-%m") for i in range(count)]

    latest_month_key = end_period.strftime("%Y-%m")
    latest_end_dt = week_end
    latest_end_dt_ly = week_end - pd.DateOffset(years=1)

    def _sum_for_month(month_key: str, end_dt: Optional[pd.Timestamp]) -> Dict[str, float]:
        sub = df.loc[df["_month"] == month_key]
        if end_dt is not None:
            sub = sub.loc[sub[date_col] <= end_dt]

        grouped = (
            sub.groupby(["_category", "_is_sale"], dropna=False)["_net_sales"]
            .sum()
            .reset_index()
        )
        out: Dict[str, float] = {}
        for _, row in grouped.iterrows():
            cat = str(row["_category"])
            is_sale = bool(row["_is_sale"])
            val = float(row["_net_sales"] or 0.0)
            key = f"{'SALE' if is_sale else 'FULL'}_{cat}"
            out[key] = float(out.get(key, 0.0) + val)
        return out

    category_sales: List[Dict[str, Any]] = []
    for mk in month_keys:
        is_latest = mk == latest_month_key
        cur_end = latest_end_dt if is_latest else None
        ly_end = latest_end_dt_ly if is_latest else None

        ly_period = pd.Period(mk, freq="M") - 12
        ly_key = ly_period.strftime("%Y-%m")

        category_sales.append(
            {
                "month": mk,
                "categories": _sum_for_month(mk, end_dt=cur_end),
                "last_year": {"month": ly_key, "categories": _sum_for_month(ly_key, end_dt=ly_end)},
            }
        )

    latest_range = get_week_date_range(base_week)
    return {
        "base_week": base_week,
        "months": months,
        "granularity": "month",
        "segment": seg,
        "filename": latest_file.name,
        "columns_used": {
            "date": date_col,
            "net_sales": net_sales_col,
            "ordinary_price": ordinary_price_col,
            "category": category_col,
            "customer_type": customer_col,
        },
        "period_info": {"latest_week": base_week, "latest_dates": f"{latest_range.get('start')} - {latest_range.get('end')}"},
        "category_sales": category_sales,
    }


def calculate_discounts_customer_segments(
    base_week: str,
    data_root: Path,
    months: int = 12,
    segment: str = "all",
) -> Dict[str, Any]:
    """
    Customer segmentation based on Full Price vs Sale purchase behavior, plus repeat behavior.

    Window: last N calendar months ending at base week's end date.
    Latest month is MTD (clamped to base week end); LY comparisons are clamped similarly where relevant.
    """
    raw_path = Path(data_root) / "raw" / base_week / "discounts"
    files = [f for f in raw_path.glob("*.*") if not f.name.startswith(".")]
    if not files:
        return {"base_week": base_week, "months": months, "segment": segment, "window": None, "segments_overall": [], "first_purchase": [], "transitions": {}}

    latest_file = max(files, key=lambda f: f.stat().st_mtime)
    df = _read_csv_flexible(latest_file)
    df.columns = [c.strip().replace('"', "") for c in df.columns]

    date_col = _pick_column(df, ["Date", "Day", "Dag", "Datum"])
    net_sales_col = _pick_column(df, ["Nettoförsäljning", "Net Revenue", "Net sales", "Net amount"])
    ordinary_price_col = _pick_column(
        df,
        [
            "Produktvariantens ordinare pris",
            "Produktvariantens ordinarie pris",
            "Ordinarie pris",
            "Regular price",
            "Compare at price",
        ],
    )
    customer_col = _pick_column(
        df,
        [
            "Kund-ID",
            "Kund ID",
            "Kundid",
            "Customer ID",
            "Customer Id",
            "Customer E-mail",
            "Customer Email",
            "Customer email",
            "E-mail",
            "Email",
            "Epost",
            "E-post",
            "Kund e-post",
            "Kund epost",
            "Customer",
        ],
    )
    order_col = _pick_column(
        df,
        [
            "Order",
            "Order name",
            "Order Name",
            "Order ID",
            "Order Id",
            "Order number",
            "Order Number",
            "Ordernummer",
            "Beställning",
            "Bestallning",
        ],
    )

    if not date_col or not net_sales_col or not ordinary_price_col or not customer_col:
        return {
            "base_week": base_week,
            "months": months,
            "segment": segment,
            "error": "Missing required columns",
            "detected": {
                "date": date_col,
                "net_sales": net_sales_col,
                "ordinary_price": ordinary_price_col,
                "customer": customer_col,
                "order": order_col,
                "columns": df.columns.tolist(),
                "filename": latest_file.name,
            },
            "segments_overall": [],
            "first_purchase": [],
            "transitions": {},
        }

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])
    df["_net_sales"] = _to_number(df[net_sales_col])
    df["_ordinary_price"] = _to_number(df[ordinary_price_col])
    # In this dataset, "compare at price"/ordinary price is typically blank/0 for full price items.
    df["_is_sale"] = df["_ordinary_price"] > 0

    df["_customer"] = df[customer_col].astype(str).str.strip().str.lower()
    df = df[df["_customer"].notna() & (df["_customer"] != "") & (df["_customer"] != "nan")]

    if order_col:
        df["_order_id"] = df[order_col].astype(str).str.strip()
    else:
        # Fallback: approximate order id by customer + calendar date (unique purchase-days)
        df["_order_id"] = df["_customer"] + "|" + df[date_col].dt.strftime("%Y-%m-%d")

    # Optional: filter to Shopify "new/returning" segment (existing semantics in this codebase)
    seg = (segment or "all").strip().lower()
    if seg not in ("all", "new", "returning"):
        return {"base_week": base_week, "months": months, "segment": seg, "error": f"Invalid segment: {segment}", "segments_overall": [], "first_purchase": [], "transitions": {}}
    seg_col = None
    if seg != "all":
        seg_col = _pick_column(
            df,
            [
                "Ny eller återkommande kund",
                "Ny eller återkommande kund (New/Returning)",
                "New or returning customer",
                "New/Returning Customer",
            ],
        )
        if not seg_col:
            return {
                "base_week": base_week,
                "months": months,
                "segment": seg,
                "error": "Missing customer segment column",
                "detected": {"customer_type": None, "columns": df.columns.tolist(), "filename": latest_file.name},
                "segments_overall": [],
                "first_purchase": [],
                "transitions": {},
            }
        df["_customer_segment"] = df[seg_col].map(_normalize_customer_segment)
        df = df[df["_customer_segment"] == seg]

    week_end = pd.to_datetime(get_week_date_range(base_week)["end"], errors="coerce")
    if pd.isna(week_end):
        return {"base_week": base_week, "months": months, "segment": seg, "error": "Invalid base_week date range", "segments_overall": [], "first_purchase": [], "transitions": {}}

    # Window: last N calendar months (inclusive of end date)
    months_i = max(1, int(months or 12))
    window_start = (week_end - pd.DateOffset(months=months_i)) + pd.Timedelta(days=1)
    window_end = week_end
    dfw = df.loc[(df[date_col] >= window_start) & (df[date_col] <= window_end)].copy()
    if dfw.empty:
        return {
            "base_week": base_week,
            "months": months_i,
            "segment": seg,
            "window": {"start": str(window_start.date()), "end": str(window_end.date())},
            "segments_overall": [],
            "first_purchase": [],
            "transitions": {},
        }

    # --- Overall mix segments (within window)
    cust_mix = (
        dfw.groupby("_customer", dropna=False)
        .agg(
            revenue=("_net_sales", "sum"),
            orders=("_order_id", pd.Series.nunique),
            has_sale=("_is_sale", "max"),
            has_full=("_is_sale", lambda s: (~s.astype(bool)).any()),
        )
        .reset_index()
    )

    def _mix_label(row) -> str:
        has_sale = bool(row["has_sale"])
        has_full = bool(row["has_full"])
        if has_sale and has_full:
            return "Mixed"
        if has_sale:
            return "Sale Only"
        return "Full Price Only"

    cust_mix["segment"] = cust_mix.apply(_mix_label, axis=1)

    seg_overall_rows: List[Dict[str, Any]] = []
    for seg_name in ["Full Price Only", "Sale Only", "Mixed"]:
        sub = cust_mix[cust_mix["segment"] == seg_name]
        customers = int(len(sub))
        revenue = float(sub["revenue"].sum() or 0.0)
        orders = int(sub["orders"].sum() or 0)
        aov = float(revenue / orders) if orders else 0.0
        seg_overall_rows.append(
            {
                "segment": seg_name,
                "customers": customers,
                "orders": orders,
                "revenue": revenue,
                "aov": aov,
                "rev_per_customer": float(revenue / customers) if customers else 0.0,
                "orders_per_customer": float(orders / customers) if customers else 0.0,
            }
        )

    # Total row
    total_customers = int(len(cust_mix))
    total_revenue = float(cust_mix["revenue"].sum() or 0.0)
    total_orders = int(cust_mix["orders"].sum() or 0)
    seg_overall_rows.append(
        {
            "segment": "Total",
            "customers": total_customers,
            "orders": total_orders,
            "revenue": total_revenue,
            "aov": float(total_revenue / total_orders) if total_orders else 0.0,
            "rev_per_customer": float(total_revenue / total_customers) if total_customers else 0.0,
            "orders_per_customer": float(total_orders / total_customers) if total_customers else 0.0,
        }
    )

    # --- First purchase + repeat behavior (within window)
    # Find first order per customer (by earliest order date within window).
    first_order_dt = dfw.groupby("_customer")[date_col].min().rename("first_dt").reset_index()
    dfw = dfw.merge(first_order_dt, on="_customer", how="left")
    dfw["_is_first"] = dfw[date_col] == dfw["first_dt"]

    # Determine first-segment based on first-day lines:
    first_lines = dfw[dfw["_is_first"]].copy()
    first_agg = (
        first_lines.groupby("_customer", dropna=False)
        .agg(first_has_sale=("_is_sale", "max"), first_has_full=("_is_sale", lambda s: (~s.astype(bool)).any()))
        .reset_index()
    )

    def _first_label(row) -> str:
        hs = bool(row["first_has_sale"])
        hf = bool(row["first_has_full"])
        if hs and hf:
            return "First Mixed"
        if hs:
            return "First Sale"
        return "First Full Price"

    first_agg["first_segment"] = first_agg.apply(_first_label, axis=1)

    # Repeat determination: any order_id strictly after first_dt
    dfw["_after_first"] = dfw[date_col] > dfw["first_dt"]
    after = dfw[dfw["_after_first"]].copy()
    after_agg = (
        after.groupby("_customer", dropna=False)
        .agg(after_has_sale=("_is_sale", "max"), after_has_full=("_is_sale", lambda s: (~s.astype(bool)).any()))
        .reset_index()
    )

    def _after_label(row) -> str:
        hs = bool(row.get("after_has_sale", False))
        hf = bool(row.get("after_has_full", False))
        if hs and hf:
            return "Repeat Mixed"
        if hs:
            return "Repeat Sale"
        if hf:
            return "Repeat Full Price"
        return "No Repeat"

    # Join and compute repeat segment (No Repeat if missing)
    fp = first_agg.merge(after_agg, on="_customer", how="left")
    fp["repeat_segment"] = fp.apply(_after_label, axis=1)

    first_purchase_rows: List[Dict[str, Any]] = []
    transitions: Dict[str, Dict[str, int]] = {}
    for fs in ["First Full Price", "First Sale", "First Mixed"]:
        sub = fp[fp["first_segment"] == fs]
        customers = int(len(sub))
        repeat_customers = int((sub["repeat_segment"] != "No Repeat").sum())
        repeat_rate = float(repeat_customers / customers * 100.0) if customers else 0.0

        breakdown = sub["repeat_segment"].value_counts().to_dict()
        transitions[fs] = {k: int(v) for k, v in breakdown.items()}
        first_purchase_rows.append(
            {
                "first_segment": fs,
                "customers": customers,
                "repeat_customers": repeat_customers,
                "repeat_rate_pct": repeat_rate,
                "repeat_full_price": int(breakdown.get("Repeat Full Price", 0)),
                "repeat_sale": int(breakdown.get("Repeat Sale", 0)),
                "repeat_mixed": int(breakdown.get("Repeat Mixed", 0)),
                "no_repeat": int(breakdown.get("No Repeat", 0)),
            }
        )

    # Total row
    total_fp = int(len(fp))
    total_repeat = int((fp["repeat_segment"] != "No Repeat").sum())
    first_purchase_rows.append(
        {
            "first_segment": "Total",
            "customers": total_fp,
            "repeat_customers": total_repeat,
            "repeat_rate_pct": float(total_repeat / total_fp * 100.0) if total_fp else 0.0,
            "repeat_full_price": int((fp["repeat_segment"] == "Repeat Full Price").sum()),
            "repeat_sale": int((fp["repeat_segment"] == "Repeat Sale").sum()),
            "repeat_mixed": int((fp["repeat_segment"] == "Repeat Mixed").sum()),
            "no_repeat": int((fp["repeat_segment"] == "No Repeat").sum()),
        }
    )

    return {
        "base_week": base_week,
        "months": months_i,
        "segment": seg,
        "filename": latest_file.name,
        "columns_used": {
            "date": date_col,
            "net_sales": net_sales_col,
            "ordinary_price": ordinary_price_col,
            "customer": customer_col,
            "order": order_col,
            "customer_type": seg_col,
        },
        "window": {"start": str(window_start.date()), "end": str(window_end.date())},
        "segments_overall": seg_overall_rows,
        "first_purchase": first_purchase_rows,
        "transitions": transitions,
    }


def calculate_discount_category_breakdown(
    base_week: str,
    iso_week: str,
    data_root: Path,
    segment: str = "all",
) -> Dict[str, Any]:
    """
    Category breakdown for a given ISO week, sorted by net sales desc.
    Category column is inferred from discounts file (e.g. 'Produkttyp').
    """
    raw_path = Path(data_root) / "raw" / base_week / "discounts"
    files = [f for f in raw_path.glob("*.*") if not f.name.startswith(".")]
    if not files:
        return {"base_week": base_week, "iso_week": iso_week, "segment": segment, "categories": []}

    latest_file = max(files, key=lambda f: f.stat().st_mtime)
    df = _read_csv_flexible(latest_file)
    df.columns = [c.strip().replace('"', "") for c in df.columns]

    date_col = _pick_column(df, ["Date", "Day", "Dag", "Datum"])
    net_sales_col = _pick_column(df, ["Nettoförsäljning", "Net Revenue", "Net sales", "Net amount"])
    category_col = _pick_column(df, ["Produkttyp", "Product type", "Kategori", "Category"])

    if not date_col or not net_sales_col or not category_col:
        return {
            "base_week": base_week,
            "iso_week": iso_week,
            "segment": segment,
            "error": "Missing required columns",
            "detected": {
                "date": date_col,
                "net_sales": net_sales_col,
                "category": category_col,
                "columns": df.columns.tolist(),
                "filename": latest_file.name,
            },
            "categories": [],
        }

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])
    df["_week"] = _iso_week_series(df[date_col])
    df["_net_sales"] = _to_number(df[net_sales_col])

    # Segment filter (optional)
    seg = (segment or "all").strip().lower()
    if seg not in ("all", "new", "returning"):
        return {"base_week": base_week, "iso_week": iso_week, "segment": seg, "error": f"Invalid segment: {segment}", "categories": []}
    if seg != "all":
        customer_col = _pick_column(
            df,
            [
                "Ny eller återkommande kund",
                "Ny eller återkommande kund (New/Returning)",
                "New or returning customer",
                "New/Returning Customer",
            ],
        )
        if not customer_col:
            return {
                "base_week": base_week,
                "iso_week": iso_week,
                "segment": seg,
                "error": "Missing required columns",
                "detected": {
                    "date": date_col,
                    "net_sales": net_sales_col,
                    "category": category_col,
                    "customer_type": None,
                    "columns": df.columns.tolist(),
                    "filename": latest_file.name,
                },
                "categories": [],
            }
        df["_customer_segment"] = df[customer_col].map(_normalize_customer_segment)
        df = df[df["_customer_segment"] == seg]

    # Build comparable weeks (current + last year + 2 years ago) with same week number
    parsed = _parse_iso_week(iso_week)
    if not parsed:
        return {"base_week": base_week, "iso_week": iso_week, "segment": seg, "error": "Invalid iso_week", "categories": []}
    y, ww = parsed
    ly_week = f"{y-1}-{ww:02d}"
    two_years_week = f"{y-2}-{ww:02d}"

    df = df[df["_week"].isin([iso_week, ly_week, two_years_week])]
    if df.empty:
        return {
            "base_week": base_week,
            "iso_week": iso_week,
            "segment": seg,
            "filename": latest_file.name,
            "columns_used": {"date": date_col, "net_sales": net_sales_col, "category": category_col},
            "categories": [],
        }

    cat_series = df[category_col].astype(str).str.strip().replace({"": "Unknown", "nan": "Unknown"})
    by_cat_week = (
        pd.DataFrame({"category": cat_series, "week": df["_week"], "net_sales": df["_net_sales"]})
        .groupby(["category", "week"], dropna=False)["net_sales"]
        .sum()
        .reset_index()
    )

    # Pivot to get three columns per category
    pivot = by_cat_week.pivot_table(index="category", columns="week", values="net_sales", aggfunc="sum", fill_value=0.0)
    pivot = pivot.reset_index()

    def _get(col: str, row: pd.Series) -> float:
        try:
            return float(row.get(col, 0.0) or 0.0)
        except Exception:
            return 0.0

    categories: List[Dict[str, Any]] = []
    for _, r in pivot.iterrows():
        cat = str(r["category"])
        cur = _get(iso_week, r)
        ly = _get(ly_week, r)
        two = _get(two_years_week, r)
        yoy_abs = cur - ly
        yoy_pct = (yoy_abs / ly * 100.0) if ly > 0 else None
        vs_two_abs = cur - two
        vs_two_pct = (vs_two_abs / two * 100.0) if two > 0 else None
        categories.append(
            {
                "category": cat,
                "net_sales": cur,
                "last_year": ly,
                "two_years_ago": two,
                "yoy_abs": yoy_abs,
                "yoy_pct": yoy_pct,
                "vs_two_abs": vs_two_abs,
                "vs_two_pct": vs_two_pct,
            }
        )

    categories.sort(key=lambda x: float(x.get("net_sales") or 0.0), reverse=True)
    return {
        "base_week": base_week,
        "iso_week": iso_week,
        "segment": seg,
        "comparison_weeks": {"last_year": ly_week, "two_years_ago": two_years_week},
        "filename": latest_file.name,
        "columns_used": {"date": date_col, "net_sales": net_sales_col, "category": category_col},
        "categories": categories,
    }


def calculate_discount_category_country_breakdown(
    base_week: str,
    iso_week: str,
    category: str,
    data_root: Path,
    segment: str = "all",
) -> Dict[str, Any]:
    """
    For a selected category + ISO week, return net sales split by country (Leveransland),
    including LY / 2y ago and growth metrics.
    """
    raw_path = Path(data_root) / "raw" / base_week / "discounts"
    files = [f for f in raw_path.glob("*.*") if not f.name.startswith(".")]
    if not files:
        return {"base_week": base_week, "iso_week": iso_week, "segment": segment, "category": category, "countries": []}

    latest_file = max(files, key=lambda f: f.stat().st_mtime)
    df = _read_csv_flexible(latest_file)
    df.columns = [c.strip().replace('"', "") for c in df.columns]

    date_col = _pick_column(df, ["Date", "Day", "Dag", "Datum"])
    net_sales_col = _pick_column(df, ["Nettoförsäljning", "Net Revenue", "Net sales", "Net amount"])
    category_col = _pick_column(df, ["Produkttyp", "Product type", "Kategori", "Category"])
    country_col = _pick_column(
        df,
        [
            "Leveransland",
            "Land",
            "Country",
            "Shipping country",
            "Delivery country",
            "Ship country",
        ],
    )

    if not date_col or not net_sales_col or not category_col or not country_col:
        return {
            "base_week": base_week,
            "iso_week": iso_week,
            "segment": segment,
            "category": category,
            "error": "Missing required columns",
            "detected": {
                "date": date_col,
                "net_sales": net_sales_col,
                "category": category_col,
                "country": country_col,
                "columns": df.columns.tolist(),
                "filename": latest_file.name,
            },
            "countries": [],
        }

    parsed = _parse_iso_week(iso_week)
    if not parsed:
        return {"base_week": base_week, "iso_week": iso_week, "segment": segment, "category": category, "error": "Invalid iso_week", "countries": []}
    y, ww = parsed
    ly_week = f"{y-1}-{ww:02d}"
    two_years_week = f"{y-2}-{ww:02d}"

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])
    df["_week"] = _iso_week_series(df[date_col])
    df["_net_sales"] = _to_number(df[net_sales_col])

    seg = (segment or "all").strip().lower()
    if seg not in ("all", "new", "returning"):
        return {"base_week": base_week, "iso_week": iso_week, "segment": seg, "category": category, "error": f"Invalid segment: {segment}", "countries": []}
    if seg != "all":
        customer_col = _pick_column(
            df,
            [
                "Ny eller återkommande kund",
                "Ny eller återkommande kund (New/Returning)",
                "New or returning customer",
                "New/Returning Customer",
            ],
        )
        if not customer_col:
            return {
                "base_week": base_week,
                "iso_week": iso_week,
                "segment": seg,
                "category": category,
                "error": "Missing required columns",
                "detected": {
                    "date": date_col,
                    "net_sales": net_sales_col,
                    "category": category_col,
                    "country": country_col,
                    "customer_type": None,
                    "columns": df.columns.tolist(),
                    "filename": latest_file.name,
                },
                "countries": [],
            }
        df["_customer_segment"] = df[customer_col].map(_normalize_customer_segment)
        df = df[df["_customer_segment"] == seg]

    # Filter to the category + comparable weeks
    df = df[df[category_col].astype(str).str.strip() == str(category).strip()]
    df = df[df["_week"].isin([iso_week, ly_week, two_years_week])]

    if df.empty:
        return {
            "base_week": base_week,
            "iso_week": iso_week,
            "segment": seg,
            "category": category,
            "comparison_weeks": {"last_year": ly_week, "two_years_ago": two_years_week},
            "filename": latest_file.name,
            "columns_used": {"date": date_col, "net_sales": net_sales_col, "category": category_col, "country": country_col},
            "countries": [],
        }

    ctry_series = df[country_col].astype(str).str.strip().replace({"": "Unknown", "nan": "Unknown"})
    by_country_week = (
        pd.DataFrame({"country": ctry_series, "week": df["_week"], "net_sales": df["_net_sales"]})
        .groupby(["country", "week"], dropna=False)["net_sales"]
        .sum()
        .reset_index()
    )

    pivot = by_country_week.pivot_table(index="country", columns="week", values="net_sales", aggfunc="sum", fill_value=0.0).reset_index()

    def _get(col: str, row: pd.Series) -> float:
        try:
            return float(row.get(col, 0.0) or 0.0)
        except Exception:
            return 0.0

    countries: List[Dict[str, Any]] = []
    for _, r in pivot.iterrows():
        ctry = str(r["country"])
        cur = _get(iso_week, r)
        ly = _get(ly_week, r)
        two = _get(two_years_week, r)
        yoy_abs = cur - ly
        yoy_pct = (yoy_abs / ly * 100.0) if ly > 0 else None
        vs_two_abs = cur - two
        vs_two_pct = (vs_two_abs / two * 100.0) if two > 0 else None
        countries.append(
            {
                "country": ctry,
                "net_sales": cur,
                "last_year": ly,
                "two_years_ago": two,
                "yoy_abs": yoy_abs,
                "yoy_pct": yoy_pct,
                "vs_two_abs": vs_two_abs,
                "vs_two_pct": vs_two_pct,
            }
        )

    countries.sort(key=lambda x: float(x.get("net_sales") or 0.0), reverse=True)
    return {
        "base_week": base_week,
        "iso_week": iso_week,
        "segment": seg,
        "category": category,
        "comparison_weeks": {"last_year": ly_week, "two_years_ago": two_years_week},
        "filename": latest_file.name,
        "columns_used": {"date": date_col, "net_sales": net_sales_col, "category": category_col, "country": country_col},
        "countries": countries,
    }


def calculate_discount_category_breakdown_month(
    base_week: str,
    month: str,
    data_root: Path,
    segment: str = "all",
) -> Dict[str, Any]:
    """
    Category breakdown for a given calendar month (YYYY-MM), sorted by net sales desc.
    For the latest month (containing base week's end date), values are MTD and LY/2Y are clamped to the same cutoff.
    """
    raw_path = Path(data_root) / "raw" / base_week / "discounts"
    files = [f for f in raw_path.glob("*.*") if not f.name.startswith(".")]
    if not files:
        return {"base_week": base_week, "month": month, "segment": segment, "categories": []}

    latest_file = max(files, key=lambda f: f.stat().st_mtime)
    df = _read_csv_flexible(latest_file)
    df.columns = [c.strip().replace('"', "") for c in df.columns]

    date_col = _pick_column(df, ["Date", "Day", "Dag", "Datum"])
    net_sales_col = _pick_column(df, ["Nettoförsäljning", "Net Revenue", "Net sales", "Net amount"])
    category_col = _pick_column(df, ["Produkttyp", "Product type", "Kategori", "Category"])

    if not date_col or not net_sales_col or not category_col:
        return {
            "base_week": base_week,
            "month": month,
            "segment": segment,
            "error": "Missing required columns",
            "detected": {
                "date": date_col,
                "net_sales": net_sales_col,
                "category": category_col,
                "columns": df.columns.tolist(),
                "filename": latest_file.name,
            },
            "categories": [],
        }

    # Validate month key
    try:
        m_period = pd.Period(str(month), freq="M")
    except Exception:
        return {"base_week": base_week, "month": month, "segment": segment, "error": "Invalid month (expected YYYY-MM)", "categories": []}

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])
    df["_net_sales"] = _to_number(df[net_sales_col])

    seg = (segment or "all").strip().lower()
    if seg not in ("all", "new", "returning"):
        return {"base_week": base_week, "month": month, "segment": seg, "error": f"Invalid segment: {segment}", "categories": []}
    if seg != "all":
        customer_col = _pick_column(
            df,
            [
                "Ny eller återkommande kund",
                "Ny eller återkommande kund (New/Returning)",
                "New or returning customer",
                "New/Returning Customer",
            ],
        )
        if not customer_col:
            return {
                "base_week": base_week,
                "month": month,
                "segment": seg,
                "error": "Missing required columns",
                "detected": {
                    "date": date_col,
                    "net_sales": net_sales_col,
                    "category": category_col,
                    "customer_type": None,
                    "columns": df.columns.tolist(),
                    "filename": latest_file.name,
                },
                "categories": [],
            }
        df["_customer_segment"] = df[customer_col].map(_normalize_customer_segment)
        df = df[df["_customer_segment"] == seg]

    week_end = pd.to_datetime(get_week_date_range(base_week)["end"], errors="coerce")
    if pd.isna(week_end):
        return {"base_week": base_week, "month": month, "segment": seg, "error": "Invalid base_week date range", "categories": []}

    latest_month_key = week_end.to_period("M").strftime("%Y-%m")
    is_latest_month = str(month) == latest_month_key

    start_dt = m_period.start_time.normalize()
    end_dt = week_end if is_latest_month else m_period.end_time.normalize()

    ly_period = m_period - 12
    two_period = m_period - 24
    ly_start = ly_period.start_time.normalize()
    two_start = two_period.start_time.normalize()
    ly_end = (week_end - pd.DateOffset(years=1)) if is_latest_month else ly_period.end_time.normalize()
    two_end = (week_end - pd.DateOffset(years=2)) if is_latest_month else two_period.end_time.normalize()

    def _sum_for_range(s: pd.Timestamp, e: pd.Timestamp) -> Dict[str, float]:
        sub = df.loc[(df[date_col] >= s) & (df[date_col] <= e)]
        if sub.empty:
            return {}
        cat_series = sub[category_col].astype(str).str.strip().replace({"": "Unknown", "nan": "Unknown"})
        grouped = (
            pd.DataFrame({"category": cat_series, "net_sales": sub["_net_sales"]})
            .groupby("category", dropna=False)["net_sales"]
            .sum()
            .to_dict()
        )
        return {str(k): float(v or 0.0) for k, v in grouped.items()}

    cur_map = _sum_for_range(start_dt, end_dt)
    ly_map = _sum_for_range(ly_start, ly_end)
    two_map = _sum_for_range(two_start, two_end)

    cats = set(cur_map.keys()) | set(ly_map.keys()) | set(two_map.keys())
    categories: List[Dict[str, Any]] = []
    for cat in cats:
        cur = float(cur_map.get(cat, 0.0) or 0.0)
        ly = float(ly_map.get(cat, 0.0) or 0.0)
        two = float(two_map.get(cat, 0.0) or 0.0)
        yoy_abs = cur - ly
        yoy_pct = (yoy_abs / ly * 100.0) if ly > 0 else None
        vs_two_abs = cur - two
        vs_two_pct = (vs_two_abs / two * 100.0) if two > 0 else None
        categories.append(
            {
                "category": cat,
                "net_sales": cur,
                "last_year": ly,
                "two_years_ago": two,
                "yoy_abs": yoy_abs,
                "yoy_pct": yoy_pct,
                "vs_two_abs": vs_two_abs,
                "vs_two_pct": vs_two_pct,
            }
        )

    categories.sort(key=lambda x: float(x.get("net_sales") or 0.0), reverse=True)
    return {
        "base_week": base_week,
        "month": str(month),
        # Include iso_week for frontend compatibility (it uses split('-')[0] for the year).
        "iso_week": str(month),
        "segment": seg,
        "comparison_weeks": {"last_year": ly_period.strftime("%Y-%m"), "two_years_ago": two_period.strftime("%Y-%m")},
        "filename": latest_file.name,
        "columns_used": {"date": date_col, "net_sales": net_sales_col, "category": category_col},
        "categories": categories,
    }


def calculate_discount_category_country_breakdown_month(
    base_week: str,
    month: str,
    category: str,
    data_root: Path,
    segment: str = "all",
) -> Dict[str, Any]:
    """
    For a selected category + month, return net sales split by country (Leveransland),
    including LY / 2y ago and growth metrics.
    """
    raw_path = Path(data_root) / "raw" / base_week / "discounts"
    files = [f for f in raw_path.glob("*.*") if not f.name.startswith(".")]
    if not files:
        return {"base_week": base_week, "month": month, "segment": segment, "category": category, "countries": []}

    latest_file = max(files, key=lambda f: f.stat().st_mtime)
    df = _read_csv_flexible(latest_file)
    df.columns = [c.strip().replace('"', "") for c in df.columns]

    date_col = _pick_column(df, ["Date", "Day", "Dag", "Datum"])
    net_sales_col = _pick_column(df, ["Nettoförsäljning", "Net Revenue", "Net sales", "Net amount"])
    category_col = _pick_column(df, ["Produkttyp", "Product type", "Kategori", "Category"])
    country_col = _pick_column(
        df,
        [
            "Leveransland",
            "Land",
            "Country",
            "Shipping country",
            "Delivery country",
            "Ship country",
        ],
    )

    if not date_col or not net_sales_col or not category_col or not country_col:
        return {
            "base_week": base_week,
            "month": month,
            "segment": segment,
            "category": category,
            "error": "Missing required columns",
            "detected": {
                "date": date_col,
                "net_sales": net_sales_col,
                "category": category_col,
                "country": country_col,
                "columns": df.columns.tolist(),
                "filename": latest_file.name,
            },
            "countries": [],
        }

    try:
        m_period = pd.Period(str(month), freq="M")
    except Exception:
        return {"base_week": base_week, "month": month, "segment": segment, "category": category, "error": "Invalid month (expected YYYY-MM)", "countries": []}

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])
    df["_net_sales"] = _to_number(df[net_sales_col])

    seg = (segment or "all").strip().lower()
    if seg not in ("all", "new", "returning"):
        return {"base_week": base_week, "month": month, "segment": seg, "category": category, "error": f"Invalid segment: {segment}", "countries": []}
    if seg != "all":
        customer_col = _pick_column(
            df,
            [
                "Ny eller återkommande kund",
                "Ny eller återkommande kund (New/Returning)",
                "New or returning customer",
                "New/Returning Customer",
            ],
        )
        if not customer_col:
            return {
                "base_week": base_week,
                "month": month,
                "segment": seg,
                "category": category,
                "error": "Missing required columns",
                "detected": {
                    "date": date_col,
                    "net_sales": net_sales_col,
                    "category": category_col,
                    "country": country_col,
                    "customer_type": None,
                    "columns": df.columns.tolist(),
                    "filename": latest_file.name,
                },
                "countries": [],
            }
        df["_customer_segment"] = df[customer_col].map(_normalize_customer_segment)
        df = df[df["_customer_segment"] == seg]

    week_end = pd.to_datetime(get_week_date_range(base_week)["end"], errors="coerce")
    if pd.isna(week_end):
        return {"base_week": base_week, "month": month, "segment": seg, "category": category, "error": "Invalid base_week date range", "countries": []}

    latest_month_key = week_end.to_period("M").strftime("%Y-%m")
    is_latest_month = str(month) == latest_month_key

    start_dt = m_period.start_time.normalize()
    end_dt = week_end if is_latest_month else m_period.end_time.normalize()

    ly_period = m_period - 12
    two_period = m_period - 24
    ly_start = ly_period.start_time.normalize()
    two_start = two_period.start_time.normalize()
    ly_end = (week_end - pd.DateOffset(years=1)) if is_latest_month else ly_period.end_time.normalize()
    two_end = (week_end - pd.DateOffset(years=2)) if is_latest_month else two_period.end_time.normalize()

    # Filter to category
    df = df[df[category_col].astype(str).str.strip() == str(category).strip()]

    def _sum_for_range(s: pd.Timestamp, e: pd.Timestamp) -> Dict[str, float]:
        sub = df.loc[(df[date_col] >= s) & (df[date_col] <= e)]
        if sub.empty:
            return {}
        ctry_series = sub[country_col].astype(str).str.strip().replace({"": "Unknown", "nan": "Unknown"})
        grouped = (
            pd.DataFrame({"country": ctry_series, "net_sales": sub["_net_sales"]})
            .groupby("country", dropna=False)["net_sales"]
            .sum()
            .to_dict()
        )
        return {str(k): float(v or 0.0) for k, v in grouped.items()}

    cur_map = _sum_for_range(start_dt, end_dt)
    ly_map = _sum_for_range(ly_start, ly_end)
    two_map = _sum_for_range(two_start, two_end)

    ctries = set(cur_map.keys()) | set(ly_map.keys()) | set(two_map.keys())
    countries: List[Dict[str, Any]] = []
    for ctry in ctries:
        cur = float(cur_map.get(ctry, 0.0) or 0.0)
        ly = float(ly_map.get(ctry, 0.0) or 0.0)
        two = float(two_map.get(ctry, 0.0) or 0.0)
        yoy_abs = cur - ly
        yoy_pct = (yoy_abs / ly * 100.0) if ly > 0 else None
        vs_two_abs = cur - two
        vs_two_pct = (vs_two_abs / two * 100.0) if two > 0 else None
        countries.append(
            {
                "country": ctry,
                "net_sales": cur,
                "last_year": ly,
                "two_years_ago": two,
                "yoy_abs": yoy_abs,
                "yoy_pct": yoy_pct,
                "vs_two_abs": vs_two_abs,
                "vs_two_pct": vs_two_pct,
            }
        )

    countries.sort(key=lambda x: float(x.get("net_sales") or 0.0), reverse=True)
    return {
        "base_week": base_week,
        "month": str(month),
        "iso_week": str(month),
        "segment": seg,
        "category": category,
        "comparison_weeks": {"last_year": ly_period.strftime("%Y-%m"), "two_years_ago": two_period.strftime("%Y-%m")},
        "filename": latest_file.name,
        "columns_used": {"date": date_col, "net_sales": net_sales_col, "category": category_col, "country": country_col},
        "countries": countries,
    }


def calculate_discount_category_series(
    base_week: str,
    category: str,
    data_root: Path,
    segment: str = "all",
    all_weeks: bool = False,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """Weekly net sales series for a category (optionally full history up to base week)."""
    raw_path = Path(data_root) / "raw" / base_week / "discounts"
    files = [f for f in raw_path.glob("*.*") if not f.name.startswith(".")]
    if not files:
        return {"base_week": base_week, "segment": segment, "category": category, "weeks": []}

    latest_file = max(files, key=lambda f: f.stat().st_mtime)
    df = _read_csv_flexible(latest_file)
    df.columns = [c.strip().replace('"', "") for c in df.columns]

    date_col = _pick_column(df, ["Date", "Day", "Dag", "Datum"])
    net_sales_col = _pick_column(df, ["Nettoförsäljning", "Net Revenue", "Net sales", "Net amount"])
    category_col = _pick_column(df, ["Produkttyp", "Product type", "Kategori", "Category"])

    if not date_col or not net_sales_col or not category_col:
        return {
            "base_week": base_week,
            "segment": segment,
            "category": category,
            "error": "Missing required columns",
            "detected": {
                "date": date_col,
                "net_sales": net_sales_col,
                "category": category_col,
                "columns": df.columns.tolist(),
                "filename": latest_file.name,
            },
            "weeks": [],
        }

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])
    if end_date:
        end_dt = pd.to_datetime(end_date, errors="coerce")
        if pd.notna(end_dt):
            df = df[df[date_col] <= end_dt]

    df["_week"] = _iso_week_series(df[date_col])
    df["_net_sales"] = _to_number(df[net_sales_col])

    seg = (segment or "all").strip().lower()
    if seg not in ("all", "new", "returning"):
        return {"base_week": base_week, "segment": seg, "category": category, "error": f"Invalid segment: {segment}", "weeks": []}
    if seg != "all":
        customer_col = _pick_column(
            df,
            [
                "Ny eller återkommande kund",
                "Ny eller återkommande kund (New/Returning)",
                "New or returning customer",
                "New/Returning Customer",
            ],
        )
        if not customer_col:
            return {
                "base_week": base_week,
                "segment": seg,
                "category": category,
                "error": "Missing required columns",
                "detected": {
                    "date": date_col,
                    "net_sales": net_sales_col,
                    "category": category_col,
                    "customer_type": None,
                    "columns": df.columns.tolist(),
                    "filename": latest_file.name,
                },
                "weeks": [],
            }
        df["_customer_segment"] = df[customer_col].map(_normalize_customer_segment)
        df = df[df["_customer_segment"] == seg]

    df = df[df[category_col].astype(str).str.strip() == str(category).strip()]
    if df.empty:
        return {
            "base_week": base_week,
            "segment": seg,
            "category": category,
            "filename": latest_file.name,
            "columns_used": {"date": date_col, "net_sales": net_sales_col, "category": category_col},
            "weeks": [],
        }

    if all_weeks:
        expected_weeks = _sort_iso_weeks(df["_week"].dropna().unique().tolist())
    else:
        expected_weeks = _build_display_weeks(base_week, 8)

    grouped = df.groupby("_week", dropna=False)["_net_sales"].sum().to_dict()
    weeks_out = [{"week": w, "net_sales": float(grouped.get(w, 0.0) or 0.0)} for w in expected_weeks]
    return {
        "base_week": base_week,
        "segment": seg,
        "category": category,
        "filename": latest_file.name,
        "columns_used": {"date": date_col, "net_sales": net_sales_col, "category": category_col},
        "weeks": weeks_out,
    }


def calculate_discount_level_for_weeks(
    base_week: str,
    num_weeks: int,
    data_root: Path,
) -> Dict[str, Any]:
    """
    Discount level metrics for last N weeks with YoY, for Total and per market.

    Metrics:
    - discounted_sales
    - full_price_sales
    - total_sales
    - discounted_share_pct
    - discount_amount
    - discount_level_pct
    """
    raw_path = Path(data_root) / "raw" / base_week / "discounts"
    files = [f for f in raw_path.glob("*.*") if not f.name.startswith(".")]
    if not files:
        return {"base_week": base_week, "num_weeks": num_weeks, "weeks": [], "markets": []}

    latest_file = max(files, key=lambda f: f.stat().st_mtime)
    df = _read_csv_flexible(latest_file)
    df.columns = [c.strip().replace('"', "") for c in df.columns]

    date_col = _pick_column(df, ["Date", "Day", "Dag", "Datum"])
    net_sales_col = _pick_column(df, ["Nettoförsäljning", "Net Revenue", "Net sales", "Net amount"])
    ordinary_price_col = _pick_column(
        df,
        [
            "Produktvariantens ordinare pris",
            "Produktvariantens ordinarie pris",
            "Ordinarie pris",
            "Regular price",
            "Compare at price",
        ],
    )
    price_col = _pick_column(df, ["Produktvariantpris", "Produktvariantpris (SEK)", "Variant price", "Price"])
    qty_col = _pick_column(df, ["Antal", "Quantity", "Qty"])
    country_col = _pick_column(
        df,
        [
            "Leveransland",
            "Country",
            "Shipping country",
            "Delivery country",
            "Ship country",
        ],
    )

    if not date_col or not net_sales_col or not ordinary_price_col:
        return {
            "base_week": base_week,
            "num_weeks": num_weeks,
            "error": "Missing required columns",
            "detected": {
                "date": date_col,
                "net_sales": net_sales_col,
                "ordinary_price": ordinary_price_col,
                "price": price_col,
                "qty": qty_col,
                "country": country_col,
                "columns": df.columns.tolist(),
                "filename": latest_file.name,
            },
            "weeks": [],
            "markets": [],
        }

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col]).copy()
    df["_week"] = _iso_week_series(df[date_col])
    df["_net_sales"] = _to_number(df[net_sales_col])
    df["_ordinary_price"] = _to_number(df[ordinary_price_col])
    df["_price"] = _to_number(df[price_col]) if price_col else 0.0
    df["_qty"] = _to_number(df[qty_col]) if qty_col else 1.0
    df["_qty"] = df["_qty"].replace(0, 1.0)
    df["_is_discounted"] = df["_ordinary_price"] > 0

    # Discount amount estimation from row price deltas.
    df["_discount_amount"] = ((df["_ordinary_price"] - df["_price"]).clip(lower=0.0) * df["_qty"]).fillna(0.0)
    df["_gross_before_discount"] = (
        (df["_ordinary_price"].where(df["_ordinary_price"] > 0, df["_price"]) * df["_qty"]).fillna(0.0)
    )

    if country_col:
        m = df[country_col].astype(str).str.strip()
        df["_market"] = m.replace({"": "Unknown", "nan": "Unknown", "None": "Unknown"})
    else:
        df["_market"] = "Total"

    expected_weeks = _build_display_weeks(base_week, num_weeks)
    expected_last_year = [f"{int(w.split('-')[0]) - 1}-{w.split('-')[1]}" for w in expected_weeks]
    df = df[df["_week"].isin(set(expected_weeks + expected_last_year))]

    def _agg(sub: pd.DataFrame) -> Dict[str, float]:
        if sub.empty:
            return {
                "discounted_sales": 0.0,
                "full_price_sales": 0.0,
                "total_sales": 0.0,
                "discounted_share_pct": 0.0,
                "discount_amount": 0.0,
                "discount_level_pct": 0.0,
            }
        discounted_sales = float(sub.loc[sub["_is_discounted"], "_net_sales"].sum() or 0.0)
        full_price_sales = float(sub.loc[~sub["_is_discounted"], "_net_sales"].sum() or 0.0)
        total_sales = discounted_sales + full_price_sales
        discount_amount = float(sub["_discount_amount"].sum() or 0.0)
        gross_before = float(sub["_gross_before_discount"].sum() or 0.0)
        discounted_share_pct = (discounted_sales / total_sales * 100.0) if total_sales > 0 else 0.0
        discount_level_pct = (discount_amount / gross_before * 100.0) if gross_before > 0 else 0.0
        return {
            "discounted_sales": discounted_sales,
            "full_price_sales": full_price_sales,
            "total_sales": total_sales,
            "discounted_share_pct": round(discounted_share_pct, 2),
            "discount_amount": discount_amount,
            "discount_level_pct": round(discount_level_pct, 2),
        }

    markets = sorted([m for m in df["_market"].dropna().astype(str).unique().tolist() if m and m != "Total"])
    weeks_out: List[Dict[str, Any]] = []
    for w in expected_weeks:
        ly_w = f"{int(w.split('-')[0]) - 1}-{w.split('-')[1]}"
        cur = df[df["_week"] == w]
        ly = df[df["_week"] == ly_w]
        total_cur = _agg(cur)
        total_ly = _agg(ly)
        per_market: Dict[str, Any] = {}
        for market in markets:
            m_cur = _agg(cur[cur["_market"] == market])
            m_ly = _agg(ly[ly["_market"] == market])
            per_market[market] = {**m_cur, "last_year": {"week": ly_w, **m_ly}}
        weeks_out.append(
            {
                "week": w,
                "total": {**total_cur, "last_year": {"week": ly_w, **total_ly}},
                "markets": per_market,
            }
        )

    return {
        "base_week": base_week,
        "num_weeks": num_weeks,
        "filename": latest_file.name,
        "columns_used": {
            "date": date_col,
            "net_sales": net_sales_col,
            "ordinary_price": ordinary_price_col,
            "price": price_col,
            "qty": qty_col,
            "country": country_col,
        },
        "markets": markets,
        "weeks": weeks_out,
    }


def preview_discounts_file(week: str, data_root: Path, nrows: int = 10) -> Dict[str, Any]:
    raw_path = Path(data_root) / "raw" / week / "discounts"
    files = [f for f in raw_path.glob("*.*") if not f.name.startswith(".")]
    if not files:
        return {"week": week, "filename": None, "columns": [], "row_count": 0, "sample_rows": []}

    latest_file = max(files, key=lambda f: f.stat().st_mtime)
    df = _read_csv_flexible(latest_file, nrows=nrows)
    df.columns = [c.strip().replace('"', "") for c in df.columns]
    # basic row count (fast-ish)
    try:
        with open(latest_file, "r", encoding="utf-8") as f:
            row_count = max(0, sum(1 for _ in f) - 1)
    except Exception:
        row_count = 0

    sample_rows = df.fillna("").to_dict(orient="records")
    return {
        "week": week,
        "filename": latest_file.name,
        "columns": df.columns.tolist(),
        "row_count": row_count,
        "sample_rows": sample_rows,
    }


