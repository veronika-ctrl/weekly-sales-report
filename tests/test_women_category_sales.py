"""Women category sales reads the Qlik slice only and reuses a saved result."""

from __future__ import annotations

import inspect
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from weekly_report.src.adapters import qlik
from weekly_report.src.metrics.category_sales import calculate_category_sales_for_weeks
from weekly_report.src.metrics.gender_sales import calculate_gender_sales_for_weeks
from weekly_report.src.metrics.men_category_sales import calculate_men_category_sales_for_weeks
from weekly_report.src.metrics.women_category_sales import (
    _cache,
    calculate_women_category_sales_for_weeks,
)


def _iso(year: int, week: int) -> str:
    return date.fromisocalendar(year, week, 3).isoformat()


def _write_qlik(tmp_path: Path, base_week: str = "2026-42") -> Path:
    week = tmp_path / "raw" / base_week / "qlik"
    week.mkdir(parents=True)
    rows = [
        (_iso(2026, 42), "Online", "WOMEN", "TOPS", 100),
        (_iso(2026, 42), "Online", "WOMEN", "DRESSES", 50),
        (_iso(2026, 42), "Online", "WOMEN", "TOPS", 25),
        (_iso(2026, 42), "Online", "WOMEN", "-", 999),
        (_iso(2026, 42), "Retail", "WOMEN", "TOPS", 999),
        (_iso(2026, 42), "Online", "MEN", "TOPS", 80),
        (_iso(2026, 42), "Online", "UNISEX", "TOPS", 5),
        (_iso(2026, 41), "Online", "WOMEN", "TOPS", 10),
        (_iso(2025, 42), "Online", "WOMEN", "TOPS", 40),
        (_iso(2025, 52), "Online", "WOMEN", "TOPS", 7),
        (_iso(2026, 1), "Online", "WOMEN", "TOPS", 11),
        (_iso(2025, 1), "Online", "WOMEN", "TOPS", 3),
    ]
    frame = pd.DataFrame(rows, columns=["Date", "Sales Channel", "Gender", "Product Category", "Gross Revenue"])
    # Extra column that a full Qlik export would carry and this slide must ignore.
    frame["Notes"] = "x" * 40
    frame.to_csv(week / "qlik.csv", index=False)
    return tmp_path


@pytest.fixture(autouse=True)
def _clear_women_cache():
    _cache.clear_memory()
    yield
    _cache.clear_memory()


def test_women_online_totals_and_last_year_without_other_exports(tmp_path: Path):
    data_root = _write_qlik(tmp_path)
    rows = calculate_women_category_sales_for_weeks("2026-42", 2, data_root)
    by_week = {row["week"]: row for row in rows}
    assert set(by_week) == {"2026-41", "2026-42"}
    assert by_week["2026-41"]["categories"] == {"TOPS": 10.0}
    assert by_week["2026-41"]["last_year"] is None
    assert by_week["2026-42"]["categories"] == {"TOPS": 125.0, "DRESSES": 50.0}
    assert by_week["2026-42"]["last_year"]["categories"] == {"TOPS": 40.0}
    assert not (data_root / "raw" / "2026-42" / "dema").exists()


def test_year_rollover_uses_previous_iso_year(tmp_path: Path):
    data_root = _write_qlik(tmp_path, "2026-01")
    rows = calculate_women_category_sales_for_weeks("2026-01", 2, data_root)
    by_week = {row["week"]: row for row in rows}
    assert by_week["2025-52"]["categories"] == {"TOPS": 7.0}
    assert by_week["2026-01"]["categories"] == {"TOPS": 11.0}
    assert by_week["2026-01"]["last_year"]["categories"] == {"TOPS": 3.0}


def test_saved_result_skips_a_second_read_until_the_file_changes(tmp_path: Path, monkeypatch):
    data_root = _write_qlik(tmp_path)
    calls = {"n": 0}
    real = qlik.load_category_qlik

    def wrapped(path):
        calls["n"] += 1
        return real(path)

    monkeypatch.setattr(
        "weekly_report.src.metrics.women_category_sales.load_category_qlik",
        wrapped,
    )
    first = calculate_women_category_sales_for_weeks("2026-42", 2, data_root)
    assert calls["n"] == 1
    cache_file = data_root / "cache" / "women-category-sales" / "2026-42__n2.json"
    assert cache_file.exists()

    _cache.clear_memory()
    second = calculate_women_category_sales_for_weeks("2026-42", 2, data_root)
    assert calls["n"] == 1
    assert second == first

    csv_path = data_root / "raw" / "2026-42" / "qlik" / "qlik.csv"
    csv_path.write_text(csv_path.read_text(encoding="utf-8") + f"{_iso(2026, 42)},Online,WOMEN,TOPS,5\n", encoding="utf-8")
    third = calculate_women_category_sales_for_weeks("2026-42", 2, data_root)
    assert calls["n"] == 2
    by_week = {row["week"]: row for row in third}
    assert by_week["2026-42"]["categories"]["TOPS"] == 130.0


def test_sibling_slides_also_skip_the_full_raw_load(tmp_path: Path):
    data_root = _write_qlik(tmp_path)
    men = calculate_men_category_sales_for_weeks("2026-42", 1, data_root)
    assert men[0]["categories"] == {"TOPS": 85.0}

    gender = calculate_gender_sales_for_weeks("2026-42", 1, data_root)
    assert gender[0]["women_sales"] == 1174.0
    assert gender[0]["men_unisex_sales"] == 85.0

    categories = calculate_category_sales_for_weeks("2026-42", 1, data_root)
    assert categories[0]["categories"]["WOMEN_TOPS"] == 125.0
    assert categories[0]["categories"]["WOMEN_DRESSES"] == 50.0
    assert categories[0]["categories"]["MEN_TOPS"] == 85.0
    assert categories[0]["categories"]["MEN_OTHER"] == 999.0


def test_parquet_read_requests_only_the_category_columns(tmp_path: Path, monkeypatch):
    qlik_dir = tmp_path / "raw" / "2026-42" / "qlik"
    qlik_dir.mkdir(parents=True)
    (qlik_dir / "sales.parquet").write_bytes(b"placeholder")
    seen = {}

    monkeypatch.setattr(
        qlik,
        "_parquet_column_names",
        lambda path: ["Date", "Sales Channel", "Gender", "Product Category", "Gross Revenue", "Huge"],
    )

    def fake_read(path, columns=None, **kwargs):
        seen["columns"] = list(columns)
        return pd.DataFrame({col: pd.Series(dtype="object") for col in columns})

    monkeypatch.setattr(qlik.pd, "read_parquet", fake_read)
    frame = qlik.load_category_qlik(tmp_path / "raw" / "2026-42")
    assert seen["columns"] == ["Date", "Sales Channel", "Gender", "Product Category", "Gross Revenue"]
    assert "Huge" not in frame.columns


def test_women_endpoint_does_not_block_the_event_loop():
    from weekly_report.api.routes import get_women_category_sales

    assert not inspect.iscoroutinefunction(get_women_category_sales)
