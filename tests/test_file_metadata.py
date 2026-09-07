"""Tests for upload metadata extraction (especially large Qlik Excel files)."""

import pandas as pd

from weekly_report.src.utils.file_metadata import extract_file_metadata


def test_xlsx_metadata_counts_rows_without_full_pandas_load(tmp_path, monkeypatch):
    path = tmp_path / "qlik.xlsx"
    df = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2025-01-06", "2025-01-07", "2025-01-13"]),
            "Gross Revenue": [100.0, 200.0, 150.0],
        }
    )
    df.to_excel(path, index=False)

    original = pd.read_excel

    def guarded_read_excel(*args, **kwargs):
        if "nrows" not in kwargs:
            raise AssertionError("full workbook pandas read is forbidden")
        return original(*args, **kwargs)

    monkeypatch.setattr(pd, "read_excel", guarded_read_excel)

    meta = extract_file_metadata(path, "qlik")
    assert meta.get("error") is None
    assert meta["row_count"] == 3
    assert meta["first_date"] == "2025-01-06"
    assert meta["last_date"] == "2025-01-13"
    assert meta["date_column"] == "Date"


def test_csv_metadata_counts_rows(tmp_path):
    path = tmp_path / "qlik.csv"
    path.write_text(
        "Date;Gross Revenue\n2025-01-06;100\n2025-01-13;200\n",
        encoding="utf-8",
    )
    meta = extract_file_metadata(path, "qlik")
    assert meta.get("error") is None
    assert meta["row_count"] == 2
    assert meta["first_date"] == "2025-01-06"
    assert meta["last_date"] == "2025-01-13"
