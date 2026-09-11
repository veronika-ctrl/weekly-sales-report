"""Upload metadata must not pandas-scan a full Qlik workbook."""

from pathlib import Path

from weekly_report.src.utils.file_metadata import extract_file_metadata


def test_xlsx_metadata_skips_pandas(tmp_path: Path, monkeypatch):
    path = tmp_path / "Qlik W36.xlsx"
    path.write_bytes(b"not-a-real-xlsx")

    import weekly_report.src.utils.file_metadata as mod

    def boom(*_args, **_kwargs):
        raise AssertionError("pd.read_excel must not run for xlsx metadata")

    monkeypatch.setattr(mod.pd, "read_excel", boom)
    result = extract_file_metadata(path, "qlik")
    assert result["skipped"] is True
    assert result["reason"] == "xlsx_full_scan_skipped"
    assert result["row_count"] is None


def test_csv_metadata_still_reads_dates(tmp_path: Path):
    path = tmp_path / "Revenue_by_channel_2026-08.csv"
    path.write_text("Channel;Day;Revenue\nA;2026-08-01;1\nA;2026-08-31;2\n", encoding="utf-8")
    result = extract_file_metadata(path, "amer_revenue")
    assert result["first_date"] == "2026-08-01"
    assert result["last_date"] == "2026-08-31"
    assert result["row_count"] == 2
