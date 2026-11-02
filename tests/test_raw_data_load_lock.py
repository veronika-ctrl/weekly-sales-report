"""Serialize overlapping Qlik loads so Render does not OOM."""

from __future__ import annotations

import threading
from pathlib import Path

import pandas as pd

from weekly_report.src.adapters import qlik
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


def test_second_week_replaces_cached_raw_data(monkeypatch):
    raw_data_cache.clear()

    def fake_qlik(path: Path) -> pd.DataFrame:
        return pd.DataFrame({"Date": pd.to_datetime(["2026-09-14"]), "path": [path.name]})

    empty = pd.DataFrame({"Days": pd.to_datetime(["2026-09-14"])})
    monkeypatch.setattr(table1.qlik, "load_data", fake_qlik)
    monkeypatch.setattr(table1.dema, "load_data", lambda _p: empty.copy())
    monkeypatch.setattr(table1.dema_gm2, "load_data", lambda _p: empty.copy())
    monkeypatch.setattr(table1.shopify, "load_data", lambda _p: empty.copy())

    first = Path("/tmp/week-a")
    second = Path("/tmp/week-b")
    table1.load_all_raw_data(first)
    table1.load_all_raw_data(second)

    assert list(raw_data_cache.cache) == [str(second)]


def test_filter_period_slices_one_week_without_mutating_source():
    qlik = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2026-09-14", "2026-09-21"]),
            "iso_week": ["2026-38", "2026-39"],
            "Gross Revenue": [1.0, 2.0],
        }
    )
    dema = pd.DataFrame(
        {
            "Days": pd.to_datetime(["2026-09-14", "2026-09-21"]),
            "iso_week": ["2026-38", "2026-39"],
            "Marketing spend": [3.0, 4.0],
        }
    )
    before_weeks = list(qlik["iso_week"])
    out = table1.filter_data_for_period(
        {"qlik": qlik, "dema_spend": dema, "dema_gm2": dema.copy()},
        "2026-39",
    )

    assert list(out["qlik"]["Gross Revenue"]) == [2.0]
    assert list(out["dema_spend"]["Marketing spend"]) == [4.0]
    assert list(qlik["iso_week"]) == before_weeks
    assert "ISO_Week" not in qlik.columns


def test_resident_section_blocks_a_second_thread_and_is_reentrant():
    hold_result: list[bool] = []

    def probe() -> None:
        acquired = qlik.qlik_resident_section().acquire(timeout=0.05)
        hold_result.append(acquired)
        if acquired:
            qlik.qlik_resident_section().release()

    with qlik.qlik_resident_section():
        with qlik.qlik_resident_section():
            worker = threading.Thread(target=probe)
            worker.start()
            worker.join(timeout=1)
    assert hold_result == [False]
    acquired = qlik.qlik_resident_section().acquire(timeout=0.05)
    assert acquired is True
    qlik.qlik_resident_section().release()


def test_full_qlik_read_uses_the_resident_lock(monkeypatch, tmp_path: Path):
    week = tmp_path / "qlik"
    week.mkdir()
    (week / "a.csv").write_text("Date,Gross Revenue\n2026-10-19,1\n", encoding="utf-8")
    saw: list[bool] = []
    real = qlik.load_csv_files

    def wrapped(path: Path, name: str) -> pd.DataFrame:
        def other() -> None:
            acquired = qlik.qlik_resident_section().acquire(timeout=0.05)
            saw.append(acquired)
            if acquired:
                qlik.qlik_resident_section().release()

        probe = threading.Thread(target=other)
        probe.start()
        probe.join(timeout=1)
        return real(path, name)

    monkeypatch.setattr(qlik, "load_csv_files", wrapped)
    frame = qlik.load_data(tmp_path)
    assert saw == [False]
    assert len(frame) == 1
    acquired = qlik.qlik_resident_section().acquire(timeout=0.05)
    assert acquired is True
    qlik.qlik_resident_section().release()


def test_summary_keeps_the_qlik_lock_until_the_frames_are_gone(monkeypatch):
    saw: list[bool] = []

    def fake_frames(_path: Path):
        def other() -> None:
            acquired = qlik.qlik_resident_section().acquire(timeout=0.05)
            saw.append(acquired)
            if acquired:
                qlik.qlik_resident_section().release()

        probe = threading.Thread(target=other)
        probe.start()
        probe.join(timeout=1)
        return {
            "qlik": pd.DataFrame(
                {
                    "Date": pd.to_datetime(["2026-10-19"]),
                    "iso_week": ["2026-43"],
                    "Sales Channel": ["Online"],
                    "Gross Revenue": [1.0],
                    "Net Revenue": [1.0],
                    "Returns": [0.0],
                    "Country": ["Sweden"],
                    "New/Returning Customer": ["New"],
                    "Customer E-mail": ["a@example.com"],
                }
            ),
            "dema_spend": pd.DataFrame(),
            "dema_gm2": pd.DataFrame(),
        }

    monkeypatch.setattr(table1, "load_summary_frames", fake_frames)
    table1.calculate_table1_for_periods_with_ytd({"actual": "2026-43"}, Path("/tmp/not-used"))
    assert saw == [False]
    acquired = qlik.qlik_resident_section().acquire(timeout=0.05)
    assert acquired is True
    qlik.qlik_resident_section().release()


def test_mtd_summary_releases_the_qlik_lock(monkeypatch):
    monkeypatch.setattr(
        table1,
        "load_summary_frames",
        lambda _path: {
            "qlik": pd.DataFrame(
                {
                    "Date": pd.to_datetime(["2026-10-19"]),
                    "iso_week": ["2026-43"],
                    "Sales Channel": ["Online"],
                    "Gross Revenue": [1.0],
                    "Net Revenue": [1.0],
                    "Returns": [0.0],
                    "Country": ["Sweden"],
                    "New/Returning Customer": ["New"],
                    "Customer E-mail": ["a@example.com"],
                }
            ),
            "dema_spend": pd.DataFrame(),
            "dema_gm2": pd.DataFrame(),
        },
    )
    payload = table1.calculate_table1_mtd_and_ytd("2026-43", Path("/tmp/not-used"))
    assert "actual" in payload["periods"]
    acquired = qlik.qlik_resident_section().acquire(timeout=0.05)
    assert acquired is True
    qlik.qlik_resident_section().release()


def test_api_startup_does_not_read_the_qlik_workbook():
    routes = Path(__file__).resolve().parents[1] / "weekly_report" / "api" / "routes.py"
    text = routes.read_text(encoding="utf-8")
    start = text.index("def _log_supabase_status")
    window = text[start : text.index("def _append_cors_origin")]
    assert "Thread" not in window
    assert "calculate_women_category" not in window
    assert "read_excel" not in window


def test_summary_recalculates_markets_only_on_refresh():
    page = Path(__file__).resolve().parents[1] / "frontend" / "contexts" / "DataCacheContext.tsx"
    text = page.read_text()
    start = text.index("Recompute markets from the Qlik files only on an explicit refresh.")
    window = text[start : start + 700]
    assert "if (forceRefresh)" in window
    assert "getTopMarkets(week, 8, true)" in window
    assert text.count("getTopMarkets(week, 8, true)") == 1
