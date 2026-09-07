"""Tests for upload metadata extraction (especially large Qlik Excel files)."""

import pandas as pd

from weekly_report.src.utils.file_metadata import extract_file_metadata


def test_xlsx_metadata_does_not_load_full_workbook(tmp_path, monkeypatch):
    path = tmp_path / "qlik.xlsx"
    df = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2025-01-06", "2025-01-07", "2025-01-13"]),
            "Gross Revenue": [100.0, 200.0, 150.0],
        }
    )
    df.to_excel(path, index=False)

    def forbidden_read_excel(*args, **kwargs):
        raise AssertionError("xlsx metadata must not call pandas.read_excel")

    monkeypatch.setattr(pd, "read_excel", forbidden_read_excel)

    meta = extract_file_metadata(path, "qlik")
    assert meta.get("error") is None
    assert meta["row_count"] == 3
    assert meta["first_date"] == "2025-01-06"
    assert meta["last_date"] == "2025-01-13"
    assert meta["date_column"] == "Date"


def test_xlsx_newest_first_uses_last_row_for_earliest_date(tmp_path, monkeypatch):
    path = tmp_path / "qlik.xlsx"
    dates = pd.date_range("2024-01-01", "2024-01-10")[::-1]
    df = pd.DataFrame({"Date": dates, "Gross Revenue": list(range(len(dates)))})
    df.to_excel(path, index=False)

    monkeypatch.setattr(
        pd,
        "read_excel",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("xlsx metadata must not call pandas.read_excel")
        ),
    )

    meta = extract_file_metadata(path, "qlik")
    assert meta.get("error") is None
    assert meta["row_count"] == 10
    assert meta["first_date"] == "2024-01-01"
    assert meta["last_date"] == "2024-01-10"


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


def test_csv_comma_separator(tmp_path):
    path = tmp_path / "discounts.csv"
    path.write_text(
        "Date,Full Price,Total\n2025-01-01,10,20\n2026-09-07,11,21\n",
        encoding="utf-8",
    )
    meta = extract_file_metadata(path, "discounts")
    assert meta.get("error") is None
    assert meta["row_count"] == 2
    assert meta["first_date"] == "2025-01-01"
    assert meta["last_date"] == "2026-09-07"


def test_budget_without_date_column(tmp_path):
    path = tmp_path / "budget.csv"
    path.write_text("Market;Apr;May\nSE;1;2\nNO;3;4\n", encoding="utf-8")
    meta = extract_file_metadata(path, "budget")
    assert meta.get("error") is None
    assert meta["row_count"] == 2
    assert "first_date" not in meta


def test_xlsx_missing_date_column_still_returns_row_count(tmp_path):
    path = tmp_path / "qlik.xlsx"
    df = pd.DataFrame({"Country": ["SE", "NO"], "Gross Revenue": [1.0, 2.0]})
    df.to_excel(path, index=False)
    meta = extract_file_metadata(path, "qlik")
    assert meta["row_count"] == 2
    assert "error" in meta


def test_xlsx_header_names_does_not_use_pandas(tmp_path, monkeypatch):
    from weekly_report.src.utils.file_metadata import xlsx_header_names

    path = tmp_path / "qlik.xlsx"
    pd.DataFrame({"Date": ["2025-01-06"], "Country": ["SE"]}).to_excel(path, index=False)
    monkeypatch.setattr(
        pd,
        "read_excel",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("xlsx headers must not call pandas.read_excel")
        ),
    )
    assert xlsx_header_names(path) == ["Date", "Country"]


def test_csv_accepts_day_alias_for_dema_spend(tmp_path):
    path = tmp_path / "spend.csv"
    path.write_text(
        "Channel;Country;Day;Marketing spend\nPaid;SE;2025-01-06;10\n",
        encoding="utf-8",
    )
    meta = extract_file_metadata(path, "dema_spend")
    assert meta.get("error") is None
    assert meta["first_date"] == "2025-01-06"
    assert meta["date_column"] == "Day"
