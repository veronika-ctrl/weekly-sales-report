"""CSV auto-detection must load Qlik exports that csv.Sniffer rejects."""

import csv
from pathlib import Path

import pandas as pd
import pytest

from weekly_report.api.routes import validate_file_dimensions
from weekly_report.src.adapters.csv_util import read_csv_auto
from weekly_report.src.adapters.qlik import load_data as load_qlik
from weekly_report.src.utils.file_metadata import extract_file_metadata

QLIK_HEADER = (
    "Date,Country,Sales Channel,Customer E-mail,New/Returning Customer,Order No,"
    "Gross Revenue,Returns,Net Revenue,Gender,Product Category,Product,Product Name,"
    "Product Type,Color,Freight Revenue,Freight Tax,Returns VAT,VAT Amount,Sales Qty,"
    "Order No,Year,Product Name (Pack)"
)


def _csv_field(value: str) -> str:
    if any(ch in value for ch in ',;"\n'):
        return '"' + value.replace('"', '""') + '"'
    return value


def _qlik_row(**overrides: str) -> str:
    values = {
        "Date": "2026-09-07",
        "Country": "Sweden",
        "Sales Channel": "Online",
        "Customer E-mail": "a@example.com",
        "New/Returning Customer": "New",
        "Order No": "1001",
        "Gross Revenue": "250.50",
        "Returns": "0",
        "Net Revenue": "250.50",
        "Gender": "Women",
        "Product Category": "Bags",
        "Product": "Tote",
        "Product Name": "Classic Tote",
        "Product Type": "Bag",
        "Color": "Black",
        "Freight Revenue": "0",
        "Freight Tax": "0",
        "Returns VAT": "0",
        "VAT Amount": "50",
        "Sales Qty": "1",
        "Order No_dup": "1001",
        "Year": "2026",
        "Product Name (Pack)": "Classic Tote Pack",
    }
    values.update(overrides)
    ordered = [
        values["Date"],
        values["Country"],
        values["Sales Channel"],
        values["Customer E-mail"],
        values["New/Returning Customer"],
        values["Order No"],
        values["Gross Revenue"],
        values["Returns"],
        values["Net Revenue"],
        values["Gender"],
        values["Product Category"],
        values["Product"],
        values["Product Name"],
        values["Product Type"],
        values["Color"],
        values["Freight Revenue"],
        values["Freight Tax"],
        values["Returns VAT"],
        values["VAT Amount"],
        values["Sales Qty"],
        values["Order No_dup"],
        values["Year"],
        values["Product Name (Pack)"],
    ]
    return ",".join(_csv_field(v) for v in ordered)


def test_csv_sniffer_1024_window_raises_on_quoted_run():
    """Old qlik.detect_csv_dialect() sniffed only 1024 bytes.

    When that window is the header plus the start of a long quoted field,
    Sniffer raises the error Audience Sweden showed after the Qlik CSV upload.
    """
    sample = QLIK_HEADER + '\n"' + ("x" * 2000)
    with pytest.raises(csv.Error, match="Could not determine delimiter"):
        csv.Sniffer().sniff(sample[:1024])


def test_excel_whole_row_quoted_csv_splits(tmp_path: Path):
    path = tmp_path / "Qlik_W37.csv"
    path.write_text(
        f'"{QLIK_HEADER}"\n"{_qlik_row()}"\n',
        encoding="utf-8",
    )
    df = read_csv_auto(path)
    assert "Country" in df.columns
    assert df.iloc[0]["Country"] == "Sweden"
    assert float(df.iloc[0]["Gross Revenue"]) == 250.50


def test_wide_comma_qlik_csv_loads_without_sniffer(tmp_path: Path):
    long_name = "Classic Tote " + ("Very Long Product Name " * 80)
    path = tmp_path / "Qlik_W37.csv"
    path.write_text(QLIK_HEADER + "\n" + _qlik_row(**{"Product Name": long_name}) + "\n", encoding="utf-8")

    df = read_csv_auto(path)
    assert df.shape[1] >= 20
    assert df.iloc[0]["Country"] == "Sweden"


def test_semicolon_dema_csv_still_loads(tmp_path: Path):
    path = tmp_path / "spend.csv"
    path.write_text("Days;Country;Marketing spend\n2026-09-07;Sweden;100\n", encoding="utf-8")
    df = read_csv_auto(path)
    assert list(df.columns) == ["Days", "Country", "Marketing spend"]
    assert df.iloc[0]["Country"] == "Sweden"


def test_utf8_bom_comma_csv(tmp_path: Path):
    path = tmp_path / "bom.csv"
    path.write_text("Date,Country\n2026-09-07,Sweden\n", encoding="utf-8-sig")
    df = read_csv_auto(path)
    assert list(df.columns) == ["Date", "Country"]


def test_utf16_comma_csv(tmp_path: Path):
    path = tmp_path / "utf16.csv"
    path.write_text("Date,Country\n2026-09-07,Sweden\n", encoding="utf-16")
    df = read_csv_auto(path)
    assert list(df.columns) == ["Date", "Country"]
    assert df.iloc[0]["Country"] == "Sweden"


def test_qlik_load_data_from_week_folder(tmp_path: Path):
    qlik_dir = tmp_path / "2026-37" / "qlik"
    qlik_dir.mkdir(parents=True)
    (qlik_dir / "Qlik_W37.csv").write_text(
        QLIK_HEADER + "\n" + _qlik_row() + "\n",
        encoding="utf-8",
    )
    df = load_qlik(tmp_path / "2026-37")
    assert "Country" in df.columns
    assert df["_source_type"].iloc[0] == "qlik"
    assert (df["Country"] == "Sweden").any()


def test_qlik_file_dimensions_splits_comma_header(tmp_path: Path):
    path = tmp_path / "Qlik_W37.csv"
    path.write_text(QLIK_HEADER + "\n" + _qlik_row() + "\n", encoding="utf-8")
    result = validate_file_dimensions(path, "qlik")
    assert "Country" in result["columns"]
    assert result["has_country"] is True
    assert len(result["columns"]) > 1


def test_qlik_metadata_finds_date_column(tmp_path: Path):
    path = tmp_path / "Qlik_W37.csv"
    path.write_text(QLIK_HEADER + "\n" + _qlik_row() + "\n", encoding="utf-8")
    result = extract_file_metadata(path, "qlik")
    assert result.get("first_date") == "2026-09-07"
    assert result.get("last_date") == "2026-09-07"
