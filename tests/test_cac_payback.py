"""Tests for last-click CAC payback by channel."""

from __future__ import annotations

from pathlib import Path

from weekly_report.src.metrics.cac_payback import (
    CAC_PAYBACK_GROUPS_TYPE,
    CAC_PAYBACK_HORIZON_TYPE,
    CAC_PAYBACK_SEGMENTS_TYPE,
    calculate_cac_payback,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


GROUPS = """ChannelGroup;Spend;NewCustomers;CAC;GP2_FirstOrder;GP2_180d;Payback_FirstOrder;Payback_180d;PB_low;PB_high
social_ppc;1000;10;100;20;30;0.2;0.3;0.3;1.0
sem;2000;20;100;80;180;0.8;1.8;1.0;2.0
affiliate;500;5;100;90;200;0.9;2.0;1.5;3.0
"""

SEGMENTS = """Horizon;AcquisitionChannelGroup;Segment;Spend;NewCustomers;RepeatRate;new_share;CAC_full;CAC_newshare;GP2_perCust;Payback_full;Payback_newshare
180d;social_ppc;TOF / prospecting;600;6;0.2;0.7;100;70;40;0.4;0.57
180d;social_ppc;BOF / retargeting;400;4;0.1;0.3;100;30;20;0.2;0.67
180d;sem;Non-branded search;1500;10;0.2;0.7;150;105;90;0.6;0.86
180d;sem;Branded search;500;10;0.2;0.4;50;20;200;4.0;10.0
180d;affiliate;Content / editorial (indicative);400;4;0.2;;100;;180;1.8;
180d;affiliate;Coupon / cashback (indicative);100;1;0.2;;100;;50;0.5;
"""

HORIZON = """AcquisitionChannelGroup;Segment;NewCustomers_180;CAC_full_180;GP2_perCust_180;GP2_perCust_365;GP2_uplift_pct;Payback_180;Payback_365
social_ppc;ALL campaigns;8;120;30;36;0.2;0.25;0.3
sem;ALL campaigns;15;90;180;210;0.17;2.0;2.33
affiliate;ALL campaigns;4;110;200;230;0.15;1.82;2.09
sem;Branded search;9;40;200;230;0.15;5.0;5.75
sem;Non-branded search;6;160;90;100;0.11;0.56;0.63
"""


def test_empty_state(tmp_path: Path):
    payload = calculate_cac_payback(tmp_path)
    assert payload["available"] is False
    assert payload["attribution"] == "last_click"
    assert "CAC payback" in payload["message"]
    assert len(payload["caveats"]) >= 3


def test_headline_channels_and_period(tmp_path: Path):
    _write(
        tmp_path / "raw" / "2026-36" / CAC_PAYBACK_GROUPS_TYPE / "CAC_payback_by_channelgroup_2025-03_2026-02.csv",
        GROUPS,
    )
    payload = calculate_cac_payback(tmp_path)
    assert payload["available"] is True
    assert payload["period_min"] == "2025-03"
    assert payload["period_max"] == "2026-02"
    names = [r["channel_group"] for r in payload["channels"]]
    assert names == ["social_ppc", "sem", "affiliate"]
    by = {r["channel_group"]: r for r in payload["channels"]}
    assert by["social_ppc"]["cac"] == 100
    assert by["social_ppc"]["gp2_180d"] == 30
    assert by["social_ppc"]["payback_180d"] == 0.3
    assert by["sem"]["payback_180d"] == 1.8
    assert payload["missing_files"]["groups"] is False
    assert payload["missing_files"]["segments"] is True


def test_segments_keep_meta_search_affiliate_splits(tmp_path: Path):
    _write(tmp_path / "raw" / "2026-36" / CAC_PAYBACK_SEGMENTS_TYPE / "segments.csv", SEGMENTS)
    payload = calculate_cac_payback(tmp_path)
    kinds = [(r["channel_group"], r["segment"], r["indicative"]) for r in payload["segments"]]
    assert ("social_ppc", "prospecting", False) in kinds
    assert ("social_ppc", "retargeting", False) in kinds
    assert ("sem", "branded", False) in kinds
    assert ("sem", "non_branded", False) in kinds
    assert ("affiliate", "editorial", True) in kinds
    assert ("affiliate", "coupon", True) in kinds
    by = {(r["channel_group"], r["segment"]): r for r in payload["segments"]}
    assert by[("sem", "branded")]["cac"] == 50
    assert by[("sem", "branded")]["payback"] == 4.0
    assert by[("affiliate", "editorial")]["cac_newshare"] is None
    order = [r["segment"] for r in payload["segments"] if r["channel_group"] == "social_ppc"]
    assert order == ["prospecting", "retargeting"]


def test_horizon_180_vs_365(tmp_path: Path):
    _write(tmp_path / "raw" / "2026-36" / CAC_PAYBACK_HORIZON_TYPE / "horizon.csv", HORIZON)
    payload = calculate_cac_payback(tmp_path)
    totals = [r for r in payload["horizon"] if r["is_channel_total"]]
    assert [r["channel_group"] for r in totals] == ["social_ppc", "sem", "affiliate"]
    sem = next(r for r in payload["horizon"] if r["channel_group"] == "sem" and r["is_channel_total"])
    assert sem["payback_180"] == 2.0
    assert sem["payback_365"] == 2.33
    branded = next(r for r in payload["horizon"] if r["segment"] == "branded")
    assert branded["is_channel_total"] is False
    assert branded["payback_365"] == 5.75
