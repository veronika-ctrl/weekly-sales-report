"""Audience per country streams Online Qlik columns instead of the full workbook."""

from __future__ import annotations

import inspect
from pathlib import Path

import pandas as pd

from weekly_report.src.adapters import qlik
from weekly_report.src.adapters.qlik import resolve_existing_qlik_week
from weekly_report.src.metrics import audience_metrics_per_country as audience_mod
from weekly_report.src.metrics.audience_metrics_per_country import (
    calculate_audience_metrics_per_country_for_weeks,
)
from weekly_report.src.periods.calculator import get_week_date_range


def _qlik_week_dir(tmp_path: Path, week: str = "2026-44") -> Path:
    raw = tmp_path / "raw" / week
    qlik_dir = raw / "qlik"
    qlik_dir.mkdir(parents=True)
    week_start = get_week_date_range(week)["start"]
    ly_start = get_week_date_range(f"{int(week.split('-')[0]) - 1}-{week.split('-')[1]}")["start"]
    rows = [
        (week_start, "Online", "United States", 2000.0, 1800.0, 200.0, "O1", "a@example.com", "New"),
        (week_start, "Online", "United Kingdom", 1000.0, 900.0, 100.0, "O2", "b@example.com", "Returning"),
        (week_start, "Retail", "United States", 9000.0, 9000.0, 0.0, "R1", "store@example.com", "New"),
        (ly_start, "Online", "United States", 1000.0, 900.0, 100.0, "O3", "c@example.com", "New"),
    ]
    df = pd.DataFrame(
        rows,
        columns=[
            "Date",
            "Sales Channel",
            "Country",
            "Gross Revenue",
            "Net Revenue",
            "Returns",
            "Order No",
            "Customer E-mail",
            "New/Returning Customer",
        ],
    )
    df["Product"] = "Wide product name " * 20
    df["Color"] = "x" * 40
    df.to_csv(qlik_dir / "qlik.csv", index=False)
    dema_dir = raw / "dema_spend"
    dema_dir.mkdir()
    pd.DataFrame(
        {
            "Days": [week_start, week_start],
            "Country": ["United States", "United Kingdom"],
            "Marketing spend": [100.0, 40.0],
        }
    ).to_csv(dema_dir / "dema.csv", index=False)
    return tmp_path


def test_audience_online_only_and_last_year(tmp_path):
    data_root = _qlik_week_dir(tmp_path)
    payload = calculate_audience_metrics_per_country_for_weeks("2026-44", 1, data_root)
    weeks = payload["audience_metrics_per_country"]
    assert len(weeks) == 1
    usa = weeks[0]["countries"]["United States"]
    assert usa["total_orders"] == 1
    assert usa["total_aov"] == 2000.0
    assert usa["new_customers"] == 1
    assert usa["last_year"]["total_aov"] == 1000.0
    uk = weeks[0]["countries"]["United Kingdom"]
    assert uk["total_orders"] == 1
    assert uk["returning_customers"] == 1
    assert "Retail" not in str(payload)


def test_missing_iso_week_uses_latest_qlik(tmp_path):
    data_root = _qlik_week_dir(tmp_path)
    assert resolve_existing_qlik_week("2026-45", data_root) == "2026-44"
    payload = calculate_audience_metrics_per_country_for_weeks("2026-45", 2, data_root)
    weeks = {row["week"]: row for row in payload["audience_metrics_per_country"]}
    assert "United States" in weeks["2026-44"]["countries"]
    assert payload["period_info"]["latest_week"] == "2026-45"


def test_audience_excel_never_loads_the_full_sheet(tmp_path, monkeypatch):
    week = tmp_path / "raw" / "2026-44"
    qlik_dir = week / "qlik"
    qlik_dir.mkdir(parents=True)
    start = get_week_date_range("2026-44")["start"]
    pd.DataFrame(
        {
            "Date": [start, start],
            "Sales Channel": ["Online", "Retail"],
            "Country": ["United States", "United States"],
            "Gross Revenue": [4000.0, 9000.0],
            "Net Revenue": [3600.0, 9000.0],
            "Returns": [400.0, 0.0],
            "Order No": ["O1", "R1"],
            "Customer E-mail": ["a@example.com", "b@example.com"],
            "New/Returning Customer": ["New", "New"],
            "Product": ["Tee", "Store Only"],
            "Color": ["Black", "Red"],
            "Notes": ["x" * 400, "y" * 400],
        }
    ).to_excel(qlik_dir / "Qlik_W44.xlsx", index=False)

    def refuse_full_sheet(*_args, **_kwargs):
        raise AssertionError("full-sheet pandas.read_excel is disabled")

    monkeypatch.setattr(qlik.pd, "read_excel", refuse_full_sheet)
    payload = calculate_audience_metrics_per_country_for_weeks("2026-44", 1, tmp_path)
    usa = payload["audience_metrics_per_country"][0]["countries"]["United States"]
    assert usa["total_aov"] == 4000.0


def test_audience_path_uses_column_stream_and_resident_lock():
    source = inspect.getsource(audience_mod)
    assert "load_qlik_columns" in source
    assert "qlik_resident_section" in source
    assert "keep_row" in source
    assert "pd.read_excel" not in source
    assert "load_all_raw_data" not in source
    assert "Product" not in audience_mod.AUDIENCE_QLIK_COLUMNS
    assert "Color" not in audience_mod.AUDIENCE_QLIK_COLUMNS


def test_audience_endpoint_missing_week_is_not_500(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("DISABLE_SUPABASE", "true")
    _qlik_week_dir(tmp_path)
    from weekly_report.api import routes

    assert not inspect.iscoroutinefunction(routes.get_audience_metrics_per_country)
    body = routes.get_audience_metrics_per_country("2026-45", num_weeks=2)
    assert body.period_info["latest_week"] == "2026-45"
    assert any(week.week == "2026-44" for week in body.audience_metrics_per_country)
