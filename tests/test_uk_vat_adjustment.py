"""UK VAT correction: order match, day-level share, and the slides that read Qlik."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from weekly_report.src.metrics.audience_metrics_per_country import (
    calculate_audience_metrics_per_country_for_weeks,
)
from weekly_report.src.metrics.markets import calculate_top_markets_for_weeks
from weekly_report.src.periods.calculator import get_week_date_range
from weekly_report.src.transform.uk_vat_adjustment import (
    VAT_FACTOR,
    adjust_dema,
    adjust_dema_gm2,
    adjust_qlik,
    adjust_shopify,
    clear_runtime_state,
    rows_from_orders_export,
)


@pytest.fixture(autouse=True)
def _isolated_vat(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_ROOT", str(tmp_path / "settings"))
    monkeypatch.setenv("ADJUST_UK_VAT", "true")
    monkeypatch.delenv("UK_VAT_AFFECTED_ORDERS_CSV", raising=False)
    clear_runtime_state()
    yield
    clear_runtime_state()


def _orders_csv(path: Path, names: list[str]) -> None:
    rows = []
    for name in names:
        rows.append(
            {
                "order_name": name,
                "order_created_at": "2026-09-29 12:00:00+0200",
                "shipping_country": "United Kingdom",
                "gross_sales": 396.92,
                "taxes": 0,
                "vat_factor": 1.2,
            }
        )
    pd.DataFrame(rows).to_csv(path, index=False)


def _use_orders(monkeypatch, path: Path, names: list[str]) -> None:
    _orders_csv(path, names)
    monkeypatch.setenv("UK_VAT_AFFECTED_ORDERS_CSV", str(path))
    monkeypatch.setenv("ADJUST_UK_VAT", "true")
    clear_runtime_state()


def _qlik_row(**kwargs) -> dict:
    base = {
        "Date": "2026-09-29",
        "Sales Channel": "Online",
        "Country": "United Kingdom",
        "Gross Revenue": 0.0,
        "Net Revenue": 0.0,
        "Discounts": 0.0,
        "Returns": 0.0,
        "Shipping": 0.0,
        "Total sales": 0.0,
        "Sales Qty": 1,
        "COGS": 10.0,
        "Order No": "",
        "Customer E-mail": "a@example.com",
        "New/Returning Customer": "New",
        "Taxes": 0.0,
    }
    base.update(kwargs)
    return base


def test_matched_order_is_divided_and_counts_stay(tmp_path, monkeypatch):
    _use_orders(monkeypatch, tmp_path / "orders.csv", ["#100288154"])
    frame = pd.DataFrame(
        [
            _qlik_row(
                **{
                    "Order No": "#100288154",
                    "Gross Revenue": 396.92,
                    "Net Revenue": 330.0,
                    "Discounts": 20.0,
                    "Returns": 6.0,
                    "Shipping": 12.0,
                    "Total sales": 396.92,
                    "Sales Qty": 3,
                    "COGS": 40.0,
                }
            )
        ]
    )
    adjusted = adjust_qlik(frame)
    row = adjusted.iloc[0]
    assert row["Gross Revenue"] == pytest.approx(396.92 / VAT_FACTOR)
    assert row["Net Revenue"] == pytest.approx(330.0 / VAT_FACTOR)
    assert row["Discounts"] == pytest.approx(20.0 / VAT_FACTOR)
    assert row["Returns"] == pytest.approx(6.0 / VAT_FACTOR)
    assert row["Shipping"] == pytest.approx(12.0 / VAT_FACTOR)
    assert row["Total sales"] == pytest.approx(396.92 / VAT_FACTOR)
    assert row["Sales Qty"] == 3
    assert row["COGS"] == 40.0
    assert bool(row["vat_adjusted"]) is True
    assert adjusted["Order No"].nunique() == frame["Order No"].nunique()
    again = adjust_qlik(adjusted)
    assert again.iloc[0]["Gross Revenue"] == pytest.approx(row["Gross Revenue"])


def test_taxed_uk_order_in_the_window_is_unchanged(tmp_path, monkeypatch):
    _use_orders(monkeypatch, tmp_path / "orders.csv", ["#100288145", "#100288154"])
    frame = pd.DataFrame(
        [
            _qlik_row(
                **{
                    "Order No": "100288145",
                    "Gross Revenue": 126.74,
                    "Net Revenue": 101.39,
                    "Taxes": 25.35,
                }
            )
        ]
    )
    adjusted = adjust_qlik(frame)
    assert adjusted.iloc[0]["Gross Revenue"] == pytest.approx(126.74)
    assert adjusted.iloc[0]["Net Revenue"] == pytest.approx(101.39)
    assert "vat_adjusted" not in adjusted.columns


def test_non_uk_order_is_unchanged(tmp_path, monkeypatch):
    _use_orders(monkeypatch, tmp_path / "orders.csv", ["#100288154"])
    frame = pd.DataFrame(
        [
            _qlik_row(
                **{
                    "Country": "United States",
                    "Order No": "#9001",
                    "Gross Revenue": 500.0,
                    "Net Revenue": 480.0,
                }
            )
        ]
    )
    adjusted = adjust_qlik(frame)
    assert adjusted.iloc[0]["Gross Revenue"] == pytest.approx(500.0)
    assert float(adjusted["Gross Revenue"].sum()) == pytest.approx(500.0)


def test_later_return_on_affected_order_is_divided(tmp_path, monkeypatch):
    _use_orders(monkeypatch, tmp_path / "orders.csv", ["100288154"])
    frame = pd.DataFrame(
        [
            _qlik_row(**{"Order No": "100288154", "Date": "2026-09-29", "Gross Revenue": 396.92, "Net Revenue": 396.92}),
            _qlik_row(
                **{
                    "Order No": "#100288154",
                    "Date": "2026-12-01",
                    "Gross Revenue": -39.69,
                    "Net Revenue": -39.69,
                    "Returns": 39.69,
                }
            ),
        ]
    )
    adjusted = adjust_qlik(frame)
    assert adjusted.iloc[1]["Gross Revenue"] == pytest.approx(-39.69 / VAT_FACTOR)
    assert adjusted.iloc[1]["Returns"] == pytest.approx(39.69 / VAT_FACTOR)
    assert bool(adjusted.iloc[1]["vat_adjusted"]) is True


def test_day_level_share_scales_revenue_and_recomputes_margin(tmp_path, monkeypatch):
    _use_orders(monkeypatch, tmp_path / "orders.csv", ["#100288154"])
    shopify = pd.DataFrame(
        [
            {
                "order_name": "#100288154",
                "Created at": "2026-09-29 09:00:00",
                "Shipping country": "United Kingdom",
                "Gross sales": 120.0,
                "Net sales": 120.0,
                "Taxes": 0.0,
                "Orders": 1,
            },
            {
                "order_name": "#100288200",
                "Created at": "2026-09-29 09:30:00",
                "Shipping country": "United Kingdom",
                "Gross sales": 60.0,
                "Net sales": 60.0,
                "Taxes": 0.0,
                "Orders": 1,
            },
            {
                "order_name": "#55",
                "Created at": "2026-09-29 09:30:00",
                "Shipping country": "Sweden",
                "Gross sales": 90.0,
                "Net sales": 90.0,
                "Taxes": 10.0,
                "Orders": 1,
            },
        ]
    )
    adjust_shopify(shopify)
    dema = pd.DataFrame(
        [
            {"Days": "2026-09-29", "Country": "United Kingdom", "Net sales": 180.0, "Marketing spend": 50.0},
            {"Days": "2026-09-29", "Country": "Sweden", "Net sales": 90.0, "Marketing spend": 10.0},
        ]
    )
    adjusted = adjust_dema(dema)
    # Overstatement 120/6 = 20. UK revenue that day 180. Share 20/180.
    assert adjusted.loc[0, "Net sales"] == pytest.approx(180.0 * (1 - 20.0 / 180.0))
    assert adjusted.loc[0, "Marketing spend"] == pytest.approx(50.0)
    assert adjusted.loc[1, "Net sales"] == pytest.approx(90.0)
    assert adjusted.loc[1, "Marketing spend"] == pytest.approx(10.0)
    gm2 = pd.DataFrame(
        [
            {
                "Days": "2026-09-29",
                "Country": "United Kingdom",
                "Net sales": 180.0,
                "Net gross profit 2": 60.0,
                "Marketing spend": 15.0,
            }
        ]
    )
    gm2_adjusted = adjust_dema_gm2(gm2)
    assert gm2_adjusted.loc[0, "Net sales"] == pytest.approx(160.0)
    # Cost was 180 - 60 = 120, and stays 120. Profit becomes 160 - 120.
    assert gm2_adjusted.loc[0, "Net gross profit 2"] == pytest.approx(40.0)
    assert gm2_adjusted.loc[0, "Marketing spend"] == pytest.approx(15.0)
    assert adjust_dema_gm2(gm2_adjusted).loc[0, "Net gross profit 2"] == pytest.approx(40.0)


def test_switch_off_leaves_the_frame_alone(tmp_path, monkeypatch):
    _use_orders(monkeypatch, tmp_path / "orders.csv", ["#100288154"])
    monkeypatch.setenv("ADJUST_UK_VAT", "false")
    clear_runtime_state()
    frame = pd.DataFrame([_qlik_row(**{"Order No": "#100288154", "Gross Revenue": 396.92, "Net Revenue": 396.92})])
    assert adjust_qlik(frame).iloc[0]["Gross Revenue"] == pytest.approx(396.92)


def test_orders_export_keeps_first_line_and_the_three_rules():
    export = pd.DataFrame(
        [
            {"Name": "#100288154", "Created at": "2026-09-29 08:00:00", "Shipping Country": "United Kingdom", "Subtotal": 396.92, "Taxes": 0, "Lineitem quantity": 1},
            {"Name": "#100288154", "Created at": "", "Shipping Country": "", "Subtotal": "", "Taxes": "", "Lineitem quantity": 1},
            {"Name": "#100288145", "Created at": "2026-09-29 08:05:00", "Shipping Country": "GB", "Subtotal": 126.74, "Taxes": 25.35, "Lineitem quantity": 1},
            {"Name": "#200", "Created at": "2026-09-29 08:05:00", "Shipping Country": "United States", "Subtotal": 400, "Taxes": 0, "Lineitem quantity": 1},
            {"Name": "#201", "Created at": "2026-09-28 23:00:00", "Shipping Country": "United Kingdom", "Subtotal": 400, "Taxes": 0, "Lineitem quantity": 1},
            {"Name": "#202", "Created at": "2026-11-09 10:22:00", "Shipping Country": "United Kingdom", "Subtotal": 200, "Taxes": 0, "Lineitem quantity": 1},
            {"Name": "#203", "Created at": "2026-11-09 10:23:00", "Shipping Country": "United Kingdom", "Subtotal": 200, "Taxes": 0, "Lineitem quantity": 1},
            {"Name": "#204", "Created at": "2026-10-01 10:00:00", "Shipping Country": "United Kingdom", "Subtotal": 0, "Taxes": 0, "Lineitem quantity": 1},
        ]
    )
    rows = rows_from_orders_export(export)
    names = [row["order_name"] for row in rows]
    assert names == ["#100288154", "#202"]
    assert all(row["vat_factor"] == 1.2 for row in rows)
    assert rows[0]["gross_sales"] == pytest.approx(396.92)


def _write_qlik(root: Path, week: str, rows: list[dict]) -> None:
    folder = root / "raw" / week / "qlik"
    folder.mkdir(parents=True)
    pd.DataFrame(rows).to_csv(folder / "qlik.csv", index=False)
    dema = root / "raw" / week / "dema_spend"
    dema.mkdir(parents=True)
    pd.DataFrame(
        {"Days": ["2026-09-29"], "Country": ["United Kingdom"], "Marketing spend": [40.0]}
    ).to_csv(dema / "spend.csv", index=False)


def _slide_rows() -> list[dict]:
    return [
        _qlik_row(**{"Order No": "#100288154", "Country": "United Kingdom", "Gross Revenue": 396.92, "Net Revenue": 396.92, "Customer E-mail": "uk-new@example.com", "New/Returning Customer": "New"}),
        _qlik_row(**{"Order No": "S1", "Country": "Sweden", "Gross Revenue": 350.0, "Net Revenue": 350.0, "Customer E-mail": "se@example.com", "New/Returning Customer": "Returning"}),
        _qlik_row(**{"Order No": "G1", "Country": "Germany", "Gross Revenue": 80.0, "Net Revenue": 80.0, "Customer E-mail": "de@example.com", "New/Returning Customer": "New"}),
        _qlik_row(**{"Order No": "N1", "Country": "Norway", "Gross Revenue": 50.0, "Net Revenue": 50.0, "Customer E-mail": "no@example.com", "New/Returning Customer": "New"}),
        _qlik_row(**{"Order No": "U1", "Country": "United States", "Gross Revenue": 200.0, "Net Revenue": 200.0, "Customer E-mail": "us@example.com", "New/Returning Customer": "Returning"}),
    ]


def _market_ranks(result: dict) -> dict[str, int]:
    countries = [row["country"] for row in result["markets"] if row["country"] not in {"ROW", "Total"}]
    return {country: index + 1 for index, country in enumerate(countries)}


def _market(result: dict, country: str) -> dict:
    return next(row for row in result["markets"] if row["country"] == country)


def test_top_markets_and_audience_use_adjusted_totals(tmp_path, monkeypatch):
    _use_orders(monkeypatch, tmp_path / "orders.csv", ["#100288154"])
    _write_qlik(tmp_path, "2026-40", _slide_rows())
    on = calculate_top_markets_for_weeks("2026-40", 1, tmp_path)
    uk_on = _market(on, "United Kingdom")["weeks"]["2026-40"]
    total_on = _market(on, "Total")["weeks"]["2026-40"]
    germany_on = _market(on, "Germany")["weeks"]["2026-40"]
    assert uk_on == pytest.approx(396.92 / VAT_FACTOR)
    assert total_on == pytest.approx(1076.92 - (396.92 - 396.92 / VAT_FACTOR))
    assert germany_on == pytest.approx(80.0)
    assert _market_ranks(on)["United Kingdom"] == 2
    assert _market_ranks(on)["Sweden"] == 1
    again = calculate_top_markets_for_weeks("2026-40", 1, tmp_path)
    assert _market(again, "United Kingdom")["weeks"]["2026-40"] == pytest.approx(uk_on)

    monkeypatch.setenv("ADJUST_UK_VAT", "false")
    clear_runtime_state()
    off = calculate_top_markets_for_weeks("2026-40", 1, tmp_path)
    uk_off = _market(off, "United Kingdom")["weeks"]["2026-40"]
    total_off = _market(off, "Total")["weeks"]["2026-40"]
    assert uk_off == pytest.approx(396.92)
    assert total_off - total_on == pytest.approx(uk_off - uk_on)
    assert _market(off, "Germany")["weeks"]["2026-40"] == pytest.approx(germany_on)
    assert _market_ranks(off)["United Kingdom"] == 1

    monkeypatch.setenv("ADJUST_UK_VAT", "true")
    clear_runtime_state()
    audience_on = calculate_audience_metrics_per_country_for_weeks("2026-40", 1, tmp_path)
    week = audience_on["audience_metrics_per_country"][0]["countries"]
    uk = week["United Kingdom"]
    assert uk["new_customers"] == 1
    assert uk["returning_customers"] == 0
    assert uk["total_orders"] == 1
    assert uk["total_customers"] == 1
    assert uk["aov_new_customer"] == pytest.approx(396.92 / VAT_FACTOR, abs=0.02)
    assert uk["total_aov"] == pytest.approx(396.92 / VAT_FACTOR, abs=0.02)
    germany = week["Germany"]
    assert germany["total_aov"] == pytest.approx(80.0)
    assert germany["new_customers"] == 1
    assert germany["total_orders"] == 1
    row = week["ROW"]
    assert row["total_orders"] == 1
    assert row["total_aov"] == pytest.approx(50.0)
    total = week["Total"]
    assert total["total_orders"] == 5
    assert total["total_customers"] == 5

    monkeypatch.setenv("ADJUST_UK_VAT", "false")
    clear_runtime_state()
    audience_off = calculate_audience_metrics_per_country_for_weeks("2026-40", 1, tmp_path)
    off_countries = audience_off["audience_metrics_per_country"][0]["countries"]
    assert off_countries["United Kingdom"]["new_customers"] == uk["new_customers"]
    assert off_countries["United Kingdom"]["total_orders"] == uk["total_orders"]
    assert off_countries["Germany"]["total_aov"] == pytest.approx(germany["total_aov"])
    assert off_countries["ROW"]["total_aov"] == pytest.approx(row["total_aov"])
    assert off_countries["United States"]["total_aov"] == pytest.approx(week["United States"]["total_aov"])
    assert off_countries["United Kingdom"]["total_aov"] == pytest.approx(396.92)
    # New-customer net is the UK gross here, so the AOV gap is the VAT share.
    assert off_countries["Total"]["total_aov"] * off_countries["Total"]["total_orders"] - total["total_aov"] * total[
        "total_orders"
    ] == pytest.approx(396.92 - 396.92 / VAT_FACTOR, abs=0.05)


def test_2027_last_year_week_uses_adjusted_2026(tmp_path, monkeypatch):
    _use_orders(monkeypatch, tmp_path / "orders.csv", ["#100288154"])
    this_year = get_week_date_range("2027-40")["start"]
    rows = _slide_rows()
    rows.append(
        _qlik_row(
            **{
                "Date": this_year,
                "Order No": "LY-OTHER",
                "Country": "Sweden",
                "Gross Revenue": 10.0,
                "Net Revenue": 10.0,
                "Customer E-mail": "se-2027@example.com",
                "New/Returning Customer": "New",
            }
        )
    )
    rows.append(
        _qlik_row(
            **{
                "Date": this_year,
                "Order No": "UK-2027",
                "Country": "United Kingdom",
                "Gross Revenue": 20.0,
                "Net Revenue": 20.0,
                "Customer E-mail": "uk-2027@example.com",
                "New/Returning Customer": "Returning",
            }
        )
    )
    _write_qlik(tmp_path, "2027-40", rows)
    on = calculate_audience_metrics_per_country_for_weeks("2027-40", 1, tmp_path)
    uk = on["audience_metrics_per_country"][0]["countries"]["United Kingdom"]["last_year"]
    assert uk is not None
    assert uk["total_orders"] == 1
    assert uk["new_customers"] == 1
    assert uk["total_aov"] == pytest.approx(396.92 / VAT_FACTOR, abs=0.02)
    markets = calculate_top_markets_for_weeks("2027-40", 1, tmp_path)
    assert _market(markets, "United Kingdom")["weeks"]["2026-40"] == pytest.approx(396.92 / VAT_FACTOR)

    monkeypatch.setenv("ADJUST_UK_VAT", "false")
    clear_runtime_state()
    off = calculate_audience_metrics_per_country_for_weeks("2027-40", 1, tmp_path)
    uk_off = off["audience_metrics_per_country"][0]["countries"]["United Kingdom"]["last_year"]
    assert uk_off["total_aov"] == pytest.approx(396.92)
    assert uk_off["total_orders"] == uk["total_orders"]
