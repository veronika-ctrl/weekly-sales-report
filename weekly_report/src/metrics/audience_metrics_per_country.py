"""Audience metrics per country: Total AOV, customers, return rates (overall/new/returning), COS, CAC, aMER."""
from typing import Any, Dict, List, Optional

import pandas as pd
from loguru import logger
from pathlib import Path

from weekly_report.src.metrics.discounts_sales import _normalize_customer_segment, _pick_column
from weekly_report.src.metrics.table1 import load_all_raw_data
from weekly_report.src.periods.calculator import get_week_date_range

# Lowercase Qlik/DEMA labels -> exact names used by Audience frontend (see SLUG_TO_NAME).
_COUNTRY_ALIASES_LOWER_TO_CANONICAL: Dict[str, str] = {
    # Sweden
    "sverige": "Sweden",
    "sweden": "Sweden",
    # United Kingdom
    "united kingdom": "United Kingdom",
    "uk": "United Kingdom",
    "great britain": "United Kingdom",
    "britain": "United Kingdom",
    "gb": "United Kingdom",
    "g.b.": "United Kingdom",
    "storbritannien": "United Kingdom",
    # United States
    "united states": "United States",
    "united states of america": "United States",
    "usa": "United States",
    "us": "United States",
    "u.s.": "United States",
    "u.s.a.": "United States",
    # Germany
    "germany": "Germany",
    "deutschland": "Germany",
    "tyskland": "Germany",
    "allemagne": "Germany",
    # France
    "france": "France",
    "frankreich": "France",
    "frankrike": "France",
    # Canada
    "canada": "Canada",
    "kanada": "Canada",
    # Australia
    "australia": "Australia",
    "australien": "Australia",
    # Switzerland (Audience has /audience/switzerland)
    "switzerland": "Switzerland",
    "schweiz": "Switzerland",
    "suisse": "Switzerland",
    "svizzera": "Switzerland",
    # UAE
    "uae": "UAE",
    "united arab emirates": "UAE",
    "förenade arabemiraten": "UAE",
    "forenade arabemiraten": "UAE",
}

# Canonical names that have their own Audience pages (excluded from ROW).
_AUDIENCE_CORE_MARKETS_LOWER: frozenset = frozenset(
    n.lower()
    for n in (
        "Sweden",
        "United Kingdom",
        "United States",
        "Germany",
        "France",
        "Canada",
        "Australia",
        "Switzerland",
        "UAE",
    )
)


def _audience_canonical_country(raw: Any) -> Any:
    """Map export country label to the Audience UI country key; unknown labels pass through."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return pd.NA
    s = str(raw).strip()
    if not s or s.lower() in ("nan", "none", "-"):
        return pd.NA
    return _COUNTRY_ALIASES_LOWER_TO_CANONICAL.get(s.lower(), s)


def _normalize_sales_channel(val: Any) -> Optional[str]:
    """Map raw channel labels to 'online' for filtering (locale / casing tolerant)."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip().strip('"').strip("'").lower()
    if not s or s == "nan":
        return None
    if "online" in s:
        return "online"
    if "e-handel" in s or "ecommerce" in s or "e-commerce" in s or "ecom" in s:
        return "online"
    if s in ("web", "www", "digital", "d2c", "dtc"):
        return "online"
    if "webb" in s:  # Swedish "webbshop" etc.
        return "online"
    return None


def _prepare_online_frame(qlik_df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """
    Resolve Qlik column aliases, filter to online sales, and add standard internal columns:
    _Country, _CountryCanonical, _Gross, _Net, _Returns_raw, _Order, _Email, _Seg
    """
    if qlik_df.empty:
        return None

    df = qlik_df.copy()
    df.columns = df.columns.astype(str).str.strip()

    sales_col = _pick_column(
        df,
        [
            "Sales Channel",
            "Försäljningskanal",
            "Sales channel",
            "Channel",
            "Kanal",
            "Forsaljningskanal",
        ],
    )
    country_col = _pick_column(
        df,
        [
            "Country",
            "Land",
            "Market",
            "Country/Region",
            "Ship country",
            "Shipping country",
        ],
    )
    gross_col = _pick_column(
        df,
        [
            "Gross Revenue",
            "Bruttointäkt",
            "Bruttoförsäljning",
            "Gross sales",
            "Gross Sales",
        ],
    )
    net_col = _pick_column(
        df,
        [
            "Net Revenue",
            "Nettoförsäljning",
            "Net sales",
            "Net Sales",
            "Net amount",
        ],
    )
    returns_pick = _pick_column(df, ["Returns", "Returer", "Return amount", "Returns amount"])
    order_col = _pick_column(
        df,
        [
            "Order No",
            "Order No.",
            "Order number",
            "Order Number",
            "Ordernummer",
            "Order",
            "Order name",
            "Order Name",
            "Order ID",
            "Order Id",
            "Beställning",
            "Bestallning",
        ],
    )
    email_col = _pick_column(
        df,
        [
            "Customer E-mail",
            "Customer Email",
            "Customer email",
            "E-mail",
            "Email",
            "Kund e-post",
            "Kund epost",
            "E-post",
            "Epost",
            "Customer E mail",
            "Kundens e-postadress",
        ],
    )
    seg_col = _pick_column(
        df,
        [
            "New/Returning Customer",
            "New or returning customer",
            "Ny eller återkommande kund",
            "Ny eller återkommande kund (New/Returning)",
        ],
    )

    if not sales_col or not country_col or not gross_col:
        logger.warning(
            "Audience per country: missing required Qlik columns (sales channel, country, and/or gross). "
            f"Columns present: {df.columns.tolist()}"
        )
        return None

    mask = df[sales_col].map(_normalize_sales_channel).eq("online")
    online = df.loc[mask].copy()
    if online.empty:
        return online

    online["_Country"] = online[country_col].map(
        lambda x: str(x).strip()
        if pd.notna(x) and str(x).strip() and str(x).strip().lower() not in ("nan", "none")
        else pd.NA
    )
    online["_CountryCanonical"] = online["_Country"].map(_audience_canonical_country)
    online["_Gross"] = pd.to_numeric(online[gross_col], errors="coerce").fillna(0.0)

    if net_col:
        online["_Net"] = pd.to_numeric(online[net_col], errors="coerce").fillna(0.0)
    else:
        online["_Net"] = 0.0

    if returns_pick:
        online["_Returns_raw"] = pd.to_numeric(online[returns_pick], errors="coerce")
    else:
        online["_Returns_raw"] = pd.Series(pd.NA, index=online.index, dtype="Float64")

    if order_col:
        online["_Order"] = online[order_col].map(lambda x: str(x).strip() if pd.notna(x) else "")
        online.loc[online["_Order"].isin(("", "nan", "None")), "_Order"] = pd.NA
    else:
        online["_Order"] = pd.NA
        logger.warning("Audience per country: no order id column found; total_orders will be 0.")

    if email_col:
        online["_Email"] = (
            online[email_col].map(lambda x: str(x).strip().lower() if pd.notna(x) else "")
        )
        online.loc[online["_Email"].isin(("", "nan", "none")), "_Email"] = pd.NA
    else:
        online["_Email"] = pd.NA
        logger.warning("Audience per country: no customer email column; new/returning counts will be 0.")

    if seg_col:
        online["_Seg"] = online[seg_col].map(_normalize_customer_segment)
    else:
        online["_Seg"] = pd.NA
        logger.warning(
            "Audience per country: no new/returning segment column; new/returning counts will be 0."
        )

    return online


def _build_weeks(base_week: str, num_weeks: int) -> List[str]:
    """Build last N ISO weeks ending at base_week."""
    year, week = map(int, base_week.split("-"))
    weeks: List[str] = []
    i = 0
    while len(weeks) < num_weeks:
        week_num = week - i
        week_year = year
        if week_num < 1:
            prev_year = year - 1
            week_year = prev_year
            week_num = 52 + week_num
        week_str = f"{week_year}-{week_num:02d}"
        if week_str not in weeks:
            weeks.append(week_str)
        i += 1
    return weeks[::-1]


def _get_last_year_week(week_str: str) -> str:
    """Same ISO week number, previous year (for YoY comparison)."""
    year, week_num = map(int, week_str.split("-"))
    return f"{year - 1}-{week_num:02d}"


def _segment_return_rate_pct(
    ret_seg: float,
    gross_seg: float,
    gross_country: float,
    overall_rr_pct: float,
) -> float:
    """
    Return rate for new/returning segment = returns_seg / gross_seg.

    When gross_seg is tiny vs the country's total online gross for the week, this ratio is
    numerically unstable (few line items → spikes to 50–70% or 0% next week). Fall back to
    the country's overall online return rate for that week so charts stay interpretable.
    """
    if gross_seg <= 0:
        return 0.0
    raw = (ret_seg / gross_seg) * 100.0
    raw = min(100.0, max(0.0, raw))
    if gross_country <= 0:
        return raw
    # At least ~2% of country's online gross, or a small absolute floor (same currency as Qlik).
    threshold = max(2000.0, 0.02 * float(gross_country))
    if gross_seg < threshold:
        return float(overall_rr_pct)
    return raw


def calculate_audience_metrics_per_country_for_week(
    qlik_df: pd.DataFrame,
    dema_df: pd.DataFrame,
    week_str: str,
) -> Dict[str, Any]:
    """
    For one week, compute per country (and Total): total_aov, total_customers, total_orders,
    new_customers, returning_customers, return_rate_pct, return_rate_new_pct,
    return_rate_returning_pct, cos_pct, cac, amer (online new-customer net / DEMA spend, same as slide 1 eMER).
    Uses online sales only.
    """
    if qlik_df.empty:
        return {"week": week_str, "countries": {}}

    online = _prepare_online_frame(qlik_df)
    if online is None or online.empty:
        return {"week": week_str, "countries": {}}

    online = online[online["_CountryCanonical"].notna()].copy()
    if online.empty:
        return {"week": week_str, "countries": {}}

    # Per country: gross, net, returns (amount). Return rate % = returns / gross (typically 5–6%).
    # Prefer "Returns" column when it gives a plausible rate (0–30%); else use Gross - Net.
    rev_orders = online.groupby("_CountryCanonical", dropna=False).agg(
        gross_revenue=("_Gross", "sum"),
        orders=("_Order", "nunique"),
    ).reset_index()
    rev_orders.rename(columns={"_CountryCanonical": "Country"}, inplace=True)

    net_by_country = online.groupby("_CountryCanonical", dropna=False)["_Net"].sum().reset_index()
    net_by_country.columns = ["Country", "net_revenue"]
    rev_orders = rev_orders.merge(net_by_country, on="Country", how="left")
    rev_orders["net_revenue"] = rev_orders["net_revenue"].fillna(0)
    rev_orders["returns_gross_minus_net"] = (rev_orders["gross_revenue"] - rev_orders["net_revenue"]).clip(lower=0)

    returns_by_country = online.groupby("_CountryCanonical", dropna=False)["_Returns_raw"].sum().reset_index()
    returns_by_country.rename(columns={"_CountryCanonical": "Country", "_Returns_raw": "returns_col"}, inplace=True)
    rev_orders = rev_orders.merge(returns_by_country, on="Country", how="left")
    rev_orders["returns_col"] = rev_orders["returns_col"].fillna(0)
    # Prefer Returns column when present and > 0; else use Gross - Net (so we don't show flat 0 when Gross > Net)
    def _pick_returns(row: pd.Series) -> float:
        gross = float(row["gross_revenue"])
        if gross <= 0:
            return 0.0
        val = row.get("returns_col")
        if val is not None and pd.notna(val) and float(val) > 0:
            return float(val)
        return float(row["returns_gross_minus_net"])
    rev_orders["returns_amount"] = rev_orders.apply(_pick_returns, axis=1)

    # Per-row effective returns for segment-level return rates.
    # Prefer Returns when > 0; otherwise use Gross - Net fallback.
    online["_returns_effective"] = online["_Returns_raw"]
    online["_returns_effective"] = online["_returns_effective"].where(
        online["_returns_effective"].notna() & (online["_returns_effective"] > 0),
        (online["_Gross"] - online["_Net"]).clip(lower=0),
    )

    seg_returns = (
        online[online["_Seg"].isin(["new", "returning"]).fillna(False)]
        .groupby(["_CountryCanonical", "_Seg"], dropna=False)
        .agg(seg_gross=("_Gross", "sum"), seg_returns=("_returns_effective", "sum"))
        .reset_index()
    )
    seg_pivot = seg_returns.pivot(index="_CountryCanonical", columns="_Seg", values=["seg_gross", "seg_returns"])
    if isinstance(seg_pivot.columns, pd.MultiIndex):
        seg_pivot.columns = [f"{a}_{b}" for a, b in seg_pivot.columns]
    seg_pivot = seg_pivot.reset_index().rename(columns={"_CountryCanonical": "Country"})
    rev_orders = rev_orders.merge(seg_pivot, on="Country", how="left")
    for c in ("seg_gross_new", "seg_returns_new", "seg_gross_returning", "seg_returns_returning"):
        if c not in rev_orders.columns:
            rev_orders[c] = 0.0
        rev_orders[c] = rev_orders[c].fillna(0.0)

    new_df = (
        online[online["_Seg"].eq("new").fillna(False)]
        .groupby("_CountryCanonical", dropna=False)
        .agg(new_customers=("_Email", "nunique"))
        .reset_index()
        .rename(columns={"_CountryCanonical": "Country"})
    )
    ret_df = (
        online[online["_Seg"].eq("returning").fillna(False)]
        .groupby("_CountryCanonical", dropna=False)
        .agg(returning_customers=("_Email", "nunique"))
        .reset_index()
        .rename(columns={"_CountryCanonical": "Country"})
    )

    new_net_df = (
        online[online["_Seg"].eq("new").fillna(False)]
        .groupby("_CountryCanonical", dropna=False)["_Net"]
        .sum()
        .reset_index()
        .rename(columns={"_CountryCanonical": "Country", "_Net": "new_customers_net_revenue"})
    )
    ret_net_df = (
        online[online["_Seg"].eq("returning").fillna(False)]
        .groupby("_CountryCanonical", dropna=False)["_Net"]
        .sum()
        .reset_index()
        .rename(columns={"_CountryCanonical": "Country", "_Net": "returning_customers_net_revenue"})
    )

    merged = (
        rev_orders.merge(new_df, on="Country", how="left")
        .merge(ret_df, on="Country", how="left")
        .merge(new_net_df, on="Country", how="left")
        .merge(ret_net_df, on="Country", how="left")
    )
    merged["new_customers_net_revenue"] = merged["new_customers_net_revenue"].fillna(0.0)
    merged["returning_customers_net_revenue"] = merged["returning_customers_net_revenue"].fillna(0.0)
    merged["new_customers"] = merged["new_customers"].fillna(0).astype(int)
    merged["returning_customers"] = merged["returning_customers"].fillna(0).astype(int)
    merged["total_customers"] = merged["new_customers"] + merged["returning_customers"]

    # Marketing spend per country from DEMA (canonicalize labels to match Qlik / Audience keys)
    total_dema_mkt_all = 0.0
    if not dema_df.empty:
        dema_cc = dema_df.copy()
        dema_cc.columns = dema_cc.columns.astype(str).str.strip()
        spend_col = _pick_column(
            dema_cc,
            ["Marketing spend", "Marketing Spend", "Spend", "Cost", "Kostnad", "Ad spend"],
        )
        if spend_col and spend_col in dema_cc.columns:
            total_dema_mkt_all = float(pd.to_numeric(dema_cc[spend_col], errors="coerce").fillna(0).sum())
        if spend_col and "Country" in dema_cc.columns:
            spend = dema_cc.groupby("Country")[spend_col].sum().reset_index()
            spend.columns = ["_dema_country", "marketing_spend"]
            spend["Country"] = spend["_dema_country"].map(_audience_canonical_country)
            spend = spend.dropna(subset=["Country"])
            spend = spend.groupby("Country", as_index=False)["marketing_spend"].sum()
            merged = merged.merge(spend, on="Country", how="left")
        else:
            merged["marketing_spend"] = 0.0
    else:
        merged["marketing_spend"] = 0.0
    merged["marketing_spend"] = merged["marketing_spend"].fillna(0)

    # New customer spend 70% allocation for CAC (nCAC)
    merged["new_customer_spend"] = merged["marketing_spend"] * 0.70

    result = {"week": week_str, "countries": {}}
    for _, row in merged.iterrows():
        country = row["Country"]
        if pd.isna(country) or country == "-":
            continue
        gross_revenue = float(row["gross_revenue"])
        net_revenue = float(row["net_revenue"])
        new_cust_net = float(row.get("new_customers_net_revenue", 0.0))
        ret_cust_net = float(row.get("returning_customers_net_revenue", 0.0))
        returns_amount = float(row["returns_amount"])
        orders = int(row["orders"])
        new_c = int(row["new_customers"])
        ret_c = int(row["returning_customers"])
        total_c = int(row["total_customers"])
        spend = float(row["marketing_spend"])
        new_spend = float(row["new_customer_spend"])

        total_aov = (gross_revenue / orders) if orders > 0 else 0.0
        return_rate_pct = (returns_amount / gross_revenue * 100) if gross_revenue > 0 else 0.0
        new_gross = float(row.get("seg_gross_new", 0.0))
        new_returns = float(row.get("seg_returns_new", 0.0))
        ret_gross = float(row.get("seg_gross_returning", 0.0))
        ret_returns = float(row.get("seg_returns_returning", 0.0))
        return_rate_new_pct = _segment_return_rate_pct(
            new_returns, new_gross, gross_revenue, return_rate_pct
        )
        return_rate_returning_pct = _segment_return_rate_pct(
            ret_returns, ret_gross, gross_revenue, return_rate_pct
        )
        cos_pct = (
            min(100.0, (spend / gross_revenue * 100.0)) if gross_revenue > 0 else 0.0
        )
        cac = (new_spend / new_c) if new_c > 0 else 0.0
        # aMER = online new-customer net revenue / DEMA marketing spend (same as Table 1 eMER / slide 1)
        amer = (new_cust_net / spend) if spend > 0 else 0.0
        # Segment AOV: net revenue ÷ unique customers (same as Online KPIs)
        aov_new_customer = (new_cust_net / new_c) if new_c > 0 else 0.0
        aov_returning_customer = (ret_cust_net / ret_c) if ret_c > 0 else 0.0

        result["countries"][country] = {
            "total_aov": round(total_aov, 2),
            "total_customers": total_c,
            "total_orders": orders,
            "new_customers": new_c,
            "returning_customers": ret_c,
            "aov_new_customer": round(aov_new_customer, 2),
            "aov_returning_customer": round(aov_returning_customer, 2),
            "return_rate_pct": round(return_rate_pct, 2),
            "return_rate_new_pct": round(return_rate_new_pct, 2),
            "return_rate_returning_pct": round(return_rate_returning_pct, 2),
            "cos_pct": round(cos_pct, 2),
            "cac": round(cac, 2),
            "amer": round(amer, 2),
        }

    # ROW aggregate (Rest of World): all countries outside main Audience market pages.
    merged_valid = merged[~merged["Country"].isna()].copy()
    merged_valid["CountryNorm"] = merged_valid["Country"].astype(str).str.strip().str.lower()
    merged_valid = merged_valid[merged_valid["CountryNorm"] != "-"]
    row_df = merged_valid[~merged_valid["CountryNorm"].isin(_AUDIENCE_CORE_MARKETS_LOWER)]
    if not row_df.empty:
        row_revenue = float(row_df["gross_revenue"].sum() or 0.0)
        row_returns = float(row_df["returns_amount"].sum() or 0.0)
        row_new_gross = float(row_df["seg_gross_new"].sum() or 0.0)
        row_new_returns = float(row_df["seg_returns_new"].sum() or 0.0)
        row_ret_gross = float(row_df["seg_gross_returning"].sum() or 0.0)
        row_ret_returns = float(row_df["seg_returns_returning"].sum() or 0.0)
        row_orders = int(row_df["orders"].sum() or 0)
        row_new = int(row_df["new_customers"].sum() or 0)
        row_ret = int(row_df["returning_customers"].sum() or 0)
        row_total_customers = row_new + row_ret
        row_spend = float(row_df["marketing_spend"].sum() or 0.0)
        row_new_spend = float(row_df["new_customer_spend"].sum() or 0.0)
        row_new_cust_net = float(row_df["new_customers_net_revenue"].sum() or 0.0)
        row_ret_cust_net = float(row_df["returning_customers_net_revenue"].sum() or 0.0)
        result["countries"]["ROW"] = {
            "total_aov": round((row_revenue / row_orders) if row_orders > 0 else 0.0, 2),
            "total_customers": row_total_customers,
            "total_orders": row_orders,
            "new_customers": row_new,
            "returning_customers": row_ret,
            "aov_new_customer": round((row_new_cust_net / row_new) if row_new > 0 else 0.0, 2),
            "aov_returning_customer": round((row_ret_cust_net / row_ret) if row_ret > 0 else 0.0, 2),
            "return_rate_pct": round((row_returns / row_revenue * 100) if row_revenue > 0 else 0.0, 2),
            "return_rate_new_pct": round(
                _segment_return_rate_pct(
                    row_new_returns,
                    row_new_gross,
                    row_revenue,
                    (row_returns / row_revenue * 100) if row_revenue > 0 else 0.0,
                ),
                2,
            ),
            "return_rate_returning_pct": round(
                _segment_return_rate_pct(
                    row_ret_returns,
                    row_ret_gross,
                    row_revenue,
                    (row_returns / row_revenue * 100) if row_revenue > 0 else 0.0,
                ),
                2,
            ),
            "cos_pct": round(
                min(100.0, (row_spend / row_revenue * 100.0)) if row_revenue > 0 else 0.0,
                2,
            ),
            "cac": round((row_new_spend / row_new) if row_new > 0 else 0.0, 2),
            "amer": round((row_new_cust_net / row_spend) if row_spend > 0 else 0.0, 2),
        }

    # Total row
    tot_revenue = merged["gross_revenue"].sum()
    tot_returns = merged["returns_amount"].sum()
    tot_new_gross = merged["seg_gross_new"].sum()
    tot_new_returns = merged["seg_returns_new"].sum()
    tot_ret_gross = merged["seg_gross_returning"].sum()
    tot_ret_returns = merged["seg_returns_returning"].sum()
    tot_orders = merged["orders"].sum()
    tot_new = merged["new_customers"].sum()
    tot_ret = merged["returning_customers"].sum()
    tot_cust = tot_new + tot_ret
    tot_spend = merged["marketing_spend"].sum()
    tot_new_spend = merged["new_customer_spend"].sum()
    # Total aMER: match Table 1 / slide 1 — all online new-customer net ÷ full DEMA spend for the week
    slide1_new_net_total = float(online.loc[online["_Seg"].eq("new").fillna(False), "_Net"].sum() or 0.0)
    amer_total_denom = total_dema_mkt_all if total_dema_mkt_all > 0 else float(tot_spend)
    amer_total = (slide1_new_net_total / amer_total_denom) if amer_total_denom > 0 else 0.0
    tot_new_net = float(merged["new_customers_net_revenue"].sum() or 0.0)
    tot_ret_net = float(merged["returning_customers_net_revenue"].sum() or 0.0)

    result["countries"]["Total"] = {
        "total_aov": round((tot_revenue / tot_orders) if tot_orders > 0 else 0.0, 2),
        "total_customers": int(tot_cust),
        "total_orders": int(tot_orders),
        "new_customers": int(tot_new),
        "returning_customers": int(tot_ret),
        "aov_new_customer": round((tot_new_net / tot_new) if tot_new > 0 else 0.0, 2),
        "aov_returning_customer": round((tot_ret_net / tot_ret) if tot_ret > 0 else 0.0, 2),
        "return_rate_pct": round((tot_returns / tot_revenue * 100) if tot_revenue > 0 else 0.0, 2),
        "return_rate_new_pct": round(
            _segment_return_rate_pct(
                tot_new_returns,
                tot_new_gross,
                tot_revenue,
                (tot_returns / tot_revenue * 100) if tot_revenue > 0 else 0.0,
            ),
            2,
        ),
        "return_rate_returning_pct": round(
            _segment_return_rate_pct(
                tot_ret_returns,
                tot_ret_gross,
                tot_revenue,
                (tot_returns / tot_revenue * 100) if tot_revenue > 0 else 0.0,
            ),
            2,
        ),
        "cos_pct": round(
            min(100.0, (tot_spend / tot_revenue * 100.0)) if tot_revenue > 0 else 0.0,
            2,
        ),
        "cac": round((tot_new_spend / tot_new) if tot_new > 0 else 0.0, 2),
        "amer": round(amer_total, 2),
    }

    return result


def calculate_audience_metrics_per_country_for_weeks(
    base_week: str, num_weeks: int, data_root: Path
) -> Dict[str, Any]:
    """
    Returns audience metrics per country for the last N weeks.
    Response: { "audience_metrics_per_country": [ { week, countries: { country: { total_aov, total_customers, total_orders, new_customers, returning_customers, return_rate_pct, cos_pct, cac } } } ], "period_info": { ... } }
    """
    raw_path = data_root / "raw" / base_week
    raw = load_all_raw_data(raw_path)
    qlik_df = raw.get("qlik", pd.DataFrame())
    dema_df = raw.get("dema_spend", pd.DataFrame())

    if qlik_df.empty:
        logger.warning(f"No Qlik data in {raw_path}")
        return {"audience_metrics_per_country": [], "period_info": {"latest_week": base_week, "latest_dates": ""}}

    if "iso_week" not in qlik_df.columns and "Date" in qlik_df.columns:
        qlik_df = qlik_df.copy()
        qlik_df["Date"] = pd.to_datetime(qlik_df["Date"], errors="coerce")
        ic = qlik_df["Date"].dt.isocalendar()
        qlik_df["iso_week"] = ic["year"].astype(str) + "-" + ic["week"].astype(str).str.zfill(2)
    if not dema_df.empty and "iso_week" not in dema_df.columns and "Days" in dema_df.columns:
        dema_df = dema_df.copy()
        dema_df["Days"] = pd.to_datetime(dema_df["Days"], errors="coerce")
        ic = dema_df["Days"].dt.isocalendar()
        dema_df["iso_week"] = ic["year"].astype(str) + "-" + ic["week"].astype(str).str.zfill(2)

    weeks = _build_weeks(base_week, num_weeks)
    results = []
    for w in weeks:
        w_qlik = qlik_df[qlik_df["iso_week"] == w]
        w_dema = dema_df[dema_df["iso_week"] == w] if not dema_df.empty else pd.DataFrame()
        week_result = calculate_audience_metrics_per_country_for_week(w_qlik, w_dema, w)

        # Add last year (same ISO week, previous year) from the same loaded data
        last_year_week = _get_last_year_week(w)
        ly_qlik = qlik_df[qlik_df["iso_week"] == last_year_week]
        ly_dema = dema_df[dema_df["iso_week"] == last_year_week] if not dema_df.empty else pd.DataFrame()
        ly_result = calculate_audience_metrics_per_country_for_week(ly_qlik, ly_dema, last_year_week)

        for country in week_result.get("countries", {}):
            ly_country = ly_result.get("countries", {}).get(country)
            if ly_country is not None:
                week_result["countries"][country]["last_year"] = ly_country
            else:
                week_result["countries"][country]["last_year"] = None

        results.append(week_result)
    date_range = get_week_date_range(base_week)
    return {
        "audience_metrics_per_country": results,
        "period_info": {"latest_week": base_week, "latest_dates": date_range.get("display", "")},
    }
