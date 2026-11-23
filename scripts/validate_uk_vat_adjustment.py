#!/usr/bin/env python3
"""Print and save reports/uk_vat_adjustment_check.csv.

Production week files are read when present under DATA_ROOT or ./data.
This environment has no Shopify/Qlik extract for W40–W46 2026, so those
rows explain the gap. A clearly labeled fixture block checks the rule on
synthetic orders (not the $74,209 reference).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from weekly_report.src.transform.uk_vat_adjustment import (  # noqa: E402
    QLIK_INCLUDES_UK_VAT,
    VAT_FACTOR,
    adjust_qlik,
    adjust_shopify,
    invalidate_local_caches,
    invalidate_supabase_overlapping,
    load_affected_orders,
)

WEEKS = [f"2026-{n:02d}" for n in range(40, 47)]
OUTPUT = REPO / "reports" / "uk_vat_adjustment_check.csv"


def _data_roots() -> list[Path]:
    roots = [Path(os.getenv("DATA_ROOT", REPO / "data"))]
    roots.append(REPO / "data")
    return roots


def _find_week_frame(slot: str) -> pd.DataFrame | None:
    frames = []
    for root in _data_roots():
        raw = root / "raw"
        if not raw.exists():
            continue
        for week in WEEKS:
            folder = raw / week / slot
            if not folder.exists():
                continue
            for path in list(folder.glob("*.csv")) + list(folder.glob("*.parquet")):
                if path.suffix == ".parquet":
                    frames.append(pd.read_parquet(path))
                else:
                    frames.append(pd.read_csv(path))
    if not frames:
        return None
    return pd.concat(frames, ignore_index=True)


def _uk_mask(frame: pd.DataFrame) -> pd.Series:
    for column in ("Shipping Country", "Shipping country", "Country", "Land"):
        if column in frame.columns:
            return frame[column].astype(str).str.strip().str.lower().isin(
                {"united kingdom", "uk", "gb", "great britain"}
            )
    return pd.Series(False, index=frame.index)


def _sum(frame: pd.DataFrame, names: list[str]) -> float | None:
    for name in names:
        if name in frame.columns:
            return float(pd.to_numeric(frame[name], errors="coerce").fillna(0).sum())
    return None


def _production_rows(source: str, adjust) -> list[dict]:
    frame = _find_week_frame("shopify" if source == "shopify" else "qlik")
    rows = []
    if frame is None:
        for week in WEEKS:
            rows.append(
                {
                    "section": source,
                    "week": week,
                    "metric": "uk_gross",
                    "before": None,
                    "after": None,
                    "difference": None,
                    "affected_orders": None,
                    "note": "no source file for this week in the local data folders",
                }
            )
        return rows
    before = frame
    after = adjust(frame.copy())
    for week in WEEKS:
        rows.append(
            {
                "section": source,
                "week": week,
                "metric": "uk_gross",
                "before": _sum(before.loc[_uk_mask(before)], ["Gross sales", "Gross Revenue", "Subtotal"]),
                "after": _sum(after.loc[_uk_mask(after)], ["Gross sales", "Gross Revenue", "Subtotal"]),
                "difference": None,
                "affected_orders": len(load_affected_orders()),
                "note": "full extract; week split needs a date column on the file",
            }
        )
    return rows


def _fixture_rows() -> list[dict]:
    """One affected order and one taxed UK order. Not the 178-order reference."""
    shopify = pd.DataFrame(
        [
            {
                "order_name": "#100288154",
                "Created at": "2026-09-29 12:00:00",
                "Shipping country": "United Kingdom",
                "Gross sales": 396.92,
                "Discounts": 0.0,
                "Net sales": 396.92,
                "Shipping": 0.0,
                "Taxes": 0.0,
                "Orders": 1,
            },
            {
                "order_name": "#100288145",
                "Created at": "2026-09-29 13:00:00",
                "Shipping country": "United Kingdom",
                "Gross sales": 126.74,
                "Discounts": 0.0,
                "Net sales": 101.39,
                "Shipping": 0.0,
                "Taxes": 25.35,
                "Orders": 1,
            },
        ]
    )
    # The committed list may be empty. This block only shows the rule.
    os.environ["UK_VAT_AFFECTED_ORDERS_CSV"] = str(_fixture_csv())
    from weekly_report.src.transform.uk_vat_adjustment import clear_runtime_state

    clear_runtime_state()
    adjusted = adjust_shopify(shopify)
    gross_before = 396.92
    gross_after = float(adjusted.loc[adjusted["order_name"].eq("#100288154"), "Gross sales"].iloc[0])
    return [
        {
            "section": "fixture_not_production",
            "week": "2026-40",
            "metric": "order_100288154_gross",
            "before": gross_before,
            "after": round(gross_after, 2),
            "difference": round(gross_before - gross_after, 2),
            "affected_orders": 1,
            "note": f"divided by {VAT_FACTOR}; 396.92/1.2 rounds to 330.77. Taxed order #100288145 is not in the fixture list.",
        }
    ]


def _fixture_csv() -> Path:
    path = REPO / "reports" / "_uk_vat_fixture_orders.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "order_name": "#100288154",
                "order_created_at": "2026-09-29 12:00:00+0200",
                "shipping_country": "United Kingdom",
                "gross_sales": 396.92,
                "taxes": 0,
                "vat_factor": 1.2,
            }
        ]
    ).to_csv(path, index=False)
    return path


def _slide_rows() -> list[dict]:
    """W40 fixture passed through Top Markets and Audience. Not production revenue."""
    from weekly_report.src.metrics.audience_metrics_per_country import (
        calculate_audience_metrics_per_country_for_weeks,
    )
    from weekly_report.src.metrics.markets import calculate_top_markets_for_weeks
    from weekly_report.src.transform.uk_vat_adjustment import clear_runtime_state

    root = REPO / "reports" / "_uk_vat_fixture_data"
    week = root / "raw" / "2026-40"
    qlik = week / "qlik"
    dema = week / "dema_spend"
    qlik.mkdir(parents=True, exist_ok=True)
    dema.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {"Date": "2026-09-29", "Sales Channel": "Online", "Country": "United Kingdom", "Gross Revenue": 396.92, "Net Revenue": 396.92, "Returns": 0, "Order No": "#100288154", "Customer E-mail": "uk@example.com", "New/Returning Customer": "New", "Sales Qty": 2},
            {"Date": "2026-09-29", "Sales Channel": "Online", "Country": "Sweden", "Gross Revenue": 350.0, "Net Revenue": 350.0, "Returns": 0, "Order No": "S1", "Customer E-mail": "se@example.com", "New/Returning Customer": "Returning", "Sales Qty": 1},
            {"Date": "2026-09-29", "Sales Channel": "Online", "Country": "Germany", "Gross Revenue": 80.0, "Net Revenue": 80.0, "Returns": 0, "Order No": "G1", "Customer E-mail": "de@example.com", "New/Returning Customer": "New", "Sales Qty": 1},
            {"Date": "2026-09-29", "Sales Channel": "Online", "Country": "Norway", "Gross Revenue": 50.0, "Net Revenue": 50.0, "Returns": 0, "Order No": "N1", "Customer E-mail": "no@example.com", "New/Returning Customer": "New", "Sales Qty": 1},
            {"Date": "2026-09-29", "Sales Channel": "Online", "Country": "United States", "Gross Revenue": 200.0, "Net Revenue": 200.0, "Returns": 0, "Order No": "U1", "Customer E-mail": "us@example.com", "New/Returning Customer": "Returning", "Sales Qty": 1},
        ]
    ).to_csv(qlik / "qlik.csv", index=False)
    pd.DataFrame({"Days": ["2026-09-29"], "Country": ["United Kingdom"], "Marketing spend": [40.0]}).to_csv(
        dema / "spend.csv", index=False
    )
    os.environ["UK_VAT_AFFECTED_ORDERS_CSV"] = str(_fixture_csv())
    os.environ["DATA_ROOT"] = str(root)

    def snap(enabled: str) -> dict:
        os.environ["ADJUST_UK_VAT"] = enabled
        clear_runtime_state()
        markets = calculate_top_markets_for_weeks("2026-40", 1, root)
        audience = calculate_audience_metrics_per_country_for_weeks("2026-40", 1, root)
        countries = {row["country"]: row for row in markets["markets"]}
        aud = audience["audience_metrics_per_country"][0]["countries"]
        ranks = [row["country"] for row in markets["markets"] if row["country"] not in {"ROW", "Total"}]
        return {"markets": countries, "audience": aud, "ranks": {name: i + 1 for i, name in enumerate(ranks)}}

    on = snap("true")
    off = snap("false")
    uk_rank_on = on["ranks"].get("United Kingdom")
    uk_rank_off = off["ranks"].get("United Kingdom")
    rows = [
        {
            "section": "fixture_top_markets",
            "week": "2026-40",
            "metric": "uk_gross_and_rank",
            "before": off["markets"]["United Kingdom"]["weeks"]["2026-40"],
            "after": on["markets"]["United Kingdom"]["weeks"]["2026-40"],
            "difference": off["markets"]["United Kingdom"]["weeks"]["2026-40"] - on["markets"]["United Kingdom"]["weeks"]["2026-40"],
            "affected_orders": 1,
            "note": f"rank {uk_rank_off} -> {uk_rank_on}. Sweden stays {off['markets']['Sweden']['weeks']['2026-40']}.",
        },
        {
            "section": "fixture_top_markets",
            "week": "2026-40",
            "metric": "total_gross",
            "before": off["markets"]["Total"]["weeks"]["2026-40"],
            "after": on["markets"]["Total"]["weeks"]["2026-40"],
            "difference": off["markets"]["Total"]["weeks"]["2026-40"] - on["markets"]["Total"]["weeks"]["2026-40"],
            "affected_orders": 1,
            "note": "Company total drops by the UK difference. Germany unchanged.",
        },
    ]
    for label, key in (("audience_total", "Total"), ("audience_uk", "United Kingdom")):
        before = off["audience"][key]
        after = on["audience"][key]
        rows.append(
            {
                "section": f"fixture_{label}",
                "week": "2026-40",
                "metric": "new_returning_aov_customers",
                "before": before["aov_new_customer"],
                "after": after["aov_new_customer"],
                "difference": before["aov_new_customer"] - after["aov_new_customer"],
                "affected_orders": 1,
                "note": (
                    f"new customers {before['new_customers']}->{after['new_customers']}, "
                    f"returning {before['returning_customers']}->{after['returning_customers']}, "
                    f"orders {before['total_orders']}->{after['total_orders']}, "
                    f"returning AOV {before['aov_returning_customer']}->{after['aov_returning_customer']}"
                ),
            }
        )
    rows.append(
        {
            "section": "fixture_audience_other",
            "week": "2026-40",
            "metric": "germany_usa_row_aov",
            "before": off["audience"]["Germany"]["total_aov"],
            "after": on["audience"]["Germany"]["total_aov"],
            "difference": 0,
            "affected_orders": 0,
            "note": (
                f"Germany {off['audience']['Germany']['total_aov']}->{on['audience']['Germany']['total_aov']}; "
                f"USA {off['audience']['United States']['total_aov']}->{on['audience']['United States']['total_aov']}; "
                f"ROW (Norway, not UK) {off['audience']['ROW']['total_aov']}->{on['audience']['ROW']['total_aov']}."
            ),
        }
    )
    return rows


def _print_table(title: str, rows: list[dict]) -> None:
    print(f"\n{title}")
    if not rows:
        print("(none)")
        return
    frame = pd.DataFrame(rows)
    print(frame.to_string(index=False))


def main() -> int:
    orders = load_affected_orders()
    cache = invalidate_local_caches(Path(os.getenv("DATA_ROOT", REPO / "data")))
    supabase = invalidate_supabase_overlapping()
    production = _production_rows("shopify", adjust_shopify) + _production_rows("qlik", adjust_qlik)
    fixture = _fixture_rows() + _slide_rows()
    gap = [
        {
            "section": "gap",
            "week": "W40-W46",
            "metric": "affected_orders",
            "before": 178,
            "after": len(orders),
            "difference": len(orders) - 178,
            "affected_orders": len(orders),
            "note": (
                "Reference (USD, sale rows created in the window): 178 orders, "
                "gross $74,209.63, discounts $2,274.07, net $69,348.44, shipping $419.01, tax $0. "
                "Expected reduction about $12,368 gross and about $11,558 net. "
                "No Shopify orders export was in the repo or local data/cache, so no order rows were written. "
                "Cin7 claim orders are warehouse claims, not these Shopify order names, and have no Taxes column."
            ),
        },
        {
            "section": "qlik_check",
            "week": "2026-40",
            "metric": "order_100288154",
            "before": None,
            "after": None,
            "difference": None,
            "affected_orders": None,
            "note": (
                "Could not open #100288154 in Qlik: no Qlik extract is on disk. "
                + (
                    "QLIK_INCLUDES_UK_VAT is True, so Qlik is adjusted together with Shopify and Dema, "
                    "because Top Markets and Audience read Qlik gross and net. "
                    "If a later export shows Qlik already excluding VAT, set QLIK_INCLUDES_UK_VAT = False "
                    "and only Shopify and Dema will be adjusted."
                    if QLIK_INCLUDES_UK_VAT
                    else "QLIK_INCLUDES_UK_VAT is False; Qlik is not adjusted."
                )
            ),
        },
        {
            "section": "not_run",
            "week": "",
            "metric": "pipeline",
            "before": None,
            "after": None,
            "difference": None,
            "affected_orders": None,
            "note": "Weekly pipeline was not re-run: no raw week files and no Supabase credentials in this environment.",
        },
        {
            "section": "not_run",
            "week": "",
            "metric": "supabase",
            "before": None,
            "after": None,
            "difference": None,
            "affected_orders": None,
            "note": str(supabase),
        },
        {
            "section": "cache",
            "week": "",
            "metric": "local",
            "before": None,
            "after": None,
            "difference": None,
            "affected_orders": None,
            "note": f"removed {cache['removed_count']} cache files; source parquet kept; memory caches cleared",
        },
    ]
    rows = production + fixture + gap
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUTPUT, index=False)
    _print_table("Shopify / Qlik weeks W40–W46 (production files)", production)
    _print_table("Fixture (not the 178-order reference)", fixture)
    _print_table("Gap, Qlik check, what was not run", gap)
    print(f"\nwrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
