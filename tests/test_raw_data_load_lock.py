"""Serialize overlapping Qlik loads so Render does not OOM."""

from __future__ import annotations

import threading
from pathlib import Path

import pandas as pd

from weekly_report.src.cache.manager import raw_data_cache
from weekly_report.src.metrics import table1


def test_concurrent_raw_loads_only_read_qlik_once(monkeypatch):
    raw_data_cache.clear()
    started = threading.Event()
    release = threading.Event()
    calls: list[str] = []

    def fake_qlik(path: Path) -> pd.DataFrame:
        calls.append(str(path))
        started.set()
        assert release.wait(timeout=2)
        return pd.DataFrame({"Date": pd.to_datetime(["2026-09-14"]), "Gross Revenue": [1.0]})

    empty = pd.DataFrame()
    monkeypatch.setattr(table1.qlik, "load_data", fake_qlik)
    monkeypatch.setattr(table1.dema, "load_data", lambda _p: empty.copy())
    monkeypatch.setattr(table1.dema_gm2, "load_data", lambda _p: empty.copy())
    monkeypatch.setattr(table1.shopify, "load_data", lambda _p: empty.copy())

    path = Path("/tmp/not-a-real-week")
    results: list[object] = []
    errors: list[BaseException] = []

    def worker() -> None:
        try:
            results.append(table1.load_all_raw_data(path))
        except BaseException as exc:  # noqa: BLE001 — surface in assertions
            errors.append(exc)

    t1 = threading.Thread(target=worker)
    t2 = threading.Thread(target=worker)
    t1.start()
    assert started.wait(timeout=2)
    t2.start()
    release.set()
    t1.join(timeout=2)
    t2.join(timeout=2)

    assert errors == []
    assert len(results) == 2
    assert calls == [str(path)]
