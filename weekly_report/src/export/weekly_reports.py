"""Mapper to transform weekly report metrics to Supabase format."""

import json
from typing import Dict, Any
from datetime import datetime
from loguru import logger


def map_batch_metrics_to_supabase(
    base_week: str,
    metrics: Dict[str, Any],
    file_hashes: Dict[str, str],
    num_weeks: int = 8
) -> Dict[str, Any]:
    """
    Map BatchMetricsResponse to Supabase row format.
    
    Args:
        base_week: ISO week string like '2025-42'
        metrics: Complete BatchMetricsResponse dictionary
        file_hashes: Dictionary of file_type -> hash for cache tracking
        num_weeks: Number of weeks analyzed
        
    Returns:
        Dictionary ready for Supabase insert/upsert:
        {
            "base_week": "2025-42",
            "metrics": {...},  # JSONB
            "computed_at": "2025-10-31T15:00:00Z",
            "file_hashes": {...},  # JSONB
            "num_weeks": 8
        }
    """
    # Ensure metrics can be serialized to JSON
    # Convert any non-serializable objects to safe formats
    metrics_json = _sanitize_for_json(metrics)
    
    # Supabase-py requires JSON STRINGS for JSONB columns, not dicts
    # Convert to JSON string explicitly to ensure compatibility
    try:
        metrics_json_str = json.dumps(metrics_json, ensure_ascii=False)
        file_hashes_str = json.dumps(file_hashes, ensure_ascii=False) if file_hashes else None
    except (TypeError, ValueError) as e:
        logger.error(f"Failed to serialize metrics to JSON: {e}")
        raise ValueError(f"Cannot serialize metrics for Supabase: {e}")
    
    return {
        "base_week": base_week,
        "metrics": metrics_json_str,  # JSON string for JSONB column
        "computed_at": datetime.utcnow().isoformat(),
        "file_hashes": file_hashes_str,  # JSON string for JSONB column
        "num_weeks": num_weeks
    }


def _sanitize_for_json(obj: Any) -> Any:
    """
    Recursively sanitize object for JSON serialization.
    
    Handles:
    - NaN, Infinity -> None
    - pandas objects -> Python native types
    - numpy types -> Python native types
    """
    import math
    import pandas as pd
    import numpy as np
    
    if obj is None:
        return None
    elif isinstance(obj, (dict,)):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(item) for item in obj]
    elif isinstance(obj, (pd.DataFrame, pd.Series)):
        # Convert pandas objects to native Python structures
        if isinstance(obj, pd.Series):
            return obj.fillna(0).astype(object).tolist()
        else:
            return obj.fillna(0).astype(object).to_dict(orient="records")
    elif isinstance(obj, (np.integer, np.floating)):
        # Convert numpy numeric types to Python native
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj.item() if hasattr(obj, 'item') else float(obj)
    elif isinstance(obj, float):
        # Handle Python float NaN/Inf
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    elif isinstance(obj, (str, int, bool)):
        return obj
    elif hasattr(obj, '__dict__'):
        # For custom objects, try to convert to dict
        return _sanitize_for_json(obj.__dict__)
    else:
        # Fallback: convert to string
        logger.warning(f"Could not serialize {type(obj)}, converting to string")
        return str(obj)


def reconstruct_metrics_from_supabase(supabase_row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Reconstruct metrics dictionary from Supabase row.
    
    Args:
        supabase_row: Row from weekly_report_metrics table
        
    Returns:
        Dictionary matching BatchMetricsResponse structure
    """
    if not supabase_row:
        return {}
    
    metrics_json = supabase_row.get("metrics")
    if isinstance(metrics_json, str):
        # JSONB column stored as JSON string - parse it
        try:
            metrics_json = json.loads(metrics_json)
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Failed to parse metrics JSON string: {e}")
            return {}
    elif isinstance(metrics_json, dict):
        # Already parsed (Supabase may return JSONB as dict in some cases)
        pass
    elif metrics_json is None:
        logger.warning("Metrics field is None in Supabase row")
        return {}
    else:
        logger.error(f"Unexpected metrics type: {type(metrics_json)}")
        return {}
    
    # Ensure periods has date_ranges and ytd_periods if missing
    if isinstance(metrics_json, dict) and 'periods' in metrics_json:
        periods = metrics_json.get('periods', {})
        if isinstance(periods, dict) and 'date_ranges' not in periods:
            # Extract base_week from supabase_row
            base_week = supabase_row.get('base_week')
            if base_week:
                try:
                    from weekly_report.src.periods.calculator import get_week_date_range, get_ytd_periods_for_week
                    date_ranges = {}
                    for period_name, period_week in periods.items():
                        if period_name not in ['date_ranges', 'ytd_periods']:
                            try:
                                date_ranges[period_name] = get_week_date_range(period_week)
                            except Exception as e:
                                logger.warning(f"Could not get date range for {period_week}: {e}")
                                date_ranges[period_name] = {
                                    'start': 'N/A',
                                    'end': 'N/A', 
                                    'display': 'N/A'
                                }
                    ytd_periods = get_ytd_periods_for_week(base_week)
                    periods = {
                        **periods,
                        'date_ranges': date_ranges,
                        'ytd_periods': ytd_periods
                    }
                    metrics_json['periods'] = periods
                except Exception as e:
                    logger.warning(f"Could not enhance periods with date_ranges: {e}")
    
    return metrics_json


