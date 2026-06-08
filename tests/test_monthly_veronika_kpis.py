import pytest
import pandas as pd

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


