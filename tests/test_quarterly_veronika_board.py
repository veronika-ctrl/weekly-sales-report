import pytest

from weekly_report.src.metrics.quarterly_veronika_board import (
    _quarter_bounds,
    _yoy_pct,
    _yoy_pp,
)


def test_quarter_bounds_q2():
    start, end, label = _quarter_bounds("2026-Q2")
    assert start == "2026-04-01"
    assert end == "2026-06-30"
    assert label == "2026-Q2"


def test_quarter_bounds_invalid():
    with pytest.raises(ValueError):
        _quarter_bounds("2026-Q5")
    with pytest.raises(ValueError):
        _quarter_bounds("26-Q1")


def test_yoy_helpers():
    assert _yoy_pct(110, 100) == 10.0
    assert _yoy_pp(55.0, 50.0) == 5.0
    assert _yoy_pct(100, 0) is None
