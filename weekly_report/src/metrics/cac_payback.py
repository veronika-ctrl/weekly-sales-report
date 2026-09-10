"""
CAC payback by last-click acquisition channel.

Sibling of Retention by channel — not Adjusted aMER. These Dema customer-grain
exports use last-click ChannelGroup; CFA is not available here. Net GP2 is
derived from channel margin rates, not an official per-customer metric.
Payback is an average (not marginal) return.

Inputs (semicolon CSV):

    cac_payback_groups   — ChannelGroup CAC, GP2_180d, Payback_180d
    cac_payback_segments — campaign-segment CAC / payback (180d)
    cac_payback_horizon  — 180d vs 365d payback, same channels/segments
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from loguru import logger

from weekly_report.src.metrics.discounts_sales import _read_csv_flexible

CAC_PAYBACK_GROUPS_TYPE = "cac_payback_groups"
CAC_PAYBACK_SEGMENTS_TYPE = "cac_payback_segments"
CAC_PAYBACK_HORIZON_TYPE = "cac_payback_horizon"
CAC_PAYBACK_FILE_TYPES = (
    CAC_PAYBACK_GROUPS_TYPE,
    CAC_PAYBACK_SEGMENTS_TYPE,
    CAC_PAYBACK_HORIZON_TYPE,
)

CHANNEL_ORDER = ["social_ppc", "sem", "affiliate"]

SEGMENT_KIND_ORDER = [
    "all",
    "prospecting",
    "retargeting",
    "branded",
    "non_branded",
    "editorial",
    "coupon",
]

CAVEATS = [
    "Net GP2 per customer is derived from channel margin rates applied to "
    "last-click net sales — it is not an official per-customer GP2 metric.",
    "These are average returns, not marginal. Scaling spend will not "
    "necessarily reproduce the same CAC or payback.",
    "Branded search and editorial affiliate are capped by demand and "
    "inventory; a high payback multiple does not mean the channel is scalable.",
]

FOOTNOTES = [
    "Last-click AcquisitionChannelGroup / ChannelGroup. Not comparable to "
    "Adjusted aMER (CFA) headlines.",
    "Headline CAC = spend ÷ new customers (full allocation). Payback 180d = "
    "180-day net GP2 per customer ÷ CAC.",
    "Campaign segments use the same full-allocation CAC and payback. "
    "New-share CAC is shown where the export provides it (blank for affiliate).",
    "The 365-day comparison uses customers with a full year of observation, "
    "so the cohort is smaller than the 180-day headline.",
    *CAVEATS,
]


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _norm_group(value: Any) -> str:
    text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return text or "unknown"


def _norm_segment(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return "unknown"
    if text.startswith("all"):
        return "all"
    if "prospect" in text or text.startswith("tof"):
        return "prospecting"
    if "retarget" in text or text.startswith("bof"):
        return "retargeting"
    if "non-brand" in text or "non_brand" in text or "nonbrand" in text:
        return "non_branded"
    if "brand" in text:
        return "branded"
    if "editorial" in text or "content" in text:
        return "editorial"
    if "coupon" in text or "cashback" in text:
        return "coupon"
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_") or "unknown"


def _to_number(series: pd.Series) -> pd.Series:
    as_str = series.astype(str).str.strip().str.replace("\u00a0", "", regex=False)
    as_str = as_str.replace({"": None, "nan": None, "None": None, "NaT": None})
    return pd.to_numeric(as_str.str.replace(",", ".", regex=False), errors="coerce")


def _num(row: pd.Series, *names: str) -> Optional[float]:
    for name in names:
        if name in row.index:
            val = row[name]
            if pd.isna(val):
                return None
            try:
                return float(val)
            except (TypeError, ValueError):
                return None
    return None


def _int(row: pd.Series, *names: str) -> Optional[int]:
    val = _num(row, *names)
    if val is None:
        return None
    return int(round(val))


def _sort_channels(names: List[str]) -> List[str]:
    extras = sorted(n for n in names if n not in CHANNEL_ORDER)
    return [n for n in CHANNEL_ORDER if n in names] + extras


def _segment_rank(kind: str) -> int:
    try:
        return SEGMENT_KIND_ORDER.index(kind)
    except ValueError:
        return len(SEGMENT_KIND_ORDER)


def _scan_type(data_root: Path, file_type: str) -> List[Path]:
    raw = Path(data_root) / "raw"
    if not raw.exists():
        return []
    files = [
        f
        for f in raw.glob(f"*/{file_type}/*.*")
        if f.suffix.lower() == ".csv" and not f.name.startswith(".")
    ]
    files.sort(key=lambda p: p.stat().st_mtime)
    return files


def _file_meta(paths: List[Path]) -> List[Dict[str, str]]:
    return [
        {
            "filename": p.name,
            "uploaded_at": _iso(datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)),
        }
        for p in paths
    ]


def _period_from_name(name: str) -> Tuple[Optional[str], Optional[str]]:
    hits = re.findall(r"(20\d{2}-\d{2})", name)
    if len(hits) >= 2:
        return hits[0], hits[1]
    if len(hits) == 1:
        return hits[0], hits[0]
    return None, None


def _load_latest(paths: List[Path]) -> pd.DataFrame:
    if not paths:
        return pd.DataFrame()
    path = paths[-1]
    try:
        df = _read_csv_flexible(path)
    except Exception as exc:
        logger.warning(f"Skipping CAC payback file {path}: {exc}")
        return pd.DataFrame()
    df.columns = [str(c).strip().strip('"').strip("'") for c in df.columns]
    return df


def _empty_payload(message: str, files: Optional[Dict[str, List[Dict[str, str]]]] = None) -> Dict[str, Any]:
    return {
        "available": False,
        "message": message,
        "attribution": "last_click",
        "period_min": None,
        "period_max": None,
        "channels": [],
        "segments": [],
        "horizon": [],
        "files": files
        or {
            "groups": [],
            "segments": [],
            "horizon": [],
        },
        "missing_files": {
            "groups": True,
            "segments": True,
            "horizon": True,
        },
        "as_of": None,
        "caveats": list(CAVEATS),
        "footnotes": list(FOOTNOTES),
        "warnings": [],
    }


def _channel_rows(df: pd.DataFrame) -> List[Dict[str, Any]]:
    if df.empty or "ChannelGroup" not in df.columns:
        return []
    work = df.copy()
    work["channel_group"] = work["ChannelGroup"].map(_norm_group)
    for col in work.columns:
        if col in ("ChannelGroup", "channel_group"):
            continue
        work[col] = _to_number(work[col])
    rows = []
    for name in _sort_channels(sorted(work["channel_group"].unique())):
        part = work[work["channel_group"] == name].iloc[-1]
        rows.append(
            {
                "channel_group": name,
                "spend": _num(part, "Spend"),
                "new_customers": _int(part, "NewCustomers"),
                "cac": _num(part, "CAC"),
                "gp2_first_order": _num(part, "GP2_FirstOrder"),
                "gp2_180d": _num(part, "GP2_180d"),
                "payback_first_order": _num(part, "Payback_FirstOrder"),
                "payback_180d": _num(part, "Payback_180d"),
                "payback_low": _num(part, "PB_low"),
                "payback_high": _num(part, "PB_high"),
            }
        )
    return rows


def _segment_rows(df: pd.DataFrame) -> List[Dict[str, Any]]:
    group_col = "AcquisitionChannelGroup" if "AcquisitionChannelGroup" in df.columns else "ChannelGroup"
    if df.empty or group_col not in df.columns or "Segment" not in df.columns:
        return []
    work = df.copy()
    work["channel_group"] = work[group_col].map(_norm_group)
    work["segment_label"] = work["Segment"].astype(str).str.strip()
    work["segment"] = work["Segment"].map(_norm_segment)
    numeric_cols = [c for c in work.columns if c not in (group_col, "Segment", "Horizon", "channel_group", "segment_label", "segment")]
    for col in numeric_cols:
        work[col] = _to_number(work[col])
    rows = []
    for _, part in work.iterrows():
        label = str(part.get("segment_label") or "")
        rows.append(
            {
                "channel_group": part["channel_group"],
                "segment": part["segment"],
                "segment_label": label,
                "indicative": "indicative" in label.lower(),
                "horizon": str(part["Horizon"]).strip() if "Horizon" in part.index and pd.notna(part.get("Horizon")) else "180d",
                "spend": _num(part, "Spend"),
                "new_customers": _int(part, "NewCustomers"),
                "repeat_rate": _num(part, "RepeatRate"),
                "cac": _num(part, "CAC_full", "CAC"),
                "cac_newshare": _num(part, "CAC_newshare"),
                "gp2_per_customer": _num(part, "GP2_perCust", "GP2_180d"),
                "payback": _num(part, "Payback_full", "Payback_180d"),
                "payback_newshare": _num(part, "Payback_newshare"),
            }
        )
    rows.sort(
        key=lambda r: (
            CHANNEL_ORDER.index(r["channel_group"]) if r["channel_group"] in CHANNEL_ORDER else 99,
            _segment_rank(r["segment"]),
        )
    )
    return rows


def _horizon_rows(df: pd.DataFrame) -> List[Dict[str, Any]]:
    group_col = "AcquisitionChannelGroup" if "AcquisitionChannelGroup" in df.columns else "ChannelGroup"
    if df.empty or group_col not in df.columns:
        return []
    work = df.copy()
    work["channel_group"] = work[group_col].map(_norm_group)
    if "Segment" in work.columns:
        work["segment_label"] = work["Segment"].astype(str).str.strip()
        work["segment"] = work["Segment"].map(_norm_segment)
    else:
        work["segment_label"] = "ALL campaigns"
        work["segment"] = "all"
    numeric_cols = [
        c
        for c in work.columns
        if c not in (group_col, "Segment", "channel_group", "segment_label", "segment")
    ]
    for col in numeric_cols:
        work[col] = _to_number(work[col])
    rows = []
    for _, part in work.iterrows():
        kind = part["segment"]
        rows.append(
            {
                "channel_group": part["channel_group"],
                "segment": kind,
                "segment_label": str(part.get("segment_label") or ""),
                "is_channel_total": kind == "all",
                "new_customers_180": _int(part, "NewCustomers_180", "NewCustomers"),
                "cac_180": _num(part, "CAC_full_180", "CAC"),
                "gp2_180": _num(part, "GP2_perCust_180", "GP2_180d"),
                "gp2_365": _num(part, "GP2_perCust_365"),
                "gp2_uplift_pct": _num(part, "GP2_uplift_pct"),
                "payback_180": _num(part, "Payback_180"),
                "payback_365": _num(part, "Payback_365"),
            }
        )
    rows.sort(
        key=lambda r: (
            0 if r["channel_group"] in CHANNEL_ORDER else 1,
            CHANNEL_ORDER.index(r["channel_group"]) if r["channel_group"] in CHANNEL_ORDER else 99,
            0 if r["is_channel_total"] else 1,
            _segment_rank(r["segment"]),
        )
    )
    return rows


def calculate_cac_payback(data_root: Path) -> Dict[str, Any]:
    group_files = _scan_type(data_root, CAC_PAYBACK_GROUPS_TYPE)
    segment_files = _scan_type(data_root, CAC_PAYBACK_SEGMENTS_TYPE)
    horizon_files = _scan_type(data_root, CAC_PAYBACK_HORIZON_TYPE)
    files = {
        "groups": _file_meta(group_files),
        "segments": _file_meta(segment_files),
        "horizon": _file_meta(horizon_files),
    }
    if not group_files and not segment_files and not horizon_files:
        return _empty_payload(
            "Upload the CAC payback CSVs in Settings under CAC payback by channel."
        )

    groups_df = _load_latest(group_files)
    segments_df = _load_latest(segment_files)
    horizon_df = _load_latest(horizon_files)
    channels = _channel_rows(groups_df)
    segments = _segment_rows(segments_df)
    horizon = _horizon_rows(horizon_df)

    warnings: List[Dict[str, str]] = []
    if not group_files:
        warnings.append(
            {
                "code": "missing_groups",
                "message": "Headline ChannelGroup file is missing. Upload CAC_payback_by_channelgroup_*.csv.",
            }
        )
    elif groups_df.empty or "ChannelGroup" not in groups_df.columns:
        warnings.append(
            {
                "code": "groups_unreadable",
                "message": "ChannelGroup CAC file is missing the ChannelGroup column.",
            }
        )
    if not segment_files:
        warnings.append(
            {
                "code": "missing_segments",
                "message": "Campaign-segment file is missing. Upload CAC_payback_by_campaign_segment.csv.",
            }
        )
    if not horizon_files:
        warnings.append(
            {
                "code": "missing_horizon",
                "message": "180d vs 365d file is missing. Upload CAC_payback_horizon_180d_vs_365d.csv.",
            }
        )

    period_min, period_max = (None, None)
    if group_files:
        period_min, period_max = _period_from_name(group_files[-1].name)

    mtimes = []
    for path in [*group_files, *segment_files, *horizon_files]:
        mtimes.append(datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc))
    as_of = max(mtimes) if mtimes else None

    available = bool(channels or segments or horizon)
    message = None
    if not available:
        message = "CAC payback files were found but could not be parsed."

    return {
        "available": available,
        "message": message,
        "attribution": "last_click",
        "period_min": period_min,
        "period_max": period_max,
        "channels": channels,
        "segments": segments,
        "horizon": horizon,
        "files": files,
        "missing_files": {
            "groups": not bool(group_files),
            "segments": not bool(segment_files),
            "horizon": not bool(horizon_files),
        },
        "as_of": _iso(as_of) if as_of else None,
        "caveats": list(CAVEATS),
        "footnotes": list(FOOTNOTES),
        "warnings": warnings,
    }
