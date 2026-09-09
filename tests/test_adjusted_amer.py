"""Unit tests for the Adjusted aMER module.

Fixtures match production Dema ChannelGroups and spaced column headers:
    Channel;ChannelGroup;Country;Day;Revenue_MTA;Revenue_CFA;Revenue_New_MTA;Revenue_Returning_MTA
    Channel;ChannelGroup;Country;Day;Marketing spend
    Channel;ChannelGroup;Country;Day;Net gross profit 2;Net sales;Net gross margin 2;Marketing spend

Manual recompute (fixture week 2026-36 = Mon 2026-08-31 .. Sun 2026-09-06):

  Paid CFA (social_ppc+sem+affiliate) week days:
    Facebook 100 (Aug 31) + Instagram 50 (Sep 1) + TikTok 40 (Sep 1) + Google 20 (Sep 2) + CJ 10 (Sep 3)
    = 220
  Organic CFA: email 30 (Sep 1) + direct 15 (Sep 4) = 45
  Unattributed CFA: unknown 25 (Sep 5) = 25
  Other CFA: podcast 8 (Sep 6) = 8
  totalRevenue = 220+45+25 = 290  (other excluded)
  New MTA paid: 40+10+12+8+3 = 73
  Paid spend: Facebook 50+20 + TikTok 30 + Google 25 + CJ 15 = 140
    (Instagram has revenue but no spend — Meta booked to facebook)
  adjustedAMER = 220/140 = 1.571428...
  blendedMER = 290/140 = 2.071428...
  newCustomerAdjustedAMER = 73/140 = 0.521428...
  Net GM2 = (80+40+20+10) / (200+90+50+30) = 150/370 ≈ 0.405405

  Unmatched spend (TikTok SE 2026-09-01 spend 30, no extra unmatched in this grain
  beyond Instagram spend=0). Unmatched revenue (direct SE 2026-09-04, no spend) spend = 0.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from weekly_report.src.metrics.adjusted_amer import (
    AMER_GM2_TYPE,
    AMER_REVENUE_TYPE,
    AMER_SPEND_TYPE,
    SHOPIFY_CUSTOMERS_TYPE,
    aggregate_amer_metrics,
    calculate_adjusted_amer,
    classify_channel_group,
    full_outer_join_amer,
    infer_channel_group,
    is_provisional,
    load_gm2_frame,
    load_revenue_frame,
    load_spend_frame,
    monthly_channel_rows,
    monthly_group_rows,
    monthly_headline_rows,
    recruited_vs_dropped,
    safe_ratio,
)


WEEK = "2026-36"  # Mon 2026-08-31 .. Sun 2026-09-06


def _write_csv(path: Path, header: str, rows: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + "\n" + "\n".join(rows) + "\n", encoding="utf-8")
    return path


def _amer_week_dir(tmp_path: Path, week: str = WEEK) -> Path:
    return tmp_path / "raw" / week


def write_w36_style_fixtures(tmp_path: Path, week: str = WEEK) -> Path:
    """Production ChannelGroups; Meta spend on facebook, CFA on facebook+instagram."""
    base = _amer_week_dir(tmp_path, week)
    _write_csv(
        base / AMER_REVENUE_TYPE / "Revenue_by_channel_W36.csv",
        "Channel;ChannelGroup;Country;Day;Revenue_MTA;Revenue_CFA;Revenue_New_MTA;Revenue_Returning_MTA",
        [
            "Facebook;social_ppc;Sweden;2026-08-31;90;100;40;60",
            "Instagram;social_ppc;Sweden;2026-09-01;55;50;10;40",
            "TikTok;social_ppc;Sweden;2026-09-01;44;40;12;28",
            "Google;sem;Sweden;2026-09-02;22;20;8;12",
            "CJ;affiliate;Sweden;2026-09-03;11;10;3;7",
            "Klaviyo;email;Sweden;2026-09-01;30;30;30;0",
            "Direct;direct;Sweden;2026-09-04;15;15;0;15",
            "Unknown;unknown;Sweden;2026-09-05;25;25;0;25",
            "Podcast;podcast;Sweden;2026-09-06;8;8;0;8",
            "Facebook;social_ppc;Sweden;2026-07-15;200;180;70;110",
        ],
    )
    _write_csv(
        base / AMER_SPEND_TYPE / "Marketing_spend_W36.csv",
        "Channel;ChannelGroup;Country;Day;Marketing spend",
        [
            "Facebook;social_ppc;Sweden;2026-08-31;50",
            "Facebook;social_ppc;Sweden;2026-09-01;20",
            "TikTok;social_ppc;Sweden;2026-09-01;30",
            "Google;sem;Sweden;2026-09-02;25",
            "CJ;affiliate;Sweden;2026-09-03;15",
            "Facebook;social_ppc;Sweden;2026-07-15;90",
        ],
    )
    _write_csv(
        base / AMER_GM2_TYPE / "Net_GM2_W36.csv",
        "Channel;ChannelGroup;Country;Day;Net gross profit 2;Net sales;Net gross margin 2;Marketing spend",
        [
            "Facebook;social_ppc;Sweden;2026-08-31;80;200;0.40;50",
            "TikTok;social_ppc;Sweden;2026-09-01;40;90;0.444;30",
            "Google;sem;Sweden;2026-09-02;20;50;0.40;25",
            "CJ;affiliate;Sweden;2026-09-03;10;30;0.333;15",
            "Facebook;social_ppc;Sweden;2026-07-15;1;100;0.99;90",
        ],
    )
    return tmp_path


# ---------------------------------------------------------------------------
# Taxonomy
# ---------------------------------------------------------------------------

def test_taxonomy_production_channel_groups():
    assert infer_channel_group("Facebook", None) == "social_ppc"
    assert infer_channel_group("Instagram", None) == "social_ppc"
    assert infer_channel_group("TikTok", None) == "social_ppc"
    assert infer_channel_group("Pinterest", None) == "social_ppc"
    assert infer_channel_group("Google", None) == "sem"
    assert infer_channel_group("CJ", None) == "affiliate"
    assert infer_channel_group("wordseed", None) == "affiliate"
    assert infer_channel_group("klarna", None) == "affiliate"
    assert infer_channel_group("goodonyou", None) == "affiliate"
    assert classify_channel_group("social_ppc") == "paid"
    assert classify_channel_group("sem") == "paid"
    assert classify_channel_group("affiliate") == "paid"
    assert classify_channel_group("meta") == "other"
    assert classify_channel_group("tiktok") == "other"
    assert classify_channel_group("facebook") == "other"


def test_taxonomy_spec_organic_unattributed_other():
    assert classify_channel_group("organic") == "organic"
    assert classify_channel_group("email") == "organic"
    assert classify_channel_group("social_organic") == "organic"
    assert classify_channel_group("referral") == "organic"
    assert classify_channel_group("direct") == "organic"
    assert classify_channel_group("backfilled") == "unattributed"
    assert classify_channel_group("unknown") == "unattributed"
    assert classify_channel_group("unattributed") == "unattributed"
    assert classify_channel_group("podcast") == "other"
    assert classify_channel_group("display") == "other"
    assert classify_channel_group("weird_new_network") == "other"


def test_channel_group_from_file_wins_over_inference():
    assert infer_channel_group("Facebook", "email") == "email"
    assert classify_channel_group("email") == "organic"


# ---------------------------------------------------------------------------
# Join
# ---------------------------------------------------------------------------

def test_full_outer_join_keeps_unmatched_spend_and_revenue(tmp_path: Path):
    write_w36_style_fixtures(tmp_path)
    week_path = _amer_week_dir(tmp_path)
    revenue = load_revenue_frame(week_path / AMER_REVENUE_TYPE / "Revenue_by_channel_W36.csv")
    spend = load_spend_frame(week_path / AMER_SPEND_TYPE / "Marketing_spend_W36.csv")
    gm2 = load_gm2_frame(week_path / AMER_GM2_TYPE / "Net_GM2_W36.csv")
    joined = full_outer_join_amer(revenue, spend, gm2)

    tiktok = joined[
        (joined["Channel"] == "TikTok")
        & (joined["Day"] == pd.Timestamp("2026-09-01"))
    ]
    assert len(tiktok) == 1
    assert float(tiktok.iloc[0]["marketing_spend"]) == 30.0
    assert float(tiktok.iloc[0]["revenue_cfa"]) == 40.0

    direct = joined[
        (joined["Channel"] == "Direct")
        & (joined["Day"] == pd.Timestamp("2026-09-04"))
    ]
    assert len(direct) == 1
    assert float(direct.iloc[0]["revenue_cfa"]) == 15.0
    assert float(direct.iloc[0]["marketing_spend"]) == 0.0

    # Spend-only grain would disappear on a left join from revenue — extra spend
    # row with no revenue is simulated by a unique country.
    extra_spend = pd.DataFrame(
        {
            "Channel": ["TikTok"],
            "ChannelGroup": ["social_ppc"],
            "Country": ["Norway"],
            "Day": [pd.Timestamp("2026-09-01")],
            "bucket": ["paid"],
            "marketing_spend": [99.0],
            "_source_mtime": [pd.Timestamp("2026-09-08")],
        }
    )
    joined2 = full_outer_join_amer(revenue, pd.concat([spend, extra_spend], ignore_index=True), gm2)
    norway = joined2[(joined2["Country"] == "Norway") & (joined2["Channel"] == "TikTok")]
    assert len(norway) == 1
    assert float(norway.iloc[0]["marketing_spend"]) == 99.0
    assert float(norway.iloc[0]["revenue_cfa"]) == 0.0


# ---------------------------------------------------------------------------
# Ratios / weekly aggregates / CFA vs MTA
# ---------------------------------------------------------------------------

def test_weekly_aggregates_match_manual_recompute(tmp_path: Path):
    write_w36_style_fixtures(tmp_path)
    payload = calculate_adjusted_amer(WEEK, tmp_path)
    week = payload["week"]
    assert week is not None
    assert week["paidRevenue"] == pytest.approx(220.0)
    assert week["organicRevenue"] == pytest.approx(45.0)
    assert week["unattributedRevenue"] == pytest.approx(25.0)
    assert week["otherRevenue"] == pytest.approx(8.0)
    assert week["totalRevenue"] == pytest.approx(290.0)
    assert week["newCustomerPaidRevenue"] == pytest.approx(73.0)
    assert week["paidSpend"] == pytest.approx(140.0)
    assert week["adjustedAMER"] == pytest.approx(220.0 / 140.0)
    assert week["blendedMER"] == pytest.approx(290.0 / 140.0)
    assert week["newCustomerAdjustedAMER"] == pytest.approx(73.0 / 140.0)
    assert week["paidRevShare"] == pytest.approx(220.0 / 290.0)
    assert week["organicRevShare"] == pytest.approx(45.0 / 290.0)
    assert week["unattributedShare"] == pytest.approx(25.0 / 290.0)
    assert week["netGM2"] == pytest.approx(150.0 / 370.0)
    # CFA headline ≠ MTA new-customer ratio
    assert week["adjustedAMER"] != pytest.approx(week["newCustomerAdjustedAMER"])


def test_unattributed_not_folded_into_organic():
    df = pd.DataFrame(
        {
            "bucket": ["organic", "unattributed"],
            "revenue_cfa": [100.0, 50.0],
            "revenue_new_mta": [0.0, 0.0],
            "marketing_spend": [0.0, 0.0],
            "net_gross_profit_2": [0.0, 0.0],
            "net_sales": [0.0, 0.0],
        }
    )
    m = aggregate_amer_metrics(df)
    assert m["organicRevenue"] == 100.0
    assert m["unattributedRevenue"] == 50.0
    assert m["totalRevenue"] == 150.0


def test_safe_ratio_guards_divide_by_zero():
    assert safe_ratio(10, 0) is None
    assert safe_ratio(10, None) is None
    assert safe_ratio(float("nan"), 5) is None
    assert safe_ratio(10, 4) == pytest.approx(2.5)


def test_zero_paid_spend_ratios_are_null():
    df = pd.DataFrame(
        {
            "bucket": ["paid", "organic"],
            "revenue_cfa": [100.0, 50.0],
            "revenue_new_mta": [20.0, 0.0],
            "marketing_spend": [0.0, 0.0],
            "net_gross_profit_2": [10.0, 0.0],
            "net_sales": [0.0, 0.0],
        }
    )
    m = aggregate_amer_metrics(df)
    assert m["adjustedAMER"] is None
    assert m["blendedMER"] is None
    assert m["newCustomerAdjustedAMER"] is None
    assert m["netGM2"] is None


# ---------------------------------------------------------------------------
# Month split + GM2 recompute
# ---------------------------------------------------------------------------

def test_month_split_week_straddles_august_september(tmp_path: Path):
    write_w36_style_fixtures(tmp_path)
    payload = calculate_adjusted_amer(WEEK, tmp_path)
    months = {row["year_month"]: row for row in payload["monthly"]}
    assert "2026-08" in months
    assert "2026-09" in months
    # Aug 31 Facebook CFA 100 is August, not September
    assert months["2026-08"]["paidRevenue"] == pytest.approx(100.0)
    assert months["2026-09"]["paidRevenue"] == pytest.approx(120.0)
    # July history from the same weekly file
    assert months["2026-07"]["paidRevenue"] == pytest.approx(180.0)


def test_gm2_is_sum_over_sum_not_row_average(tmp_path: Path):
    write_w36_style_fixtures(tmp_path)
    payload = calculate_adjusted_amer(WEEK, tmp_path)
    july = next(r for r in payload["monthly"] if r["year_month"] == "2026-07")
    # One July GM2 row: 1 / 100 = 0.01. Averaging the 0.99 row-level margin would be wrong.
    assert july["netGM2"] == pytest.approx(1.0 / 100.0)
    assert july["netGM2"] != pytest.approx(0.99)

    by_ch = [
        r
        for r in payload["monthly_by_channel"]
        if r["year_month"] == "2026-09" and r["channel"] == "Instagram"
    ]
    assert len(by_ch) == 1
    assert by_ch[0]["adjustedAMER"] is None
    assert by_ch[0]["newCustomerAdjustedAMER"] is None
    assert by_ch[0]["revenue_cfa"] == pytest.approx(50.0)

    by_g = [
        r
        for r in payload["monthly_by_group"]
        if r["year_month"] == "2026-09" and r["channel_group"] == "social_ppc"
    ]
    assert len(by_g) == 1
    # Instagram 50 + TikTok 40 CFA; Facebook 20 + TikTok 30 spend
    assert by_g[0]["adjustedAMER"] == pytest.approx(90.0 / 50.0)
    assert by_g[0]["newCustomerAdjustedAMER"] == pytest.approx(22.0 / 50.0)


def test_monthly_channel_keeps_channel_and_group_without_ratios():
    df = pd.DataFrame(
        {
            "Channel": ["Facebook", "Instagram"],
            "ChannelGroup": ["social_ppc", "social_ppc"],
            "bucket": ["paid", "paid"],
            "Day": pd.to_datetime(["2026-01-10", "2026-01-20"]),
            "revenue_cfa": [100.0, 50.0],
            "revenue_new_mta": [40.0, 10.0],
            "marketing_spend": [50.0, 0.0],
            "net_gross_profit_2": [0.0, 0.0],
            "net_sales": [0.0, 0.0],
            "_as_of": pd.to_datetime(["2026-09-01", "2026-09-01"], utc=True),
        }
    )
    channels = monthly_channel_rows(df, date(2026, 9, 1))
    assert len(channels) == 2
    insta = next(r for r in channels if r["channel"] == "Instagram")
    assert insta["adjustedAMER"] is None
    assert insta["revenue_cfa"] == pytest.approx(50.0)

    groups = monthly_group_rows(df, date(2026, 9, 1))
    assert len(groups) == 1
    assert groups[0]["channel_group"] == "social_ppc"
    assert groups[0]["adjustedAMER"] == pytest.approx(150.0 / 50.0)
    assert groups[0]["newCustomerAdjustedAMER"] == pytest.approx(50.0 / 50.0)
    assert set(groups[0]["channels"]) == {"Facebook", "Instagram"}


# ---------------------------------------------------------------------------
# Missing files / no silent stale fallback
# ---------------------------------------------------------------------------

def test_missing_files_warning_does_not_use_stale_week_headline(tmp_path: Path):
    write_w36_style_fixtures(tmp_path, week="2026-35")
    payload = calculate_adjusted_amer(WEEK, tmp_path)
    assert payload["week"] is None
    assert payload["missing_files"][AMER_REVENUE_TYPE] is True
    assert payload["missing_files"][AMER_SPEND_TYPE] is True
    assert payload["missing_files"][AMER_GM2_TYPE] is True
    assert any(w["code"] == "missing_agent_files" for w in payload["warnings"])
    assert "stale" in payload["warnings"][0]["message"].lower()


def test_partial_missing_file_blocks_week_headline(tmp_path: Path):
    write_w36_style_fixtures(tmp_path)
    spend = _amer_week_dir(tmp_path) / AMER_SPEND_TYPE / "Marketing_spend_W36.csv"
    spend.unlink()
    payload = calculate_adjusted_amer(WEEK, tmp_path)
    assert payload["week"] is None
    assert payload["missing_files"][AMER_SPEND_TYPE] is True
    assert payload["missing_files"][AMER_REVENUE_TYPE] is False


# ---------------------------------------------------------------------------
# Provisional / as-of
# ---------------------------------------------------------------------------

def test_provisional_flag_six_weeks():
    as_of = date(2026, 9, 8)
    assert is_provisional(date(2026, 9, 6), as_of) is True
    assert is_provisional(date(2026, 7, 31), as_of) is True  # 39 days
    assert is_provisional(date(2026, 6, 30), as_of) is False  # 70 days


def test_payload_includes_as_of_and_provisional(tmp_path: Path):
    write_w36_style_fixtures(tmp_path)
    payload = calculate_adjusted_amer(WEEK, tmp_path)
    assert payload["as_of"]
    assert payload["week"]["as_of"]
    assert payload["week"]["provisional"] is True
    july = next(r for r in payload["monthly"] if r["year_month"] == "2026-07")
    assert "as_of" in july


# ---------------------------------------------------------------------------
# Recruited vs dropped (Shopify-only)
# ---------------------------------------------------------------------------

def test_recruited_vs_dropped_months():
    orders = pd.DataFrame(
        {
            "customer_id": ["a", "a", "b", "c"],
            "order_date": pd.to_datetime(
                ["2025-03-10", "2026-03-05", "2025-09-15", "2026-09-01"]
            ),
        }
    )
    rows = {r["year_month"]: r for r in recruited_vs_dropped(orders)}
    assert rows["2025-03"]["recruited"] == 1  # a
    assert rows["2025-09"]["recruited"] == 1  # b
    assert rows["2026-09"]["recruited"] == 1  # c
    # b's last order is 2025-09 → dropped in 2026-09
    assert rows["2026-09"]["dropped"] == 1
    # a ordered again in 2026-03 so not dropped 12 months after 2025-03
    assert rows["2026-03"]["dropped"] == 0


def test_shopify_customers_empty_state(tmp_path: Path):
    write_w36_style_fixtures(tmp_path)
    payload = calculate_adjusted_amer(WEEK, tmp_path)
    assert payload["recruited_vs_dropped"]["available"] is False
    assert "Shopify customer-order" in payload["recruited_vs_dropped"]["message"]


def test_shopify_customers_upload_computes_cohorts(tmp_path: Path):
    write_w36_style_fixtures(tmp_path)
    _write_csv(
        tmp_path / "raw" / WEEK / SHOPIFY_CUSTOMERS_TYPE / "customers.csv",
        "Customer ID;Created at",
        [
            "a;2025-03-10",
            "a;2026-03-05",
            "b;2025-09-15",
            "c;2026-09-01",
        ],
    )
    payload = calculate_adjusted_amer(WEEK, tmp_path)
    rvd = payload["recruited_vs_dropped"]
    assert rvd["available"] is True
    by_m = {r["year_month"]: r for r in rvd["months"]}
    assert by_m["2026-09"]["recruited"] == 1
    assert by_m["2026-09"]["dropped"] == 1


def test_european_decimal_spend_parses(tmp_path: Path):
    base = _amer_week_dir(tmp_path)
    _write_csv(
        base / AMER_REVENUE_TYPE / "rev.csv",
        "Channel;ChannelGroup;Country;Day;Revenue_MTA;Revenue_CFA;Revenue_New_MTA;Revenue_Returning_MTA",
        ["Facebook;social_ppc;Sweden;2026-09-01;10;10;4;6"],
    )
    _write_csv(
        base / AMER_SPEND_TYPE / "spend.csv",
        "Channel;ChannelGroup;Country;Day;Marketing spend",
        ["Facebook;social_ppc;Sweden;2026-09-01;12,5"],
    )
    _write_csv(
        base / AMER_GM2_TYPE / "gm2.csv",
        "Channel;ChannelGroup;Country;Day;Net gross profit 2;Net sales;Net gross margin 2;Marketing spend",
        ["Facebook;social_ppc;Sweden;2026-09-01;5;10;0,5;12,5"],
    )
    payload = calculate_adjusted_amer(WEEK, tmp_path)
    assert payload["week"]["paidSpend"] == pytest.approx(12.5)
    assert payload["week"]["adjustedAMER"] == pytest.approx(10 / 12.5)
    assert payload["week"]["netGM2"] == pytest.approx(0.5)


def test_spaced_column_headers_match_production_names(tmp_path: Path):
    """Parser must accept 'Marketing spend', 'Net gross profit 2', 'Net sales', 'Net gross margin 2'."""
    base = _amer_week_dir(tmp_path)
    _write_csv(
        base / AMER_REVENUE_TYPE / "Revenue_by_channel_W36.csv",
        "Channel;ChannelGroup;Country;Day;Revenue_MTA;Revenue_CFA;Revenue_New_MTA;Revenue_Returning_MTA",
        ["Facebook;social_ppc;Sweden;2026-09-01;10;20;4;16"],
    )
    _write_csv(
        base / AMER_SPEND_TYPE / "Marketing_spend_W36.csv",
        "Channel;ChannelGroup;Country;Day;Marketing spend",
        ["Facebook;social_ppc;Sweden;2026-09-01;8"],
    )
    _write_csv(
        base / AMER_GM2_TYPE / "Net_GM2_W36.csv",
        "Channel;ChannelGroup;Country;Day;Net gross profit 2;Net sales;Net gross margin 2;Marketing spend",
        ["Facebook;social_ppc;Sweden;2026-09-01;3;10;0.3;8"],
    )
    spend = load_spend_frame(base / AMER_SPEND_TYPE / "Marketing_spend_W36.csv")
    gm2 = load_gm2_frame(base / AMER_GM2_TYPE / "Net_GM2_W36.csv")
    assert float(spend["marketing_spend"].iloc[0]) == 8.0
    assert float(gm2["net_gross_profit_2"].iloc[0]) == 3.0
    assert float(gm2["net_sales"].iloc[0]) == 10.0
    payload = calculate_adjusted_amer(WEEK, tmp_path)
    assert payload["week"]["netSales"] == pytest.approx(10.0)
    assert payload["week"]["adjustedAMER"] == pytest.approx(20.0 / 8.0)
    assert payload["ratio_grain"] == "ChannelGroup"


def test_reconciliation_matches_dema_validated_totals(tmp_path: Path):
    base = _amer_week_dir(tmp_path)
    _write_csv(
        base / AMER_REVENUE_TYPE / "Revenue_by_channel_W36.csv",
        "Channel;ChannelGroup;Country;Day;Revenue_MTA;Revenue_CFA;Revenue_New_MTA;Revenue_Returning_MTA",
        ["Facebook;social_ppc;Sweden;2026-09-01;1;1;0;1"],
    )
    _write_csv(
        base / AMER_SPEND_TYPE / "Marketing_spend_W36.csv",
        "Channel;ChannelGroup;Country;Day;Marketing spend",
        ["Facebook;social_ppc;Sweden;2026-09-01;144583.25"],
    )
    _write_csv(
        base / AMER_GM2_TYPE / "Net_GM2_W36.csv",
        "Channel;ChannelGroup;Country;Day;Net gross profit 2;Net sales;Net gross margin 2;Marketing spend",
        ["Facebook;social_ppc;Sweden;2026-09-01;100;1211140.23;0.08;144583.25"],
    )
    _write_csv(
        base / AMER_REVENUE_TYPE / "Revenue_by_channel_August_2026.csv",
        "Channel;ChannelGroup;Country;Day;Revenue_MTA;Revenue_CFA;Revenue_New_MTA;Revenue_Returning_MTA",
        ["Facebook;social_ppc;Sweden;2026-08-15;1;1;0;1"],
    )
    _write_csv(
        base / AMER_SPEND_TYPE / "Marketing_spend_August_2026.csv",
        "Channel;ChannelGroup;Country;Day;Marketing spend",
        ["Facebook;social_ppc;Sweden;2026-08-15;780010.85"],
    )
    _write_csv(
        base / AMER_GM2_TYPE / "Net_GM2_August_2026.csv",
        "Channel;ChannelGroup;Country;Day;Net gross profit 2;Net sales;Net gross margin 2;Marketing spend",
        ["Facebook;social_ppc;Sweden;2026-08-15;400;6748620.98;0.06;780010.85"],
    )
    payload = calculate_adjusted_amer(WEEK, tmp_path)
    by = {(row["kind"], row["key"]): row for row in payload["reconciliation"]}
    assert by[("week", "2026-36")]["match"] is True
    assert by[("month", "2026-08")]["match"] is True
    assert by[("week", "2026-36")]["net_sales"] == pytest.approx(1_211_140.23)
    assert by[("week", "2026-36")]["marketing_spend"] == pytest.approx(144_583.25)
    assert by[("month", "2026-08")]["net_sales"] == pytest.approx(6_748_620.98)
    assert by[("month", "2026-08")]["marketing_spend"] == pytest.approx(780_010.85)
    assert not any(w["code"] == "reconciliation_mismatch" for w in payload["warnings"])
