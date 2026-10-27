"""Full price share: exchanges out, discount codes including internal stay discounted."""

from __future__ import annotations

import pandas as pd
import pytest

from weekly_report.src.metrics.commercial_full_price import (
    NOTE,
    attach_trigger_discounts,
    build_commercial_periods,
    trigger_discounts_from_daily,
)
from weekly_report.src.periods.calculator import get_week_date_range


@pytest.fixture(autouse=True)
def _disable_fx(monkeypatch):
    monkeypatch.setenv("DISABLE_FX_CONVERSION", "1")


def test_trigger_amounts_keep_internal_separate_from_klaviyo_and_care():
    day = pd.Timestamp("2026-10-14")
    daily = pd.DataFrame(
        {
            "_date": [day, day, day, day],
            "group": [
                "1 Klaviyo",
                "1 Klaviyo",
                "2 Customer care",
                "5 Investors, team, PR & friends",
            ],
            "_gross_sales_usd": [500.0, 100.0, 80.0, 100.0],
            "_discount_amount_usd": [30.0, 20.0, 20.0, 40.0],
        }
    )
    triggers = trigger_discounts_from_daily(daily)
    assert len(triggers) == 1
    assert triggers.iloc[0]["klaviyo_discount"] == pytest.approx(50.0)
    assert triggers.iloc[0]["customer_care_discount"] == pytest.approx(20.0)
    assert triggers.iloc[0]["internal_discount"] == pytest.approx(40.0)


def test_internal_orders_stay_in_discounted_and_in_weighted_discount():
    week = "2026-42"
    this_day = get_week_date_range(week)["start"]
    ly_day = get_week_date_range("2025-42")["start"]
    pricing = pd.DataFrame(
        {
            "_date": pd.to_datetime([this_day, ly_day]),
            "_full": [1212.0, 900.0],
            "_discounted": [188.0, 100.0],
            "_total": [1400.0, 1000.0],
            "_discount": [23.7, 10.0],
        }
    )
    triggers = pd.DataFrame(
        {
            "_date": pd.to_datetime([this_day, ly_day]),
            "klaviyo_discount": [14.0, 13.0],
            "customer_care_discount": [1.0, 3.0],
            "internal_discount": [6.6, 4.0],
        }
    )
    adjusted = attach_trigger_discounts(pricing, triggers)
    periods = build_commercial_periods(adjusted, week, granularity="week", num_weeks=1)
    current = next(p for p in periods if p["week"] == week)
    assert current["full_price"] == pytest.approx(1212.0)
    assert current["discounted"] == pytest.approx(188.0)
    assert current["total"] == pytest.approx(1400.0)
    assert current["full_price_pct"] == pytest.approx(1212.0 / 1400.0 * 100.0)
    assert current["discount_amount"] == pytest.approx(23.7)
    assert current["weighted_discount_pct"] == pytest.approx(23.7 / (188.0 + 23.7) * 100.0)
    assert current["klaviyo_discount"] == pytest.approx(14.0)
    assert current["customer_care_discount"] == pytest.approx(1.0)
    assert current["internal_discount"] == pytest.approx(6.6)
    ly = current["last_year"]
    assert ly["full_price"] == pytest.approx(900.0)
    assert ly["discounted"] == pytest.approx(100.0)
    assert ly["klaviyo_discount"] == pytest.approx(13.0)
    assert ly["customer_care_discount"] == pytest.approx(3.0)
    assert ly["internal_discount"] == pytest.approx(4.0)
    assert "counted as full price" not in NOTE


def test_duplicate_pricing_dates_do_not_double_trigger_discounts():
    week = "2026-42"
    this_day = get_week_date_range(week)["start"]
    ly_day = get_week_date_range("2025-42")["start"]
    pricing = pd.DataFrame(
        {
            "_date": pd.to_datetime([this_day, this_day, ly_day]),
            "_full": [60.0, 60.0, 90.0],
            "_discounted": [20.0, 10.0, 30.0],
            "_total": [80.0, 70.0, 120.0],
            "_discount": [8.0, 4.0, 12.0],
        }
    )
    triggers = pd.DataFrame(
        {
            "_date": pd.to_datetime([this_day, ly_day]),
            "klaviyo_discount": [50.0, 15.0],
            "customer_care_discount": [20.0, 5.0],
            "internal_discount": [7.0, 2.0],
        }
    )
    adjusted = attach_trigger_discounts(pricing, triggers)
    assert len(adjusted) == 2
    this_row = adjusted.loc[adjusted["_date"].eq(pd.Timestamp(this_day))].iloc[0]
    assert this_row["klaviyo_discount"] == pytest.approx(50.0)
    assert this_row["internal_discount"] == pytest.approx(7.0)
    assert this_row["_full"] == pytest.approx(120.0)
    assert this_row["_discounted"] == pytest.approx(30.0)
    periods = build_commercial_periods(adjusted, week, granularity="week", num_weeks=1)
    current = next(p for p in periods if p["week"] == week)
    assert current["full_price"] == pytest.approx(120.0)
    assert current["discounted"] == pytest.approx(30.0)
    assert current["last_year"]["internal_discount"] == pytest.approx(2.0)
