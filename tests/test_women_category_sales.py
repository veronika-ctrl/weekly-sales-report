"""Women category sales reads the Qlik slice only and reuses a saved result."""

from __future__ import annotations

import inspect
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from weekly_report.src.adapters import qlik
from weekly_report.src.metrics import (
    category_sales,
    gender_sales,
    men_category_sales,
    online_kpis,
    women_category_sales,
)
from weekly_report.src.metrics.category_sales import calculate_category_sales_for_weeks
from weekly_report.src.metrics.gender_sales import calculate_gender_sales_for_weeks
from weekly_report.src.metrics.markets import calculate_top_markets_for_weeks
from weekly_report.src.metrics.men_category_sales import calculate_men_category_sales_for_weeks
from weekly_report.src.metrics.top_products import calculate_top_products_for_weeks
from weekly_report.src.metrics.top_products_gender import calculate_top_products_by_gender_for_weeks
from weekly_report.src.metrics.women_category_sales import (
    _cache,
    calculate_women_category_sales_for_weeks,
)
from weekly_report.src.metrics import table1 as table1_metrics


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
    frame["New/Returning Customer"] = "New"
    frame["Product"] = "Tee"
    frame["Color"] = "Black"
    frame["Sales Qty"] = 1
    frame["Country"] = "Sweden"
    frame.to_csv(week / "qlik.csv", index=False)
    return tmp_path


@pytest.fixture(autouse=True)
def _clear_women_cache():
    for cache in (
        _cache,
        men_category_sales._cache,
        gender_sales._cache,
        category_sales._cache,
    ):
        cache.clear_memory()
    yield
    for cache in (
        _cache,
        men_category_sales._cache,
        gender_sales._cache,
        category_sales._cache,
    ):
        cache.clear_memory()


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
    csv_path.write_text(
        csv_path.read_text(encoding="utf-8") + f"{_iso(2026, 42)},Online,WOMEN,TOPS,5,x,New,Tee,Black,1,Sweden\n",
        encoding="utf-8",
    )
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
    from weekly_report.api import routes

    for handler in (
        routes.get_women_category_sales,
        routes.get_men_category_sales,
        routes.get_gender_sales,
        routes.get_category_sales,
        routes.get_top_products,
        routes.get_top_products_by_gender,
        routes.get_online_kpis,
        routes.get_table1_metrics,
        routes.get_top_markets,
    ):
        assert not inspect.iscoroutinefunction(handler)


def test_sales_slides_do_not_call_load_all_raw_data(tmp_path: Path, monkeypatch):
    def boom(*_args, **_kwargs):
        raise AssertionError("load_all_raw_data")

    monkeypatch.setattr(table1_metrics, "load_all_raw_data", boom)
    data_root = _write_qlik(tmp_path)
    assert calculate_women_category_sales_for_weeks("2026-42", 1, data_root)
    assert calculate_men_category_sales_for_weeks("2026-42", 1, data_root)
    assert calculate_gender_sales_for_weeks("2026-42", 1, data_root)
    assert calculate_category_sales_for_weeks("2026-42", 1, data_root)
    assert calculate_top_products_for_weeks("2026-42", 1, data_root, top_n=5, customer_type="new")
    assert calculate_top_products_by_gender_for_weeks("2026-42", 1, data_root, "women", top_n=5)
    markets = calculate_top_markets_for_weeks("2026-42", 1, data_root)
    assert markets["markets"]

    for module in (
        women_category_sales,
        men_category_sales,
        gender_sales,
        category_sales,
        online_kpis,
    ):
        assert "load_all_raw_data(" not in inspect.getsource(module)


def test_parquet_footer_names_and_projection_skip_unused_columns(tmp_path: Path, monkeypatch):
    import pyarrow as pa
    import pyarrow.parquet as pq

    qlik_dir = tmp_path / "raw" / "2026-42" / "qlik"
    qlik_dir.mkdir(parents=True)
    path = qlik_dir / "sales.parquet"
    pq.write_table(
        pa.table(
            {
                "Date": ["2026-10-14"],
                "Sales Channel": ["Online"],
                "Gender": ["WOMEN"],
                "Product Category": ["TOPS"],
                "Gross Revenue": [12.0],
                "Huge": ["z" * 50],
            }
        ),
        path,
    )
    footer_names = qlik._parquet_footer_column_names(path)
    assert footer_names is not None
    assert "Huge" in footer_names
    assert "Gross Revenue" in footer_names

    monkeypatch.setattr(qlik, "_parquet_column_names", lambda _path: qlik._parquet_footer_column_names(_path))
    frame = qlik.load_category_qlik(tmp_path / "raw" / "2026-42")
    assert "Huge" not in frame.columns
    assert float(frame["Gross Revenue"].iloc[0]) == 12.0
    assert frame["iso_week"].iloc[0] == "2026-42"


def test_projection_failure_drops_unused_columns_immediately(tmp_path: Path, monkeypatch):
    import pyarrow as pa
    import pyarrow.parquet as pq

    qlik_dir = tmp_path / "raw" / "2026-42" / "qlik"
    qlik_dir.mkdir(parents=True)
    pq.write_table(
        pa.table(
            {
                "Date": ["2026-10-14"],
                "Sales Channel": ["Online"],
                "Gender": ["WOMEN"],
                "Product Category": ["TOPS"],
                "Gross Revenue": [9.0],
                "Huge": ["z" * 20],
            }
        ),
        qlik_dir / "sales.parquet",
    )
    real_read = pd.read_parquet

    def wrapped(path, columns=None, **kwargs):
        if columns is not None:
            raise RuntimeError("engine cannot project")
        return real_read(path, **kwargs)

    monkeypatch.setattr(qlik.pd, "read_parquet", wrapped)
    frame = qlik.load_category_qlik(tmp_path / "raw" / "2026-42")
    assert list(frame.columns) == [
        "Date",
        "Sales Channel",
        "Gender",
        "Product Category",
        "Gross Revenue",
        "iso_week",
    ]
    assert float(frame["Gross Revenue"].iloc[0]) == 9.0


def test_summary_frames_do_not_read_shopify(tmp_path: Path, monkeypatch):
    week = tmp_path / "raw" / "2026-42"
    qlik_dir = week / "qlik"
    qlik_dir.mkdir(parents=True)
    pd.DataFrame(
        {
            "Date": ["2026-10-14"],
            "Sales Channel": ["Online"],
            "Gross Revenue": [10.0],
            "Net Revenue": [8.0],
            "Country": ["Sweden"],
            "New/Returning Customer": ["New"],
            "Customer E-mail": ["a@example.com"],
            "Notes": ["ignore"],
        }
    ).to_csv(qlik_dir / "qlik.csv", index=False)
    for name, columns in (
        ("dema_spend", ["Days", "Marketing spend"]),
        ("dema_gm2", ["Days", "GM2"]),
    ):
        folder = week / name
        folder.mkdir()
        pd.DataFrame({columns[0]: ["2026-10-14"], columns[1]: [3.0]}).to_csv(folder / f"{name}.csv", index=False)

    def boom(_path):
        raise AssertionError("shopify should not be loaded for summary")

    monkeypatch.setattr(table1_metrics.shopify, "load_data", boom)
    frames = table1_metrics.load_summary_frames(week)
    assert "Notes" not in frames["qlik"].columns
    assert "Gross Revenue" in frames["qlik"].columns
    assert "Marketing spend" in frames["dema_spend"].columns
    assert "GM2" not in frames["dema_gm2"].columns
    assert "iso_week" in frames["qlik"].columns
    assert list(table1_metrics.raw_data_cache.cache) == []


def test_excel_qlik_reads_requested_columns_with_calamine(tmp_path: Path, monkeypatch):
    qlik_dir = tmp_path / "raw" / "2026-42" / "qlik"
    qlik_dir.mkdir(parents=True)
    pd.DataFrame(
        {
            "Date": ["2026-10-14", "2026-10-14"],
            "Sales Channel": ["Online", "Retail"],
            "Gender": ["WOMEN", "WOMEN"],
            "Product Category": ["TOPS", "TOPS"],
            "Gross Revenue": [80.0, 500.0],
            "Notes": ["x" * 200, "y" * 200],
        }
    ).to_excel(qlik_dir / "Qlik_W42.xlsx", index=False)

    engines = []
    real = pd.read_excel

    def spy(*args, **kwargs):
        engines.append(kwargs.get("engine"))
        assert kwargs.get("usecols") is not None
        return real(*args, **kwargs)

    monkeypatch.setattr("weekly_report.src.adapters.qlik.pd.read_excel", spy)
    rows = calculate_women_category_sales_for_weeks("2026-42", 1, tmp_path)
    assert engines[0] == "calamine"
    assert rows[0]["week"] == "2026-42"
    assert rows[0]["categories"] == {"TOPS": 80.0}
