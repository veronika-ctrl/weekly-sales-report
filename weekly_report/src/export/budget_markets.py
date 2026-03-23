"""Export mapper for Budget Markets data to Supabase format."""

from typing import Any, Dict, List

from loguru import logger


def map_budget_markets_to_rows(
    data: Dict[str, Any],
    kind: str = "actuals"
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Map Budget Markets detailed API response to Supabase rows.
    
    Args:
        data: Response from /api/actuals-markets-detailed (similar structure to budget-general but per market)
        kind: 'budget' or 'actuals'
    
    Returns:
        (detailed_rows, totals_rows) where:
        - detailed_rows: list of {base_week, market, metric, month, value, kind}
        - totals_rows: list of {base_week, market, metric, scope, value, kind}
    """
    base_week = data.get("week")
    if not base_week:
        logger.warning(f"No week in {kind} markets data")
        return [], []
    
    table = data.get("table", {})
    totals = data.get("totals", {})
    ytd_totals = data.get("ytd_totals", {})
    markets = data.get("markets", [])
    metrics = data.get("metrics", [])
    
    detailed_rows = []
    totals_rows = []
    
    # Map per-market, per-month data
    for market in markets:
        market_table = table.get(market, {})
        for metric in metrics:
            metric_by_month = market_table.get(metric, {})
            for month, value in metric_by_month.items():
                if value is None or (isinstance(value, float) and (value != value or value == float('inf') or value == float('-inf'))):
                    value = 0.0
                detailed_rows.append({
                    "base_week": base_week,
                    "market": market,
                    "metric": metric,
                    "month": month,
                    "value": float(value),
                    "kind": kind
                })
    
    # Map totals (Total and YTD per market)
    for market in markets:
        market_totals = totals.get(market, {})
        market_ytd = ytd_totals.get(market, {})
        
        for metric in metrics:
            # Total
            total_value = market_totals.get(metric, 0.0)
            if total_value is None or (isinstance(total_value, float) and (total_value != total_value or total_value == float('inf') or total_value == float('-inf'))):
                total_value = 0.0
            totals_rows.append({
                "base_week": base_week,
                "market": market,
                "metric": metric,
                "scope": "TOTAL",
                "value": float(total_value),
                "kind": kind
            })
            
            # YTD
            ytd_value = market_ytd.get(metric, 0.0)
            if ytd_value is None or (isinstance(ytd_value, float) and (ytd_value != ytd_value or ytd_value == float('inf') or ytd_value == float('-inf'))):
                ytd_value = 0.0
            totals_rows.append({
                "base_week": base_week,
                "market": market,
                "metric": metric,
                "scope": "YTD",
                "value": float(ytd_value),
                "kind": kind
            })
    
    logger.info(f"Mapped {len(detailed_rows)} detailed rows and {len(totals_rows)} totals rows for {kind} markets")
    return detailed_rows, totals_rows






