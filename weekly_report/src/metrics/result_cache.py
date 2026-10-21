"""Small JSON cache for metric payloads that are expensive to rebuild.

The value is tiny compared with the Qlik export. Keeping it on disk means a
restart can answer immediately, and a browser that drops the first connection
can retry onto the finished result.
"""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List

from loguru import logger

from weekly_report.src.adapters.qlik import qlik_source_signature


class ResultCache:
    def __init__(self, name: str) -> None:
        self.name = name
        self._mem: Dict[str, List[Any]] = {}
        self._lock = threading.Lock()

    def clear_memory(self) -> None:
        with self._lock:
            self._mem.clear()

    def get_or_compute(
        self,
        data_root: Path,
        raw_week_dir: Path,
        base_week: str,
        num_weeks: int,
        compute: Callable[[], List[Any]],
        extra: str = "",
    ) -> List[Any]:
        try:
            signature = qlik_source_signature(raw_week_dir)
        except FileNotFoundError:
            return compute()
        if extra:
            signature = f"{signature}:{extra}"

        mem_key = f"{Path(data_root).resolve()}|{base_week}|{int(num_weeks)}|{signature}"
        with self._lock:
            cached = self._mem.get(mem_key)
            if cached is not None:
                logger.info(f"{self.name} memory cache hit {base_week} n={num_weeks}")
                return cached

            disk = self._read_disk(data_root, base_week, num_weeks, signature, extra)
            if disk is not None:
                self._remember(mem_key, disk)
                logger.info(f"{self.name} disk cache hit {base_week} n={num_weeks}")
                return disk

            result = compute()
            self._remember(mem_key, result)
            self._write_disk(data_root, base_week, num_weeks, signature, result, extra)
            return result

    def _remember(self, key: str, rows: List[Any]) -> None:
        self._mem[key] = rows
        while len(self._mem) > 8:
            self._mem.pop(next(iter(self._mem)))

    def _path(self, data_root: Path, base_week: str, num_weeks: int, extra: str = "") -> Path:
        safe_week = base_week.replace("/", "-")
        suffix = ""
        if extra:
            suffix = "__" + hashlib.sha256(extra.encode()).hexdigest()[:10]
        return Path(data_root) / "cache" / self.name / f"{safe_week}__n{int(num_weeks)}{suffix}.json"

    def _read_disk(self, data_root: Path, base_week: str, num_weeks: int, signature: str, extra: str = "") -> List[Any] | None:
        path = self._path(data_root, base_week, num_weeks, extra)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(f"{self.name} disk cache unreadable ({exc})")
            return None
        if not isinstance(payload, dict) or payload.get("signature") != signature:
            return None
        rows = payload.get("rows")
        if not isinstance(rows, list):
            return None
        return rows

    def _write_disk(
        self,
        data_root: Path,
        base_week: str,
        num_weeks: int,
        signature: str,
        rows: List[Any],
        extra: str = "",
    ) -> None:
        path = self._path(data_root, base_week, num_weeks, extra)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".json.tmp")
            tmp.write_text(
                json.dumps({"signature": signature, "rows": rows}),
                encoding="utf-8",
            )
            tmp.replace(path)
        except (OSError, TypeError, ValueError) as exc:
            logger.warning(f"{self.name} disk cache not written ({exc})")
