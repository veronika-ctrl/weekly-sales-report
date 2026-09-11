"""Tests for last-click retention by acquisition channel."""

from __future__ import annotations

from pathlib import Path

from weekly_report.src.metrics.retention_by_channel import (
    RETENTION_CUSTOMERS_TYPE,
    calculate_retention_by_channel,
)


HEADER = (
    "CustomerId;AcquisitionDate;AcquisitionCohort;AcquisitionChannelGroup;"
    "Eligible180d;Repeated180d;NetSales180d;NetSalesTotal180d;"
    "DaysToSecondOrder;NetSalesLifetime;FullPriceShareLifetime"
)


def _write(path: Path, rows: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(HEADER + "\n" + "\n".join(rows) + "\n", encoding="utf-8")


def test_empty_state(tmp_path: Path):
    payload = calculate_retention_by_channel(tmp_path)
    assert payload["available"] is False
    assert payload["attribution"] == "last_click"
    assert payload["acquisition_min"] is None
    assert payload["acquisition_max"] is None
    assert "Retention_customers" in payload["message"]


def test_eligible_filter_and_backfilled_own_row(tmp_path: Path):
    _write(
        tmp_path / "raw" / "2026-36" / RETENTION_CUSTOMERS_TYPE / "retention.csv",
        [
            # ineligible — must not affect rates
            "a;2026-08-01;2026-08;sem;0;1;100;200;10;200;1",
            "b;2025-03-01;2025-03;sem;1;1;50;150;20;150;0.5",
            "c;2025-03-01;2025-03;sem;1;0;0;80;;80;1",
            "d;2025-03-01;2025-03;backfilled;1;1;40;140;30;140;0.8",
            "e;2025-03-01;2025-03;backfilled;1;0;0;90;;90;0.2",
            "f;2025-03-01;2025-03;organic;1;0;0;100;;100;1",
        ],
    )
    payload = calculate_retention_by_channel(tmp_path)
    assert payload["available"] is True
    assert payload["eligible_count"] == 5
    assert payload["customer_count"] == 6
    by = {r["channel_group"]: r for r in payload["channels"]}
    assert "backfilled" in by
    assert by["backfilled"]["is_backfilled"] is True
    assert by["sem"]["customers"] == 2
    assert by["sem"]["repeat_rate_180d"] == 0.5
    assert by["sem"]["net_sales_per_customer_180d"] == (150 + 80) / 2
    assert by["sem"]["full_price_share_lifetime"] == (0.5 + 1.0) / 2
    assert by["sem"]["median_days_to_second_order"] == 20
    assert by["backfilled"]["repeat_rate_180d"] == 0.5
    assert by["backfilled"]["median_days_to_second_order"] == 30
    assert by["organic"]["repeat_rate_180d"] == 0.0
    assert by["organic"]["median_days_to_second_order"] is None
    # ineligible sem repeater must not inflate sem
    assert payload["total"]["customers"] == 5
    assert payload["total"]["is_total"] is True
    names = [r["channel_group"] for r in payload["channels"]]
    assert names.index("sem") < names.index("organic") < names.index("backfilled")
    assert payload["cohort_min"] == "2025-03"
    assert payload["cohort_max"] == "2025-03"
    assert payload["acquisition_min"] == "2025-03-01"
    assert payload["acquisition_max"] == "2025-03-01"


def test_does_not_fold_backfilled_into_unknown(tmp_path: Path):
    _write(
        tmp_path / "raw" / "2026-36" / RETENTION_CUSTOMERS_TYPE / "retention.csv",
        [
            "a;2025-03-01;2025-03;backfilled;1;1;10;20;5;20;1",
            "b;2025-03-01;2025-03;unknown;1;0;0;10;;10;0",
        ],
    )
    payload = calculate_retention_by_channel(tmp_path)
    names = {r["channel_group"] for r in payload["channels"]}
    assert names == {"backfilled", "unknown"}
    by = {r["channel_group"]: r for r in payload["channels"]}
    assert by["backfilled"]["customers"] == 1
    assert by["unknown"]["customers"] == 1
