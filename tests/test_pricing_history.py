"""Month-filename parser and skip-if-missing Full Price % integration."""

from __future__ import annotations

from pathlib import Path

import pytest

from weekly_report.src.metrics.discounts_sales import calculate_full_price_vs_sale_monthly
from weekly_report.src.metrics.pricing_history import (
    discover_pricing_files,
    is_legacy_weekly_filename,
    parse_iso_week_from_filename,
    parse_month_from_filename,
)


@pytest.mark.parametrize(
    "name,expected",
    [
        ("january_2025.csv", (2025, 1)),
        ("august_2026_full_exchanges.csv", (2026, 8)),
        ("september_full_26.csv", (2026, 9)),
        ("january_2026_ful_exchanges.csv", (2026, 1)),
        ("april_25.csv", (2025, 4)),
        ("Full_Price_vs_Sale_W40.csv", None),
        ("Exchanges_W40.csv", None),
        ("Exchanges_Historical_Data.csv", None),
        ("full-price-vs-sale-2024-01-01-to-2024-01-07.csv", None),
        ("full-price-vs-sale-excl-exchanges-2026-08-24-to-2026-08-30.csv", None),
        ("week.csv", None),
    ],
)
def test_parse_month_from_filename(name, expected):
    assert parse_month_from_filename(name) == expected


def test_legacy_weekly_detection():
    assert is_legacy_weekly_filename("Full_Price_vs_Sale_W40.csv")
    assert is_legacy_weekly_filename("Exchanges_W40.csv")
    assert is_legacy_weekly_filename("Exchanges_Historical_Data.csv")
    assert not is_legacy_weekly_filename("august_2026_full_exchanges.csv")


def test_iso_week_continuation_names():
    assert parse_iso_week_from_filename("week_2026_41.csv") == "2026-41"
    assert parse_iso_week_from_filename("iso-2026-40.csv") == "2026-40"
    assert parse_iso_week_from_filename("Full_Price_vs_Sale_W40.csv") is None


@pytest.fixture(autouse=True)
def _disable_fx(monkeypatch):
    monkeypatch.setenv("DISABLE_FX_CONVERSION", "1")


def test_full_price_pct_integration_if_month_files_present():
    """Expected mix when the 22 production month CSVs are available locally."""
    data_root = Path("/workspace/data")
    files, _ignored = discover_pricing_files(data_root)
    bundled = Path("/workspace/weekly_report/data/pricing_type")
    if bundled.exists():
        files = list(files) + list(bundled.glob("*.csv"))
    if not files:
        pytest.skip("month-named Full Price vs Sale CSVs are not in this workspace")
    payload = calculate_full_price_vs_sale_monthly("2026-41", 24, data_root if data_root.exists() else bundled.parent)
    by_month = {m["month"]: m for m in payload["months_data"]}
    expected = {
        "2025-01": 41.6,
        "2025-09": 72.0,
        "2026-08": 78.2,
        "2026-09": 86.4,
    }
    missing = [k for k in expected if k not in by_month or not (by_month[k].get("total") or 0)]
    if missing:
        pytest.skip(f"month files did not cover {missing}")
    for month, pct in expected.items():
        assert by_month[month]["full_price_pct"] == pytest.approx(pct, abs=0.1), month
