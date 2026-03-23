"""Export mapper for Budget General data to Supabase format."""

from typing import Any, Dict, List

from loguru import logger


def map_budget_general_to_rows(
    data: Dict[str, Any],
    kind: str = "budget"
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Map Budget General API response to Supabase rows.
    
    Args:
        data: Response from /api/budget-general or /api/actuals-general
        kind: 'budget' or 'actuals'
    
    Returns:
        (detailed_rows, totals_rows) where:
        - detailed_rows: list of {base_week, metric, customer, month, value, kind}
        - totals_rows: list of {base_week, metric, customer, scope, value, kind}
    """
    base_week = data.get("week")
    if not base_week:
        logger.warning(f"No week in {kind} data")
        return [], []
    
    table = data.get("table", {})
    totals = data.get("totals", {})
    ytd_totals = data.get("ytd_totals", {})
    customer_by_metric = data.get("customer_by_metric", {})
    
    detailed_rows = []
    totals_rows = []
    
    # Map month-by-month data
    for metric, by_month in table.items():
        customer = customer_by_metric.get(metric, "")
        for month, value in by_month.items():
            if value is None or (isinstance(value, float) and (value != value or value == float('inf') or value == float('-inf'))):
                value = 0.0
            detailed_rows.append({
                "base_week": base_week,
                "metric": metric,
                "customer": customer,
                "month": month,
                "value": float(value),
                "kind": kind
            })
    
    # Map totals (Total and YTD)
    for metric, total_value in totals.items():
        customer = customer_by_metric.get(metric, "")
        if total_value is None or (isinstance(total_value, float) and (total_value != total_value or total_value == float('inf') or total_value == float('-inf'))):
            total_value = 0.0
        totals_rows.append({
            "base_week": base_week,
            "metric": metric,
            "customer": customer,
            "scope": "TOTAL",
            "value": float(total_value),
            "kind": kind
        })
    
    # Map YTD totals
    for metric, ytd_value in ytd_totals.items():
        customer = customer_by_metric.get(metric, "")
        if ytd_value is None or (isinstance(ytd_value, float) and (ytd_value != ytd_value or ytd_value == float('inf') or ytd_value == float('-inf'))):
            ytd_value = 0.0
        totals_rows.append({
            "base_week": base_week,
            "metric": metric,
            "customer": customer,
            "scope": "YTD",
            "value": float(ytd_value),
            "kind": kind
        })
    
    logger.info(f"Mapped {len(detailed_rows)} detailed rows and {len(totals_rows)} totals rows for {kind}")
    return detailed_rows, totals_rows






