"""Map budget-general `table` (metric → month → value) to Table 1 keys for one calendar month."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from loguru import logger


def derive_emer_from_budget_components(
    emer_explicit: float,
    new_net_new_customers: float,
    marketing_spend: float,
) -> float:
    """Table 1: eMER = new customers online net / marketing when explicit aMER is absent or zero."""
    try:
        e = float(emer_explicit or 0)
    except (TypeError, ValueError):
        e = 0.0
    if abs(e) >= 1e-9:
        return e
    try:
        mkt = float(marketing_spend or 0)
        nn = float(new_net_new_customers or 0)
    except (TypeError, ValueError):
        return 0.0
    if abs(mkt) > 1e-9 and abs(nn) > 1e-9:
        return abs(nn) / abs(mkt)
    return e


def budget_table1_for_calendar_month(
    table: Dict[str, Any], target_year: int, target_month: int
) -> Dict[str, Any]:
    """One calendar month's budget mapped to table1 keys (MTD / monthly views)."""
    try:
        anchor = datetime(target_year, target_month, 1)
        month_str = anchor.strftime("%B %Y")
    except Exception:
        return {}

    month_variants = [
        month_str,
        anchor.strftime("%Y-%m"),
        anchor.strftime("%b %Y"),
        anchor.strftime("%B %Y"),
    ]

    _swedish_months = {
        "januari": 1,
        "februari": 2,
        "mars": 3,
        "april": 4,
        "maj": 5,
        "juni": 6,
        "juli": 7,
        "augusti": 8,
        "september": 9,
        "oktober": 10,
        "november": 11,
        "december": 12,
    }
    _english_months = {
        "january": 1,
        "february": 2,
        "march": 3,
        "april": 4,
        "may": 5,
        "june": 6,
        "july": 7,
        "august": 8,
        "september": 9,
        "october": 10,
        "november": 11,
        "december": 12,
    }

    def _month_matches(m_key: str) -> bool:
        if not m_key or not str(m_key).strip():
            return False
        s = str(m_key).strip()
        for fmt in ("%B %Y", "%b %Y", "%Y-%m"):
            try:
                if fmt == "%Y-%m" and len(s) >= 7:
                    dt = datetime.strptime(s[:7], "%Y-%m")
                else:
                    dt = datetime.strptime(s, fmt)
                return dt.year == target_year and dt.month == target_month
            except Exception:
                continue
        if s.lower() == month_str.lower():
            return True
        parts = s.replace(".", " ").lower().split()
        if len(parts) >= 2 and parts[-1].isdigit():
            yr = int(parts[-1])
            mo = _swedish_months.get(parts[0]) or _english_months.get(parts[0])
            if mo is not None and mo == target_month and yr == target_year:
                return True
        return False

    def get_val(metric_name: str) -> float:
        by_month = table.get(metric_name) or {}
        for variant in month_variants:
            v = by_month.get(variant)
            if v is not None:
                return float(v)
        for m_key, val in by_month.items():
            if _month_matches(m_key):
                return float(val)
        return 0.0

    def get_budget_val(*preferred_names: str) -> float:
        for name in preferred_names:
            v = get_val(name)
            if v != 0.0 or name == preferred_names[-1]:
                return v
        key_lower = {k.strip().lower(): k for k in table.keys()}
        for name in preferred_names:
            k = key_lower.get(name.strip().lower())
            if k is not None:
                return get_val(k)
        return 0.0

    if not table:
        logger.debug("budget_table1_for_calendar_month: empty table for %s-%02d", target_year, target_month)
        return {}

    total_gross = get_budget_val("Total Gross Revenue", "Online Gross Revenue")
    if total_gross == 0.0:
        total_gross = get_budget_val("Returning Gross Revenue") + get_budget_val("New Gross Revenue")

    returns = get_budget_val("Returns")
    if returns == 0.0:
        returns = get_budget_val("Returning Returns") + get_budget_val("New Returns")

    return_rate_pct = get_budget_val("Return rate (%)")
    if return_rate_pct == 0.0 and total_gross and total_gross > 0 and returns != 0.0:
        return_rate_pct = (returns / total_gross) * 100

    total_net = get_budget_val("Net Revenue", "Online Net Revenue")
    if total_net == 0.0:
        total_net = get_budget_val("Returning Net Revenue") + get_budget_val("New Net Revenue")

    returning_customers = int(round(get_budget_val("Returning Customers")))
    new_customers = int(round(get_budget_val("New Customers")))
    marketing_spend = get_budget_val("Online Marketing Spend")
    cos_pct = get_budget_val("COS %", "COS")
    amer = get_budget_val("aMER", "AMER", "eMER", "emer")
    new_net_new_customers = get_budget_val("New Net Revenue")
    amer = derive_emer_from_budget_components(amer, new_net_new_customers, marketing_spend)
    return {
        "online_gross_revenue": total_gross,
        "returns": returns,
        "return_rate_pct": round(return_rate_pct, 1),
        "online_net_revenue": total_net,
        "retail_concept_store": 0.0,
        "retail_popups_outlets": 0.0,
        "retail_net_revenue": 0.0,
        "wholesale_net_revenue": 0.0,
        "total_net_revenue": total_net,
        "returning_customers": returning_customers,
        "new_customers": new_customers,
        "marketing_spend": float(marketing_spend),
        "online_cost_of_sale_3": round(float(cos_pct), 1),
        "emer": round(float(amer), 1),
        "new_net_revenue_new_seg": float(new_net_new_customers or 0),
    }
