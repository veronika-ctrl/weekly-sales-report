"""Klaviyo Reporting API client (private key from env — never log the key)."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

KLAVIYO_BASE = "https://a.klaviyo.com"
DEFAULT_REVISION = "2024-10-15"


def klaviyo_api_key() -> Optional[str]:
    raw = (os.getenv("KLAVIYO_PRIVATE_API_KEY") or os.getenv("KLAVIYO_API_KEY") or "").strip()
    return raw or None


def klaviyo_key_configured() -> bool:
    return bool(klaviyo_api_key())


def _revision() -> str:
    return (os.getenv("KLAVIYO_API_REVISION") or DEFAULT_REVISION).strip() or DEFAULT_REVISION


def _request(
    method: str,
    path: str,
    *,
    query: Optional[Dict[str, str]] = None,
    body: Optional[Dict[str, Any]] = None,
    timeout: int = 60,
) -> Dict[str, Any]:
    key = klaviyo_api_key()
    if not key:
        raise RuntimeError("KLAVIYO_PRIVATE_API_KEY is not set")
    url = f"{KLAVIYO_BASE}{path}"
    if query:
        url = f"{url}?{urllib.parse.urlencode(query)}"
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {
        "Authorization": f"Klaviyo-API-Key {key}",
        "revision": _revision(),
        "Accept": "application/json",
        "User-Agent": "ohjay-weekly-report/klaviyo",
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
    last_err: Optional[Exception] = None
    for attempt in range(4):
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            last_err = exc
            if exc.code in (429, 503) and attempt < 3:
                wait = 2 ** attempt
                logger.warning(f"Klaviyo {exc.code} on {path}; retry in {wait}s")
                time.sleep(wait)
                continue
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"Klaviyo HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            last_err = exc
            if attempt < 3:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"Klaviyo network error: {exc}") from exc
    raise RuntimeError(f"Klaviyo request failed: {last_err}")


def find_placed_order_metric_id() -> str:
    override = (os.getenv("KLAVIYO_CONVERSION_METRIC_ID") or "").strip()
    if override:
        return override
    payload = _request(
        "GET",
        "/api/metrics",
        query={"fields[metric]": "name,integration", "page[size]": "200"},
    )
    rows = payload.get("data") or []
    placed = []
    for row in rows:
        attrs = row.get("attributes") or {}
        name = str(attrs.get("name") or "").strip().lower()
        if name == "placed order":
            integ = attrs.get("integration") or {}
            placed.append((str(integ.get("name") or ""), row.get("id")))
    if not placed:
        raise RuntimeError("No Klaviyo metric named Placed Order. Set KLAVIYO_CONVERSION_METRIC_ID.")
    shopify = [p for p in placed if "shopify" in p[0].lower()]
    chosen = shopify[0] if shopify else placed[0]
    return str(chosen[1])


def query_values_report(
    report_type: str,
    *,
    conversion_metric_id: str,
    statistics: List[str],
    group_by: List[str],
    send_channel: str = "email",
    timeframe_key: str = "last_12_months",
) -> List[Dict[str, Any]]:
    path = "/api/flow-values-reports/" if report_type.startswith("flow") else "/api/campaign-values-reports/"
    body = {
        "data": {
            "type": report_type,
            "attributes": {
                "statistics": statistics,
                "timeframe": {"key": timeframe_key},
                "conversion_metric_id": conversion_metric_id,
                "filter": f'equals(send_channel,"{send_channel}")',
                "group_by": group_by,
            },
        }
    }
    payload = _request("POST", path, body=body, timeout=90)
    attrs = (payload.get("data") or {}).get("attributes") or {}
    return list(attrs.get("results") or [])


def probe_connection() -> Tuple[bool, Optional[str]]:
    """Lightweight check: key present and Klaviyo accepts it. Never returns the key."""
    if not klaviyo_key_configured():
        return False, "KLAVIYO_PRIVATE_API_KEY is not set"
    try:
        _request("GET", "/api/metrics", query={"page[size]": "1"})
        return True, None
    except Exception as exc:
        return False, str(exc)
