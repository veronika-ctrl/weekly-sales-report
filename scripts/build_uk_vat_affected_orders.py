#!/usr/bin/env python3
"""Build weekly_report/data/adjustments/uk_vat_affected_orders.csv.

Looks for a Shopify orders export (Name, Created at, Shipping Country, Subtotal,
Taxes) or a Qlik/Shopify extract with the same facts. One row per order. Does
not invent orders. Re-run after a new export is added:

    python scripts/build_uk_vat_affected_orders.py
    python scripts/build_uk_vat_affected_orders.py /path/to/orders_export.csv
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable, List

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from weekly_report.src.transform.uk_vat_adjustment import (  # noqa: E402
    rows_from_orders_export,
    write_affected_orders_csv,
)

OUTPUT = REPO / "weekly_report" / "data" / "adjustments" / "uk_vat_affected_orders.csv"
SKIP_DIR_NAMES = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".next",
    "site-packages",
}


def _search_roots(extra: Iterable[str]) -> List[Path]:
    roots = [Path(arg).expanduser() for arg in extra]
    roots.extend(
        [
            REPO / "data",
            REPO / "weekly_report" / "data",
            REPO / "uploads",
            Path.home() / ".cursor" / "projects",
        ]
    )
    return roots


def _candidate_files(roots: Iterable[Path]) -> List[Path]:
    found: List[Path] = []
    for root in roots:
        if not root.exists():
            continue
        if root.is_file():
            found.append(root)
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in SKIP_DIR_NAMES for part in path.parts):
                continue
            if path.suffix.lower() not in {".csv", ".xlsx", ".xls"}:
                continue
            if path.resolve() == OUTPUT.resolve():
                continue
            found.append(path)
    return found


def _read(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        for sep in (",", ";", "\t", "|"):
            try:
                frame = pd.read_csv(path, sep=sep, encoding=encoding, low_memory=False)
            except Exception:
                continue
            if frame.shape[1] >= 4:
                return frame
    return pd.DataFrame()


def main(argv: List[str]) -> int:
    files = _candidate_files(_search_roots(argv[1:]))
    chosen: List[dict] = []
    source = ""
    scanned = 0
    for path in files:
        scanned += 1
        try:
            frame = _read(path)
        except Exception as exc:
            print(f"skip {path}: {exc}")
            continue
        rows = rows_from_orders_export(frame)
        if len(rows) > len(chosen):
            chosen = rows
            source = str(path)
    write_affected_orders_csv(chosen, OUTPUT)
    gross = sum(float(row["gross_sales"]) for row in chosen)
    print(f"scanned_files {scanned}")
    print(f"source {source or 'none'}")
    print(f"affected_orders {len(chosen)}")
    print(f"gross_sales {gross:.2f}")
    print(f"wrote {OUTPUT}")
    if len(chosen) != 178:
        print(
            "gap vs reference 178 orders / gross sales $74,209.63: "
            f"this run kept {len(chosen)} orders"
            + (f" from {source}." if source else " because no orders export with "
               "Name, Created at, Shipping Country, Subtotal and Taxes was found. "
               "Cin7 claim files and Shopify daily totals do not have those columns. "
               "No order rows were invented.")
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
