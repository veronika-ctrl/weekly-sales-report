import pandas as pd

from weekly_report.src.export.full_price_vs_sale_excel import build_full_price_vs_sale_excel


def test_build_full_price_vs_sale_excel(tmp_path, monkeypatch):
    monkeypatch.setenv("DISABLE_FX_CONVERSION", "1")
    headers = (
        "Date,Full Price,Compare-at Price Sale,Discount Code / Auto Discount,Both,"
        "Price Drop Sale,Total,Discount Amount,Full Price Share %,Exchange Orders,"
        "Exchange Gross Value,Exchange Discount,Exchange Net Revenue\n"
    )

    def row(date: str, full: str, total: str) -> str:
        compare = str(int(total) - int(full))
        return f"{date},{full},{compare},0,0,0,{total},0,0,0,0,0,0\n"

    slot = tmp_path / "raw" / "2026-23" / "full_price_vs_sale_excl_exchanges"
    slot.mkdir(parents=True)
    (slot / "april_2025.csv").write_text(headers + row("2025-04-01", "400", "1000"), encoding="utf-8")
    (slot / "may_2025.csv").write_text(headers + row("2025-05-01", "300", "1000"), encoding="utf-8")
    (slot / "april_2026.csv").write_text(headers + row("2026-04-01", "600", "1000"), encoding="utf-8")
    (slot / "may_2026.csv").write_text(headers + row("2026-05-01", "500", "1000"), encoding="utf-8")
    (slot / "june_2026.csv").write_text(headers + row("2026-06-01", "550", "1000"), encoding="utf-8")
    buf = build_full_price_vs_sale_excel("2026-23", tmp_path, months=3, num_weeks=2)
    xl = pd.ExcelFile(buf)
    assert "About" in xl.sheet_names
    assert "YTD Summary" in xl.sheet_names
    assert "Monthly" in xl.sheet_names
    assert "Weekly" in xl.sheet_names
    monthly = pd.read_excel(xl, "Monthly")
    assert "Month" in monthly.columns
    assert len(monthly) >= 1
