"""Discount types: mapping, display order, Sep 2025/2026 USD totals."""

from __future__ import annotations

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


def test_fixture_share_and_free_shipping(tmp_path: Path):
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
        "aftership",
        "internal",
        "campaign",
        "test",
        "other",
    ]
    welcome = next(s for s in groups["klaviyo"]["subgroups"] if s["id"] == "welcome_code")
    free = next(s for s in groups["klaviyo"]["subgroups"] if s["id"] == "free_shipping")
    assert welcome["discount_amount"] == pytest.approx(10.0)
    assert welcome["orders"] == 2
    assert welcome["share_of_discounts_pct"] == pytest.approx(10.0 / 35.0 * 100.0)
    assert free["is_free_shipping"] is True
    assert free["discount_amount"] == pytest.approx(0.0)
    assert free["orders"] == 3
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
