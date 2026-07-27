import pytest
import pandas as pd

from weekly_report.src.metrics.discounts_sales import calculate_full_price_share_for_date_range
from weekly_report.src.metrics.monthly_veronika_kpis import (
    _month_bounds,
    _shopify_sessions_in_range,
)


def test_month_bounds_february():
    start, end, label = _month_bounds("2026-02")
    assert start == "2026-02-01"
    assert end == "2026-02-28"
    assert label == "2026-02"


def test_month_bounds_invalid():
    with pytest.raises(ValueError):
        _month_bounds("2026-13")
    with pytest.raises(ValueError):
        _month_bounds("26-01")


def test_shopify_sessions_month_column():
    df = pd.DataFrame(
        {
            "Month": ["2026-05-01", "2026-05-01", "2026-04-01"],
            "Session country": ["SE", "DE", "SE"],
            "Sessions": [100, 50, 999],
        }
    )
    start = pd.Timestamp("2026-05-01")
    end = pd.Timestamp("2026-05-31 23:59:59")
    assert _shopify_sessions_in_range(df, start, end) == 150


def test_full_price_share_revenue_over_time_format(tmp_path):
    discounts_dir = tmp_path / "raw" / "2026-23" / "discounts"
    discounts_dir.mkdir(parents=True)
    csv = discounts_dir / "revenue-over-time.csv"
    csv.write_text(
        "Date,Full Price,Compare-at Price Sale,Total\n"
        "2026-05-01,600,0,1000\n"
        "2026-05-02,400,0,1000\n",
        encoding="utf-8",
    )
    out = calculate_full_price_share_for_date_range(
        "2026-23", tmp_path, "2026-05-01", "2026-05-31"
    )
    assert out["source"] == "revenue_over_time"
    assert out["full_price_share_pct"] == 50.0
    assert out["supporting"]["days_in_range"] == 2


