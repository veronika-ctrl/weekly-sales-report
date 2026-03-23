"""Audience metrics per country: Total AOV, Total customers, Return rate, COS, CAC (no split by customer type)."""
from typing import Dict, Any, List
import pandas as pd
from loguru import logger
from pathlib import Path

from weekly_report.src.metrics.table1 import load_all_raw_data
from weekly_report.src.periods.calculator import get_week_date_range


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


def calculate_audience_metrics_per_country_for_week(
    qlik_df: pd.DataFrame,
    dema_df: pd.DataFrame,
    week_str: str,
) -> Dict[str, Any]:
    """
    For one week, compute per country (and Total): total_aov, total_customers, return_rate_pct, cos_pct, cac.
    Uses online sales only; no split by new/returning in the displayed metrics.
    """
    if qlik_df.empty:
        return {"week": week_str, "countries": {}}

    online = qlik_df[qlik_df["Sales Channel"] == "Online"].copy()
    if online.empty:
        return {"week": week_str, "countries": {}}

    # Per country: gross, net, returns (amount). Return rate % = returns / gross (typically 5–6%).
    # Prefer "Returns" column when it gives a plausible rate (0–30%); else use Gross - Net.
    rev_orders = online.groupby("Country").agg(
        gross_revenue=("Gross Revenue", "sum"),
        orders=("Order No", "nunique"),
    ).reset_index()
    if "Net Revenue" in online.columns:
        net_by_country = online.groupby("Country")["Net Revenue"].sum().reset_index()
        net_by_country.columns = ["Country", "net_revenue"]
        rev_orders = rev_orders.merge(net_by_country, on="Country", how="left")
        rev_orders["net_revenue"] = rev_orders["net_revenue"].fillna(0)
        rev_orders["returns_gross_minus_net"] = (rev_orders["gross_revenue"] - rev_orders["net_revenue"]).clip(lower=0)
    else:
        rev_orders["net_revenue"] = 0.0
        rev_orders["returns_gross_minus_net"] = 0.0
    if "Returns" in online.columns:
        returns_by_country = online.groupby("Country")["Returns"].sum().reset_index()
        returns_by_country.columns = ["Country", "returns_col"]
        rev_orders = rev_orders.merge(returns_by_country, on="Country", how="left")
        rev_orders["returns_col"] = rev_orders["returns_col"].fillna(0)
    else:
        rev_orders["returns_col"] = None
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

    new_df = online[online["New/Returning Customer"] == "New"].groupby("Country").agg(
        new_customers=("Customer E-mail", "nunique")
    ).reset_index()
    ret_df = online[online["New/Returning Customer"] == "Returning"].groupby("Country").agg(
        returning_customers=("Customer E-mail", "nunique")
    ).reset_index()

    merged = rev_orders.merge(new_df, on="Country", how="left").merge(ret_df, on="Country", how="left")
    merged["new_customers"] = merged["new_customers"].fillna(0).astype(int)
    merged["returning_customers"] = merged["returning_customers"].fillna(0).astype(int)
    merged["total_customers"] = merged["new_customers"] + merged["returning_customers"]

    # Marketing spend per country from DEMA
    if not dema_df.empty and "Country" in dema_df.columns:
        spend = dema_df.groupby("Country")["Marketing spend"].sum().reset_index()
        spend.columns = ["Country", "marketing_spend"]
        merged = merged.merge(spend, on="Country", how="left")
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
        returns_amount = float(row["returns_amount"])
        orders = int(row["orders"])
        new_c = int(row["new_customers"])
        ret_c = int(row["returning_customers"])
        total_c = int(row["total_customers"])
        spend = float(row["marketing_spend"])
        new_spend = float(row["new_customer_spend"])

        total_aov = (gross_revenue / orders) if orders > 0 else 0.0
        return_rate_pct = (returns_amount / gross_revenue * 100) if gross_revenue > 0 else 0.0
        cos_pct = (spend / gross_revenue * 100) if gross_revenue > 0 else 0.0
        cac = (new_spend / new_c) if new_c > 0 else 0.0

        result["countries"][country] = {
            "total_aov": round(total_aov, 2),
            "total_customers": total_c,
            "return_rate_pct": round(return_rate_pct, 2),
            "cos_pct": round(cos_pct, 2),
            "cac": round(cac, 2),
        }

    # Total row
    tot_revenue = merged["gross_revenue"].sum()
    tot_returns = merged["returns_amount"].sum()
    tot_orders = merged["orders"].sum()
    tot_new = merged["new_customers"].sum()
    tot_ret = merged["returning_customers"].sum()
    tot_cust = tot_new + tot_ret
    tot_spend = merged["marketing_spend"].sum()
    tot_new_spend = merged["new_customer_spend"].sum()
    result["countries"]["Total"] = {
        "total_aov": round((tot_revenue / tot_orders) if tot_orders > 0 else 0.0, 2),
        "total_customers": int(tot_cust),
        "return_rate_pct": round((tot_returns / tot_revenue * 100) if tot_revenue > 0 else 0.0, 2),
        "cos_pct": round((tot_spend / tot_revenue * 100) if tot_revenue > 0 else 0.0, 2),
        "cac": round((tot_new_spend / tot_new) if tot_new > 0 else 0.0, 2),
    }

    return result


def calculate_audience_metrics_per_country_for_weeks(
    base_week: str, num_weeks: int, data_root: Path
) -> Dict[str, Any]:
    """
    Returns audience metrics per country for the last N weeks.
    Response: { "audience_metrics_per_country": [ { week, countries: { country: { total_aov, total_customers, return_rate_pct, cos_pct, cac } } } ], "period_info": { ... } }
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
