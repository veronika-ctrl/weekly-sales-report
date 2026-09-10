"""
Email Performance (Klaviyo) — standalone from Adjusted aMER.

Recipient-based attribution: anyone who received or opened a message and later
purchased. Do not sum with CFA / last-click aMER totals.

Source of truth while the private API key is unset: Klaviyo_email_performance_*.csv.
When KLAVIYO_PRIVATE_API_KEY is set, the report pulls last-12-months values from
the Klaviyo Reporting API and falls back to the CSV if the API call fails.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from loguru import logger

from weekly_report.src.fx_rates import get_latest_usd_sek_rate
from weekly_report.src.klaviyo_client import (
    find_placed_order_metric_id,
    klaviyo_key_configured,
    query_values_report,
)
from weekly_report.src.metrics.discounts_sales import _read_csv_flexible

KLAVIYO_EMAIL_TYPE = "klaviyo_email"

HEADER_NOTE = (
    "Klaviyo-native view of email performance — recipient-based attribution "
    "(credits anyone who received or opened a message and later purchased). "
    "This is a different measurement than Adjusted aMER's last-click channel "
    "attribution and should not be summed with those totals — the same order "
    "can appear in both reports under different channels."
)

STATS = ["recipients", "conversion_uniques", "conversions", "conversion_value"]


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _public_api_failure_message(exc: BaseException) -> str:
    """User-facing API fallback copy — never dump Klaviyo JSON bodies."""
    text = str(exc)
    lowered = text.lower()
    if "429" in text or "throttled" in lowered:
        return (
            "Klaviyo rate-limited the live pull (HTTP 429). "
            "Showing the uploaded CSV instead — retry in about a minute."
        )
    if "401" in text or "403" in text or "authentication" in lowered or "unauthorized" in lowered:
        return "Klaviyo rejected the private API key. Showing the uploaded CSV instead."
    head = text.split(":", 1)[0].strip()
    if len(head) > 120:
        head = head[:117] + "..."
    return f"Klaviyo API pull failed ({head}). Showing the uploaded CSV instead."


def _to_number(series: pd.Series) -> pd.Series:
    as_str = series.astype(str).str.strip().str.replace("\u00a0", "", regex=False)
    as_str = as_str.replace({"": None, "nan": None, "None": None, "NaT": None})
    return pd.to_numeric(as_str.str.replace(",", ".", regex=False), errors="coerce")


def _scan_files(data_root: Path) -> List[Path]:
    raw = Path(data_root) / "raw"
    if not raw.exists():
        return []
    files = [
        f
        for f in raw.glob(f"*/{KLAVIYO_EMAIL_TYPE}/*.*")
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


def _row(
    *,
    kind: str,
    name: str,
    recipients: float,
    unique_converters: float,
    conversions: Optional[float],
    revenue_usd: float,
    campaign_count: Optional[int] = None,
) -> Dict[str, Any]:
    rec = int(round(recipients or 0))
    conv = int(round(unique_converters or 0))
    return {
        "kind": kind,
        "name": name,
        "recipients": rec,
        "unique_converters": conv,
        "conversions": None if conversions is None else int(round(conversions)),
        "conversion_rate": (conv / rec) if rec else None,
        "revenue_usd": float(revenue_usd or 0),
        "campaign_count": campaign_count,
        "is_newsletter": kind == "campaign",
    }


def _totals(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    rec = sum(int(r["recipients"] or 0) for r in rows)
    conv = sum(int(r["unique_converters"] or 0) for r in rows)
    usd = sum(float(r["revenue_usd"] or 0) for r in rows)
    return {
        "recipients": rec,
        "unique_converters": conv,
        "conversion_rate": (conv / rec) if rec else None,
        "revenue_usd": usd,
    }


def _apply_sek(rows: List[Dict[str, Any]], rate: Optional[float]) -> None:
    for r in rows:
        usd = float(r.get("revenue_usd") or 0)
        r["revenue_sek"] = None if rate is None else usd * rate


def _empty(message: str, files: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    return {
        "available": False,
        "message": message,
        "source": "none",
        "header_note": HEADER_NOTE,
        "timeframe": "last_12_months",
        "flows": [],
        "newsletter": None,
        "total": None,
        "fx": {"applied": False, "source_currency": "USD", "target_currency": "SEK"},
        "klaviyo": {
            "key_configured": klaviyo_key_configured(),
            "connected": False,
        },
        "files": files or [],
        "as_of": None,
        "footnotes": [
            HEADER_NOTE,
            "Unique converters are Klaviyo's per-flow / per-campaign uniques; "
            "the overall total sums those rows and can count a person twice if they "
            "converted from both a flow and a campaign.",
            "Revenue is converted from Klaviyo USD to SEK with an approximate ECB daily rate.",
        ],
        "warnings": [],
        "caveats": [],
    }


def _from_csv(df: pd.DataFrame) -> tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    work = df.copy()
    work.columns = [str(c).strip().strip('"').strip("'") for c in work.columns]
    required = {"Type", "Name", "Recipients", "UniqueConverters", "RevenueUSD"}
    missing = required - set(work.columns)
    if missing:
        raise ValueError(f"missing columns: {', '.join(sorted(missing))}")
    work["Type"] = work["Type"].astype(str).str.strip().str.lower()
    work["Name"] = work["Name"].astype(str).str.strip()
    work["Recipients"] = _to_number(work["Recipients"]).fillna(0)
    work["UniqueConverters"] = _to_number(work["UniqueConverters"]).fillna(0)
    work["RevenueUSD"] = _to_number(work["RevenueUSD"]).fillna(0)
    conversions = _to_number(work["Conversions"]) if "Conversions" in work.columns else None

    flows: List[Dict[str, Any]] = []
    newsletter = None
    for i, part in work.iterrows():
        convs = None if conversions is None else float(conversions.iloc[i]) if pd.notna(conversions.iloc[i]) else None
        kind = "campaign" if part["Type"].startswith("campaign") else "flow"
        name = part["Name"]
        row = _row(
            kind=kind,
            name=name,
            recipients=float(part["Recipients"]),
            unique_converters=float(part["UniqueConverters"]),
            conversions=convs,
            revenue_usd=float(part["RevenueUSD"]),
        )
        if kind == "campaign":
            row["is_newsletter"] = True
            count = None
            for token in name.replace("(", " ").replace(")", " ").split():
                if token.isdigit():
                    count = int(token)
                    break
            row["campaign_count"] = count
            newsletter = row
        else:
            flows.append(row)
    flows.sort(key=lambda r: (-float(r["revenue_usd"]), r["name"]))
    return flows, newsletter


def _num(stats: Dict[str, Any], key: str) -> float:
    val = stats.get(key)
    try:
        return float(val or 0)
    except (TypeError, ValueError):
        return 0.0


def _from_api() -> tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    metric_id = find_placed_order_metric_id()
    flow_results = query_values_report(
        "flow-values-report",
        conversion_metric_id=metric_id,
        statistics=STATS,
        group_by=["flow_id", "flow_message_id", "flow_name", "send_channel"],
    )
    by_flow: Dict[str, Dict[str, Any]] = {}
    for item in flow_results:
        g = item.get("groupings") or {}
        s = item.get("statistics") or {}
        fid = str(g.get("flow_id") or "")
        if not fid:
            continue
        bucket = by_flow.setdefault(
            fid,
            {
                "name": str(g.get("flow_name") or fid),
                "recipients": 0.0,
                "unique_converters": 0.0,
                "conversions": 0.0,
                "revenue_usd": 0.0,
            },
        )
        if g.get("flow_name"):
            bucket["name"] = str(g.get("flow_name"))
        bucket["recipients"] += _num(s, "recipients")
        bucket["unique_converters"] += _num(s, "conversion_uniques")
        bucket["conversions"] += _num(s, "conversions")
        bucket["revenue_usd"] += _num(s, "conversion_value")
    flows = [
        _row(
            kind="flow",
            name=b["name"],
            recipients=b["recipients"],
            unique_converters=b["unique_converters"],
            conversions=b["conversions"],
            revenue_usd=b["revenue_usd"],
        )
        for b in by_flow.values()
    ]
    flows.sort(key=lambda r: (-float(r["revenue_usd"]), r["name"]))

    campaign_results = query_values_report(
        "campaign-values-report",
        conversion_metric_id=metric_id,
        statistics=STATS,
        group_by=["campaign_id", "campaign_message_id", "send_channel"],
    )
    by_campaign: Dict[str, Dict[str, Any]] = {}
    for item in campaign_results:
        g = item.get("groupings") or {}
        s = item.get("statistics") or {}
        cid = str(g.get("campaign_id") or "")
        if not cid:
            continue
        bucket = by_campaign.setdefault(
            cid,
            {"recipients": 0.0, "unique_converters": 0.0, "conversions": 0.0, "revenue_usd": 0.0},
        )
        bucket["recipients"] += _num(s, "recipients")
        bucket["unique_converters"] += _num(s, "conversion_uniques")
        bucket["conversions"] += _num(s, "conversions")
        bucket["revenue_usd"] += _num(s, "conversion_value")
    n = len(by_campaign)
    newsletter = None
    if n:
        newsletter = _row(
            kind="campaign",
            name=f"All newsletter campaigns ({n} campaigns aggregated)",
            recipients=sum(b["recipients"] for b in by_campaign.values()),
            unique_converters=sum(b["unique_converters"] for b in by_campaign.values()),
            conversions=sum(b["conversions"] for b in by_campaign.values()),
            revenue_usd=sum(b["revenue_usd"] for b in by_campaign.values()),
            campaign_count=n,
        )
    return flows, newsletter


def calculate_klaviyo_email(data_root: Path) -> Dict[str, Any]:
    files = _scan_files(data_root)
    rate, fx_meta = get_latest_usd_sek_rate(Path(data_root))
    warnings: List[Dict[str, str]] = []
    source = "csv"
    flows: List[Dict[str, Any]] = []
    newsletter: Optional[Dict[str, Any]] = None
    as_of = None
    connected = False

    if klaviyo_key_configured():
        try:
            flows, newsletter = _from_api()
            source = "klaviyo_api"
            connected = True
            as_of = _iso(datetime.now(timezone.utc))
        except Exception as exc:
            logger.warning(f"Klaviyo API pull failed, falling back to CSV: {exc}")
            warnings.append(
                {
                    "code": "klaviyo_api_failed",
                    "message": _public_api_failure_message(exc),
                }
            )

    if source != "klaviyo_api":
        if not files:
            payload = _empty(
                "Upload Klaviyo_email_performance_*.csv in Settings, or set "
                "KLAVIYO_PRIVATE_API_KEY to pull last-12-months data automatically."
            )
            payload["warnings"] = warnings
            payload["fx"] = fx_meta
            payload["klaviyo"]["connected"] = connected
            return payload
        try:
            df = _read_csv_flexible(files[-1])
            flows, newsletter = _from_csv(df)
            as_of = _iso(datetime.fromtimestamp(files[-1].stat().st_mtime, tz=timezone.utc))
        except Exception as exc:
            payload = _empty(f"Could not read Klaviyo email CSV: {exc}", files=_file_meta(files))
            payload["warnings"] = warnings
            payload["fx"] = fx_meta
            return payload

    rows_for_total = list(flows)
    if newsletter:
        rows_for_total.append(newsletter)
    total = _totals(rows_for_total)
    _apply_sek(flows, rate)
    if newsletter:
        _apply_sek([newsletter], rate)
    if total:
        usd = float(total["revenue_usd"] or 0)
        total["revenue_sek"] = None if rate is None else usd * rate

    if rate is None:
        warnings.append(
            {
                "code": "fx_unavailable",
                "message": "USD→SEK rate unavailable; revenue is shown in USD only.",
            }
        )
        if fx_meta.get("error"):
            warnings[-1]["message"] += f" ({fx_meta['error']})"

    fx_out = dict(fx_meta)
    fx_out["source_currency"] = "USD"
    fx_out["target_currency"] = "SEK"

    return {
        "available": True,
        "message": None,
        "source": source,
        "header_note": HEADER_NOTE,
        "timeframe": "last_12_months",
        "flows": flows,
        "newsletter": newsletter,
        "total": total,
        "fx": fx_out,
        "klaviyo": {
            "key_configured": klaviyo_key_configured(),
            "connected": connected,
        },
        "files": _file_meta(files),
        "as_of": as_of,
        "footnotes": [
            HEADER_NOTE,
            "Unique converters are Klaviyo's per-flow / per-campaign uniques; "
            "the overall total sums those rows and can count a person twice if they "
            "converted from both a flow and a campaign.",
            "Revenue is converted from Klaviyo USD to SEK with an approximate ECB daily rate "
            "(same Frankfurter/ECB source as Full price vs Sale).",
            "When the Klaviyo API is connected, campaign email sends are rolled into the "
            "newsletter row (count in the name). Flow message stats are summed per flow.",
        ],
        "warnings": warnings,
        "caveats": [],
    }
