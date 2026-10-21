"""Commercial full price: investor/team net moves into full price; other codes stay discounted."""

from __future__ import annotations

import pandas as pd
import pytest

from weekly_report.src.metrics.commercial_full_price import (
    apply_investor_adjustment,
    build_commercial_periods,
    investor_adjustments_from_daily,
)
from weekly_report.src.periods.calculator import get_week_date_range


@pytest.fixture(autouse=True)
def _disable_fx(monkeypatch):
    monkeypatch.setenv("DISABLE_FX_CONVERSION", "1")


def test_investor_rows_only():
    daily = pd.DataFrame(
        {
            "_date": pd.to_datetime(["2026-10-14", "2026-10-14", "2026-10-14"]),
            "group": [
                "5 Investors, team, PR & friends",
                "1 Klaviyo",
                "2 Customer care",
            ],
            "_gross_sales_usd": [100.0, 500.0, 80.0],
            "_discount_amount_usd": [40.0, 50.0, 20.0],
        }
    )
    out = investor_adjustments_from_daily(daily)
    assert len(out) == 1
    assert out.iloc[0]["investor_net"] == pytest.approx(60.0)
    assert out.iloc[0]["investor_discount"] == pytest.approx(40.0)


def test_move_is_capped_at_discounted_net():
    pricing = pd.DataFrame(
        {
            "_date": pd.to_datetime(["2026-10-14"]),
            "_full": [100.0],
            "_discounted": [30.0],
            "_total": [130.0],
            "_discount": [10.0],
        }
    )
    investor = pd.DataFrame(
        {
            "_date": pd.to_datetime(["2026-10-14"]),
            "investor_net": [80.0],
            "investor_discount": [25.0],
        }
    )
    out = apply_investor_adjustment(pricing, investor)
    row = out.iloc[0]
    assert row["_full"] == pytest.approx(130.0)
    assert row["_discounted"] == pytest.approx(0.0)
    assert row["_total"] == pytest.approx(130.0)
    assert row["_discount"] == pytest.approx(0.0)
    assert row["_investor_net_moved"] == pytest.approx(30.0)


def test_week_period_keeps_klaviyo_in_discount_and_compares_last_year():
    week = "2026-42"
    this_day = get_week_date_range(week)["start"]
    ly_day = get_week_date_range("2025-42")["start"]
    pricing = pd.DataFrame(
        {
            "_date": pd.to_datetime([this_day, ly_day]),
            "_full": [100.0, 80.0],
            "_discounted": [50.0, 40.0],
            "_total": [150.0, 120.0],
            "_discount": [20.0, 16.0],
        }
    )
    investor = pd.DataFrame(
        {
            "_date": pd.to_datetime([this_day, ly_day]),
            "investor_net": [20.0, 10.0],
            "investor_discount": [8.0, 4.0],
        }
    )
    adjusted = apply_investor_adjustment(pricing, investor)
    periods = build_commercial_periods(adjusted, week, granularity="week", num_weeks=1)
    current = next(p for p in periods if p["week"] == week)
    assert current["full_price"] == pytest.approx(120.0)
    assert current["discounted"] == pytest.approx(30.0)
    assert current["total"] == pytest.approx(150.0)
    assert current["full_price_pct"] == pytest.approx(80.0)
    assert current["discount_amount"] == pytest.approx(12.0)
    assert current["weighted_discount_pct"] == pytest.approx(12.0 / 42.0 * 100.0)
    assert current["investor_net_moved"] == pytest.approx(20.0)
    ly = current["last_year"]
    assert ly["full_price"] == pytest.approx(90.0)
    assert ly["discounted"] == pytest.approx(30.0)
    assert ly["total"] == pytest.approx(120.0)
    assert current["yoy_total_pct"] == pytest.approx((150 - 120) / 120 * 100.0)
    assert current["full_price_pct_delta"] == pytest.approx(80.0 - 75.0)
