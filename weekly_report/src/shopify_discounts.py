"""Pull weekly discount usage from ShopifyQL and classify codes.

ShopifyQL (selected week Monday–Sunday):

    FROM sales SHOW orders, gross_sales, discounts
    GROUP BY day, discount_name
    SINCE <Mon> UNTIL <Sun>

Credentials (any of these; never log the token):

    SHOPIFY_SHOP / SHOPIFY_STORE / SHOPIFY_SHOP_DOMAIN
    SHOPIFY_ACCESS_TOKEN / SHOPIFY_ADMIN_ACCESS_TOKEN / SHOPIFY_ADMIN_API_TOKEN
    SHOPIFY_API_VERSION (optional, default 2024-10)

The resulting CSV is the same shape as an uploaded discount_groups_daily file
and is merged by day like any other week file.
"""

from __future__ import annotations

import csv
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from loguru import logger

from weekly_report.src.periods.calculator import get_week_date_range

DEFAULT_API_VERSION = "2024-10"
CSV_COLUMNS = [
    "date",
    "group",
    "subgroup",
    "code_or_title",
    "orders",
    "gross_sales_usd",
    "discount_amount_usd",
]

WINBACK_RE = re.compile(r"^W[A-Za-z0-9]{8}$")
CDLP_CARE_RE = re.compile(r"^CDLP\d+_.+")
AFTERSHIP_EXCHANGE = "AfterShip Returns exchange"

GROUP_AFTERSHIP = "0 AfterShip exchanges"
GROUP_KLAVIYO = "1 Klaviyo"
GROUP_CARE = "2 Customer care"
GROUP_OTHER = "8 Other / unknown"

SUB_AFTERSHIP_ORDERS = "AfterShip exchange orders"
SUB_MANUAL_EXCHANGE = "Manual exchange codes"
SUB_WELCOME = "Welcome code"
SUB_FREE_SHIPPING = "Abandoned checkout / free shipping (FS-)"
SUB_WINBACK = "Inactive Winback"
SUB_NAMED_CARE = "Named / care codes"
SUB_MANUAL_DISCOUNT = "Manual discount on order (draft/edit)"


def shopify_shop() -> Optional[str]:
    raw = (
        os.getenv("SHOPIFY_SHOP")
        or os.getenv("SHOPIFY_STORE")
        or os.getenv("SHOPIFY_SHOP_DOMAIN")
        or ""
    ).strip()
    if not raw:
        return None
    raw = re.sub(r"^https?://", "", raw, flags=re.I).rstrip("/")
    if "/" in raw:
        raw = raw.split("/", 1)[0]
    if raw.endswith(".myshopify.com"):
        return raw
    if "." not in raw:
        return f"{raw}.myshopify.com"
    return raw


def shopify_token() -> Optional[str]:
    raw = (
        os.getenv("SHOPIFY_ACCESS_TOKEN")
        or os.getenv("SHOPIFY_ADMIN_ACCESS_TOKEN")
        or os.getenv("SHOPIFY_ADMIN_API_TOKEN")
        or os.getenv("SHOPIFY_ADMIN_TOKEN")
        or ""
    ).strip()
    return raw or None


def shopify_api_version() -> str:
    return (os.getenv("SHOPIFY_API_VERSION") or DEFAULT_API_VERSION).strip() or DEFAULT_API_VERSION


def shopify_configured() -> bool:
    return bool(shopify_shop() and shopify_token())


def shopifyql_query_for_week(base_week: str) -> Tuple[str, str, str]:
    rng = get_week_date_range(base_week)
    start, end = rng["start"], rng["end"]
    query = (
        "FROM sales SHOW orders, gross_sales, discounts "
        f"GROUP BY day, discount_name SINCE {start} UNTIL {end}"
    )
    return query, start, end


def load_code_mapping(mapping_path: Optional[Path] = None) -> Dict[str, Tuple[str, str]]:
    """code_or_title → (group, subgroup). First row for a code wins."""
    if mapping_path is None:
        mapping_path = (
            Path(__file__).resolve().parents[1] / "data" / "discount_types" / "discount_code_mapping.csv"
        )
    out: Dict[str, Tuple[str, str]] = {}
    if mapping_path is None or not mapping_path.exists():
        return out
    from weekly_report.src.metrics.discounts_sales import _read_csv_flexible

    frame = _read_csv_flexible(mapping_path)
    frame.columns = [str(c).strip().replace('"', "") for c in frame.columns]
    if "code_or_title" not in frame.columns or "group" not in frame.columns:
        return out
    for _, row in frame.iterrows():
        code = str(row.get("code_or_title") or "").strip()
        if not code or code in out:
            continue
        group = str(row.get("group") or "").strip()
        subgroup = str(row.get("subgroup") or "").strip()
        if group:
            out[code] = (group, subgroup)
    return out


def classify_discount_code(
    code_or_title: str,
    mapping: Optional[Dict[str, Tuple[str, str]]] = None,
) -> Tuple[str, str, str]:
    """Return (group, subgroup, source) with source in mapping|rule|unknown."""
    code = str(code_or_title or "").strip()
    if mapping:
        hit = mapping.get(code)
        if hit:
            group, subgroup = hit
            return group, subgroup or code, "mapping"

    if code == AFTERSHIP_EXCHANGE:
        return GROUP_AFTERSHIP, SUB_AFTERSHIP_ORDERS, "rule"
    if code.endswith("_Exchange") or code.endswith("_exchange"):
        return GROUP_AFTERSHIP, SUB_MANUAL_EXCHANGE, "rule"
    if code.lower().startswith("welcome-"):
        return GROUP_KLAVIYO, SUB_WELCOME, "rule"
    if code.lower().startswith("fs-"):
        return GROUP_KLAVIYO, SUB_FREE_SHIPPING, "rule"
    if WINBACK_RE.match(code):
        return GROUP_KLAVIYO, SUB_WINBACK, "rule"
    if CDLP_CARE_RE.match(code):
        return GROUP_CARE, SUB_NAMED_CARE, "rule"
    if " " in code:
        return GROUP_CARE, SUB_MANUAL_DISCOUNT, "rule"
    return GROUP_OTHER, code or "Unspecified", "unknown"


def _money(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, dict):
        value = value.get("amount") or value.get("value") or value.get("shopMoney") or 0
        if isinstance(value, dict):
            value = value.get("amount") or 0
    text = str(value).strip().replace("\u00a0", "").replace(",", "")
    if not text or text.lower() in {"nan", "none", "null"}:
        return 0.0
    try:
        return abs(float(text))
    except ValueError:
        return 0.0


def _orders(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, dict):
        value = value.get("value") or value.get("amount") or 0
    try:
        return abs(float(str(value).strip().replace(",", "") or 0))
    except ValueError:
        return 0.0


def _cell(row: Any, columns: Sequence[str], name: str) -> Any:
    key = name.lower()
    if isinstance(row, dict):
        for candidate in (name, key, name.replace("_", " ")):
            if candidate in row:
                return row[candidate]
        for k, v in row.items():
            if str(k).lower().replace(" ", "_") == key:
                return v
        return None
    if isinstance(row, (list, tuple)):
        for i, col in enumerate(columns):
            if str(col).lower().replace(" ", "_") == key and i < len(row):
                return row[i]
    return None


def rows_from_shopifyql_table(table: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Normalise ShopifyQL tableData into daily discount rows (amounts positive)."""
    raw_cols = table.get("columns") or []
    columns: List[str] = []
    for col in raw_cols:
        if isinstance(col, dict):
            columns.append(str(col.get("name") or col.get("displayName") or "").strip())
        else:
            columns.append(str(col).strip())
    rows_out: List[Dict[str, Any]] = []
    for raw in table.get("rows") or []:
        day = _cell(raw, columns, "day") or _cell(raw, columns, "date")
        name = _cell(raw, columns, "discount_name") or _cell(raw, columns, "discount_title")
        if day is None or name is None:
            continue
        day_s = str(day).strip()[:10]
        code = str(name).strip()
        if not day_s or not code or code.lower() in {"nan", "none", "null"}:
            continue
        rows_out.append(
            {
                "date": day_s,
                "code_or_title": code,
                "orders": _orders(_cell(raw, columns, "orders")),
                "gross_sales_usd": _money(_cell(raw, columns, "gross_sales")),
                "discount_amount_usd": _money(_cell(raw, columns, "discounts")),
            }
        )
    return rows_out


def classify_rows(
    rows: Iterable[Dict[str, Any]],
    mapping: Optional[Dict[str, Tuple[str, str]]] = None,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    classified: List[Dict[str, Any]] = []
    unknown: List[str] = []
    seen_unknown: set = set()
    for row in rows:
        code = str(row.get("code_or_title") or "").strip()
        group, subgroup, source = classify_discount_code(code, mapping)
        classified.append(
            {
                "date": str(row.get("date") or "")[:10],
                "group": group,
                "subgroup": subgroup,
                "code_or_title": code,
                "orders": _orders(row.get("orders")),
                "gross_sales_usd": _money(row.get("gross_sales_usd")),
                "discount_amount_usd": _money(row.get("discount_amount_usd")),
                "_source": source,
            }
        )
        if source == "unknown" and code not in seen_unknown:
            seen_unknown.add(code)
            unknown.append(code)
    return classified, unknown


def week_csv_name(start: str, end: str) -> str:
    return f"discount_groups_daily_{start}_to_{end}.csv"


def write_discount_groups_csv(path: Path, rows: Sequence[Dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in CSV_COLUMNS})
    return path


def save_week_csv(data_root: Path, base_week: str, rows: Sequence[Dict[str, Any]], start: str, end: str) -> Path:
    """Write into the shared slot and the selected week folder (later file wins on merge)."""
    name = week_csv_name(start, end)
    shared = Path(data_root) / "discount_types" / name
    write_discount_groups_csv(shared, rows)
    week_dir = Path(data_root) / "raw" / base_week / "discount_types"
    week_path = week_dir / name
    if week_path.resolve() != shared.resolve():
        write_discount_groups_csv(week_path, rows)
    return shared


def _graphql(shop: str, token: str, query: str, timeout: int = 60) -> Dict[str, Any]:
    version = shopify_api_version()
    url = f"https://{shop}/admin/api/{version}/graphql.json"
    body = json.dumps({"query": query}).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": token,
        "Accept": "application/json",
        "User-Agent": "ohjay-weekly-report/shopifyql",
    }
    last_err: Optional[Exception] = None
    for attempt in range(4):
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            last_err = exc
            payload = exc.read().decode("utf-8", errors="replace")[:400]
            if exc.code in (429, 503) and attempt < 3:
                time.sleep(min(2 ** attempt, 16))
                continue
            raise RuntimeError(f"Shopify HTTP {exc.code}: {payload}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            last_err = exc
            if attempt < 3:
                time.sleep(min(2 ** attempt, 16))
                continue
            raise RuntimeError(f"Shopify network error: {exc}") from exc
    raise RuntimeError(f"Shopify request failed: {last_err}")


def fetch_shopifyql_rows(ql: str) -> List[Dict[str, Any]]:
    shop = shopify_shop()
    token = shopify_token()
    if not shop or not token:
        raise RuntimeError("Shopify Admin API is not configured (set SHOPIFY_SHOP and SHOPIFY_ACCESS_TOKEN)")
    # Inline the query string — some Admin API versions reject variables on shopifyqlQuery.
    escaped = json.dumps(ql)
    gql = (
        "{ shopifyqlQuery(query: %s) { parseErrors tableData { columns { name dataType displayName } rows } } }"
        % escaped
    )
    payload = _graphql(shop, token, gql)
    errors = payload.get("errors") or []
    if errors:
        msg = errors[0].get("message") if isinstance(errors[0], dict) else str(errors[0])
        raise RuntimeError(f"Shopify GraphQL error: {msg}")
    block = ((payload.get("data") or {}).get("shopifyqlQuery")) or {}
    parse_errors = block.get("parseErrors") or []
    if parse_errors:
        raise RuntimeError(f"ShopifyQL parse error: {parse_errors}")
    table = block.get("tableData") or {}
    return rows_from_shopifyql_table(table)


def fetch_and_save_week(
    base_week: str,
    data_root: Path,
    *,
    mapping_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Pull the selected week from ShopifyQL, classify, save, return a public summary."""
    if not shopify_configured():
        return {
            "ok": False,
            "reason": "not_configured",
            "error": (
                "Shopify Admin API is not configured. Set SHOPIFY_SHOP (or SHOPIFY_STORE) "
                "and SHOPIFY_ACCESS_TOKEN (or SHOPIFY_ADMIN_API_TOKEN) on the backend."
            ),
        }
    ql, start, end = shopifyql_query_for_week(base_week)
    try:
        raw_rows = fetch_shopifyql_rows(ql)
    except Exception as exc:
        logger.warning(f"ShopifyQL discount pull failed for {base_week}: {exc}")
        return {"ok": False, "reason": "fetch_failed", "error": str(exc), "query": ql, "start": start, "end": end}

    mapping = load_code_mapping(mapping_path)
    classified, unknown = classify_rows(raw_rows, mapping)
    path = save_week_csv(Path(data_root), base_week, classified, start, end)
    logger.info(f"ShopifyQL discount week {base_week} saved {path} ({len(classified)} rows)")
    return {
        "ok": True,
        "reason": "fetched",
        "week": base_week,
        "start": start,
        "end": end,
        "query": ql,
        "rows": len(classified),
        "unknown_codes": unknown,
        "file": path.name,
        "path": str(path),
    }


def week_days_covered(daily_dates: Iterable[str], start: str, end: str) -> bool:
    """True when every calendar day Mon–Sun is present in the daily dates."""
    import pandas as pd

    have = {str(d)[:10] for d in daily_dates if d}
    needed = {d.strftime("%Y-%m-%d") for d in pd.date_range(start, end, freq="D")}
    return bool(needed) and needed.issubset(have)


def maybe_fetch_week(
    base_week: str,
    data_root: Path,
    daily_dates: Optional[Iterable[str]] = None,
    *,
    force: bool = False,
) -> Dict[str, Any]:
    """Fetch when credentials exist and the week is not already fully covered, unless forced."""
    rng = get_week_date_range(base_week)
    if not force and daily_dates is not None and week_days_covered(daily_dates, rng["start"], rng["end"]):
        return {"ok": True, "reason": "already_covered", "start": rng["start"], "end": rng["end"]}
    if not shopify_configured():
        return {
            "ok": False,
            "reason": "not_configured",
            "error": (
                "Shopify Admin API is not configured. Set SHOPIFY_SHOP and "
                "SHOPIFY_ACCESS_TOKEN on the backend, then use Fetch week on Settings."
            ),
            "start": rng["start"],
            "end": rng["end"],
        }
    return fetch_and_save_week(base_week, data_root)
