"""Online Summary new/returning net sales from Qlik + budget."""

from __future__ import annotations

from datetime import date

import pandas as pd

from weekly_report.src.compute.budget_table1_month import budget_table1_for_calendar_month
from weekly_report.src.metrics.table1 import (
    _get_zero_metrics,
    calculate_table1_metrics,
    calculate_table1_metrics_for_date_range,
)
from weekly_report.src.metrics.table1_budget_daily import (
    _add_long_metric_row_to_acc,
    _finalize_table1_from_acc,
    sum_table1_budget_uniform_daily,
)


WEEK = "2026-42"  # Mon 2026-10-12 .. Sun 2026-10-18


def _qlik_rows() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Date": [
                "2026-10-13",
                "2026-10-13",
                "2026-10-14",
                "2026-10-14",
                "2026-10-15",
            ],
            "Sales Channel": ["Online", "Online", "Online", "Retail", "Online"],
            "Country": ["Sweden", "Sweden", "Sweden", "Sweden", "Norway"],
            "Gross Revenue": [1200.0, 800.0, 400.0, 500.0, 300.0],
            "Net Revenue": [1000.0, 700.0, 350.0, 450.0, 250.0],
            "New/Returning Customer": ["New", "Returning", "ny", "New", "Returning"],
            "Customer E-mail": [
                "a@example.com",
                "b@example.com",
                "c@example.com",
                "d@example.com",
                "e@example.com",
            ],
        }
    )


def _dema_spend() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Days": ["2026-10-13", "2026-10-14"],
            "Marketing spend": [200.0, 50.0],
        }
    )


def _dema_gm2() -> pd.DataFrame:
    return pd.DataFrame({"Days": ["2026-10-13"], "GM2": [10.0]})


def test_table1_online_segment_net_from_qlik():
    metrics = calculate_table1_metrics(_qlik_rows(), _dema_spend(), _dema_gm2(), WEEK)
    # Online only: new 1000 (New) + 350 (ny); returning 700 + 250. Retail 450 excluded.
    assert metrics["new_customers_net_revenue"] == 1350.0
    assert metrics["returning_customers_net_revenue"] == 950.0
    assert metrics["online_net_revenue"] == 2300.0
    # aMER = new net / marketing spend = 1350 / 250
    assert metrics["emer"] == 5.4


def test_table1_date_range_segment_net_excludes_retail():
    metrics = calculate_table1_metrics_for_date_range(
        _qlik_rows(),
        _dema_spend(),
        _dema_gm2(),
        "2026-10-12",
        "2026-10-18",
    )
    assert metrics["new_customers_net_revenue"] == 1350.0
    assert metrics["returning_customers_net_revenue"] == 950.0


def test_zero_metrics_include_segment_net_keys():
    z = _get_zero_metrics()
    assert z["new_customers_net_revenue"] == 0.0
    assert z["returning_customers_net_revenue"] == 0.0


def test_budget_table1_month_maps_new_and_returning_net():
    table = {
        "Total Gross Revenue": {"October 2026": 10000},
        "Returns": {"October 2026": 1000},
        "Net Revenue": {"October 2026": 9000},
        "Returning Customers": {"October 2026": 40},
        "New Customers": {"October 2026": 20},
        "Returning Net Revenue": {"October 2026": 6000},
        "New Net Revenue": {"October 2026": 3000},
        "Online Marketing Spend": {"October 2026": 1000},
        "COS %": {"October 2026": 10},
        "aMER": {"October 2026": 3},
    }
    out = budget_table1_for_calendar_month(table, 2026, 10)
    assert out["new_customers_net_revenue"] == 3000.0
    assert out["returning_customers_net_revenue"] == 6000.0
    assert out["new_net_revenue_new_seg"] == 3000.0
    assert out["online_net_revenue"] == 9000.0


def test_daily_budget_accumulates_returning_and_new_net():
    acc: dict[str, float] = {}
    _add_long_metric_row_to_acc("New Net Revenue", 300.0, acc)
    _add_long_metric_row_to_acc("Returning Net Revenue", 700.0, acc)
    _add_long_metric_row_to_acc("Net Revenue", 1000.0, acc)
    _add_long_metric_row_to_acc("Online Marketing Spend", 100.0, acc)
    out = _finalize_table1_from_acc(acc)
    assert out["new_customers_net_revenue"] == 300.0
    assert out["returning_customers_net_revenue"] == 700.0
    assert out["emer"] == 3.0


def test_uniform_daily_budget_spreads_segment_net():
    def get_month(y: int, m: int) -> dict:
        if (y, m) != (2026, 10):
            return {}
        return {
            "online_gross_revenue": 3100.0,
            "returns": 100.0,
            "online_net_revenue": 3000.0,
            "marketing_spend": 310.0,
            "returning_customers": 31,
            "new_customers": 31,
            "new_net_revenue_new_seg": 1240.0,
            "returning_customers_net_revenue": 1860.0,
        }

    # 7 days of a 31-day month
    out = sum_table1_budget_uniform_daily(get_month, date(2026, 10, 12), date(2026, 10, 18))
    assert round(out["new_customers_net_revenue"], 6) == round(1240.0 * 7 / 31, 6)
    assert round(out["returning_customers_net_revenue"], 6) == round(1860.0 * 7 / 31, 6)


def test_budget_csv_layouts_keep_segment_net_separate_from_total():
    from weekly_report.api.routes import (
        _budget_table1_from_budget_dataframe,
        _table1_budget_dict_for_api,
    )

    wide = pd.DataFrame(
        {
            "Metric": [
                "Total Gross Revenue",
                "Net Revenue",
                "New Net Revenue",
                "Returning Net Revenue",
                "Online Marketing Spend",
            ],
            "October 2026": [10000, 9000, 3000, 6000, 1000],
        }
    )
    wide_out = _budget_table1_from_budget_dataframe(wide, 2026, 10)
    assert wide_out["online_net_revenue"] == 9000
    assert wide_out["new_customers_net_revenue"] == 3000
    assert wide_out["returning_customers_net_revenue"] == 6000

    long = pd.DataFrame(
        {
            "Metric": ["Net Revenue", "New Net Revenue", "Returning Net Revenue"],
            "Month": ["October 2026", "October 2026", "October 2026"],
            "Value": [9000, 3000, 6000],
            "Market": ["Total CDLP", "Total CDLP", "Total CDLP"],
        }
    )
    long_out = _budget_table1_from_budget_dataframe(long, 2026, 10)
    assert long_out["online_net_revenue"] == 9000
    assert long_out["new_customers_net_revenue"] == 3000
    assert long_out["returning_customers_net_revenue"] == 6000

    api = _table1_budget_dict_for_api(long_out)
    assert "new_net_revenue_new_seg" not in api
    assert api["new_customers_net_revenue"] == 3000
    assert api["returning_customers_net_revenue"] == 6000
