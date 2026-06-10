"""USD → SEK conversion for revenue-over-time exports (ECB daily rates via Frankfurter)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pandas as pd

_FRANKFURTER = "https://api.frankfurter.app"
_USER_AGENT = "ohjay-weekly-report/1.0"
_MONEY_COLS = ("_full", "_discounted", "_total", "_discount")


def _source_currency() -> str:
    return (os.getenv("FULL_PRICE_VS_SALE_SOURCE_CURRENCY") or "USD").strip().upper()


def _target_currency() -> str:
    return (os.getenv("FULL_PRICE_VS_SALE_TARGET_CURRENCY") or "SEK").strip().upper()


def _fx_disabled() -> bool:
    return (os.getenv("DISABLE_FX_CONVERSION") or "").strip().lower() in {"1", "true", "yes"}


def _fallback_rate() -> Optional[float]:
    raw = (os.getenv("USD_SEK_FALLBACK_RATE") or os.getenv("FULL_PRICE_VS_SALE_FX_FALLBACK_RATE") or "").strip()
    if not raw:
        return None
    try:
        v = float(raw)
        return v if v > 0 else None
    except ValueError:
        return None


def _cache_path(data_root: Path) -> Path:
    return Path(data_root) / "cache" / "fx_usd_sek.json"


def _read_cache(path: Path) -> Dict[str, float]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        rates = payload.get("rates") or {}
        return {str(k): float(v) for k, v in rates.items() if v is not None}
    except Exception:
        return {}


def _write_cache(path: Path, rates: Dict[str, float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"rates": rates, "provider": "frankfurter/ecb"}, indent=2),
        encoding="utf-8",
    )


def _fetch_range(start: str, end: str) -> Dict[str, float]:
    url = f"{_FRANKFURTER}/{start}..{end}?from=USD&to=SEK"
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=45) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    out: Dict[str, float] = {}
    for day, cur in (payload.get("rates") or {}).items():
        if isinstance(cur, dict) and "SEK" in cur:
            out[str(day)] = float(cur["SEK"])
    return out


def _series_from_cache(
    idx: pd.DatetimeIndex,
    cached: Dict[str, float],
) -> pd.Series:
    s = pd.Series(index=idx, dtype="float64")
    for d in idx:
        key = d.strftime("%Y-%m-%d")
        if key in cached:
            s.loc[d] = cached[key]
    return s.ffill().bfill()


def _calendar_rates(start: pd.Timestamp, end: pd.Timestamp, cached: Dict[str, float]) -> pd.Series:
    """Build a daily USD/SEK series for every calendar day (forward-fill ECB publish days)."""
    if start > end:
        return pd.Series(dtype="float64")

    need_start = start.normalize()
    need_end = end.normalize()
    idx = pd.date_range(need_start, need_end, freq="D")
    merged = dict(cached)
    s = _series_from_cache(idx, merged)
    if s.notna().all():
        return s

    fetched = _fetch_range(need_start.strftime("%Y-%m-%d"), need_end.strftime("%Y-%m-%d"))
    merged.update(fetched)
    s = _series_from_cache(idx, merged)
    return s


def get_fx_metadata(applied: bool, error: Optional[str] = None) -> Dict[str, Any]:
    return {
        "applied": applied,
        "source_currency": _source_currency(),
        "target_currency": _target_currency(),
        "provider": "frankfurter/ecb" if applied else None,
        "error": error,
    }


def convert_revenue_over_time_to_sek(
    df: pd.DataFrame,
    data_root: Path,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Convert monetary columns in the revenue-over-time history from USD to SEK using
    the ECB daily USD/SEK rate for each calendar day (weekends use prior publish day).
    """
    source = _source_currency()
    target = _target_currency()
    if _fx_disabled() or source == target or df.empty:
        return df, get_fx_metadata(applied=False)

    out = df.copy()
    start = pd.to_datetime(out["_date"].min(), errors="coerce")
    end = pd.to_datetime(out["_date"].max(), errors="coerce")
    if pd.isna(start) or pd.isna(end):
        return out, get_fx_metadata(applied=False, error="invalid_dates")

    cache_file = _cache_path(data_root)
    cached = _read_cache(cache_file)

    try:
        rate_series = _calendar_rates(start, end, cached)
        if rate_series.isna().all():
            raise ValueError("no USD/SEK rates returned")
        # Extend cache with any newly fetched keys in range.
        for d, rate in rate_series.dropna().items():
            cached[d.strftime("%Y-%m-%d")] = float(rate)
        _write_cache(cache_file, cached)

        day_keys = pd.to_datetime(out["_date"]).dt.normalize()
        rates = day_keys.map(rate_series)
        if rates.isna().any():
            fb = _fallback_rate()
            if fb is None:
                missing = int(rates.isna().sum())
                raise ValueError(f"missing FX rate on {missing} day(s)")
            rates = rates.fillna(fb)

        for col in _MONEY_COLS:
            if col in out.columns:
                out[col] = pd.to_numeric(out[col], errors="coerce") * rates.to_numpy()

        meta = get_fx_metadata(applied=True)
        meta["rate_start"] = str(start.date())
        meta["rate_end"] = str(end.date())
        meta["sample_rate"] = float(rate_series.iloc[-1])
        return out, meta
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as exc:
        fb = _fallback_rate()
        if fb is None:
            return out, get_fx_metadata(applied=False, error=str(exc))
        for col in _MONEY_COLS:
            if col in out.columns:
                out[col] = pd.to_numeric(out[col], errors="coerce") * fb
        meta = get_fx_metadata(applied=True)
        meta["provider"] = "fallback_env"
        meta["sample_rate"] = fb
        meta["error"] = str(exc)
        return out, meta
