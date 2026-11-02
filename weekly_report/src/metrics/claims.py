"""Cin7 claim orders. These are not Shopify orders.

The export is one row per replacement line. Money on the order (freight and
discount) is repeated on every line, so each order is counted once.
Replacement cost is the landed cost in SEK from the product file, times
quantity. A line whose item code is not in that file stays at 0. The wholesale
item price is not used.
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

NOTE_SOURCE = (
    "These orders are created in Cin7 for claims. They are not Shopify orders."
)
NOTE_COST = (
    "Replacement cost is the landed cost in SEK, times quantity. It is not the wholesale item price."
)

# Carrier price we pay, from Shipping costs 2026, sheet "Delivery charges_pricing",
# column "Pricelist 2026 inkl DMT EURO". Amounts are EUR before SEK conversion.
# ECB EUR→SEK on the 15th of the claim month (Frankfurter). Other months use October.
_EUR_SEK_BY_MONTH = {
    "2026-09": 11.274,
    "2026-10": 11.1765,
}
_EUR_SEK_DEFAULT = 11.1765
_MAILBOX_EUR = 3.15  # DHL sheet: small packet up to 1 kg. Not on the country price list.

_REASON_HEADERS = (
    "claim type",
    "claim reason",
    "reason for claim",
    "reason",
    "issue",
    "complaint type",
    "complaint",
)
_UNSPECIFIED = "Not specified in the Cin7 export"


def _bundled_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "claims"


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def csv_headers(path: Path) -> set[str]:
    try:
        raw = path.read_bytes()[:8192]
    except OSError:
        return set()
    text = raw.decode("utf-8-sig", errors="replace")
    first = text.splitlines()[0] if text.strip() else ""
    delim = ";" if first.count(";") > first.count(",") else ","
    return {part.strip().strip('"').lower() for part in first.split(delim) if part.strip()}


def is_claims_csv(path: Path) -> bool:
    """A Cin7 orders export for claims, whatever the file is called."""
    if path.suffix.lower() != ".csv":
        return False
    headers = csv_headers(path)
    return "order id" in headers and "created date" in headers and "item name" in headers


def is_landed_cost_csv(path: Path) -> bool:
    """A product export with a product code and a landed cost in SEK."""
    if path.suffix.lower() != ".csv":
        return False
    headers = csv_headers(path)
    if "order id" in headers:
        return False
    has_code = "code" in headers or "product code" in headers or "item code" in headers
    return has_code and _header_landed_cost_sek(headers)


def _header_landed_cost_sek(headers: set[str]) -> bool:
    return any("landed" in header and "sek" in header and "rrp" not in header for header in headers)


def _product_code_column(columns: Sequence[str]) -> Optional[str]:
    normalized = {str(column).strip().lower(): column for column in columns}
    for name in ("code", "product code", "item code"):
        if name in normalized:
            return normalized[name]
    return None


def _landed_cost_column(columns: Sequence[str]) -> Optional[str]:
    best: Optional[str] = None
    best_score = -1
    for column in columns:
        low = str(column).strip().lower()
        if "landed" not in low or "sek" not in low or "rrp" in low or "wholesale" in low:
            continue
        score = 1
        if "excl" in low:
            score += 1
        if any(fx in low for fx in ("eur", "usd", "gbp", "dkk", "nok")):
            score -= 5
        if score > best_score:
            best_score = score
            best = column
    return best


def _landed_cost_files(data_root: Path) -> List[Path]:
    bundled = _bundled_dir()
    found: Dict[str, Path] = {}
    for folder in _claim_folders(data_root):
        for path in folder.glob("*.csv"):
            if not is_landed_cost_csv(path):
                continue
            try:
                key = str(path.resolve())
            except OSError:
                key = str(path)
            found[key] = path
    paths = list(found.values())
    paths.sort(key=lambda path: (not _is_under(path, bundled), _mtime(path), path.name))
    return paths


def _landed_costs(data_root: Path) -> tuple[Dict[str, float], List[str]]:
    """Map product code to landed cost SEK. A later file overrides the same code."""
    costs: Dict[str, float] = {}
    used: List[str] = []
    for path in _landed_cost_files(data_root):
        try:
            handle = path.open(newline="", encoding="utf-8-sig")
        except OSError:
            continue
        with handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                continue
            code_col = _product_code_column(list(reader.fieldnames))
            cost_col = _landed_cost_column(list(reader.fieldnames))
            if not code_col or not cost_col:
                continue
            added = False
            for row in reader:
                code = _text(row.get(code_col))
                if not code:
                    continue
                costs[code] = _num(row.get(cost_col))
                added = True
        if added:
            used.append(path.name)
    return costs, used


def _count_text(value: float) -> str:
    if value == int(value):
        return str(int(value))
    return f"{value:.2f}"


def _claim_folders(data_root: Path) -> List[Path]:
    root = Path(data_root)
    folders = [
        _bundled_dir(),
        root / "claims",
        root / "weekly_report" / "data" / "claims",
    ]
    raw = root / "raw"
    if raw.is_dir():
        for week_dir in raw.iterdir():
            if week_dir.is_dir():
                folders.append(week_dir / "claims")
    seen: List[Path] = []
    for folder in folders:
        try:
            resolved = folder.resolve()
        except OSError:
            continue
        if resolved.is_dir() and resolved not in seen:
            seen.append(resolved)
    return seen


def _claim_files(data_root: Path) -> List[Path]:
    bundled = _bundled_dir()
    found: Dict[str, Path] = {}
    for folder in _claim_folders(data_root):
        for path in folder.glob("*.csv"):
            if not is_claims_csv(path):
                continue
            try:
                key = str(path.resolve())
            except OSError:
                key = str(path)
            found[key] = path
    paths = list(found.values())
    paths.sort(key=lambda path: (not _is_under(path, bundled), _mtime(path), path.name))
    return paths


def _num(value: Any) -> float:
    try:
        number = float(str(value).replace(",", "").strip() or 0)
    except (TypeError, ValueError):
        return 0.0
    if number != number:  # NaN
        return 0.0
    return number


def _text(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    return "" if text.lower() in ("nan", "none") else text


def _parse_created(value: Any) -> Optional[datetime]:
    text = _text(value)
    if not text:
        return None
    for fmt in ("%d %b %Y %I:%M %p", "%d %b %Y %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    parsed = pd.to_datetime(text, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.to_pydatetime()


def _eur_to_sek(month: str) -> float:
    return _EUR_SEK_BY_MONTH.get(month, _EUR_SEK_DEFAULT)


def _norm_shipping(value: str) -> str:
    text = value.lower().replace("&", " and ")
    for char in "-/(),":
        text = text.replace(char, " ")
    return " ".join(text.split())


def carrier_price_eur(country: str, freight_name: str) -> Optional[tuple[float, str]]:
    """2026 price we pay for this shipping name and destination, in EUR.

    Returns None when the price list has no row for that service.
    """
    place = _norm_shipping(country)
    name = _norm_shipping(freight_name)
    if not name:
        return None

    def is_uk() -> bool:
        return place in {"united kingdom", "uk", "great britain"}

    def is_us() -> bool:
        return place in {"united states", "usa", "united states of america"}

    def is_sweden() -> bool:
        return place == "sweden"

    def is_germany() -> bool:
        return place == "germany"

    def is_nl_fr() -> bool:
        return place in {"netherlands", "france", "the netherlands"}

    def is_switzerland() -> bool:
        return place == "switzerland"

    if "fedex" in name and "connect plus" in name:
        if is_uk():
            return 9.9225, "UK · FedEx International Connect Plus DDP"
        if is_us():
            return 24.251, "US · FedEx International Connect Plus DDP"
        if place == "canada":
            return 26.433, "Canada · FedEx International Connect Plus DDP"
        return None
    if "mailbox" in name:
        return _MAILBOX_EUR, "Germany · DHL small packet up to 1 kg"
    if "postnord" in name and "service" in name and is_sweden():
        return 10.068, "Sweden · DHL Paket / PostNord service point"
    if "postnord" in name and "home" in name and is_sweden():
        return 10.068, "Sweden · DHL Paket / PostNord home delivery"
    if ("poste italiane" in name or "local carrier" in name or "ecommerce" in name) and "home" in name:
        if is_nl_fr():
            return 9.756, "France / Netherlands · DHL Paket home delivery"
        return 16.92, "Other EU · DHL Paket home delivery"
    if "ecommerce" in name and "service" in name:
        if is_nl_fr():
            return 9.756, "France / Netherlands · DHL Paket home delivery"
        return None
    if "postnord" in name and "home" in name:
        return 16.92, "Other EU · DHL Paket home delivery"
    if name.startswith("dhl paket") and "home" in name and "international" not in name and is_germany():
        return 6.36, "Germany · DHL Paket home delivery"
    if "express" in name and "home" in name:
        if is_sweden():
            return 20.4605, "Sweden · DHL Express home delivery"
        if is_germany():
            return 15.16245, "Germany · DHL Express home delivery"
        if is_nl_fr():
            return 17.0459, "France / Netherlands · DHL Express home delivery"
        if is_switzerland():
            return 24.39, "Switzerland · DHL Express DAP home delivery"
        return 20.596, "Other EU · DHL Express home delivery"
    if "swisspost" in name or "swiss post" in name:
        return None
    return None


def product_category(name: str) -> str:
    text = name.lower()
    if "sock" in text:
        return "Socks"
    if "swim" in text:
        return "Swim"
    if any(word in text for word in ("hoodie", "sweatshirt", "jogger")):
        return "Sweats"
    if any(word in text for word in ("t-shirt", "tank", "bralette")):
        return "Tops"
    if any(word in text for word in ("boxer", "brief", "trunk")):
        return "Underwear"
    return "Other"


def _reason_column(columns: Sequence[str]) -> Optional[str]:
    normalized = {str(column).strip().lower(): column for column in columns}
    for name in _REASON_HEADERS:
        if name in normalized:
            return str(normalized[name])
    for lowered, original in normalized.items():
        if "claim type" in lowered or "claim reason" in lowered:
            return str(original)
    return None


def _read_claims(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype=str, encoding="utf-8-sig", keep_default_na=False)
    frame.columns = [str(column).strip() for column in frame.columns]
    return frame


def _lines_from_files(paths: Sequence[Path]) -> tuple[pd.DataFrame, List[str]]:
    frames: List[pd.DataFrame] = []
    used: List[str] = []
    for rank, path in enumerate(paths):
        frame = _read_claims(path)
        if frame.empty or "Order Id" not in frame.columns:
            continue
        frame = frame.copy()
        frame["_order_id"] = frame["Order Id"].map(_text)
        frame = frame.loc[frame["_order_id"] != ""]
        if frame.empty:
            continue
        frame["_rank"] = rank
        frames.append(frame)
        used.append(path.name)
    if not frames:
        return pd.DataFrame(), []
    combined = pd.concat(frames, ignore_index=True)
    winning = combined.groupby("_order_id")["_rank"].transform("max")
    kept = combined.loc[combined["_rank"].eq(winning)].drop(columns=["_rank"])
    return kept.reset_index(drop=True), used


def _bucket(label: str) -> Dict[str, Any]:
    return {
        "label": label,
        "orders": 0,
        "units": 0.0,
        "product_cost_sek": 0.0,
        "freight_sek": 0.0,
        "discount_sek": 0.0,
    }


def _finish(bucket: Dict[str, Any]) -> Dict[str, Any]:
    bucket["orders"] = int(bucket["orders"])
    bucket["units"] = int(round(bucket["units"]))
    for key in ("product_cost_sek", "freight_sek", "discount_sek"):
        bucket[key] = round(float(bucket[key]), 2)
    return bucket


def _landed_cost_note(
    matched_lines: int,
    replacement_lines: int,
    landed_files: Sequence[str],
    unmatched_codes: set[str],
    unmatched_units: float,
    blank_lines: int,
    zero_landed_lines: int,
    zero_codes: set[str],
) -> str:
    files = f" ({', '.join(landed_files)})" if landed_files else ""
    text = f"Landed cost matched {matched_lines} of {replacement_lines} replacement lines{files}."
    if unmatched_codes:
        listed = ", ".join(sorted(unmatched_codes))
        text += (
            f" No landed cost for {_count_text(unmatched_units)} units: {listed}. Those units are 0 SEK."
        )
    if blank_lines:
        text += f" {blank_lines} lines have no item code and are 0 SEK."
    if zero_landed_lines:
        listed = ", ".join(sorted(zero_codes))
        text += (
            f" {zero_landed_lines} matched lines have a landed cost of 0 SEK in the product file: {listed}."
        )
    return text


def calculate_claims(data_root: Path) -> Dict[str, Any]:
    paths = _claim_files(data_root)
    lines, files_used = _lines_from_files(paths)
    landed, landed_files = _landed_costs(data_root)
    empty_totals = {
        "orders": 0,
        "units": 0,
        "product_cost_sek": 0.0,
        "freight_sek": 0.0,
        "discount_sek": 0.0,
        "surcharge_sek": 0.0,
        "recorded_cost_sek": 0.0,
    }
    if lines.empty:
        return {
            "available": False,
            "files_used": files_used,
            "notes": [NOTE_SOURCE, "Upload a Cin7 orders export for CDLP CLAIMS on Settings."],
            "totals": empty_totals,
            "months": [],
            "reasons": [],
            "categories": [],
            "countries": [],
            "carriers": [],
            "orders": [],
        }

    reason_col = _reason_column(list(lines.columns))
    orders: List[Dict[str, Any]] = []
    months: Dict[str, Dict[str, Any]] = {}
    reasons: Dict[str, Dict[str, Any]] = {}
    categories: Dict[str, Dict[str, Any]] = {}
    countries: Dict[str, Dict[str, Any]] = {}
    carriers: Dict[str, Dict[str, Any]] = {}
    reason_specified = False
    matched_lines = 0
    replacement_lines = 0
    unmatched_codes: set[str] = set()
    unmatched_units = 0.0
    blank_lines = 0
    zero_landed_lines = 0
    zero_codes: set[str] = set()

    for order_id, group in lines.groupby("_order_id", sort=False):
        first = group.iloc[0]
        created = _parse_created(first.get("Created Date"))
        month_key = created.strftime("%Y-%m") if created else "unknown"
        month_label = created.strftime("%b %Y") if created else "Unknown date"
        units = sum(_num(row.get("Item Qty")) for _, row in group.iterrows())
        product = 0.0
        freight = _num(first.get("Freight Cost (Local Currency)"))
        freight_name = _text(first.get("Freight Description")) or _text(first.get("Carrier"))
        country = _text(first.get("Delivery Country")) or "Unknown country"
        priced = None
        if freight <= 0:
            created_for_rate = _parse_created(first.get("Created Date"))
            month_for_rate = created_for_rate.strftime("%Y-%m") if created_for_rate else ""
            priced = carrier_price_eur(country, freight_name)
            if priced is not None:
                freight = priced[0] * _eur_to_sek(month_for_rate)
        discount = _num(first.get("Discount Total (Local Currency)")) + sum(
            _num(row.get("Item Total Discount (Local Currency)")) for _, row in group.iterrows()
        )
        surcharge = _num(first.get("Surcharge Total (Local Currency)"))
        reason = _text(first.get(reason_col)) if reason_col else ""
        if not reason:
            reason = _text(first.get("Order Tags")) or _text(first.get("Item Notes"))
        if reason:
            reason_specified = True
        else:
            reason = _UNSPECIFIED
        carrier = freight_name or "Unknown carrier"
        item_names = []
        cats = set()
        for _, row in group.iterrows():
            name = _text(row.get("Item Name")) or _text(row.get("Item Code")) or "Unknown product"
            qty = _num(row.get("Item Qty"))
            code = _text(row.get("Item Code"))
            replacement_lines += 1
            if code in landed:
                matched_lines += 1
                unit_cost = landed[code]
                if unit_cost == 0:
                    zero_landed_lines += 1
                    zero_codes.add(code)
            else:
                unit_cost = 0.0
                if code:
                    unmatched_codes.add(code)
                    unmatched_units += qty
                else:
                    blank_lines += 1
            line_cost = unit_cost * qty
            product += line_cost
            item_names.append(f"{name} × {int(qty) if qty == int(qty) else qty}")
            category = product_category(name)
            cats.add(category)
            cat = categories.setdefault(category, _bucket(category))
            cat["units"] += qty
            cat["product_cost_sek"] += line_cost
        for category in cats:
            categories[category]["orders"] += 1

        record = {
            "order_id": str(order_id),
            "order_ref": _text(first.get("Order Ref")) or str(order_id),
            "created": created.strftime("%Y-%m-%d") if created else "",
            "month": month_key,
            "country": country,
            "currency": _text(first.get("Currency Name")),
            "carrier": _text(first.get("Carrier")),
            "freight_method": carrier,
            "reason": reason,
            "units": int(round(units)),
            "product_cost_sek": round(product, 2),
            "freight_sek": round(freight, 2),
            "freight_rate": priced[1] if priced is not None else "",
            "discount_sek": round(discount, 2),
            "surcharge_sek": round(surcharge, 2),
            "items": "; ".join(item_names),
        }
        orders.append(record)

        for store, key, label in (
            (months, month_key, month_label),
            (reasons, reason, reason),
            (countries, country, country),
            (carriers, carrier, carrier),
        ):
            bucket = store.setdefault(key, _bucket(label))
            if key == month_key:
                bucket["key"] = month_key
            bucket["orders"] += 1
            bucket["units"] += units
            bucket["product_cost_sek"] += product
            bucket["freight_sek"] += freight
            bucket["discount_sek"] += discount

    orders.sort(key=lambda row: (row["created"], row["order_ref"]), reverse=True)
    month_rows = []
    for key in sorted(months):
        row = _finish(months[key])
        row["key"] = key
        month_rows.append(row)

    def ranked(store: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        rows = [_finish(bucket) for bucket in store.values()]
        rows.sort(key=lambda row: (-row["product_cost_sek"], -row["orders"], row["label"]))
        return rows

    product_cost = round(sum(row["product_cost_sek"] for row in orders), 2)
    freight_cost = round(sum(row["freight_sek"] for row in orders), 2)
    discount_cost = round(sum(row["discount_sek"] for row in orders), 2)
    surcharge_cost = round(sum(row["surcharge_sek"] for row in orders), 2)
    totals = {
        "orders": len(orders),
        "units": int(sum(row["units"] for row in orders)),
        "product_cost_sek": product_cost,
        "freight_sek": freight_cost,
        "discount_sek": discount_cost,
        "surcharge_sek": surcharge_cost,
        "recorded_cost_sek": round(product_cost + freight_cost + discount_cost + surcharge_cost, 2),
    }
    notes = [NOTE_SOURCE, NOTE_COST, _landed_cost_note(
        matched_lines,
        replacement_lines,
        landed_files,
        unmatched_codes,
        unmatched_units,
        blank_lines,
        zero_landed_lines,
        zero_codes,
    )]
    if not reason_specified:
        notes.append(
            "This export has no claim reason. Product type, country and shipping method are shown instead. "
            "Add a Claim Type column, or fill Order Tags, to split the claims by reason."
        )
    priced_orders = sum(1 for row in orders if row.get("freight_rate"))
    missing_shipping = [
        f"{row['order_ref']} ({row['country']}, {row['freight_method']})"
        for row in orders
        if row["freight_sek"] == 0
    ]
    if priced_orders:
        notes.append(
            "Shipping is the 2026 carrier price we pay (pricelist including DMT), matched on the shipping name and destination. "
            "Cin7 has no freight amount. Euro prices are converted at the ECB rate for the 15th of the claim month: "
            "11.274 SEK per EUR in September 2026 and 11.1765 in October 2026."
        )
    if missing_shipping:
        notes.append(
            "No 2026 price for: " + "; ".join(missing_shipping) + "."
        )
    elif freight_cost == 0:
        notes.append(
            "Freight cost is 0 on every order, so the shipping loss is not in this file."
        )
    if discount_cost == 0:
        notes.append("No extra discount is attached to these orders in this file.")
    return {
        "available": True,
        "files_used": files_used,
        "notes": notes,
        "totals": totals,
        "months": month_rows,
        "reasons": ranked(reasons),
        "categories": ranked(categories),
        "countries": ranked(countries),
        "carriers": ranked(carriers),
        "orders": orders,
    }
