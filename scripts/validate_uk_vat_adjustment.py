#!/usr/bin/env python3
"""Print and save reports/uk_vat_adjustment_check.csv.

The weekly gross table is the committed Shopify list
(weekly_report/data/adjustments/uk_vat_affected_orders.csv): before is
gross_sales, after is gross_sales/1.2, difference is gross_sales/6.
That file has no net, discount, or shipping column. Production Shopify,
Qlik, and Dema week files are read when present. This script does not
invent those rows.
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
    affected_orders_csv_path,
    clear_runtime_state,
    invalidate_local_caches,
    invalidate_supabase_overlapping,
    load_affected_orders,
)

WEEKS = [f"2026-{n:02d}" for n in range(40, 47)]
OUTPUT = REPO / "reports" / "uk_vat_adjustment_check.csv"


def _data_roots() -> list[Path]:
    roots = [Path(os.getenv("DATA_ROOT", REPO / "data"))]
    roots.append(REPO / "data")
    roots.append(REPO / "weekly_report" / "data")
    unique: list[Path] = []
    seen = set()
    for root in roots:
        key = str(root.resolve()) if root.exists() else str(root)
        if key in seen:
            continue
        seen.add(key)
        unique.append(root)
    return unique


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


def _csv_week_rows() -> list[dict]:
    """Gross before/after from the committed list. Net is not on that file."""
    path = affected_orders_csv_path()
    frame = pd.read_csv(path)
    created = pd.to_datetime(frame["order_created_at"], utc=True).dt.tz_convert("Europe/Stockholm")
    iso = created.dt.isocalendar()
    frame = frame.assign(week=iso.year.astype(str) + "-" + iso.week.astype(int).astype(str).str.zfill(2))
    rows = []
    note = (
        "Shopify affected-orders file only. before = gross_sales, after = gross_sales / 1.2, "
        "difference = gross_sales / 6. Net sales is not a column on this file."
    )
    net_note = (
        "Net sales, discounts and shipping are not on uk_vat_affected_orders.csv. "
        "No order-level Shopify or Qlik extract with a net column was loaded, so net before/after is blank."
    )
    for week in WEEKS:
        part = frame.loc[frame["week"].eq(week)]
        gross = float(part["gross_sales"].sum()) if len(part) else 0.0
        rows.append(
            {
                "section": "affected_orders_csv",
                "week": week,
                "metric": "uk_gross",
                "before": round(gross, 2),
                "after": round(gross / VAT_FACTOR, 2),
                "difference": round(gross / 6.0, 2),
                "affected_orders": int(len(part)),
                "note": note,
            }
        )
        rows.append(
            {
                "section": "affected_orders_csv",
                "week": week,
                "metric": "uk_net",
                "before": None,
                "after": None,
                "difference": None,
                "affected_orders": int(len(part)),
                "note": net_note,
            }
        )
    gross_total = float(frame["gross_sales"].sum())
    rows.append(
        {
            "section": "affected_orders_csv",
            "week": "W40-W46",
            "metric": "uk_gross_total",
            "before": round(gross_total, 2),
            "after": round(gross_total / VAT_FACTOR, 2),
            "difference": round(gross_total / 6.0, 2),
            "affected_orders": int(len(frame)),
            "note": note + " Order #100288414 is not in this file.",
        }
    )
    return rows


def _order_level_net_rows() -> list[dict]:
    """Sum net on any loaded extract that names these orders. Does not invent rows."""
    orders = set(load_affected_orders())
    net_names = ["Net sales", "Net Sales", "Net Revenue", "net_sales"]
    found = False
    for root in _data_roots():
        if not root.exists():
            continue
        for path in list(root.rglob("*.csv")) + list(root.rglob("*.parquet")):
            if "uk_vat_affected_orders" in path.name or "reports" in path.parts:
                continue
            try:
                frame = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path, nrows=5)
            except Exception:
                continue
            order_col = next((col for col in frame.columns if str(col) in {"Order No", "order_name", "Name", "Order name"}), None)
            net_col = next((col for col in frame.columns if str(col) in net_names), None)
            if not order_col or not net_col:
                continue
            full = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
            ids = full[order_col].astype(str).str.replace("#", "", regex=False).str.strip()
            matched = full.loc[ids.isin(orders)]
            if matched.empty:
                continue
            found = True
            before = float(pd.to_numeric(matched[net_col], errors="coerce").fillna(0).sum())
            return [
                {
                    "section": "order_level_net",
                    "week": "W40-W46",
                    "metric": "uk_net",
                    "before": round(before, 2),
                    "after": round(before / VAT_FACTOR, 2),
                    "difference": round(before / 6.0, 2),
                    "affected_orders": int(len(matched)),
                    "note": f"Net summed from {path} for order ids on the Shopify list, then divided by 1.2.",
                }
            ]
    if not found:
        return [
            {
                "section": "order_level_net",
                "week": "W40-W46",
                "metric": "uk_net",
                "before": None,
                "after": None,
                "difference": None,
                "affected_orders": 0,
                "note": (
                    "No order-level file with both an order id and Net sales / Net Revenue matched the "
                    "177 Shopify orders. Daily Shopify totals and Cin7 claims are not that extract."
                ),
            }
        ]
    return []


def _slide_unavailable_rows() -> list[dict]:
    missing = _find_week_frame("qlik") is None
    note = (
        "No Qlik week files for 2026-40 through 2026-46, so Top Markets and Audience were not recalculated. "
        "No Qlik or Dema rows were invented."
        if missing
        else "Qlik files were found; slide metrics were not rebuilt in this check."
    )
    rows = []
    for section, metric in (
        ("top_markets", "uk_revenue_rank_and_total"),
        ("audience_total", "new_returning_revenue_aov_customers"),
        ("audience_uk", "new_returning_revenue_aov_customers"),
    ):
        rows.append(
            {
                "section": section,
                "week": "W40-W46",
                "metric": metric,
                "before": None,
                "after": None,
                "difference": None,
                "affected_orders": None,
                "note": note,
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
    clear_runtime_state()
    csv_weeks = _csv_week_rows()
    production = _production_rows("shopify", adjust_shopify) + _production_rows("qlik", adjust_qlik)
    net_rows = _order_level_net_rows()
    slides = _slide_unavailable_rows()
    fixture = _fixture_rows()
    gross_row = next(row for row in csv_weeks if row["metric"] == "uk_gross_total")
    gap = [
        {
            "section": "gap",
            "week": "W40-W46",
            "metric": "affected_orders",
            "before": 177,
            "after": len(orders),
            "difference": len(orders) - 177,
            "affected_orders": len(orders),
            "note": (
                "Updated target: 177 orders, Shopify gross reduction about $12,348, "
                "net sales reduction about $11,558. "
                f"This file has {len(orders)} orders and gross sales {gross_row['before']}; "
                f"gross/6 = {gross_row['difference']}. "
                "Order #100288414 is excluded (it had GB VAT 26.48 and was later fully refunded). "
                "Net cannot be recomputed: the file has no net, discount, or shipping column, "
                "and no order-level extract with those amounts was loaded."
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
    rows = csv_weeks + production + net_rows + slides + fixture + gap
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUTPUT, index=False)
    _print_table("Affected-orders CSV, W40–W46 (gross = file, net = not on file)", csv_weeks)
    _print_table("Shopify / Qlik week folders", production)
    _print_table("Order-level net, if a source file was loaded", net_rows)
    _print_table("Top Markets and Audience (not invented)", slides)
    _print_table("Rule check on #100288154 (not a production slide)", fixture)
    _print_table("Gap, Qlik check, what was not run", gap)
    print(f"\nwrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
