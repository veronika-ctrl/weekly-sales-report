"""Full price share: exchanges out, discount codes including internal stay discounted."""

from __future__ import annotations

import pandas as pd
import pytest

from weekly_report.src.metrics.commercial_full_price import (
    NOTE,
    attach_trigger_discounts,
    build_commercial_periods,
    calculate_commercial_full_price,
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


def test_commercial_history_and_month_capped_at_week_sunday(tmp_path, monkeypatch):
    pricing = pd.DataFrame(
        {
            "_date": pd.to_datetime(["2026-11-01", "2026-11-02"]),
            "_full": [100.0, 50.0],
            "_discounted": [10.0, 5.0],
            "_total": [110.0, 55.0],
            "_discount": [2.0, 1.0],
        }
    )
    monkeypatch.setattr(
        "weekly_report.src.metrics.commercial_full_price.load_pricing_type_daily_history",
        lambda root: {
            "df": pricing,
            "files_used": ["nov.csv"],
            "fx": {"applied": False},
            "currency": "USD",
            "has_discount": True,
        },
    )
    daily = pd.DataFrame(
        {
            "_date": pd.to_datetime(["2026-11-01", "2026-11-02"]),
            "group": ["1 Klaviyo", "1 Klaviyo"],
            "_discount_amount_usd": [8.0, 900.0],
            "_gross_sales_usd": [10.0, 10.0],
        }
    )
    monkeypatch.setattr(
        "weekly_report.src.metrics.commercial_full_price._prepared_discount_daily",
        lambda root: {"daily": daily, "files_used": ["d.csv"], "fx": {"applied": False}},
    )
    payload = calculate_commercial_full_price("2026-44", tmp_path, granularity="month", months=1)
    assert payload["history_range"]["end"] == "2026-11-01"
    assert payload["discount_range"]["end"] == "2026-11-01"
    nov = next(p for p in payload["periods"] if p["key"] == "2026-11")
    assert nov["end"] == "2026-11-01"
    assert nov["total"] == pytest.approx(110.0)
    assert nov["klaviyo_discount"] == pytest.approx(8.0)


def test_w44_trigger_discounts_attach_when_pricing_days_exist(tmp_path, monkeypatch):
    days = pd.date_range("2026-10-26", "2026-11-01", freq="D")
    pricing = pd.DataFrame(
        {
            "_date": days,
            "_full": [100.0] * len(days),
            "_discounted": [10.0] * len(days),
            "_total": [110.0] * len(days),
            "_discount": [2.0] * len(days),
        }
    )
    monkeypatch.setattr(
        "weekly_report.src.metrics.commercial_full_price.load_pricing_type_daily_history",
        lambda root: {
            "df": pricing,
            "files_used": ["october.csv"],
            "fx": {"applied": False},
            "currency": "USD",
            "has_discount": True,
        },
    )
    daily = pd.DataFrame(
        {
            "_date": pd.to_datetime(["2026-10-26", "2026-10-27", "2026-11-02"]),
            "group": ["1 Klaviyo", "2 Customer care", "1 Klaviyo"],
            "_discount_amount_usd": [1175.02, 63.50, 900.0],
            "_gross_sales_usd": [10.0, 10.0, 10.0],
        }
    )
    monkeypatch.setattr(
        "weekly_report.src.metrics.commercial_full_price._prepared_discount_daily",
        lambda root: {"daily": daily, "files_used": ["w44.csv"], "fx": {"applied": False}},
    )
    payload = calculate_commercial_full_price("2026-44", tmp_path, granularity="week", num_weeks=1)
    assert payload["discount_range"]["end"] == "2026-10-27"
    assert payload["history_range"]["end"] == "2026-11-01"
    row = next(p for p in payload["periods"] if p["key"] == "2026-44")
    assert row["klaviyo_discount"] == pytest.approx(1175.02)
    assert row["customer_care_discount"] == pytest.approx(63.50)
    assert row["internal_discount"] == pytest.approx(0.0)
