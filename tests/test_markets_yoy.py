"""
Unit tests for Top Markets Y/Y GROWTH%: weekKey -> lastYearWeek mapping and 2025-W50/51/52 scenario.
See docs/DIAGNOSIS_TOP_MARKETS_YOY.md for root cause and definition.
"""

import pytest
from weekly_report.src.metrics.markets import get_last_year_week_for_yoy


class TestLastYearWeekForYoy:
    """Y/Y baseline = same ISO week number, previous year."""

    def test_week_key_matching_over_year_boundary(self):
        """Last-year week for 2026-01 is 2025-01 (year boundary)."""
        assert get_last_year_week_for_yoy("2026-01") == "2025-01"
        assert get_last_year_week_for_yoy("2025-01") == "2024-01"

    def test_2025_w50_w51_w52_baseline_is_2024(self):
        """For 2025-W50/51/52 the Y/Y baseline must be 2024-50/51/52 (so frontend can show growth when data exists)."""
        assert get_last_year_week_for_yoy("2025-50") == "2024-50"
        assert get_last_year_week_for_yoy("2025-51") == "2024-51"
        assert get_last_year_week_for_yoy("2025-52") == "2024-52"

    def test_2026_weeks_baseline_is_2025(self):
        """For 2026-W01..05 the baseline is 2025-01..05."""
        assert get_last_year_week_for_yoy("2026-05") == "2025-05"
        assert get_last_year_week_for_yoy("2026-02") == "2025-02"

    def test_week_53_maps_to_52_when_prev_year_has_no_53(self):
        """When previous year has no ISO week 53, baseline for current 53 is 52."""
        # 2024 has 53 weeks; 2023 does not -> 2024-53 baseline is 2023-52
        result = get_last_year_week_for_yoy("2024-53")
        assert result == "2023-52"
