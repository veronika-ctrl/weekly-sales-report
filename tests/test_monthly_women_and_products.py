"""Monthly women overview and top-selling products vs last year."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from weekly_report.src.metrics.monthly_women_and_products import (
    calculate_top_products_monthly,
    calculate_women_monthly,
    last_completed_calendar_month,
    month_range_for_week,
    prior_months,
)
from weekly_report.src.periods.calculator import get_week_date_range


def test_week_42_reviews_september():
    start, end = month_range_for_week("2026-42")
    assert start == date(2026, 9, 1)
    assert end == date(2026, 9, 30)
    week_end = date.fromisoformat(get_week_date_range("2026-40")["end"])
    # First week of October still reviews September.
    s, e = last_completed_calendar_month(week_end)
    assert s.month == 9 and s.year == 2026
    assert e == date(2026, 9, 30)


def test_completed_month_on_month_end():
    start, end = last_completed_calendar_month(date(2026, 9, 30))
    assert start == date(2026, 9, 1)
    assert end == date(2026, 9, 30)


def test_prior_months_oldest_to_newest():
    months = prior_months(date(2026, 9, 1), 3)
    assert [s.isoformat() for s, _ in months] == ["2026-07-01", "2026-08-01", "2026-09-01"]


def _qlik_week_dir(tmp_path: Path) -> Path:
    week = tmp_path / "raw" / "2026-42"
    week.mkdir(parents=True)
    rows = [
        # Sep 2026 women
        ("2026-09-02", "Online", "WOMEN", "Trousers", "Karate Trousers", "Black", 4000, 4),
        ("2026-09-10", "Online", "WOMEN", "Trousers", "Karate Trousers", "Black", 2000, 2),
        ("2026-09-12", "Online", "WOMEN", "Tops", "Rib Tank", "White", 1000, 5),
        ("2026-09-20", "Retail", "WOMEN", "Tops", "Store Only", "Red", 9000, 9),
        ("2026-09-08", "Online", "MEN", "Trousers", "Classic Trouser", "Navy", 8000, 8),
        # Sep 2025 women (LY)
        ("2025-09-03", "Online", "WOMEN", "Trousers", "Karate Trousers", "Black", 3000, 3),
        ("2025-09-15", "Online", "WOMEN", "Tops", "Rib Tank", "White", 2000, 4),
        ("2025-09-18", "Online", "MEN", "Trousers", "Classic Trouser", "Navy", 5000, 5),
        # Aug 2026 for trend
        ("2026-08-05", "Online", "WOMEN", "Trousers", "Karate Trousers", "Black", 1500, 1),
    ]
    df = pd.DataFrame(
        rows,
        columns=["Date", "Sales Channel", "Gender", "Product Category", "Product", "Color", "Gross Revenue", "Sales Qty"],
    )
    qlik_dir = week / "qlik"
    qlik_dir.mkdir()
    df.to_csv(qlik_dir / "qlik.csv", index=False)
    return tmp_path


def test_women_monthly_online_only_with_yoy(tmp_path):
    data_root = _qlik_week_dir(tmp_path)
    payload = calculate_women_monthly("2026-42", data_root, months=3, top_n=10)
    assert payload["focus_month"] == "2026-09"
    assert payload["headline"]["gross_revenue"] == 7000.0
    assert payload["headline"]["last_year_gross_revenue"] == 5000.0
    assert payload["headline"]["yoy_pct"] == 40.0
    cats = {c["category"]: c for c in payload["categories"]}
    assert cats["Trousers"]["gross_revenue"] == 6000.0
    assert cats["Trousers"]["last_year_gross_revenue"] == 3000.0
    assert cats["Trousers"]["yoy_pct"] == 100.0
    karate = next(p for p in payload["top_products"] if p["product"] == "Karate Trousers")
    assert karate["gross_revenue"] == 6000.0
    assert karate["last_year_gross_revenue"] == 3000.0
    assert karate["yoy_pct"] == 100.0
    assert all(p["product"] != "Store Only" for p in payload["top_products"])
    sep = next(p for p in payload["trend"] if p["month"] == "2026-09")
    assert sep["gross_revenue"] == 7000.0


def test_top_products_monthly_men_yoy(tmp_path):
    data_root = _qlik_week_dir(tmp_path)
    payload = calculate_top_products_monthly("2026-42", data_root, gender_filter="men", months=3, top_n=10)
    assert payload["focus_month"] == "2026-09"
    classic = payload["products"][0]
    assert classic["product"] == "Classic Trouser"
    assert classic["gross_revenue"] == 8000.0
    assert classic["last_year_gross_revenue"] == 5000.0
    assert classic["yoy_pct"] == 60.0
    assert payload["grand_total"]["yoy_pct"] == 60.0
