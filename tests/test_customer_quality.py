"""Tests for customer quality metrics."""

import pandas as pd

from weekly_report.src.metrics.customer_discount_quality import (
    _bucket_discount_depth,
    _build_first_orders,
    _build_order_level,
    _compute_cohort_metrics,
    compute_pathways,
)


def test_discount_flag_code_vs_markdown():
    df = pd.DataFrame(
        [
            {
                "Order ID": "1",
                "Customer Email": "a@example.com",
                "Created at": "2025-01-01",
                "Price": 100,
                "Quantity": 1,
                "Compare at price": 100,
                "Total discounts": 10,
                "Discount code": "SAVE10",
            },
            {
                "Order ID": "2",
                "Customer Email": "b@example.com",
                "Created at": "2025-01-02",
                "Price": 80,
                "Quantity": 1,
                "Compare at price": 100,
                "Total discounts": 0,
                "Discount code": "",
            },
        ]
    )
    orders, _ = _build_order_level(df)
    row1 = orders.loc[orders["order_id"] == "1"].iloc[0]
    row2 = orders.loc[orders["order_id"] == "2"].iloc[0]

    assert row1["has_code_or_auto_discount"] is True
    assert row1["has_markdown"] is False
    assert row1["is_discounted_order"] is True

    assert row2["has_code_or_auto_discount"] is False
    assert row2["has_markdown"] is True
    assert row2["is_discounted_order"] is True


def test_maturity_gating_sets_null_metrics():
    customer_window_df = pd.DataFrame(
        [
            {
                "customer_id": "a",
                "cohort": "2025-01",
                "cohort_start_date": pd.Timestamp("2025-01-01"),
                "total_revenue": 200,
                "full_price_revenue": 100,
                "gross_sales": 220,
                "discount_amount": 20,
                "repeat_flag": 1,
                "gross_profit": 50,
            },
            {
                "customer_id": "b",
                "cohort": "2025-04",
                "cohort_start_date": pd.Timestamp("2025-04-01"),
                "total_revenue": 120,
                "full_price_revenue": 60,
                "gross_sales": 130,
                "discount_amount": 10,
                "repeat_flag": 0,
                "gross_profit": 20,
            },
        ]
    )
    as_of_date = pd.Timestamp("2025-08-01")
    rows = _compute_cohort_metrics(customer_window_df, as_of_date, window_days=180)
    row_map = {r["cohort"]: r for r in rows}
    assert row_map["2025-01"]["eligible"] is True
    assert row_map["2025-04"]["eligible"] is False
    assert row_map["2025-04"]["metrics"]["net_sales_per_customer"] is None


def test_discount_depth_bucket():
    assert _bucket_discount_depth(0.05) == "0-10%"
    assert _bucket_discount_depth(0.15) == "10-20%"
    assert _bucket_discount_depth(0.25) == "20-30%"
    assert _bucket_discount_depth(0.35) == "30%+"


def test_pathway_classification():
    order_df = pd.DataFrame(
        [
            # Discount-acquired customer A: promo -> full-price
            {
                "order_id": "1",
                "customer_id": "a",
                "order_date": pd.Timestamp("2025-01-05"),
                "gross_sales": 100,
                "net_sales": 90,
                "total_discounts": 10,
                "markdown_discount_amount": 0,
                "order_discount_amount": 10,
                "is_discounted_order": True,
                "is_full_price_order": False,
                "gross_profit": 40,
            },
            {
                "order_id": "2",
                "customer_id": "a",
                "order_date": pd.Timestamp("2025-02-05"),
                "gross_sales": 120,
                "net_sales": 120,
                "total_discounts": 0,
                "markdown_discount_amount": 0,
                "order_discount_amount": 0,
                "is_discounted_order": False,
                "is_full_price_order": True,
                "gross_profit": 60,
            },
            # Discount-acquired customer B: one-and-done
            {
                "order_id": "3",
                "customer_id": "b",
                "order_date": pd.Timestamp("2025-01-10"),
                "gross_sales": 100,
                "net_sales": 80,
                "total_discounts": 20,
                "markdown_discount_amount": 0,
                "order_discount_amount": 20,
                "is_discounted_order": True,
                "is_full_price_order": False,
                "gross_profit": 30,
            },
            # FP-acquired customer C: FP -> FP
            {
                "order_id": "4",
                "customer_id": "c",
                "order_date": pd.Timestamp("2025-01-12"),
                "gross_sales": 90,
                "net_sales": 90,
                "total_discounts": 0,
                "markdown_discount_amount": 0,
                "order_discount_amount": 0,
                "is_discounted_order": False,
                "is_full_price_order": True,
                "gross_profit": 40,
            },
            {
                "order_id": "5",
                "customer_id": "c",
                "order_date": pd.Timestamp("2025-03-01"),
                "gross_sales": 110,
                "net_sales": 110,
                "total_discounts": 0,
                "markdown_discount_amount": 0,
                "order_discount_amount": 0,
                "is_discounted_order": False,
                "is_full_price_order": True,
                "gross_profit": 50,
            },
            # FP-acquired customer D: FP -> Drift (>= 0.8 discounted share)
            {
                "order_id": "6",
                "customer_id": "d",
                "order_date": pd.Timestamp("2025-01-15"),
                "gross_sales": 100,
                "net_sales": 100,
                "total_discounts": 0,
                "markdown_discount_amount": 0,
                "order_discount_amount": 0,
                "is_discounted_order": False,
                "is_full_price_order": True,
                "gross_profit": 45,
            },
            {
                "order_id": "7",
                "customer_id": "d",
                "order_date": pd.Timestamp("2025-02-01"),
                "gross_sales": 90,
                "net_sales": 70,
                "total_discounts": 20,
                "markdown_discount_amount": 0,
                "order_discount_amount": 20,
                "is_discounted_order": True,
                "is_full_price_order": False,
                "gross_profit": 30,
            },
            {
                "order_id": "8",
                "customer_id": "d",
                "order_date": pd.Timestamp("2025-02-15"),
                "gross_sales": 90,
                "net_sales": 70,
                "total_discounts": 20,
                "markdown_discount_amount": 0,
                "order_discount_amount": 20,
                "is_discounted_order": True,
                "is_full_price_order": False,
                "gross_profit": 30,
            },
            {
                "order_id": "9",
                "customer_id": "d",
                "order_date": pd.Timestamp("2025-03-10"),
                "gross_sales": 90,
                "net_sales": 70,
                "total_discounts": 20,
                "markdown_discount_amount": 0,
                "order_discount_amount": 20,
                "is_discounted_order": True,
                "is_full_price_order": False,
                "gross_profit": 30,
            },
            {
                "order_id": "10",
                "customer_id": "d",
                "order_date": pd.Timestamp("2025-04-01"),
                "gross_sales": 90,
                "net_sales": 70,
                "total_discounts": 20,
                "markdown_discount_amount": 0,
                "order_discount_amount": 20,
                "is_discounted_order": True,
                "is_full_price_order": False,
                "gross_profit": 30,
            },
        ]
    )
    first_orders = _build_first_orders(order_df)
    payload = compute_pathways(
        order_df,
        first_orders,
        as_of_date=pd.Timestamp("2025-08-01"),
        window_days=180,
        threshold_low=0.2,
        threshold_high=0.8,
        baseline_months=24,
    )
    trend = payload["trend"]
    assert trend, "Expected pathway trend output"
    cohort = trend[0]
    assert cohort["promo_full_price_share"] == 50.0
    assert cohort["promo_one_and_done_share"] == 50.0
    assert cohort["fp_fp_share"] == 50.0
    assert cohort["fp_drift_share"] == 50.0

