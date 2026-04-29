import pytest

from weekly_report.src.metrics.monthly_veronika_kpis import _month_bounds, _is_amer_country


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


def test_is_amer_country():
    assert _is_amer_country("United States") is True
    assert _is_amer_country("Canada") is True
    assert _is_amer_country("Sweden") is False
