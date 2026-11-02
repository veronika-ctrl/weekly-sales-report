"""Cin7 claim orders: monthly counts, replacement cost, freight and discounts."""

from __future__ import annotations

from pathlib import Path

import pytest

from weekly_report.src.metrics.claims import calculate_claims, carrier_price_eur, product_category


def test_product_category_splits_swim_from_underwear():
    assert product_category("DRY NYLON POPLIN SWIM TRUNKS LONG - BLACK") == "Swim"
    assert product_category("LYOCELL BOXER TRUNKS - BLACK") == "Underwear"
    assert product_category("6 X COTTON SOCKS - WHITE") == "Socks"
    assert product_category("COTTON ZIP HOODIE - WARM CHARCOAL") == "Sweats"
    assert product_category("LYOCELL MIDWEIGHT T-SHIRT - WHITE") == "Tops"


def test_bundled_claims_are_monthly_and_have_no_freight_or_discount():
    payload = calculate_claims(Path("/tmp/does-not-exist-claims"))
    assert payload["available"] is True
    assert payload["files_used"] == ["cin7_claims_orders_2026-09_to_2026-10.csv"]
    totals = payload["totals"]
    assert totals["orders"] == 37
    assert totals["units"] == 67
    assert totals["freight_sek"] == pytest.approx(5420.24, abs=0.05)
    assert totals["discount_sek"] == 0
    assert totals["product_cost_sek"] == pytest.approx(66116.57, abs=0.05)
    assert totals["recorded_cost_sek"] == pytest.approx(totals["product_cost_sek"] + totals["freight_sek"], abs=0.02)
    months = {row["key"]: row for row in payload["months"]}
    assert months["2026-09"]["orders"] == 35
    assert months["2026-10"]["orders"] == 2
    assert payload["reasons"][0]["label"] == "Not specified in the Cin7 export"
    assert payload["reasons"][0]["orders"] == 37
    assert any("not Shopify" in note for note in payload["notes"])
    assert any("2026 carrier price" in note for note in payload["notes"])
    assert any("SwissPost" in note for note in payload["notes"])
    by_ref = {row["order_ref"]: row for row in payload["orders"]}
    swisspost = next(row for row in payload["orders"] if "SwissPost" in row["freight_method"])
    assert swisspost["freight_sek"] == 0
    sweden = next(
        row for row in payload["orders"]
        if row["country"] == "Sweden" and "Service Point" in row["freight_method"] and row["created"].startswith("2026-09")
    )
    assert carrier_price_eur("Sweden", sweden["freight_method"])[0] == pytest.approx(10.068)
    assert sweden["freight_sek"] == pytest.approx(10.068 * 11.274, abs=0.01)
    uk = next(row for row in payload["orders"] if row["country"] == "United Kingdom" and row["created"].startswith("2026-10"))
    assert uk["freight_sek"] == pytest.approx(9.9225 * 11.1765, abs=0.01)
    assert by_ref[uk["order_ref"]]["freight_rate"].startswith("UK")
    assert "gmail" not in str(payload["orders"])


def test_later_file_replaces_one_order_and_can_name_the_claim(tmp_path: Path):
    folder = tmp_path / "claims"
    folder.mkdir()
    (folder / "week.csv").write_text(
        "Order Id,Order Ref,Created Date,Delivery Country,Currency Name,Carrier,Freight Description,"
        "Freight Cost (Local Currency),Discount Total (Local Currency),Item Total Discount (Local Currency),"
        "Item Name,Item Qty,Item Price (Local Currency),Claim Type\n"
        "129037,CCLA78-432,4 Oct 2026 8:40 pm,United States,USD,FedEx,Fedex,250,0,40,"
        "LYOCELL BOXER BRIEF - BLACK,1,1000,Damaged\n"
        "999001,CCLA78-500,2 Nov 2026 9:00 am,Sweden,SEK,DHL Paket,DHL home,80,15,0,"
        "COTTON SOCKS - WHITE,2,100,Lost in transit\n",
        encoding="utf-8",
    )
    payload = calculate_claims(tmp_path)
    refs = {row["order_ref"]: row for row in payload["orders"]}
    assert refs["CCLA78-432"]["reason"] == "Damaged"
    assert refs["CCLA78-432"]["freight_sek"] == pytest.approx(250)
    assert refs["CCLA78-432"]["discount_sek"] == pytest.approx(40)
    assert refs["CCLA78-432"]["product_cost_sek"] == pytest.approx(1000)
    assert "CCLA78-500" in refs
    assert payload["totals"]["orders"] == 38
    months = {row["key"]: row for row in payload["months"]}
    assert months["2026-09"]["orders"] == 35
    assert months["2026-10"]["orders"] == 2
    assert months["2026-11"]["orders"] == 1
