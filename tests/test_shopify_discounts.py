"""ShopifyQL discount classification and CSV merge helpers (no live Shopify calls)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from weekly_report.src.shopify_discounts import (
    classify_discount_code,
    classify_rows,
    maybe_fetch_week,
    rows_from_shopifyql_table,
    save_week_csv,
    shopify_configured,
    shopifyql_query_for_week,
    week_days_covered,
    week_csv_name,
)


def test_shopifyql_query_uses_monday_sunday():
    query, start, end = shopifyql_query_for_week("2026-44")
    assert start == "2026-10-26"
    assert end == "2026-11-01"
    assert "GROUP BY day, discount_name" in query
    assert "SINCE 2026-10-26 UNTIL 2026-11-01" in query


@pytest.mark.parametrize(
    "code,group,subgroup,source",
    [
        ("AfterShip Returns exchange", "0 AfterShip exchanges", "AfterShip exchange orders", "rule"),
        ("#100261448_Exchange", "0 AfterShip exchanges", "Manual exchange codes", "rule"),
        ("Welcome-9P2HLKSM", "1 Klaviyo", "Welcome code", "rule"),
        ("FS-ABC123", "1 Klaviyo", "Abandoned checkout / free shipping (FS-)", "rule"),
        ("WC77TPWX2", "1 Klaviyo", "Inactive Winback", "rule"),
        ("CDLP10_SebastianDeiss", "2 Customer care", "Named / care codes", "rule"),
        ("Product Claim", "2 Customer care", "Manual discount on order (draft/edit)", "rule"),
        ("ZZZUNKNOWN99", "8 Other / unknown", "ZZZUNKNOWN99", "unknown"),
    ],
)
def test_classification_rules(code, group, subgroup, source):
    got_group, got_sub, got_source = classify_discount_code(code, mapping={})
    assert got_group == group
    assert got_sub == subgroup
    assert got_source == source


def test_mapping_wins_over_rules():
    mapping = {"Product Claim": ("5 Investors, team, PR & friends", "PR")}
    group, subgroup, source = classify_discount_code("Product Claim", mapping)
    assert source == "mapping"
    assert group.startswith("5")
    assert subgroup == "PR"


def test_unknown_codes_collected_from_rows():
    rows = [
        {"date": "2026-10-27", "code_or_title": "Welcome-AAA", "orders": 1, "gross_sales_usd": 10, "discount_amount_usd": 2},
        {"date": "2026-10-27", "code_or_title": "MysteryCode", "orders": 1, "gross_sales_usd": 8, "discount_amount_usd": 3},
        {"date": "2026-10-28", "code_or_title": "MysteryCode", "orders": 1, "gross_sales_usd": 4, "discount_amount_usd": 1},
    ]
    classified, unknown = classify_rows(rows, mapping={})
    assert unknown == ["MysteryCode"]
    by_code = {r["code_or_title"]: r for r in classified}
    assert by_code["Welcome-AAA"]["group"] == "1 Klaviyo"
    assert by_code["MysteryCode"]["group"] == "8 Other / unknown"


def test_shopifyql_table_amounts_are_positive():
    table = {
        "columns": [
            {"name": "day"},
            {"name": "discount_name"},
            {"name": "orders"},
            {"name": "gross_sales"},
            {"name": "discounts"},
        ],
        "rows": [
            ["2026-10-26", "Welcome-AAA", "1", "82.48", "-8.24"],
            ["2026-10-26", "FS-1", 2, {"amount": "-0.0"}, {"amount": "-1.5"}],
        ],
    }
    rows = rows_from_shopifyql_table(table)
    assert len(rows) == 2
    assert rows[0]["discount_amount_usd"] == pytest.approx(8.24)
    assert rows[1]["discount_amount_usd"] == pytest.approx(1.5)


def test_maybe_fetch_without_credentials_does_not_fake(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("SHOPIFY_SHOP", raising=False)
    monkeypatch.delenv("SHOPIFY_STORE", raising=False)
    monkeypatch.delenv("SHOPIFY_SHOP_DOMAIN", raising=False)
    monkeypatch.delenv("SHOPIFY_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("SHOPIFY_ADMIN_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("SHOPIFY_ADMIN_API_TOKEN", raising=False)
    assert shopify_configured() is False
    result = maybe_fetch_week("2026-44", tmp_path, daily_dates=[], force=True)
    assert result["ok"] is False
    assert result["reason"] == "not_configured"
    assert list(tmp_path.glob("**/*.csv")) == []


def test_already_covered_week_skips_fetch(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SHOPIFY_SHOP", "example.myshopify.com")
    monkeypatch.setenv("SHOPIFY_ACCESS_TOKEN", "shpat_test")
    days = pd.date_range("2026-10-26", "2026-11-01", freq="D").strftime("%Y-%m-%d").tolist()
    result = maybe_fetch_week("2026-44", tmp_path, daily_dates=days)
    assert result["reason"] == "already_covered"
    assert week_days_covered(days, "2026-10-26", "2026-11-01") is True
    assert week_days_covered(days[:-1], "2026-10-26", "2026-11-01") is False


def test_save_week_csv_shared_and_week_folder(tmp_path: Path):
    rows = [
        {
            "date": "2026-10-26",
            "group": "1 Klaviyo",
            "subgroup": "Welcome code",
            "code_or_title": "Welcome-AAA",
            "orders": 1,
            "gross_sales_usd": 10,
            "discount_amount_usd": 2,
        }
    ]
    path = save_week_csv(tmp_path, "2026-44", rows, "2026-10-26", "2026-11-01")
    name = week_csv_name("2026-10-26", "2026-11-01")
    assert path.name == name
    assert (tmp_path / "discount_types" / name).is_file()
    assert (tmp_path / "raw" / "2026-44" / "discount_types" / name).is_file()
    text = path.read_text(encoding="utf-8")
    assert text.splitlines()[0] == "date,group,subgroup,code_or_title,orders,gross_sales_usd,discount_amount_usd"
    assert "Welcome-AAA" in text
