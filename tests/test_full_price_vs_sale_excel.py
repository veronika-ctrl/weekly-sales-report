import pandas as pd

from weekly_report.src.export.full_price_vs_sale_excel import build_full_price_vs_sale_excel


def test_build_full_price_vs_sale_excel(tmp_path):
    discounts_dir = tmp_path / "raw" / "2026-23" / "discounts"
    discounts_dir.mkdir(parents=True)
    csv = discounts_dir / "revenue-over-time.csv"
    csv.write_text(
        "Date,Full Price,Compare-at Price Sale,Total\n"
        "2025-04-01,400,0,1000\n"
        "2025-05-01,300,0,1000\n"
        "2026-04-01,600,0,1000\n"
        "2026-05-01,500,0,1000\n"
        "2026-06-01,550,0,1000\n",
        encoding="utf-8",
    )
    buf = build_full_price_vs_sale_excel("2026-23", tmp_path, months=3, num_weeks=2)
    xl = pd.ExcelFile(buf)
    assert "About" in xl.sheet_names
    assert "YTD Summary" in xl.sheet_names
    assert "Monthly" in xl.sheet_names
    assert "Weekly" in xl.sheet_names
    monthly = pd.read_excel(xl, "Monthly")
    assert "Month" in monthly.columns
    assert len(monthly) >= 1
