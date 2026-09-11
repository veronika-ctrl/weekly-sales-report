"""
Customer retention by last-click acquisition channel.

This is a separate report from Adjusted aMER. The Dema customer export is
last-click AcquisitionChannelGroup — not CFA — because CFA is not available
at individual-customer grain. Do not compare these rates to CFA headline aMER.

Input: Retention_customers_*.csv (semicolon), one row per customer.

    CustomerId;AcquisitionDate;...;AcquisitionChannelGroup;...;Eligible180d;
    Repeated180d;NetSales180d;NetSalesTotal180d;DaysToSecondOrder;
    ...;FullPriceShareLifetime

Metrics are computed only on Eligible180d = 1. Backfilled stays its own row
and is never folded into organic, unknown, or unattributed.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from loguru import logger

from weekly_report.src.metrics.discounts_sales import _read_csv_flexible

RETENTION_CUSTOMERS_TYPE = "retention_customers"

# Display order: paid, organic, leftover, backfilled last among channels.
CHANNEL_ORDER = [
    "sem",
    "social_ppc",
    "affiliate",
    "direct",
    "organic",
    "email",
    "referral",
    "social_organic",
    "unknown",
    "backfilled",
]

BACKFILLED_GROUP = "backfilled"


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _norm_group(value: Any) -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return text or "unknown"


def _to_number(series: pd.Series) -> pd.Series:
    as_str = series.astype(str).str.strip().str.replace("\u00a0", "", regex=False)
    as_str = as_str.replace({"": None, "nan": None, "None": None, "NaT": None})
    return pd.to_numeric(as_str.str.replace(",", ".", regex=False), errors="coerce")


def _scan_retention_files(data_root: Path) -> List[Path]:
    raw = Path(data_root) / "raw"
    if not raw.exists():
        return []
    files = [
        f
        for f in raw.glob(f"*/{RETENTION_CUSTOMERS_TYPE}/*.*")
        if f.suffix.lower() == ".csv" and not f.name.startswith(".")
    ]
    files.sort(key=lambda p: p.stat().st_mtime)
    return files


def load_retention_customers(data_root: Path) -> pd.DataFrame:
    """Load customer-level retention export; latest row wins per CustomerId."""
    frames: List[pd.DataFrame] = []
    for path in _scan_retention_files(data_root):
        try:
            df = _read_csv_flexible(path)
        except Exception as exc:
            logger.warning(f"Skipping retention file {path}: {exc}")
            continue
        df.columns = [str(c).strip().strip('"').strip("'") for c in df.columns]
        df["_source_file"] = path.name
        df["_source_mtime"] = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    if "CustomerId" in out.columns:
        out = out.sort_values("_source_mtime").drop_duplicates("CustomerId", keep="last")
    return out.reset_index(drop=True)


def _eligible(df: pd.DataFrame) -> pd.DataFrame:
    flag = _to_number(df["Eligible180d"])
    return df.loc[flag.fillna(0).eq(1)].copy()


def _channel_metrics(part: pd.DataFrame, channel: str) -> Dict[str, Any]:
    customers = int(len(part))
    repeat = _to_number(part["Repeated180d"])
    ns_total = _to_number(part["NetSalesTotal180d"])
    fp = _to_number(part["FullPriceShareLifetime"])
    days = _to_number(part["DaysToSecondOrder"])
    days_obs = days.dropna()
    fp_obs = fp.dropna()
    return {
        "channel_group": channel,
        "is_backfilled": channel == BACKFILLED_GROUP,
        "is_total": False,
        "customers": customers,
        "repeat_rate_180d": float(repeat.mean()) if customers else None,
        "net_sales_per_customer_180d": float(ns_total.mean()) if customers else None,
        "full_price_share_lifetime": float(fp_obs.mean()) if len(fp_obs) else None,
        "median_days_to_second_order": float(days_obs.median()) if len(days_obs) else None,
        "repeaters_180d": int(repeat.fillna(0).eq(1).sum()),
        "full_price_share_n": int(len(fp_obs)),
        "second_order_n": int(len(days_obs)),
    }


def _sort_channels(names: List[str]) -> List[str]:
    extras = sorted(n for n in names if n not in CHANNEL_ORDER)
    ordered = [n for n in CHANNEL_ORDER if n in names]
    return ordered + extras


FOOTNOTES = [
    "Last-click AcquisitionChannelGroup from the Dema customer export. "
    "CFA is not available at customer grain, so these figures are not "
    "comparable to Adjusted aMER (CFA) headlines.",
    "All metrics use Eligible180d = 1 only (customers with 180 days of observation).",
    "180-day repeat rate = share with Repeated180d = 1.",
    "Net sales per customer (180d) = mean of NetSalesTotal180d (acquisition + 180-day sales).",
    "Full-price share (lifetime) = mean of FullPriceShareLifetime among customers with a defined share.",
    "Median days to second order uses DaysToSecondOrder among customers who repeated within 180 days.",
    "Backfilled is kept as its own channel and is never folded into organic, unknown, or unattributed.",
]


def _empty_payload(
    *,
    message: str,
    files: Optional[List[Dict[str, str]]] = None,
    customer_count: int = 0,
    warnings: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    return {
        "available": False,
        "message": message,
        "attribution": "last_click",
        "filter": "Eligible180d = 1",
        "channels": [],
        "total": None,
        "files": files or [],
        "customer_count": customer_count,
        "eligible_count": 0,
        "cohort_min": None,
        "cohort_max": None,
        "acquisition_min": None,
        "acquisition_max": None,
        "as_of": None,
        "footnotes": list(FOOTNOTES),
        "warnings": warnings or [],
    }


def calculate_retention_by_channel(data_root: Path) -> Dict[str, Any]:
    files = _scan_retention_files(data_root)
    if not files:
        return _empty_payload(
            message=(
                "Upload Retention_customers_*.csv in Settings under "
                "Retention by acquisition channel."
            )
        )

    raw = load_retention_customers(data_root)
    required = [
        "AcquisitionChannelGroup",
        "Eligible180d",
        "Repeated180d",
        "NetSalesTotal180d",
        "DaysToSecondOrder",
        "FullPriceShareLifetime",
    ]
    missing_cols = [c for c in required if c not in raw.columns]
    if missing_cols:
        return _empty_payload(
            message=f"Retention file is missing columns: {', '.join(missing_cols)}.",
            files=[
                {
                    "filename": p.name,
                    "uploaded_at": _iso(datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)),
                }
                for p in files
            ],
            customer_count=int(len(raw)),
            warnings=[{"code": "missing_columns", "message": ", ".join(missing_cols)}],
        )

    work = raw.copy()
    work["channel_group"] = work["AcquisitionChannelGroup"].map(_norm_group)
    eligible = _eligible(work)
    channels = []
    for name in _sort_channels(sorted(eligible["channel_group"].unique())):
        part = eligible[eligible["channel_group"] == name]
        channels.append(_channel_metrics(part, name))
    total = _channel_metrics(eligible, "all")
    total["channel_group"] = "all"
    total["is_total"] = True
    total["is_backfilled"] = False

    cohort = eligible["AcquisitionCohort"] if "AcquisitionCohort" in eligible.columns else pd.Series(dtype=str)
    acq_dates = pd.to_datetime(eligible.get("AcquisitionDate"), errors="coerce") if "AcquisitionDate" in eligible.columns else pd.Series(dtype="datetime64[ns]")
    as_of_dt = None
    if "_source_mtime" in work.columns and work["_source_mtime"].notna().any():
        as_of_dt = pd.to_datetime(work["_source_mtime"], utc=True).max().to_pydatetime()

    return {
        "available": True,
        "message": None,
        "attribution": "last_click",
        "filter": "Eligible180d = 1",
        "channels": channels,
        "total": total,
        "files": [
            {
                "filename": p.name,
                "uploaded_at": _iso(datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)),
            }
            for p in files
        ],
        "customer_count": int(len(work)),
        "eligible_count": int(len(eligible)),
        "cohort_min": str(cohort.min()) if len(cohort) and pd.notna(cohort.min()) else None,
        "cohort_max": str(cohort.max()) if len(cohort) and pd.notna(cohort.max()) else None,
        "acquisition_min": acq_dates.min().date().isoformat() if len(acq_dates.dropna()) else None,
        "acquisition_max": acq_dates.max().date().isoformat() if len(acq_dates.dropna()) else None,
        "as_of": _iso(as_of_dt) if as_of_dt else None,
        "footnotes": list(FOOTNOTES),
        "warnings": [],
    }
