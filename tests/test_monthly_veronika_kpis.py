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


def test_full_price_share_revenue_over_time_format(tmp_path, monkeypatch):
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
    (slot / "may_2026.csv").write_text(
        headers + row("2026-05-01", "600", "1000") + row("2026-05-02", "400", "1000"),
        encoding="utf-8",
    )
    out = calculate_full_price_share_for_date_range(
        "2026-23", tmp_path, "2026-05-01", "2026-05-31"
    )
    assert out["source"] == "pricing_type"
    assert out["full_price_share_pct"] == 50.0
    assert out["supporting"]["days_in_range"] == 2


