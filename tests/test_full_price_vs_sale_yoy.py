"""YoY for Full Price vs Sale is empty until last-year dates exist in history."""

from weekly_report.src.metrics.discounts_sales import (
    calculate_full_price_vs_sale_monthly,
    calculate_full_price_vs_sale_weekly,
)


def test_current_year_only_history_has_no_last_year(tmp_path):
    discounts_dir = tmp_path / "raw" / "2026-36" / "discounts"
    discounts_dir.mkdir(parents=True)
    (discounts_dir / "Full Price vs Sale W36.csv").write_text(
        "Date,Full Price,Compare-at Price Sale,Total\n"
        "2026-08-29,100,0,200\n"
        "2026-09-07,150,0,250\n",
        encoding="utf-8",
    )

    weekly = calculate_full_price_vs_sale_weekly("2026-36", 8, tmp_path)
    assert weekly["has_last_year"] is False
    assert weekly["history_range"] == {"start": "2026-08-29", "end": "2026-09-07"}

    monthly = calculate_full_price_vs_sale_monthly("2026-36", 13, tmp_path)
    assert monthly["has_last_year"] is False
    assert monthly["ytd"]["last_year"]["total"] == 0.0
    assert monthly["ytd"]["total"] > 0


def test_last_year_export_fills_yoy(tmp_path):
    discounts_dir = tmp_path / "raw" / "2026-36" / "discounts"
    discounts_dir.mkdir(parents=True)
    (discounts_dir / "history.csv").write_text(
        "Date,Full Price,Compare-at Price Sale,Total\n"
        "2025-09-01,80,0,160\n"
        "2026-08-29,100,0,200\n"
        "2026-09-07,150,0,250\n",
        encoding="utf-8",
    )

    monthly = calculate_full_price_vs_sale_monthly("2026-36", 13, tmp_path)
    assert monthly["has_last_year"] is True
    assert monthly["ytd"]["last_year"]["total"] > 0
