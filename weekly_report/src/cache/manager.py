"""In-memory cache singletons used by the API and metric calculations."""

from __future__ import annotations

import time
from typing import Any, Dict, Iterable, Optional


class MetricsCache:
    """Caches computed Table 1 metrics per base week and period."""

    def __init__(self) -> None:
        self._data: Dict[str, Dict[str, Any]] = {}

    def get(self, base_week: str, requested_periods: Iterable[str]) -> Optional[Dict[str, Any]]:
        if base_week not in self._data:
            return None
        full = self._data[base_week]
        req = set(requested_periods)
        if not req.issubset(full.keys()):
            return None
        return {k: full[k] for k in requested_periods}

    def set(self, base_week: str, requested_periods: Any, metrics_results: Dict[str, Any]) -> None:
        if base_week not in self._data:
            self._data[base_week] = {}
        self._data[base_week].update(metrics_results)

    def clear(self) -> None:
        self._data.clear()

    def invalidate(self, base_week: str) -> None:
        self._data.pop(base_week, None)


class RawDataCache:
    """Caches loaded DataFrames per raw data directory path with TTL."""

    def __init__(self, max_age_hours: float = 2) -> None:
        self.max_age_seconds = max_age_hours * 3600.0
        # path -> (unix_ts, payload)
        self.cache: Dict[str, tuple[float, Dict[str, Any]]] = {}

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        entry = self.cache.get(key)
        if entry is None:
            return None
        ts, data = entry
        if time.time() - ts > self.max_age_seconds:
            del self.cache[key]
            return None
        return data

    def set(self, key: str, data: Dict[str, Any]) -> None:
        self.cache[key] = (time.time(), data)

    def clear(self) -> None:
        self.cache.clear()


metrics_cache = MetricsCache()
raw_data_cache = RawDataCache(max_age_hours=2)
