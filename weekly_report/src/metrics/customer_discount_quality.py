"""Customer discount quality metrics based on Shopify data."""

from __future__ import annotations

from dataclasses import dataclass
import math
from datetime import datetime, timedelta
from pathlib import Path
from datetime import timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd
from loguru import logger

from weekly_report.src.metrics.discounts_sales import _read_csv_flexible
from weekly_report.src.periods.calculator import get_week_date_range


MARKDOWN_TOLERANCE = 0.01


def _normalize_col_name(col: str) -> str:
    return str(col or "").strip().lower().replace(" ", "").replace("_", "").replace("-", "")


def _pick_column(df: pd.DataFrame, candidates: Iterable[str]) -> Optional[str]:
    if df is None or df.empty:
        return None
    norm_map = {_normalize_col_name(c): c for c in df.columns}
    for cand in candidates:
        key = _normalize_col_name(cand)
        if key in norm_map:
            return norm_map[key]
    # fallback: contains match (use first unique)
    for cand in candidates:
        key = _normalize_col_name(cand)
        hits = [orig for norm, orig in norm_map.items() if key and key in norm]
        if len(hits) == 1:
            return hits[0]
    return None


def _to_number(series: pd.Series) -> pd.Series:
    if series is None:
        return pd.Series(dtype=float)
    def _parse(v: Any) -> float:
        try:
            if pd.isna(v):
                return 0.0
            if isinstance(v, (int, float)):
                return float(v)
            s = str(v).strip()
            if s == "":
                return 0.0
            s = s.replace(" ", "").replace("%", "")
            if s.startswith("(") and s.endswith(")"):
                s = "-" + s[1:-1]
            if "," in s and "." in s:
                s = s.replace(",", "")
            elif "," in s and "." not in s:
                parts = s.split(",")
                if all(len(p) == 3 for p in parts[1:]):
                    s = "".join(parts)
                else:
                    s = s.replace(",", ".")
            return float(s)
        except Exception:
            return 0.0
    return series.map(_parse)


def _safe_div(n: float, d: float) -> float:
    return float(n) / float(d) if d else 0.0


@dataclass
class DiscountQualityConfig:
    cohort_window_days: int = 365
    threshold_low: float = 0.2
    threshold_high: float = 0.8


def _load_discounts_df(base_week: str, data_root: str) -> pd.DataFrame:
    data_path = Path(data_root)
    raw_path = data_path / "raw" / base_week / "discounts"
    files = [f for f in raw_path.glob("*.*") if f.is_file() and not f.name.startswith(".")]
    if not files:
        return pd.DataFrame()
    latest_file = max(files, key=lambda f: f.stat().st_mtime)
    df = _read_csv_flexible(latest_file)
    df.columns = [c.strip().replace('"', "") for c in df.columns]
    return df


def get_discounts_source_signature(base_week: str, data_root: str) -> Dict[str, Any]:
    """Return a lightweight signature for the Discounts source to invalidate caches safely."""
    data_path = Path(data_root)
    raw_path = data_path / "raw" / base_week / "discounts"
    files = [f for f in raw_path.glob("*.*") if f.is_file() and not f.name.startswith(".")]
    if not files:
        return {"filename": None, "mtime": None}
    latest_file = max(files, key=lambda f: f.stat().st_mtime)
    return {"filename": latest_file.name, "mtime": int(latest_file.stat().st_mtime)}


_CONTEXT_CACHE: Dict[str, Dict[str, Any]] = {}
_CONTEXT_CACHE_TTL = timedelta(minutes=30)


def build_discount_quality_context_cached(
    base_week: str,
    data_root: str,
    cfg: DiscountQualityConfig,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    sig = get_discounts_source_signature(base_week, data_root)
    cache_key = f"{data_root}|{base_week}|{cfg.cohort_window_days}|{cfg.threshold_low}|{cfg.threshold_high}|{sig.get('mtime')}"
    entry = _CONTEXT_CACHE.get(cache_key)
    if entry and datetime.utcnow() - entry["ts"] < _CONTEXT_CACHE_TTL:
        return entry["orders"], entry["customers"], entry["meta"]
    orders, customers, meta = build_discount_quality_context(base_week, data_root, cfg)
    meta["source_signature"] = sig
    _CONTEXT_CACHE[cache_key] = {"ts": datetime.utcnow(), "orders": orders, "customers": customers, "meta": meta}
    return orders, customers, meta


def _select_currency(df: pd.DataFrame) -> Tuple[pd.DataFrame, Optional[str], Optional[str]]:
    currency_col = _pick_column(df, ["Currency", "Presentment currency", "Currency code"])
    if not currency_col:
        return df, None, None
    cur_vals = df[currency_col].astype(str).str.strip()
    cur_vals = cur_vals[cur_vals.notna() & (cur_vals != "") & (cur_vals != "nan")]
    if cur_vals.empty:
        return df, None, None
    counts = cur_vals.value_counts()
    if len(counts) <= 1:
        return df, counts.index[0], None
    selected = counts.index[0]
    filtered = df[df[currency_col].astype(str).str.strip() == selected].copy()
    warning = f"Multiple currencies detected; filtered to {selected}"
    return filtered, selected, warning


def _is_gift_card_row(df: pd.DataFrame) -> pd.Series:
    name_col = _pick_column(df, ["Lineitem name", "Line item name", "Product", "Title", "Item", "Name"])
    type_col = _pick_column(df, ["Product type", "Produkttyp", "Lineitem product type", "Product Type"])
    name = df[name_col].astype(str).str.lower() if name_col else pd.Series("", index=df.index)
    ptype = df[type_col].astype(str).str.lower() if type_col else pd.Series("", index=df.index)
    return name.str.contains("gift card", na=False) | ptype.str.contains("gift card", na=False)


def _build_order_level(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    df = df.copy()
    meta: Dict[str, Any] = {}

    date_col = _pick_column(df, ["Created at", "Order date", "Date", "Day", "Dag", "Processed at", "Created At"])
    order_col = _pick_column(df, ["Order-ID", "Order ID", "Order Id", "Order", "Order name", "Order Name", "Name", "Order number", "Order Number", "Ordernummer", "Beställning"])
    customer_col = _pick_column(
        df,
        [
            "Customer ID",
            "Customer Id",
            "Kund-ID",
            "Kund ID",
            "Kundid",
            "Customer Email",
            "Customer E-mail",
            "Email",
            "E-mail",
            "Customer",
        ],
    )

    if not date_col or not order_col or not customer_col:
        meta["missing"] = {"date": date_col, "order": order_col, "customer": customer_col}
        return pd.DataFrame(), meta

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])
    df["_order_id"] = df[order_col].astype(str).str.strip()
    df["_customer_id"] = df[customer_col].astype(str).str.strip().str.lower()

    price_col = _pick_column(df, ["Produktvariantpris", "Lineitem price", "Line item price", "Price"])
    qty_col = _pick_column(df, ["Nettoantal sålda artiklar", "Lineitem quantity", "Line item quantity", "Quantity", "Qty"])
    compare_col = _pick_column(df, ["Produktvariantens ordinarie pris", "Lineitem compare at price", "Compare at price", "Compare-at price"])
    line_discount_col = _pick_column(df, ["Rabatter", "Lineitem discount", "Line item discount", "Lineitem discount amount", "Line item discount amount"])
    cost_col = _pick_column(df, ["Cost", "Cost per item", "Lineitem cost", "Line item cost", "COGS", "Cost of goods", "Cost per item amount"])
    gross_col = _pick_column(df, ["Bruttoförsäljning", "Gross sales", "Gross Sales", "Subtotal", "Subtotal price"])
    net_col = _pick_column(df, ["Nettoförsäljning", "Net sales", "Net Sales", "Net revenue", "Net Revenue", "Total sales", "Total", "Net amount"])
    discounts_col = _pick_column(df, ["Rabatter", "Total discounts", "Discounts", "Discount amount", "Total Discounts", "Order discounts"])
    refunds_col = _pick_column(df, ["Refunds", "Refunded amount", "Total refunds", "Returns", "Returned"])
    discount_code_col = _pick_column(df, ["Discount code", "Discount codes", "Discount Code", "Discount Codes"])
    discount_app_col = _pick_column(df, ["Discount applications", "Discount application", "Discount Application", "Discount applications"])

    meta["columns_used"] = {
        "date": date_col,
        "order": order_col,
        "customer": customer_col,
        "price": price_col,
        "quantity": qty_col,
        "compare_at": compare_col,
        "cost": cost_col,
        "gross_sales": gross_col,
        "net_sales": net_col,
        "total_discounts": discounts_col,
        "refunds": refunds_col,
        "discount_code": discount_code_col,
        "discount_applications": discount_app_col,
    }

    is_line_level = price_col is not None and qty_col is not None
    if is_line_level:
        df["_price"] = _to_number(df[price_col])
        df["_qty"] = _to_number(df[qty_col]).clip(lower=0)
        df["_gross_line"] = df["_price"] * df["_qty"]
        if compare_col:
            df["_compare_at"] = _to_number(df[compare_col])
        else:
            df["_compare_at"] = 0.0
        df["_has_markdown_line"] = (
            (df["_compare_at"] > 0)
            & (df["_price"] > 0)
            & (df["_compare_at"] > df["_price"] * (1 + MARKDOWN_TOLERANCE))
        )
        df["_markdown_depth_line"] = ((df["_compare_at"] - df["_price"]) / df["_compare_at"]).fillna(0.0)
        df["_markdown_amount_line"] = (df["_compare_at"] - df["_price"]).clip(lower=0) * df["_qty"]
        df.loc[~df["_has_markdown_line"], "_markdown_amount_line"] = 0.0

        df["_line_discount"] = _to_number(df[line_discount_col]).abs() if line_discount_col else 0.0
        if cost_col:
            df["_cost_line"] = _to_number(df[cost_col]).clip(lower=0) * df["_qty"]
        else:
            df["_cost_line"] = float("nan")

        is_gift_card = _is_gift_card_row(df)
        df = df[~is_gift_card].copy()
        meta["gift_card_excluded"] = int(is_gift_card.sum())

        line_agg = df.groupby("_order_id").agg(
            order_date=(date_col, "min"),
            customer_id=("_customer_id", "first"),
            gross_sales=("_gross_line", "sum"),
            has_markdown=("_has_markdown_line", "max"),
            markdown_depth=("_markdown_depth_line", "mean"),
            markdown_discount_amount=("_markdown_amount_line", "sum"),
            line_discounts=("_line_discount", "sum"),
            cogs=("_cost_line", lambda s: s.sum(min_count=1)),
        )
    else:
        line_agg = df.groupby("_order_id").agg(
            order_date=(date_col, "min"),
            customer_id=("_customer_id", "first"),
        )
        line_agg["gross_sales"] = _to_number(df[gross_col]).groupby(df["_order_id"]).first() if gross_col else 0.0
        line_agg["has_markdown"] = False
        line_agg["markdown_depth"] = 0.0
        line_agg["markdown_discount_amount"] = 0.0
        line_agg["line_discounts"] = 0.0
        line_agg["cogs"] = _to_number(df[cost_col]).groupby(df["_order_id"]).first() if cost_col else float("nan")

    # Order-level totals
    if discounts_col:
        order_discounts = _to_number(df[discounts_col]).abs().groupby(df["_order_id"]).first()
    else:
        order_discounts = line_agg["line_discounts"]
    if refunds_col:
        order_refunds = _to_number(df[refunds_col]).groupby(df["_order_id"]).first()
    else:
        order_refunds = 0.0

    if net_col:
        order_net = _to_number(df[net_col]).groupby(df["_order_id"]).first()
    else:
        order_net = line_agg["gross_sales"] - order_discounts - order_refunds

    if discount_code_col:
        has_code = df[discount_code_col].astype(str).str.strip().replace({"nan": ""}).groupby(df["_order_id"]).first()
        has_code = has_code.apply(lambda v: bool(v))
    else:
        has_code = pd.Series(False, index=line_agg.index)
    if discount_app_col:
        has_app = df[discount_app_col].astype(str).str.strip().replace({"nan": ""}).groupby(df["_order_id"]).first()
        has_app = has_app.apply(lambda v: bool(v))
    else:
        has_app = pd.Series(False, index=line_agg.index)

    order_df = line_agg.copy()
    order_df["total_discounts"] = order_discounts
    order_df["refunds"] = order_refunds
    order_df["net_sales"] = order_net
    order_df["has_code_or_auto_discount"] = (order_discounts > 0) | has_code | has_app
    order_df["is_discounted_order"] = order_df["has_code_or_auto_discount"] | order_df["has_markdown"]
    order_df["is_full_price_order"] = ~order_df["is_discounted_order"]
    order_df["order_discount_rate"] = order_df.apply(
        lambda r: _safe_div(float(r["total_discounts"]), float(r["gross_sales"])), axis=1
    )
    order_df["order_discount_amount"] = order_df["total_discounts"] + order_df["markdown_discount_amount"]
    order_df["gross_profit"] = order_df["net_sales"] - order_df["cogs"]
    order_df["order_id"] = order_df.index
    order_df = order_df.reset_index(drop=True)
    return order_df, meta


def _build_customer_features(order_df: pd.DataFrame, cfg: DiscountQualityConfig) -> pd.DataFrame:
    if order_df.empty:
        return pd.DataFrame()

    order_df = order_df.copy()
    order_df["order_date"] = pd.to_datetime(order_df["order_date"], errors="coerce")
    order_df = order_df.dropna(subset=["order_date"])

    first_orders = order_df.sort_values("order_date").groupby("customer_id").first().reset_index()
    first_orders = first_orders.rename(columns={"order_date": "first_order_date", "is_discounted_order": "first_order_is_discounted"})

    merged = order_df.merge(first_orders[["customer_id", "first_order_date", "first_order_is_discounted"]], on="customer_id", how="left")
    window_end = merged["first_order_date"] + pd.to_timedelta(cfg.cohort_window_days, unit="D")
    in_window = merged["order_date"] <= window_end
    merged = merged[in_window].copy()

    merged["is_discounted_order"] = merged["is_discounted_order"].astype(bool)

    def _orders_in_days(days: int) -> pd.Series:
        limit = merged["first_order_date"] + pd.to_timedelta(days, unit="D")
        return merged[merged["order_date"] <= limit].groupby("customer_id")["order_id"].nunique()

    def _full_orders_in_days(days: int) -> pd.Series:
        limit = merged["first_order_date"] + pd.to_timedelta(days, unit="D")
        sub = merged[(merged["order_date"] <= limit) & (~merged["is_discounted_order"])]
        return sub.groupby("customer_id")["order_id"].nunique()

    def _discount_orders_in_days(days: int) -> pd.Series:
        limit = merged["first_order_date"] + pd.to_timedelta(days, unit="D")
        sub = merged[(merged["order_date"] <= limit) & (merged["is_discounted_order"])]
        return sub.groupby("customer_id")["order_id"].nunique()

    orders_count = merged.groupby("customer_id")["order_id"].nunique()
    discounted_orders = merged[merged["is_discounted_order"]].groupby("customer_id")["order_id"].nunique()
    full_orders = merged[~merged["is_discounted_order"]].groupby("customer_id")["order_id"].nunique()
    discounted_rev = merged[merged["is_discounted_order"]].groupby("customer_id")["net_sales"].sum()
    full_rev = merged[~merged["is_discounted_order"]].groupby("customer_id")["net_sales"].sum()
    total_rev = merged.groupby("customer_id")["net_sales"].sum()

    avg_discount_rate = (
        merged[merged["is_discounted_order"]]
        .groupby("customer_id")
        .apply(lambda g: _safe_div((g["order_discount_rate"] * g["gross_sales"]).sum(), g["gross_sales"].sum()))
    )

    def _aov(mask: pd.Series) -> pd.Series:
        sub = merged[mask]
        return sub.groupby("customer_id")["net_sales"].mean()

    aov_discount = _aov(merged["is_discounted_order"])
    aov_full = _aov(~merged["is_discounted_order"])

    # time to second order
    order_sorted = merged.sort_values(["customer_id", "order_date"])
    second_order = order_sorted.groupby("customer_id")["order_date"].nth(1)
    first_order = order_sorted.groupby("customer_id")["order_date"].nth(0)
    time_to_second = (second_order - first_order).dt.days

    # time to first full/discounted order after first
    def _time_to_first(mask: pd.Series) -> pd.Series:
        sub = merged[mask].sort_values(["customer_id", "order_date"])
        first_sub = sub.groupby("customer_id")["order_date"].min()
        return (first_sub - first_order).dt.days

    time_to_first_full = _time_to_first(~merged["is_discounted_order"])
    time_to_first_discount = _time_to_first(merged["is_discounted_order"])

    customer_df = pd.DataFrame({
        "customer_id": orders_count.index,
        "orders_count_in_window": orders_count,
        "discounted_orders": discounted_orders.reindex(orders_count.index).fillna(0),
        "full_orders": full_orders.reindex(orders_count.index).fillna(0),
        "discounted_revenue": discounted_rev.reindex(orders_count.index).fillna(0.0),
        "full_price_revenue": full_rev.reindex(orders_count.index).fillna(0.0),
        "total_revenue": total_rev.reindex(orders_count.index).fillna(0.0),
    }).reset_index(drop=True)

    customer_df["discounted_order_share"] = customer_df.apply(
        lambda r: _safe_div(r["discounted_orders"], r["orders_count_in_window"]), axis=1
    )
    customer_df["discounted_revenue_share"] = customer_df.apply(
        lambda r: _safe_div(r["discounted_revenue"], r["total_revenue"]), axis=1
    )
    customer_df["full_price_revenue_share"] = customer_df.apply(
        lambda r: _safe_div(r["full_price_revenue"], r["total_revenue"]), axis=1
    )
    customer_df["avg_discount_rate_on_discounted_orders"] = avg_discount_rate.reindex(orders_count.index).fillna(0.0).values
    customer_df["time_to_second_order_days"] = time_to_second.reindex(orders_count.index).values
    customer_df["time_to_first_full_price_order_days"] = time_to_first_full.reindex(orders_count.index).values
    customer_df["time_to_first_discounted_order_days"] = time_to_first_discount.reindex(orders_count.index).values
    customer_df["aov_discounted"] = aov_discount.reindex(orders_count.index).fillna(0.0).values
    customer_df["aov_full_price"] = aov_full.reindex(orders_count.index).fillna(0.0).values

    # repeat flags
    for days in (90, 180, 365):
        count = _orders_in_days(days).reindex(orders_count.index).fillna(0)
        customer_df[f"repeat_rate_{days}d"] = (count >= 2).astype(int)
        full_count = _full_orders_in_days(days).reindex(orders_count.index).fillna(0)
        customer_df[f"full_order_within_{days}d"] = (full_count >= 1).astype(int)
        disc_count = _discount_orders_in_days(days).reindex(orders_count.index).fillna(0)
        customer_df[f"discount_order_within_{days}d"] = (disc_count >= 1).astype(int)

    customer_df = customer_df.merge(first_orders, on="customer_id", how="left")
    return customer_df


def _segment_customers(customer_df: pd.DataFrame, cfg: DiscountQualityConfig) -> pd.DataFrame:
    if customer_df.empty:
        return customer_df

    def _segment(row: pd.Series) -> str:
        if row["orders_count_in_window"] == 1:
            return "One-and-Done"
        if row["first_order_is_discounted"]:
            if row["discounted_order_share"] >= cfg.threshold_high:
                return "Bargain Hunter"
            if row["discounted_order_share"] <= cfg.threshold_low:
                return "Promo-to-Full-Price Converter"
            return "Hybrid Buyer"
        else:
            if row["discounted_order_share"] >= cfg.threshold_high:
                return "Full-Price-to-Promo Drifter"
            return "Full-Price Loyalist"

    customer_df = customer_df.copy()
    customer_df["acquisition_mode"] = customer_df["first_order_is_discounted"].apply(lambda v: "Discount_Acquired" if v else "FP_Acquired")
    customer_df["segment"] = customer_df.apply(_segment, axis=1)
    customer_df["one_and_done"] = customer_df["orders_count_in_window"] == 1
    return customer_df


def build_discount_quality_context(
    base_week: str,
    data_root: str,
    cfg: DiscountQualityConfig,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    discounts_df = _load_discounts_df(base_week, data_root)
    if discounts_df.empty:
        return pd.DataFrame(), pd.DataFrame(), {"error": "No Discounts data found"}

    discounts_df, currency, currency_warning = _select_currency(discounts_df)

    end_dt = pd.to_datetime(get_week_date_range(base_week)["end"], errors="coerce")
    if pd.notna(end_dt):
        date_col = _pick_column(discounts_df, ["Created at", "Order date", "Date", "Day", "Dag", "Processed at", "Created At"])
        if date_col:
            discounts_df[date_col] = pd.to_datetime(discounts_df[date_col], errors="coerce")
            discounts_df = discounts_df[discounts_df[date_col] <= end_dt]

    order_df, meta = _build_order_level(discounts_df)
    if order_df.empty:
        return pd.DataFrame(), pd.DataFrame(), {"error": "Missing required columns for orders", "detected": meta.get("missing"), "columns_used": meta.get("columns_used")}

    customer_df = _build_customer_features(order_df, cfg)
    customer_df = _segment_customers(customer_df, cfg)

    if pd.notna(end_dt) and not customer_df.empty:
        cohort_start = end_dt - pd.to_timedelta(cfg.cohort_window_days, unit="D")
        customer_df = customer_df[pd.to_datetime(customer_df["first_order_date"], errors="coerce") >= cohort_start]

    meta.update({"currency": currency, "currency_warning": currency_warning})
    return order_df, customer_df, meta


def compute_overview(order_df: pd.DataFrame, customer_df: pd.DataFrame) -> Dict[str, Any]:
    if order_df.empty or customer_df.empty:
        return {}
    total_orders = order_df["order_id"].nunique()
    discounted_orders = order_df[order_df["is_discounted_order"]]["order_id"].nunique()
    discounted_rev = float(order_df[order_df["is_discounted_order"]]["net_sales"].sum() or 0.0)
    total_rev = float(order_df["net_sales"].sum() or 0.0)
    avg_disc_rate = (
        order_df[order_df["is_discounted_order"]]
        .apply(lambda r: r["order_discount_rate"] * r["gross_sales"], axis=1)
        .sum()
    )
    disc_gross = float(order_df[order_df["is_discounted_order"]]["gross_sales"].sum() or 0.0)
    avg_disc_rate = _safe_div(avg_disc_rate, disc_gross)

    new_customers = customer_df["customer_id"].nunique()
    discount_acquired = customer_df[customer_df["first_order_is_discounted"]]["customer_id"].nunique()
    bargain_hunters = customer_df[customer_df["segment"] == "Bargain Hunter"]["customer_id"].nunique()

    return {
        "total_orders": total_orders,
        "discounted_order_pct": _safe_div(discounted_orders, total_orders) * 100.0,
        "discounted_revenue_share": _safe_div(discounted_rev, total_rev) * 100.0,
        "avg_order_discount_rate": avg_disc_rate * 100.0,
        "pct_new_customers_discount_acquired": _safe_div(discount_acquired, new_customers) * 100.0,
        "pct_customers_bargain_hunters": _safe_div(bargain_hunters, new_customers) * 100.0,
    }


def compute_cohorts(customer_df: pd.DataFrame, granularity: str = "month") -> List[Dict[str, Any]]:
    if customer_df.empty:
        return []
    df = customer_df.copy()
    first = pd.to_datetime(df["first_order_date"], errors="coerce")
    if granularity == "week":
        iso = first.dt.isocalendar()
        df["cohort"] = iso["year"].astype(str) + "-" + iso["week"].astype(str).str.zfill(2)
    else:
        df["cohort"] = first.dt.to_period("M").astype(str)

    cohort_rows: List[Dict[str, Any]] = []
    for cohort, sub in df.groupby("cohort"):
        total = len(sub)
        if not total:
            continue
        discount_acq = sub[sub["first_order_is_discounted"]].shape[0]
        segments = sub["segment"].value_counts().to_dict()
        cohort_rows.append(
            {
                "cohort": str(cohort),
                "customers": total,
                "pct_discount_acquired": _safe_div(discount_acq, total) * 100.0,
                "pct_fp_acquired": _safe_div(total - discount_acq, total) * 100.0,
                "segments": {k: _safe_div(v, total) * 100.0 for k, v in segments.items()},
            }
        )
    cohort_rows.sort(key=lambda x: x["cohort"], reverse=True)
    return cohort_rows


def compute_conversion(customer_df: pd.DataFrame) -> Dict[str, Any]:
    if customer_df.empty:
        return {}
    discount_acq = customer_df[customer_df["acquisition_mode"] == "Discount_Acquired"]
    if discount_acq.empty:
        return {}
    median_time = discount_acq[discount_acq["full_orders"] > 0]["time_to_first_full_price_order_days"].median()
    def _clean(val: Any, default: float = 0.0) -> float:
        try:
            return float(val) if pd.notna(val) and math.isfinite(float(val)) else float(default)
        except Exception:
            return float(default)
    return {
        "size": int(len(discount_acq)),
        "pct_full_price_90d": _clean(discount_acq["full_order_within_90d"].mean() * 100.0),
        "pct_full_price_180d": _clean(discount_acq["full_order_within_180d"].mean() * 100.0),
        "pct_full_price_365d": _clean(discount_acq["full_order_within_365d"].mean() * 100.0),
        "median_time_to_full_price_days": float(median_time) if pd.notna(median_time) and math.isfinite(float(median_time)) else None,
        "full_price_revenue_share": _clean(discount_acq["full_price_revenue_share"].mean() * 100.0),
    }


def compute_drift(customer_df: pd.DataFrame, threshold_high: float) -> Dict[str, Any]:
    if customer_df.empty:
        return {}
    fp_acq = customer_df[customer_df["acquisition_mode"] == "FP_Acquired"]
    if fp_acq.empty:
        return {}
    drifted = fp_acq[fp_acq["discounted_order_share"] >= threshold_high]
    time_to_discount = fp_acq[fp_acq["discounted_orders"] > 0]["time_to_first_discounted_order_days"].median()
    def _clean(val: Any, default: float = 0.0) -> float:
        try:
            return float(val) if pd.notna(val) and math.isfinite(float(val)) else float(default)
        except Exception:
            return float(default)
    return {
        "size": int(len(fp_acq)),
        "pct_discount_dominant": _clean(_safe_div(len(drifted), len(fp_acq)) * 100.0),
        "median_time_to_first_discount_days": float(time_to_discount) if pd.notna(time_to_discount) and math.isfinite(float(time_to_discount)) else None,
    }


def _parse_date(value: Optional[str]) -> Optional[pd.Timestamp]:
    if not value:
        return None
    dt = pd.to_datetime(value, errors="coerce")
    return None if pd.isna(dt) else dt.normalize()


def _filter_discounts_df(
    df: pd.DataFrame,
    *,
    as_of_date: Optional[pd.Timestamp] = None,
    date_from: Optional[pd.Timestamp] = None,
    date_to: Optional[pd.Timestamp] = None,
    market: Optional[str] = None,
    country: Optional[str] = None,
    category: Optional[str] = None,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    meta: Dict[str, Any] = {"filters": {}}
    if df.empty:
        return df, meta

    date_col = _pick_column(df, ["Created at", "Order date", "Date", "Day", "Dag", "Processed at", "Created At"])
    if date_col:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        if as_of_date is not None:
            df = df[df[date_col] <= as_of_date]
            meta["filters"]["as_of_date"] = as_of_date.date().isoformat()
        if date_from is not None:
            df = df[df[date_col] >= date_from]
            meta["filters"]["date_from"] = date_from.date().isoformat()
        if date_to is not None:
            df = df[df[date_col] <= date_to]
            meta["filters"]["date_to"] = date_to.date().isoformat()

    if market:
        market_col = _pick_column(df, ["Market", "Market name", "Sales channel", "Channel"])
        if market_col:
            df = df[df[market_col].astype(str).str.strip().str.lower() == market.strip().lower()]
            meta["filters"]["market"] = market
            meta["filters"]["market_col"] = market_col

    if country:
        country_col = _pick_column(df, ["Country", "Shipping country", "Ship to country", "Country/Region", "Country region"])
        if country_col:
            df = df[df[country_col].astype(str).str.strip().str.lower() == country.strip().lower()]
            meta["filters"]["country"] = country
            meta["filters"]["country_col"] = country_col

    if category:
        category_col = _pick_column(df, ["Product type", "Product category", "Category", "Product Category", "Produktkategori"])
        if category_col:
            df = df[df[category_col].astype(str).str.strip().str.lower() == category.strip().lower()]
            meta["filters"]["category"] = category
            meta["filters"]["category_col"] = category_col

    return df, meta


def build_quality_context(
    base_week: str,
    data_root: str,
    *,
    as_of_date: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    market: Optional[str] = None,
    country: Optional[str] = None,
    category: Optional[str] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    discounts_df = _load_discounts_df(base_week, data_root)
    if discounts_df.empty:
        return pd.DataFrame(), pd.DataFrame(), {"error": "No Discounts data found"}

    discounts_df, currency, currency_warning = _select_currency(discounts_df)

    as_of_dt = _parse_date(as_of_date) or pd.Timestamp(datetime.utcnow().date())
    date_from_dt = _parse_date(date_from)
    date_to_dt = _parse_date(date_to)

    discounts_df, filter_meta = _filter_discounts_df(
        discounts_df,
        as_of_date=as_of_dt,
        date_from=date_from_dt,
        date_to=date_to_dt,
        market=market,
        country=country,
        category=category,
    )

    order_df, meta = _build_order_level(discounts_df)
    if order_df.empty:
        return pd.DataFrame(), pd.DataFrame(), {"error": "Missing required columns for orders", "detected": meta.get("missing"), "columns_used": meta.get("columns_used")}

    meta.update(filter_meta)
    meta.update({"currency": currency, "currency_warning": currency_warning, "as_of_date": as_of_dt.date().isoformat()})
    return order_df, _build_first_orders(order_df), meta


def _build_first_orders(order_df: pd.DataFrame) -> pd.DataFrame:
    if order_df.empty:
        return pd.DataFrame()
    order_df = order_df.copy()
    order_df["order_date"] = pd.to_datetime(order_df["order_date"], errors="coerce")
    order_df = order_df.dropna(subset=["order_date"])
    first_orders = order_df.sort_values("order_date").groupby("customer_id").first().reset_index()
    first_orders = first_orders.rename(columns={"order_date": "first_order_date", "is_discounted_order": "first_order_is_discounted"})
    first_orders["first_order_total_discounts"] = first_orders["total_discounts"]
    first_orders["first_order_markdown_discount"] = first_orders["markdown_discount_amount"]
    first_orders["first_order_gross_sales"] = first_orders["gross_sales"]
    first_orders["first_order_net_sales"] = first_orders["net_sales"]
    first_orders["first_order_discount_depth"] = first_orders.apply(
        lambda r: _safe_div(float(r["first_order_total_discounts"] + r["first_order_markdown_discount"]), float(r["first_order_gross_sales"])),
        axis=1,
    )
    first_orders["cohort"] = pd.to_datetime(first_orders["first_order_date"], errors="coerce").dt.to_period("M").astype(str)
    first_orders["cohort_start_date"] = pd.to_datetime(first_orders["first_order_date"], errors="coerce").dt.to_period("M").dt.start_time
    return first_orders


def _compute_customer_window_metrics(order_df: pd.DataFrame, first_orders: pd.DataFrame, window_days: int) -> pd.DataFrame:
    if order_df.empty or first_orders.empty:
        return pd.DataFrame()
    merged = order_df.merge(
        first_orders[
            [
                "customer_id",
                "first_order_date",
                "first_order_is_discounted",
                "first_order_discount_depth",
                "cohort",
                "cohort_start_date",
            ]
        ],
        on="customer_id",
        how="left",
    )
    merged["first_order_date"] = pd.to_datetime(merged["first_order_date"], errors="coerce")
    window_end = merged["first_order_date"] + pd.to_timedelta(window_days, unit="D")
    merged = merged[merged["order_date"] <= window_end].copy()
    if merged.empty:
        return pd.DataFrame()

    orders_count = merged.groupby("customer_id")["order_id"].nunique()
    discounted_orders = merged.groupby("customer_id")["is_discounted_order"].sum()
    full_orders = merged.groupby("customer_id")["is_full_price_order"].sum()
    total_rev = merged.groupby("customer_id")["net_sales"].sum()
    full_rev = merged[merged["is_full_price_order"]].groupby("customer_id")["net_sales"].sum()
    gross_sales = merged.groupby("customer_id")["gross_sales"].sum()
    discount_amount = merged.groupby("customer_id")["order_discount_amount"].sum()
    gross_profit = merged.groupby("customer_id")["gross_profit"].sum(min_count=1)

    base = first_orders.set_index("customer_id")
    df = pd.DataFrame(
        {
            "customer_id": orders_count.index,
            "orders_count_in_window": orders_count,
            "discounted_orders": discounted_orders.reindex(orders_count.index).fillna(0),
            "full_orders": full_orders.reindex(orders_count.index).fillna(0),
            "total_revenue": total_rev.reindex(orders_count.index).fillna(0.0),
            "full_price_revenue": full_rev.reindex(orders_count.index).fillna(0.0),
            "gross_sales": gross_sales.reindex(orders_count.index).fillna(0.0),
            "discount_amount": discount_amount.reindex(orders_count.index).fillna(0.0),
            "gross_profit": gross_profit.reindex(orders_count.index),
        }
    ).reset_index(drop=True)

    df = df.merge(
        base[
            [
                "first_order_date",
                "first_order_is_discounted",
                "first_order_discount_depth",
                "cohort",
                "cohort_start_date",
            ]
        ],
        left_on="customer_id",
        right_index=True,
        how="left",
    )
    df["repeat_flag"] = (df["orders_count_in_window"] >= 2).astype(int)
    df["discounted_order_share"] = df.apply(
        lambda r: _safe_div(float(r["discounted_orders"]), float(r["orders_count_in_window"])), axis=1
    )
    df["full_price_revenue_share"] = df.apply(
        lambda r: _safe_div(float(r["full_price_revenue"]), float(r["total_revenue"])), axis=1
    )
    df["discount_cost_rate"] = df.apply(
        lambda r: _safe_div(float(r["discount_amount"]), float(r["gross_sales"])), axis=1
    )
    return df


def _bucket_discount_depth(depth: float) -> str:
    if depth < 0.1:
        return "0-10%"
    if depth < 0.2:
        return "10-20%"
    if depth < 0.3:
        return "20-30%"
    return "30%+"


def _compute_cohort_metrics(
    customer_window_df: pd.DataFrame,
    as_of_date: pd.Timestamp,
    window_days: int,
) -> List[Dict[str, Any]]:
    if customer_window_df.empty:
        return []

    rows: List[Dict[str, Any]] = []
    for cohort, sub in customer_window_df.groupby("cohort"):
        cohort_start = sub["cohort_start_date"].iloc[0]
        if pd.isna(cohort_start):
            continue
        cohort_age_days = int((as_of_date - cohort_start).days)
        eligible = cohort_age_days >= window_days
        customers = int(sub["customer_id"].nunique())
        metrics: Dict[str, Optional[float]] = {
            "net_sales_per_customer": None,
            "repeat_rate": None,
            "full_price_revenue_share": None,
            "discount_cost_rate": None,
            "gross_profit_per_customer": None,
        }
        if eligible and customers > 0:
            total_rev = float(sub["total_revenue"].sum() or 0.0)
            full_rev = float(sub["full_price_revenue"].sum() or 0.0)
            gross_sales = float(sub["gross_sales"].sum() or 0.0)
            discount_amount = float(sub["discount_amount"].sum() or 0.0)
            gross_profit = float(sub["gross_profit"].sum()) if sub["gross_profit"].notna().any() else None
            metrics = {
                "net_sales_per_customer": _safe_div(total_rev, customers),
                "repeat_rate": float(sub["repeat_flag"].mean() * 100.0),
                "full_price_revenue_share": _safe_div(full_rev, total_rev) * 100.0 if total_rev else None,
                "discount_cost_rate": _safe_div(discount_amount, gross_sales) * 100.0 if gross_sales else None,
                "gross_profit_per_customer": _safe_div(gross_profit, customers) if gross_profit is not None else None,
            }
        rows.append(
            {
                "cohort": str(cohort),
                "cohort_start_date": cohort_start.date().isoformat(),
                "cohort_age_days": cohort_age_days,
                "eligible": eligible,
                "customers": customers,
                "metrics": metrics,
            }
        )
    rows.sort(key=lambda r: r["cohort"])
    return rows


def _baseline_stats(values: pd.Series) -> Dict[str, Optional[float]]:
    values = values.dropna()
    if values.empty:
        return {"mean": None, "p25": None, "p75": None}
    return {
        "mean": float(values.mean()),
        "p25": float(values.quantile(0.25)),
        "p75": float(values.quantile(0.75)),
    }


def compute_quality_scorecard(
    order_df: pd.DataFrame,
    first_orders: pd.DataFrame,
    *,
    as_of_date: pd.Timestamp,
    window_days: int,
    baseline_months: int,
) -> Dict[str, Any]:
    customer_window_df = _compute_customer_window_metrics(order_df, first_orders, window_days)
    cohorts = _compute_cohort_metrics(customer_window_df, as_of_date, window_days)
    eligible = [c for c in cohorts if c["eligible"]]
    latest = eligible[-1] if eligible else None

    baseline_start = as_of_date - pd.DateOffset(months=baseline_months)
    baseline_rows = [c for c in eligible if pd.to_datetime(c["cohort_start_date"]) >= baseline_start]

    def _metric_series(metric: str) -> pd.Series:
        return pd.Series([c["metrics"].get(metric) for c in baseline_rows], dtype="float")

    baseline = {
        "net_sales_per_customer": _baseline_stats(_metric_series("net_sales_per_customer")),
        "repeat_rate": _baseline_stats(_metric_series("repeat_rate")),
        "full_price_revenue_share": _baseline_stats(_metric_series("full_price_revenue_share")),
        "discount_cost_rate": _baseline_stats(_metric_series("discount_cost_rate")),
    }
    if any(c["metrics"].get("gross_profit_per_customer") is not None for c in baseline_rows):
        baseline["gross_profit_per_customer"] = _baseline_stats(_metric_series("gross_profit_per_customer"))

    return {
        "window_days": window_days,
        "baseline_months": baseline_months,
        "latest": latest,
        "baseline": baseline,
        "trend": cohorts,
    }


def compute_discount_depth(
    order_df: pd.DataFrame,
    first_orders: pd.DataFrame,
    *,
    as_of_date: pd.Timestamp,
    window_days: int,
) -> Dict[str, Any]:
    customer_window_df = _compute_customer_window_metrics(order_df, first_orders, window_days)
    if customer_window_df.empty:
        return {"window_days": window_days, "buckets": []}
    customer_window_df = customer_window_df.copy()
    customer_window_df["cohort_age_days"] = (as_of_date - pd.to_datetime(customer_window_df["cohort_start_date"])).dt.days
    eligible = customer_window_df[customer_window_df["cohort_age_days"] >= window_days].copy()
    if eligible.empty:
        return {"window_days": window_days, "buckets": []}
    eligible["discount_depth_bucket"] = eligible["first_order_discount_depth"].fillna(0.0).apply(_bucket_discount_depth)

    rows: List[Dict[str, Any]] = []
    for bucket, sub in eligible.groupby("discount_depth_bucket"):
        customers = int(sub["customer_id"].nunique())
        if not customers:
            continue
        total_rev = float(sub["total_revenue"].sum() or 0.0)
        full_rev = float(sub["full_price_revenue"].sum() or 0.0)
        gross_sales = float(sub["gross_sales"].sum() or 0.0)
        discount_amount = float(sub["discount_amount"].sum() or 0.0)
        rows.append(
            {
                "bucket": bucket,
                "customers": customers,
                "repeat_rate": float(sub["repeat_flag"].mean() * 100.0),
                "net_sales_per_customer": _safe_div(total_rev, customers),
                "full_price_revenue_share": _safe_div(full_rev, total_rev) * 100.0 if total_rev else None,
                "discount_cost_rate": _safe_div(discount_amount, gross_sales) * 100.0 if gross_sales else None,
            }
        )
    rows.sort(key=lambda r: r["bucket"])
    return {"window_days": window_days, "buckets": rows}


def _segment_value_table(customer_window_df: pd.DataFrame, threshold_low: float, threshold_high: float) -> pd.DataFrame:
    if customer_window_df.empty:
        return customer_window_df

    def _segment(row: pd.Series) -> str:
        if row["orders_count_in_window"] == 1:
            return "One-and-Done"
        if row["first_order_is_discounted"]:
            if row["discounted_order_share"] >= threshold_high:
                return "Bargain Hunter"
            if row["discounted_order_share"] <= threshold_low:
                return "Promo-to-Full-Price Converter"
            return "Hybrid Buyer"
        else:
            if row["discounted_order_share"] >= threshold_high:
                return "Full-Price-to-Promo Drifter"
            return "Full-Price Loyalist"

    customer_window_df = customer_window_df.copy()
    customer_window_df["segment"] = customer_window_df.apply(_segment, axis=1)
    return customer_window_df


def compute_segments(
    order_df: pd.DataFrame,
    first_orders: pd.DataFrame,
    *,
    as_of_date: pd.Timestamp,
    window_days: int,
    threshold_low: float,
    threshold_high: float,
) -> Dict[str, Any]:
    customer_window_df = _compute_customer_window_metrics(order_df, first_orders, window_days)
    if customer_window_df.empty:
        return {"window_days": window_days, "segments": [], "value_metric": "net_sales"}
    customer_window_df["cohort_age_days"] = (as_of_date - pd.to_datetime(customer_window_df["cohort_start_date"])).dt.days
    eligible = customer_window_df[customer_window_df["cohort_age_days"] >= window_days].copy()
    if eligible.empty:
        return {"window_days": window_days, "segments": [], "value_metric": "net_sales"}
    eligible = _segment_value_table(eligible, threshold_low, threshold_high)

    total_customers = int(eligible["customer_id"].nunique())
    total_value = float(eligible["total_revenue"].sum() or 0.0)
    rows: List[Dict[str, Any]] = []
    for segment, sub in eligible.groupby("segment"):
        customers = int(sub["customer_id"].nunique())
        if not customers:
            continue
        total_rev = float(sub["total_revenue"].sum() or 0.0)
        full_rev = float(sub["full_price_revenue"].sum() or 0.0)
        discount_amount = float(sub["discount_amount"].sum() or 0.0)
        rows.append(
            {
                "segment": segment,
                "customers": customers,
                "customer_share": _safe_div(customers, total_customers) * 100.0 if total_customers else None,
                "net_sales_per_customer": _safe_div(total_rev, customers),
                "repeat_rate": float(sub["repeat_flag"].mean() * 100.0),
                "full_price_revenue_share": _safe_div(full_rev, total_rev) * 100.0 if total_rev else None,
                "discount_cost_per_customer": _safe_div(discount_amount, customers),
                "value_share": _safe_div(total_rev, total_value) * 100.0 if total_value else None,
            }
        )
    rows.sort(key=lambda r: r.get("net_sales_per_customer") or 0.0, reverse=True)
    return {"window_days": window_days, "segments": rows, "value_metric": "net_sales"}


def compute_pathways(
    order_df: pd.DataFrame,
    first_orders: pd.DataFrame,
    *,
    as_of_date: pd.Timestamp,
    window_days: int,
    threshold_low: float,
    threshold_high: float,
    baseline_months: int,
) -> Dict[str, Any]:
    customer_window_df = _compute_customer_window_metrics(order_df, first_orders, window_days)
    if customer_window_df.empty:
        return {"window_days": window_days, "trend": [], "baseline": {}}
    customer_window_df["cohort_age_days"] = (as_of_date - pd.to_datetime(customer_window_df["cohort_start_date"])).dt.days
    eligible = customer_window_df[customer_window_df["cohort_age_days"] >= window_days].copy()
    if eligible.empty:
        return {"window_days": window_days, "trend": [], "baseline": {}}

    rows: List[Dict[str, Any]] = []
    for cohort, sub in eligible.groupby("cohort"):
        cohort_start = sub["cohort_start_date"].iloc[0]
        cohort_age_days = int(sub["cohort_age_days"].iloc[0])
        disc_acq = sub[sub["first_order_is_discounted"]]
        fp_acq = sub[~sub["first_order_is_discounted"]]

        def _share(df: pd.DataFrame, mask: pd.Series) -> Optional[float]:
            if df.empty:
                return None
            return float(mask.mean() * 100.0)

        promo_full = _share(disc_acq, disc_acq["full_orders"] >= 1)
        promo_one = _share(disc_acq, disc_acq["orders_count_in_window"] == 1)
        promo_promo = _share(
            disc_acq,
            (disc_acq["orders_count_in_window"] >= 2) & (disc_acq["discounted_order_share"] >= threshold_high),
        )
        fp_fp = _share(
            fp_acq,
            (fp_acq["orders_count_in_window"] >= 2) & (fp_acq["discounted_order_share"] <= threshold_low),
        )
        fp_drift = _share(
            fp_acq,
            (fp_acq["orders_count_in_window"] >= 2) & (fp_acq["discounted_order_share"] >= threshold_high),
        )
        rows.append(
            {
                "cohort": str(cohort),
                "cohort_start_date": cohort_start.date().isoformat(),
                "cohort_age_days": cohort_age_days,
                "eligible": True,
                "promo_full_price_share": promo_full,
                "promo_promo_share": promo_promo,
                "promo_one_and_done_share": promo_one,
                "fp_fp_share": fp_fp,
                "fp_drift_share": fp_drift,
            }
        )
    rows.sort(key=lambda r: r["cohort"])

    baseline_start = as_of_date - pd.DateOffset(months=baseline_months)
    baseline_rows = [r for r in rows if pd.to_datetime(r["cohort_start_date"]) >= baseline_start]

    def _baseline(metric: str) -> Dict[str, Optional[float]]:
        series = pd.Series([r.get(metric) for r in baseline_rows], dtype="float")
        return _baseline_stats(series)

    baseline = {
        "promo_full_price_share": _baseline("promo_full_price_share"),
        "promo_promo_share": _baseline("promo_promo_share"),
        "promo_one_and_done_share": _baseline("promo_one_and_done_share"),
        "fp_fp_share": _baseline("fp_fp_share"),
        "fp_drift_share": _baseline("fp_drift_share"),
    }
    return {"window_days": window_days, "trend": rows, "baseline": baseline}


def compute_diagnostics(order_df: pd.DataFrame) -> Dict[str, Any]:
    if order_df.empty:
        return {}
    total = float(order_df["order_id"].nunique() or 0.0)
    if not total:
        return {}
    code_or_auto = float(order_df[order_df["has_code_or_auto_discount"]]["order_id"].nunique() or 0.0)
    markdown = float(order_df[order_df["has_markdown"]]["order_id"].nunique() or 0.0)
    either = float(order_df[order_df["is_discounted_order"]]["order_id"].nunique() or 0.0)
    return {
        "pct_code_or_auto_discounted_orders": _safe_div(code_or_auto, total) * 100.0,
        "pct_markdown_discounted_orders": _safe_div(markdown, total) * 100.0,
        "pct_any_discounted_orders": _safe_div(either, total) * 100.0,
    }


def run_basic_self_tests() -> Dict[str, Any]:
    """Basic sanity checks for discount flagging and segmentation logic."""
    orders = pd.DataFrame(
        [
            {"order_id": "1", "customer_id": "a", "order_date": "2025-01-01", "gross_sales": 100, "net_sales": 90, "is_discounted_order": True, "order_discount_rate": 0.1},
            {"order_id": "2", "customer_id": "a", "order_date": "2025-01-10", "gross_sales": 100, "net_sales": 100, "is_discounted_order": False, "order_discount_rate": 0.0},
            {"order_id": "3", "customer_id": "b", "order_date": "2025-01-05", "gross_sales": 100, "net_sales": 80, "is_discounted_order": True, "order_discount_rate": 0.2},
        ]
    )
    cfg = DiscountQualityConfig(cohort_window_days=365, threshold_low=0.2, threshold_high=0.8)
    customers = _build_customer_features(orders, cfg)
    customers = _segment_customers(customers, cfg)
    return {
        "segments": customers.set_index("customer_id")["segment"].to_dict(),
        "discounted_order_share": customers.set_index("customer_id")["discounted_order_share"].to_dict(),
    }

