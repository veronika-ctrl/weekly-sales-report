"""Budget metrics calculation."""
from typing import Dict, Any, List
import pandas as pd
from loguru import logger
from pathlib import Path
from datetime import datetime, timedelta
import calendar


def load_budget_data(data_root: Path) -> pd.DataFrame:
    """Load budget data from CSV files."""
    from weekly_report.src.adapters.budget import load_data
    
    try:
        budget_df = load_data(data_root)
        return budget_df
    except FileNotFoundError:
        logger.warning(f"No budget data found in {data_root}")
        return pd.DataFrame()


def parse_month(month_str: str) -> datetime:
    """Parse month string to datetime (e.g., '2025-01' -> 2025-01-01)."""
    try:
        return datetime.strptime(month_str, '%Y-%m')
    except ValueError:
        logger.error(f"Invalid month format: {month_str}")
        return datetime(1900, 1, 1)


def get_days_in_month(year: int, month: int) -> int:
    """Get number of days in a month."""
    return calendar.monthrange(year, month)[1]


def breakdown_budget_to_days(month_str: str, value: float) -> pd.Series:
    """Break down monthly budget to daily values."""
    dt = parse_month(month_str)
    days_in_month = get_days_in_month(dt.year, dt.month)
    daily_value = value / days_in_month
    
    # Create a series with dates
    dates = pd.date_range(start=f"{month_str}-01", periods=days_in_month, freq='D')
    return pd.Series([daily_value] * days_in_month, index=dates)


def calculate_iso_week(date: datetime) -> str:
    """Calculate ISO week from date."""
    iso_cal = date.isocalendar()
    return f"{iso_cal.year}-{iso_cal.week:02d}"


def calculate_budget_metrics(base_week: str, data_root: Path) -> Dict[str, Any]:
    """Calculate budget vs actual metrics for requested metrics."""
    
    # Load budget data
    budget_df = load_budget_data(data_root)
    
    if budget_df.empty:
        logger.warning(f"No budget data available for {base_week}")
        return {
            'week': base_week,
            'metrics': {},
            'error': 'No budget data available'
        }
    
    # Parse base week to get the current date range
    year, week = base_week.split('-')
    year = int(year)
    week = int(week)
    
    # Calculate date range for the week
    # Get the first day of the week (Monday)
    jan4 = datetime(year, 1, 4)
    jan4_week = jan4.weekday()
    days_offset = (int(week) - 1) * 7
    week_start = jan4 + timedelta(days=-jan4_week + days_offset)
    week_end = week_start + timedelta(days=6)
    
    # Get last year dates
    last_year_start = week_start.replace(year=year - 1)
    last_year_end = week_end.replace(year=year - 1)
    
    # Get YTD dates (from start of fiscal year to end of current week)
    fiscal_year_start = datetime(year, 4, 1) if week_start.month >= 4 else datetime(year - 1, 4, 1)
    
    # Budget metrics to calculate
    metrics = {}
    
    # Placeholder - will implement actual calculations
    metrics['week'] = base_week
    metrics['date_range'] = {
        'current': {'start': week_start.strftime('%Y-%m-%d'), 'end': week_end.strftime('%Y-%m-%d')},
        'last_year': {'start': last_year_start.strftime('%Y-%m-%d'), 'end': last_year_end.strftime('%Y-%m-%d')},
        'ytd': {'start': fiscal_year_start.strftime('%Y-%m-%d'), 'end': week_end.strftime('%Y-%m-%d')}
    }
    metrics['budget_data'] = {}
    metrics['actual_data'] = {}
    metrics['last_year_data'] = {}
    metrics['ytd_data'] = {}
    
    return metrics

