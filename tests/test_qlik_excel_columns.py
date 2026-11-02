"""Excel Qlik reads stay on the requested columns and are reused from disk."""

from pathlib import Path

import pandas as pd
import pytest

from weekly_report.src.adapters import qlik
from weekly_report.src.metrics import table1


def _write_week(tmp_path: Path) -> Path:
    week = tmp_path / "raw" / "2026-44"
    qlik_dir = week / "qlik"
    qlik_dir.mkdir(parents=True)
    pd.DataFrame(
        {
            "Date": ["2026-10-26", "2026-10-26"],
            "Sales Channel": ["Online", "Retail"],
            "Gender": ["WOMEN", "MEN"],
            "Product Category": ["TOPS", "TOPS"],
            "Gross Revenue": [12.0, 4.0],
            "Net Revenue": [11.0, 4.0],
            "Returns": [1.0, 0.0],
            "Country": ["Sweden", "Sweden"],
            "New/Returning Customer": ["New", "Returning"],
            "Customer E-mail": ["a@example.com", "b@example.com"],
            "Notes": ["x" * 400, "y" * 400],
        }
    ).to_excel(qlik_dir / "Qlik_W44.xlsx", index=False)
    for slot in ("dema_spend", "dema_gm2"):
        folder = week / slot
        folder.mkdir()
        pd.DataFrame({"Days": ["2026-10-26"], "Marketing spend": [3.0]}).to_csv(
            folder / f"{slot}.csv", index=False
        )
    return week


def test_excel_column_read_never_loads_the_full_sheet(tmp_path: Path, monkeypatch):
    _write_week(tmp_path)

    def refuse_full_sheet(*_args, **_kwargs):
        raise AssertionError("full-sheet pandas.read_excel is disabled")

    monkeypatch.setattr(qlik.pd, "read_excel", refuse_full_sheet)
    frame = qlik.load_qlik_columns(
        tmp_path / "raw" / "2026-44",
        ["Date", "Sales Channel", "Gross Revenue"],
    )
    assert "Notes" not in frame.columns
    assert "Customer E-mail" not in frame.columns
    assert list(frame["Gross Revenue"]) == [12.0, 4.0]
    assert "iso_week" in frame.columns


def test_excel_reader_refuses_the_full_sheet_fallback(tmp_path: Path, monkeypatch):
    path = tmp_path / "Qlik.xlsx"
    pd.DataFrame({"Date": ["2026-10-26"], "Notes": ["wide"]}).to_excel(path, index=False)

    def fail_calamine(*_args, **_kwargs):
        raise RuntimeError("calamine down")

    def fail_openpyxl(*_args, **_kwargs):
        raise RuntimeError("openpyxl down")

    def refuse_full_sheet(*_args, **_kwargs):
        raise AssertionError("full-sheet pandas.read_excel is disabled")

    monkeypatch.setattr(qlik, "_stream_calamine_columns", fail_calamine)
    monkeypatch.setattr(qlik, "_stream_openpyxl_columns", fail_openpyxl)
    monkeypatch.setattr(qlik.pd, "read_excel", refuse_full_sheet)
    with pytest.raises(RuntimeError, match="full sheet"):
        qlik._read_excel_columns(path, ["Date"])


def test_second_excel_read_uses_the_column_cache(tmp_path: Path, monkeypatch):
    _write_week(tmp_path)
    calls = {"n": 0}
    real = qlik._read_excel_columns

    def wrapped(path: Path, columns):
        calls["n"] += 1
        return real(path, columns)

    monkeypatch.setattr(qlik, "_read_excel_columns", wrapped)
    columns = ["Date", "Sales Channel", "Gross Revenue"]
    week = tmp_path / "raw" / "2026-44"
    first = qlik.load_qlik_columns(week, columns)
    second = qlik.load_qlik_columns(week, columns)
    assert calls["n"] == 1
    assert list(second["Gross Revenue"]) == list(first["Gross Revenue"])
    assert list((tmp_path / "cache" / "qlik-columns").glob("*.pkl"))

    qlik.load_qlik_columns(week, ["Date", "Gender"])
    assert calls["n"] == 2


def test_excel_stream_keep_row_drops_retail_without_using_unfiltered_cache(tmp_path: Path):
    _write_week(tmp_path)
    week = tmp_path / "raw" / "2026-44"
    columns = ["Date", "Sales Channel", "Gross Revenue"]
    qlik.load_qlik_columns(week, columns)

    def online_only(values):
        return str(values.get("Sales Channel") or "").strip().lower() == "online"

    frame = qlik.load_qlik_columns(week, columns, keep_row=online_only)
    assert list(frame["Gross Revenue"]) == [12.0]
    assert list(frame["Sales Channel"].astype(str).str.strip()) == ["Online"]


def test_openpyxl_stream_is_used_when_calamine_fails(tmp_path: Path, monkeypatch):
    _write_week(tmp_path)

    def fail_calamine(*_args, **_kwargs):
        raise RuntimeError("calamine down")

    monkeypatch.setattr(qlik, "_stream_calamine_columns", fail_calamine)
    frame = qlik._read_excel_columns(
        tmp_path / "raw" / "2026-44" / "qlik" / "Qlik_W44.xlsx",
        ["Date", "Gross Revenue"],
    )
    assert "Notes" not in frame.columns
    assert list(frame["Gross Revenue"]) == [12.0, 4.0]


def test_mtd_disk_cache_skips_a_second_workbook_read(tmp_path: Path, monkeypatch):
    _write_week(tmp_path)
    calls = {"n": 0}
    real = table1.load_summary_frames

    def wrapped(path: Path):
        calls["n"] += 1
        frames = real(path)
        assert "Notes" not in frames["qlik"].columns
        return frames

    monkeypatch.setattr(table1, "load_summary_frames", wrapped)
    first = table1.calculate_table1_mtd_and_ytd("2026-44", tmp_path)
    second = table1.calculate_table1_mtd_and_ytd("2026-44", tmp_path)
    assert calls["n"] == 1
    assert second == first
    assert list((tmp_path / "cache" / "table1-mtd").glob("*.json"))
    assert first["periods"]["actual"]["online_gross_revenue"] == 12.0
