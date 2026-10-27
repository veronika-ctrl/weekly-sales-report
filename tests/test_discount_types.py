"""Discount types: mapping, display order, Sep 2025/2026 USD totals."""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import pytest

from weekly_report.src.metrics.discount_types import (
    NOTE,
    apply_code_mapping,
    calculate_discount_types,
    load_discount_type_tables,
)


@pytest.fixture(autouse=True)
def _disable_fx(monkeypatch):
    monkeypatch.setenv("DISABLE_FX_CONVERSION", "1")


def test_weekly_upload_keeps_history_and_replaces_that_day_only(tmp_path: Path):
    """A week file is added. Days it contains replace the history. Other days stay."""
    name = "discount_groups_daily_2026-10-19_to_2026-10-25.csv"
    slot = tmp_path / "discount_types"
    slot.mkdir(parents=True)
    path = slot / name
    path.write_text(
        "date,group,subgroup,code_or_title,orders,gross_sales_usd,discount_amount_usd\n"
        "2026-10-18,1 Klaviyo,Welcome code,NEW,1,10,99\n"
        "2026-10-20,1 Klaviyo,Welcome code,W43,1,10,4\n"
        "2026-10-20,2 Customer care,Named / care codes,CARE,1,8,2\n",
        encoding="utf-8",
    )
    old = path.stat().st_mtime - 10_000_000
    os.utime(path, (old, old))
    tables = load_discount_type_tables(tmp_path)
    assert name in tables["files_used"]
    assert any(item.startswith("discount_groups_daily_2024-10-01_to_2026-10-18") for item in tables["files_used"])
    daily = tables["daily"].copy()
    daily["_day"] = pd.to_datetime(daily["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    assert (daily["_day"] == "2024-10-01").any()
    day18 = daily.loc[daily["_day"] == "2026-10-18"]
    assert set(day18["code_or_title"].astype(str)) == {"NEW"}
    assert float(day18["discount_amount_usd"].iloc[0]) == pytest.approx(99.0)
    day20 = daily.loc[daily["_day"] == "2026-10-20"]
    assert set(day20["code_or_title"].astype(str)) == {"W43", "CARE"}


def test_mapping_wins_over_daily_group():
    daily = pd.DataFrame(
        {
            "code_or_title": ["WELCOME-X", "Custom discount"],
            "group": ["7 Other / unknown", "7 Other / unknown"],
            "subgroup": ["??", "??"],
            "orders": [1, 1],
            "discount_amount_usd": [10.0, 20.0],
        }
    )
    mapping = pd.DataFrame(
        {
            "code_or_title": ["Custom discount"],
            "group": ["2 Customer care"],
            "subgroup": ["Manual discount on order (draft/edit)"],
        }
    )
    out = apply_code_mapping(daily, mapping)
    assert out.loc[out["code_or_title"] == "Custom discount", "group"].iloc[0] == "2 Customer care"
    assert out.loc[out["code_or_title"] == "WELCOME-X", "group"].iloc[0] == "7 Other / unknown"


def test_fixture_share_and_free_shipping(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "weekly_report.src.metrics.discount_types._bundled_dir",
        lambda: tmp_path / "missing-bundle",
    )
    folder = tmp_path / "discount_types"
    folder.mkdir()
    (folder / "discount_groups_daily_fix.csv").write_text(
        "date,group,subgroup,code_or_title,orders,gross_sales_usd,discount_amount_usd\n"
        "2026-09-01,1 Klaviyo,Welcome code,Welcome-A,2,100,10\n"
        "2026-09-01,1 Klaviyo,Abandoned checkout / free shipping (FS-),FS-1,3,0,5\n"
        "2026-09-01,0 AfterShip exchanges,AfterShip exchange orders,AfterShip Returns exchange,1,50,20\n",
        encoding="utf-8",
    )
    (folder / "shopify_daily_totals_fix.csv").write_text(
        "date,gross_sales_usd,discount_amount_usd,orders\n"
        "2026-09-01,1000,35,10\n",
        encoding="utf-8",
    )
    (folder / "discount_code_mapping.csv").write_text(
        "code_or_title,group,subgroup,orders,discount_amount_usd\n",
        encoding="utf-8",
    )
    payload = calculate_discount_types("2026-36", tmp_path, granularity="month", months=1)
    assert payload["note"] == NOTE
    sep = next(p for p in payload["periods"] if p["key"] == "2026-09")
    assert sep["discount_amount"] == pytest.approx(35.0)
    assert sep["gross_sales"] == pytest.approx(1000.0)
    assert sep["discount_of_gross_pct"] == pytest.approx(3.5)
    groups = {g["id"]: g for g in sep["groups"]}
    assert [g["id"] for g in sep["groups"]] == [
        "klaviyo",
        "customer_care",
        "conjured",
        "campaign",
        "investors",
        "subscription",
        "test",
        "other",
        "aftership",
    ]
    welcome = next(s for s in groups["klaviyo"]["subgroups"] if s["id"] == "welcome_code")
    klaviyo_ids = [s["id"] for s in groups["klaviyo"]["subgroups"]]
    klaviyo_labels = [s["label"] for s in groups["klaviyo"]["subgroups"]]
    assert "free_shipping" not in klaviyo_ids
    assert not any("abandoned checkout" in label.lower() for label in klaviyo_labels)
    assert welcome["discount_amount"] == pytest.approx(10.0)
    assert welcome["orders"] == 2
    assert welcome["share_of_discounts_pct"] == pytest.approx(10.0 / 35.0 * 100.0)
    assert groups["klaviyo"]["discount_amount"] == pytest.approx(15.0)
    assert groups["aftership"]["discount_amount"] == pytest.approx(20.0)


def _sep(payload: dict, key: str) -> dict:
    return next(p for p in payload["periods"] if p["key"] == key)


def test_real_csv_sep_2026_and_2025_usd_totals():
    """Must match 0.1 pt / nearest dollar when bundled discount-type CSVs are present."""
    tables = load_discount_type_tables(Path("/tmp/does-not-exist"))
    if not tables["files_used"]:
        pytest.skip("bundled discount_types CSVs not available")
    payload = calculate_discount_types("2026-40", Path("/tmp/does-not-exist"), granularity="month", months=14)
    sep26 = _sep(payload, "2026-09")
    assert sep26["discount_amount"] == pytest.approx(13067, abs=1)
    assert sep26["gross_sales"] == pytest.approx(572351, abs=1)
    assert sep26["discount_of_gross_pct"] == pytest.approx(2.28, abs=0.1)
    groups = {g["id"]: g for g in sep26["groups"]}
    welcome = next(s for s in groups["klaviyo"]["subgroups"] if s["id"] == "welcome_code")
    assert welcome["discount_amount"] == pytest.approx(6364, abs=1)
    assert welcome["orders"] == 254
    assert groups["aftership"]["discount_amount"] == pytest.approx(3109, abs=1)

    sep25 = _sep(payload, "2025-09")
    assert sep25["discount_amount"] == pytest.approx(20936, abs=1)
    assert sep25["gross_sales"] == pytest.approx(469961, abs=1)
    assert sep25["discount_of_gross_pct"] == pytest.approx(4.45, abs=0.1)


def test_weekly_has_last_year_slot():
    payload = calculate_discount_types("2026-40", Path("/tmp/does-not-exist"), granularity="week", num_weeks=8)
    if not payload.get("periods"):
        pytest.skip("bundled discount_types CSVs not available")
    assert len(payload["periods"]) == 8
    assert payload["periods"][0]["week"].endswith("-33") or payload["periods"][0]["week"] < "2026-40"
    assert "last_year" in payload["periods"][-1]
    assert payload["note"].startswith("Codes and manual discounts only")


NEW_GROUP_ORDER = [
    "klaviyo",
    "customer_care",
    "conjured",
    "campaign",
    "investors",
    "subscription",
    "test",
    "other",
    "aftership",
]

INVESTOR_SUBGROUP_LABELS = [
    "Investors, owner & founder",
    "Team",
    "PR",
    "Marketing (creative team)",
    "Friends & family",
    "Other named codes (to confirm)",
]


def test_new_groups_emit_indented_subgroups(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        "weekly_report.src.metrics.discount_types._bundled_dir",
        lambda: tmp_path / "missing-bundle",
    )
    folder = tmp_path / "discount_types"
    folder.mkdir()
    (folder / "discount_groups_daily_fix.csv").write_text(
        "date,group,subgroup,code_or_title,orders,gross_sales_usd,discount_amount_usd\n"
        "2026-09-01,1 Klaviyo,Welcome code,Welcome-A,1,100,10\n"
        "2026-09-01,1 Klaviyo,Memories,MEM-1,1,50,5\n"
        '2026-09-01,"5 Investors, team, PR & friends",Team,TEAMKALLING,1,80,8\n'
        '2026-09-01,"5 Investors, team, PR & friends",PR,SOFIAFRIENDS,1,40,4\n'
        "2026-09-01,4 Campaign codes,BLACK_FEAST,BLACK_FEAST,1,30,3\n"
        "2026-09-01,7 Subscription codes,Subscription codes,AUTOMATIQUE,1,20,2\n"
        "2026-09-01,8 Other / unknown,27CXD94R,27CXD94R,1,10,1\n",
        encoding="utf-8",
    )
    (folder / "shopify_daily_totals_fix.csv").write_text(
        "date,gross_sales_usd,discount_amount_usd,orders\n"
        "2026-09-01,1000,33,10\n",
        encoding="utf-8",
    )
    (folder / "discount_code_mapping.csv").write_text(
        "code_or_title,group,subgroup,orders,discount_amount_usd\n",
        encoding="utf-8",
    )
    payload = calculate_discount_types("2026-36", tmp_path, granularity="month", months=1)
    sep = next(p for p in payload["periods"] if p["key"] == "2026-09")
    assert [g["id"] for g in sep["groups"]] == NEW_GROUP_ORDER
    groups = {g["id"]: g for g in sep["groups"]}

    klaviyo_labels = [s["label"] for s in groups["klaviyo"]["subgroups"]]
    assert klaviyo_labels[:3] == [
        "Welcome code",
        "Memories",
        "Inactive Winback",
    ]
    assert "Abandoned checkout / free shipping" not in klaviyo_labels
    assert groups["investors"]["discount_amount"] == pytest.approx(12.0)
    assert [s["label"] for s in groups["investors"]["subgroups"]] == INVESTOR_SUBGROUP_LABELS
    team = next(s for s in groups["investors"]["subgroups"] if s["id"] == "team")
    pr = next(s for s in groups["investors"]["subgroups"] if s["id"] == "pr")
    assert team["discount_amount"] == pytest.approx(8.0)
    assert pr["discount_amount"] == pytest.approx(4.0)
    assert any(s["label"] == "BLACK_FEAST" for s in groups["campaign"]["subgroups"])
    assert any(s["label"] == "Subscription codes" for s in groups["subscription"]["subgroups"])
    assert any(s["label"] == "27CXD94R" for s in groups["other"]["subgroups"])
    assert groups["aftership"]["subgroups"]  # curated rows still present at 0


def test_real_csv_investor_subgroups_present():
    tables = load_discount_type_tables(Path("/tmp/does-not-exist"))
    if not tables["files_used"]:
        pytest.skip("bundled discount_types CSVs not available")
    payload = calculate_discount_types("2026-40", Path("/tmp/does-not-exist"), granularity="month", months=14)
    sep26 = _sep(payload, "2026-09")
    assert [g["id"] for g in sep26["groups"]] == NEW_GROUP_ORDER
    groups = {g["id"]: g for g in sep26["groups"]}
    assert groups["investors"]["label"] == "Investors, team, PR & friends"
    assert [s["label"] for s in groups["investors"]["subgroups"][:6]] == INVESTOR_SUBGROUP_LABELS
    assert groups["investors"]["discount_amount"] == pytest.approx(2838, abs=1)
    k_labels = [s["label"] for s in groups["klaviyo"]["subgroups"]]
    assert "Welcome code" in k_labels
    assert "Abandoned checkout / free shipping" not in k_labels
    assert "free_shipping" not in [s["id"] for s in groups["klaviyo"]["subgroups"]]
