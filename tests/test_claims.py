"""Cin7 claim orders: monthly counts, replacement cost, freight and discounts."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from weekly_report.src.metrics import claims as claims_mod
from weekly_report.src.metrics.claims import (
    _landed_costs,
    calculate_claims,
    carrier_price_eur,
    product_category,
)


def test_product_category_splits_swim_from_underwear():
    assert product_category("DRY NYLON POPLIN SWIM TRUNKS LONG - BLACK") == "Swim"
    assert product_category("LYOCELL BOXER TRUNKS - BLACK") == "Underwear"
    assert product_category("6 X COTTON SOCKS - WHITE") == "Socks"
    assert product_category("COTTON ZIP HOODIE - WARM CHARCOAL") == "Sweats"
    assert product_category("LYOCELL MIDWEIGHT T-SHIRT - WHITE") == "Tops"


def test_bundled_claims_are_monthly_and_have_no_freight_or_discount():
    payload = calculate_claims(Path("/tmp/does-not-exist-claims"))
    assert payload["available"] is True
    assert set(payload["files_used"]) == {
        "cin7_claims_orders_2026-09_to_2026-10.csv",
        "cin7_claims_orders_2026-10.csv",
    }
    totals = payload["totals"]
    assert totals["orders"] == 65
    assert totals["units"] == 227
    assert totals["freight_sek"] == pytest.approx(9423.22, abs=0.05)
    assert totals["discount_sek"] == 0
    wholesale_sek = 66116.59
    assert totals["product_cost_sek"] != pytest.approx(wholesale_sek, abs=0.05)
    assert totals["product_cost_sek"] == pytest.approx(20591.35, abs=0.02)
    assert totals["recorded_cost_sek"] == pytest.approx(totals["product_cost_sek"] + totals["freight_sek"], abs=0.02)
    assert sum(row["product_cost_sek"] for row in payload["orders"]) == pytest.approx(totals["product_cost_sek"], abs=0.02)
    assert sum(row["product_cost_sek"] for row in payload["categories"]) == pytest.approx(20591.37, abs=0.05)
    months = {row["key"]: row for row in payload["months"]}
    assert months["2026-09"]["orders"] == 35
    assert months["2026-09"]["units"] == 65
    assert months["2026-10"]["orders"] == 30
    assert months["2026-10"]["units"] == 162
    assert payload["reasons"][0]["label"] == "Not specified in the Cin7 export"
    assert payload["reasons"][0]["orders"] == 65
    assert any("not Shopify" in note for note in payload["notes"])
    assert any("landed cost in SEK" in note for note in payload["notes"])
    assert any("2026 carrier price" in note for note in payload["notes"])
    assert any("SwissPost" in note for note in payload["notes"])
    assert any("Fedex International Priority" in note for note in payload["notes"])
    landed_note = next(note for note in payload["notes"] if note.startswith("Landed cost matched"))
    assert "92 of 96" in landed_note
    assert "cin7_landed_cost_fw26.csv" in landed_note
    assert "MTO016031801-9000-L" not in landed_note
    assert "MTO016031801-9000-XXL" not in landed_note
    assert "MUW002031601-9000-M" in landed_note
    assert "MUW002031601-9000-L" in landed_note
    assert "Shopping bag M" in landed_note
    assert "105 units" in landed_note
    assert "MTO023030301-0246-M" in landed_note
    assert "MTO024031301-0224-XL" in landed_note
    by_ref = {row["order_ref"]: row for row in payload["orders"]}
    swisspost = next(row for row in payload["orders"] if "SwissPost" in row["freight_method"])
    assert swisspost["freight_sek"] == 0
    sweden = next(
        row for row in payload["orders"]
        if row["country"] == "Sweden" and "Service Point" in row["freight_method"] and row["created"].startswith("2026-09")
    )
    assert carrier_price_eur("Sweden", sweden["freight_method"])[0] == pytest.approx(10.068)
    assert sweden["freight_sek"] == pytest.approx(10.068 * 11.274, abs=0.01)
    uk = by_ref["CCLA78-431"]
    assert uk["created"].startswith("2026-10")
    assert uk["freight_sek"] == pytest.approx(9.9225 * 11.1765, abs=0.01)
    assert uk["freight_rate"].startswith("UK")
    assert uk["product_cost_sek"] == pytest.approx(167.05, abs=0.01)
    assert uk["product_cost_sek"] != pytest.approx(1458.17, abs=0.1)
    blob = str(payload).lower()
    assert "gmail" not in blob
    assert "@" not in blob


def test_later_file_replaces_one_order_and_can_name_the_claim(tmp_path: Path):
    folder = tmp_path / "claims"
    folder.mkdir()
    (folder / "week.csv").write_text(
        "Order Id,Order Ref,Created Date,Delivery Country,Currency Name,Carrier,Freight Description,"
        "Freight Cost (Local Currency),Discount Total (Local Currency),Item Total Discount (Local Currency),"
        "Item Name,Item Code,Item Qty,Item Price (Local Currency),Claim Type\n"
        "129037,CCLA78-432,4 Oct 2026 8:40 pm,United States,USD,FedEx,Fedex,250,0,40,"
        "LYOCELL BOXER BRIEF - BLACK,NOT-IN-FILE,1,1000,Damaged\n"
        "999001,CCLA78-500,2 Nov 2026 9:00 am,Sweden,SEK,DHL Paket,DHL home,80,15,0,"
        "COTTON SOCKS - WHITE,ALSO-MISSING,2,100,Lost in transit\n",
        encoding="utf-8",
    )
    payload = calculate_claims(tmp_path)
    refs = {row["order_ref"]: row for row in payload["orders"]}
    assert refs["CCLA78-432"]["reason"] == "Damaged"
    assert refs["CCLA78-432"]["freight_sek"] == pytest.approx(250)
    assert refs["CCLA78-432"]["discount_sek"] == pytest.approx(40)
    assert refs["CCLA78-432"]["product_cost_sek"] == pytest.approx(0)
    assert refs["CCLA78-432"]["product_cost_sek"] != pytest.approx(1000)
    assert refs["CCLA78-500"]["product_cost_sek"] == pytest.approx(0)
    joined = " ".join(payload["notes"])
    assert "NOT-IN-FILE" in joined
    assert "ALSO-MISSING" in joined
    assert "CCLA78-500" in refs
    assert payload["totals"]["orders"] == 66
    months = {row["key"]: row for row in payload["months"]}
    assert months["2026-09"]["orders"] == 35
    assert months["2026-10"]["orders"] == 30
    assert months["2026-11"]["orders"] == 1


def test_fw26_fills_unmatched_skus_and_catalog_zeros():
    payload = calculate_claims(Path("/tmp/does-not-exist-claims"))
    costs, used = _landed_costs(Path("/tmp/does-not-exist-claims"))
    assert "cin7_landed_cost_sek.csv" in used
    assert "cin7_landed_cost_fw26.csv" in used
    assert costs["MTO016031501-9999-M"] == pytest.approx(370.9)
    assert costs["MTO016031801-9000-L"] == pytest.approx(225.6923)
    assert costs["MTO016031801-9000-XXL"] == pytest.approx(225.6923)
    assert costs["MUW002031603-9000-L"] == pytest.approx(210.59)
    assert costs["MBO000030401-0224-L"] == pytest.approx(370.2)
    assert costs["MUW002004801-0224-L"] == pytest.approx(69.6)
    assert "MUW002031601-9000-M" not in costs
    assert "MUW002031601-9000-L" not in costs
    assert "Shopping bag M" not in costs
    assert costs["MTO023030301-0246-M"] == 0
    assert costs["MUW001072103-9999-L"] == pytest.approx(167.05)
    by_ref = {row["order_ref"]: row for row in payload["orders"]}
    assert by_ref["CCLA78-458"]["product_cost_sek"] == pytest.approx(2253.69, abs=0.02)
    assert "Shopping bag M × 100" in by_ref["CCLA78-458"]["items"]


def test_later_zero_landed_cost_does_not_wipe_catalog(tmp_path: Path):
    folder = tmp_path / "claims"
    folder.mkdir()
    (folder / "landed_zeros.csv").write_text(
        "Description,Style Code,Code,RRP,LandedCOST SEK Excl\n"
        "Trunks,MUW001072103-9999,MUW001072103-9999-L,999,0\n"
        "Joggers,MBO000030401-0224,MBO000030401-0224-L,999,0\n"
        "Unknown,NOT-A-REAL-SKU,NOT-A-REAL-SKU,999,0\n",
        encoding="utf-8",
    )
    payload = calculate_claims(tmp_path)
    costs, used = _landed_costs(tmp_path)
    assert "landed_zeros.csv" in used
    assert costs["MUW001072103-9999-L"] == pytest.approx(167.05)
    assert costs["MBO000030401-0224-L"] == pytest.approx(370.2)
    by_ref = {row["order_ref"]: row for row in payload["orders"]}
    assert by_ref["CCLA78-431"]["product_cost_sek"] == pytest.approx(167.05, abs=0.01)


def test_later_landed_cost_file_overrides_the_bundle(tmp_path: Path):
    folder = tmp_path / "claims"
    folder.mkdir()
    (folder / "landed.csv").write_text(
        "Description,Style Code,Code,RRP,LandedCOST SEK Excl\n"
        "Boxer,MUW003072103-9999,MUW003072103-9999-XL,999,42.5\n",
        encoding="utf-8",
    )
    payload = calculate_claims(tmp_path)
    by_ref = {row["order_ref"]: row for row in payload["orders"]}
    assert by_ref["CCLA78-432"]["product_cost_sek"] == pytest.approx(42.5)
    assert by_ref["CCLA78-432"]["product_cost_sek"] != pytest.approx(1756.73, abs=0.1)
    assert by_ref["CCLA78-431"]["product_cost_sek"] == pytest.approx(167.05, abs=0.01)
    note = next(line for line in payload["notes"] if line.startswith("Landed cost matched"))
    assert "cin7_landed_cost_sek.csv" in note
    assert "landed.csv" in note
    assert "gmail" not in str(payload).lower()


def test_claims_module_never_loads_qlik():
    source = inspect.getsource(claims_mod)
    assert "from weekly_report.src.adapters" not in source
    assert "import qlik" not in source
    assert "load_all_raw_data" not in source
    assert "read_excel" not in source
    assert "openpyxl" not in source
    assert "calamine" not in source
    assert "Never walk qlik" in inspect.getsource(claims_mod._claim_folders)


def test_claims_endpoint_never_loads_qlik():
    from weekly_report.api import routes

    source = inspect.getsource(routes.get_claims)
    assert "calculate_claims" in source
    assert "qlik" in source.lower()
    assert "Must not read Qlik" in source
    assert "load_all_raw_data" not in source
    assert "load_qlik" not in source
    assert "https://weekly-sales-report-two.vercel.app" in routes.cors_origins


def test_claims_endpoint_returns_bundled_october_without_reading_qlik(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("DISABLE_SUPABASE", "true")
    fake_qlik = tmp_path / "raw" / "2026-44" / "qlik" / "Qlik_W44.xlsx"
    fake_qlik.parent.mkdir(parents=True)
    fake_qlik.write_bytes(b"not-an-excel-workbook" * 1000)
    from weekly_report.api import routes

    payload = routes.get_claims()
    assert payload["available"] is True
    assert payload["totals"]["orders"] == 65
    assert payload["totals"]["units"] == 227
    assert "cin7_claims_orders_2026-10.csv" in payload["files_used"]
    assert fake_qlik.exists()


def test_boot_prune_does_not_read_qlik(monkeypatch, tmp_path: Path):
    from weekly_report.api import routes

    called = {}

    monkeypatch.setattr(routes, "load_config", lambda: type("C", (), {"data_root": tmp_path})())

    def fake_space(root, extra_keep=()):
        called["root"] = root
        return {"pruned": True, "bytes_freed": 12, "kept_weeks": ["2026-44"]}

    monkeypatch.setattr(routes, "ensure_upload_space", fake_space)
    routes.prune_disk_if_tight()
    assert called["root"] == tmp_path
    source = inspect.getsource(routes.prune_disk_if_tight)
    assert "ensure_upload_space" in source
    assert "load_qlik" not in source
    assert "read_excel" not in source
