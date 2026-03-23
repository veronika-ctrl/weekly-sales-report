# Customer Discount Quality

This page (`/products/customer`) analyzes customer quality based on discount behavior.

## Discounted order definition
An order is considered discounted when **either** of these conditions is true:
- **Order-level discount**: a discount code / automatic discount is present **or** total discounts > 0.
- **Line-item markdown**: compare-at price > price on any line item.

`is_discounted_order = has_code_or_auto_discount OR has_markdown`

## Thresholds
Segmentation uses two thresholds:
- `low` (default `0.2`)
- `high` (default `0.8`)

These thresholds apply to each customer’s `discounted_order_share` within the cohort window.

## Cohort window
The cohort window defines how long we observe each customer after their first order:
`cohort_window_days` (default 365). Metrics like repeat rates and conversion are computed within this window.

## Key segments
- **Bargain Hunter**: Discount_Acquired + discounted_order_share >= high
- **Promo-to-Full-Price Converter**: Discount_Acquired + discounted_order_share <= low + orders >= 2
- **Hybrid Buyer**: Discount_Acquired + between low/high
- **Full-Price Loyalist**: FP_Acquired + discounted_order_share <= low
- **Full-Price-to-Promo Drifter**: FP_Acquired + discounted_order_share >= high + orders >= 2
- **One-and-Done**: orders_count_in_window == 1 (shown explicitly)

