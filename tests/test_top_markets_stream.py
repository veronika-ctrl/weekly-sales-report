"""Top markets stream Online Qlik columns once and do not 500 on a missing week."""

from __future__ import annotations

import inspect
from pathlib import Path

import pandas as pd

from weekly_report.src.adapters import qlik
from weekly_report.src.metrics import markets as markets_mod
from weekly_report.src.metrics import markets_net_mtd as net_mod
from weekly_report.src.metrics.markets import calculate_top_markets_for_weeks
from weekly_report.src.metrics.markets_net_mtd import calculate_top_markets_net_revenue_mtd
from weekly_report.src.adapters.qlik import resolve_existing_qlik_week
from weekly_report.src.periods.calculator import get_week_date_range


def _write_markets_qlik(tmp_path: Path, week: str = "2026-44") -> Path:
    raw = tmp_path / "raw" / week
    qlik_dir = raw / "qlik"
    qlik_dir.mkdir(parents=True)
    start = get_week_date_range(week)["start"]
    ly = get_week_date_range(f"{int(week.split('-')[0]) - 1}-{week.split('-')[1]}")["start"]
    pd.DataFrame(
        {
            "Date": [start, start, start, ly],
            "Sales Channel": ["Online", "Online", "Retail", "Online"],
            "Country": ["United States", "Sweden", "United States", "United States"],
            "Gross Revenue": [4000.0, 1000.0, 9000.0, 2000.0],
            "Net Revenue": [3600.0, 900.0, 9000.0, 1800.0],
            "Product": ["Tee", "Tank", "Store", "Tee"],
            "Notes": ["x" * 80] * 4,
        }
    ).to_csv(qlik_dir / "qlik.csv", index=False)
    return tmp_path


def test_top_markets_online_only(tmp_path):
    data_root = _write_markets_qlik(tmp_path)
    payload = calculate_top_markets_for_weeks("2026-44", 1, data_root)
    by_country = {row["country"]: row for row in payload["markets"]}
    assert by_country["United States"]["weeks"]["2026-44"] == 4000.0
    assert by_country["United States"]["weeks"]["2025-44"] == 2000.0
    assert by_country["Sweden"]["weeks"]["2026-44"] == 1000.0
    assert by_country["United States"]["weeks"]["2026-44"] != 13000.0


def test_top_markets_missing_week_uses_latest_qlik(tmp_path):
    data_root = _write_markets_qlik(tmp_path)
    assert resolve_existing_qlik_week("2026-45", data_root) == "2026-44"
    payload = calculate_top_markets_for_weeks("2026-45", 2, data_root)
    by_country = {row["country"]: row for row in payload["markets"]}
    assert by_country["United States"]["weeks"]["2026-44"] == 4000.0
    net = calculate_top_markets_net_revenue_mtd("2026-45", data_root, num_weeks=2)
    assert net["markets"]


def test_top_markets_excel_never_loads_the_full_sheet(tmp_path, monkeypatch):
    week = tmp_path / "raw" / "2026-44"
    qlik_dir = week / "qlik"
    qlik_dir.mkdir(parents=True)
    start = get_week_date_range("2026-44")["start"]
    pd.DataFrame(
        {
            "Date": [start, start],
            "Sales Channel": ["Online", "Retail"],
            "Country": ["Sweden", "Sweden"],
            "Gross Revenue": [1500.0, 8000.0],
            "Net Revenue": [1400.0, 8000.0],
            "Notes": ["x" * 400, "y" * 400],
        }
    ).to_excel(qlik_dir / "Qlik_W44.xlsx", index=False)

    def refuse_full_sheet(*_args, **_kwargs):
        raise AssertionError("full-sheet pandas.read_excel is disabled")

    monkeypatch.setattr(qlik.pd, "read_excel", refuse_full_sheet)
    payload = calculate_top_markets_for_weeks("2026-44", 1, tmp_path)
    sweden = next(row for row in payload["markets"] if row["country"] == "Sweden")
    assert sweden["weeks"]["2026-44"] == 1500.0


def test_markets_path_uses_column_stream_and_resident_lock():
    source = inspect.getsource(markets_mod)
    assert "load_qlik_columns" in source
    assert "qlik_resident_section" in source
    assert "keep_row" in source
    assert "load_all_raw_data" not in source
    net_source = inspect.getsource(net_mod)
    assert "load_online_market_frame" in net_source
    assert "qlik_resident_section" in net_source
    assert "calculate_top_markets_for_weeks" not in net_source


def test_top_markets_endpoints_missing_week_is_not_500(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("DISABLE_SUPABASE", "true")
    _write_markets_qlik(tmp_path)
    from weekly_report.api import routes

    assert not inspect.iscoroutinefunction(routes.get_top_markets)
    assert not inspect.iscoroutinefunction(routes.get_top_markets_net_mtd)
    gross = routes.get_top_markets("2026-45", num_weeks=2)
    assert gross.markets
    net = routes.get_top_markets_net_mtd("2026-45", num_weeks=2)
    assert net.markets
