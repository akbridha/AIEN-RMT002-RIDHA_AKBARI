"""Build the fixed Gold analytics contract from Silver tables."""

from __future__ import annotations

import argparse
import logging
from typing import Any
from uuid import uuid4

from pipelines.ingestion.db import connect
from pipelines.ingestion.run_tracking import execute_tracked_stage

log = logging.getLogger(__name__)

GOLD_TABLES = (
    "order_360",
    "customer_daily",
    "product_daily",
    "channel_campaign_daily",
    "executive_kpis_daily",
)

DELETE_SQL = tuple(f"DELETE FROM gold.{table}" for table in GOLD_TABLES)
GOLD_DIAGNOSTICS_SQL = """
WITH inventory_by_date AS (
    SELECT
        metric_date,
        COUNT(*) FILTER (WHERE stockout_flag IS TRUE) AS stockout_products,
        COUNT(*) FILTER (WHERE stockout_flag IS NOT NULL) AS measured_products
    FROM gold.product_daily
    GROUP BY metric_date
)
SELECT
    (SELECT COUNT(*) FROM gold.channel_campaign_daily WHERE roas IS NULL),
    (SELECT COUNT(*) FROM gold.channel_campaign_daily
        WHERE roas IS NULL AND campaign_spend = 0),
    (SELECT COUNT(*) FROM gold.channel_campaign_daily
        WHERE roas IS NULL AND campaign_spend <> 0),
    (SELECT COUNT(*) FROM gold.channel_campaign_daily WHERE roas = 0),
    (SELECT COUNT(*) FROM gold.channel_campaign_daily
        WHERE roas = 0 AND campaign_spend > 0 AND net_revenue = 0),
    (SELECT COUNT(*) FROM gold.channel_campaign_daily
        WHERE roas = 0 AND (campaign_spend <= 0 OR net_revenue <> 0)),
    (SELECT COUNT(*) FROM gold.customer_daily WHERE active_channel IS NULL),
    (SELECT COUNT(*) FROM gold.customer_daily
        WHERE active_channel IS NULL AND order_count > 0),
    (SELECT COUNT(*) FROM gold.order_360 WHERE store_id IS NULL),
    (SELECT COUNT(*) FROM gold.order_360
        WHERE store_id IS NULL AND sales_channel = 'STORE'),
    (SELECT COUNT(*) FROM gold.executive_kpis_daily
        WHERE stockout_rate = 0),
    (SELECT COUNT(*)
        FROM gold.executive_kpis_daily AS kpis
        LEFT JOIN inventory_by_date AS inventory USING (metric_date)
        WHERE kpis.stockout_rate <> COALESCE(
            ROUND(
                inventory.stockout_products::NUMERIC
                    / NULLIF(inventory.measured_products, 0),
                4
            ),
            0
        ))
"""
GOLD_DIAGNOSTIC_FIELDS = (
    "null_roas",
    "null_roas_zero_spend",
    "null_roas_nonzero_spend",
    "zero_roas",
    "zero_roas_positive_spend_no_revenue",
    "zero_roas_inconsistent",
    "null_active_channel",
    "null_active_channel_with_orders",
    "null_store_id",
    "null_store_id_store_channel",
    "zero_stockout_rate_days",
    "stockout_rate_mismatch_days",
)
GOLD_DIAGNOSTIC_VIOLATIONS = (
    "null_roas_nonzero_spend",
    "zero_roas_inconsistent",
    "null_active_channel_with_orders",
    "null_store_id_store_channel",
    "stockout_rate_mismatch_days",
)

BUILD_ORDER_360_SQL = """
WITH item_totals AS (
    SELECT
        order_id,
        COUNT(*)::INTEGER AS item_count,
        COALESCE(SUM(quantity), 0)::INTEGER AS unit_quantity,
        COALESCE(SUM(quantity * unit_price), 0)::NUMERIC(14, 2)
            AS gross_merchandise_value,
        COALESCE(SUM(item_discount_amount), 0)::NUMERIC(14, 2)
            AS item_discount_amount
    FROM silver.order_items
    GROUP BY order_id
),
promotion_totals AS (
    SELECT
        order_id,
        COUNT(*)::INTEGER AS promotion_count,
        COALESCE(SUM(discount_amount), 0)::NUMERIC(14, 2) AS discount_amount
    FROM silver.order_promotions
    GROUP BY order_id
),
payment_totals AS (
    SELECT
        order_id,
        COALESCE(SUM(amount) FILTER (WHERE event_type = 'PAYMENT_CAPTURED'), 0)
            ::NUMERIC(14, 2) AS captured_payment_amount
    FROM silver.payment_events
    WHERE order_id IS NOT NULL
    GROUP BY order_id
),
refund_totals AS (
    SELECT
        order_id,
        COALESCE(SUM(amount) FILTER (WHERE event_type = 'REFUND_COMPLETED'), 0)
            ::NUMERIC(14, 2) AS refunded_amount
    FROM silver.refund_events
    WHERE order_id IS NOT NULL
    GROUP BY order_id
),
return_statuses AS (
    SELECT DISTINCT ON (order_id)
        order_id,
        event_type AS return_status
    FROM silver.return_events
    WHERE order_id IS NOT NULL
    ORDER BY order_id, occurred_at_utc DESC, event_id DESC
),
ordered_orders AS (
    SELECT
        order_id,
        customer_id,
        ordered_at_utc,
        sales_channel,
        store_id,
        shipping_revenue,
        order_status,
        ROW_NUMBER() OVER (
            PARTITION BY customer_id
            ORDER BY ordered_at_utc, order_id
        ) AS customer_order_number
    FROM silver.orders
)
INSERT INTO gold.order_360 (
    order_id, customer_id, order_date, sales_channel, store_id,
    gross_merchandise_value, discount_amount, shipping_revenue,
    captured_payment_amount, refunded_amount, net_revenue, item_count,
    unit_quantity, order_status, payment_status, return_status,
    promotion_count, first_order_flag, pipeline_run_id
)
SELECT
    orders.order_id,
    orders.customer_id,
    (orders.ordered_at_utc AT TIME ZONE 'UTC')::DATE,
    orders.sales_channel,
    orders.store_id,
    COALESCE(items.gross_merchandise_value, 0),
    COALESCE(items.item_discount_amount, 0) + COALESCE(promotions.discount_amount, 0),
    orders.shipping_revenue,
    COALESCE(payments.captured_payment_amount, 0),
    COALESCE(refunds.refunded_amount, 0),
    COALESCE(items.gross_merchandise_value, 0)
        - COALESCE(items.item_discount_amount, 0)
        - COALESCE(promotions.discount_amount, 0)
        + orders.shipping_revenue
        - COALESCE(refunds.refunded_amount, 0),
    COALESCE(items.item_count, 0),
    COALESCE(items.unit_quantity, 0),
    orders.order_status,
    CASE
        WHEN COALESCE(payments.captured_payment_amount, 0) <= 0 THEN 'NOT_CAPTURED'
        WHEN COALESCE(payments.captured_payment_amount, 0)
            >= COALESCE(items.gross_merchandise_value, 0)
                - COALESCE(items.item_discount_amount, 0)
                - COALESCE(promotions.discount_amount, 0)
                + orders.shipping_revenue
            THEN 'CAPTURED'
        ELSE 'PARTIALLY_CAPTURED'
    END,
    COALESCE(returns.return_status, 'NO_RETURN'),
    COALESCE(promotions.promotion_count, 0),
    orders.customer_order_number = 1,
    %s
FROM ordered_orders AS orders
LEFT JOIN item_totals AS items USING (order_id)
LEFT JOIN promotion_totals AS promotions USING (order_id)
LEFT JOIN payment_totals AS payments USING (order_id)
LEFT JOIN refund_totals AS refunds USING (order_id)
LEFT JOIN return_statuses AS returns USING (order_id)
"""

BUILD_CUSTOMER_DAILY_SQL = """
WITH order_metrics AS (
    SELECT
        customer_id,
        order_date AS metric_date,
        COUNT(*)::INTEGER AS order_count,
        SUM(unit_quantity)::INTEGER AS unit_quantity,
        SUM(gross_merchandise_value)::NUMERIC(14, 2) AS gross_revenue,
        SUM(net_revenue)::NUMERIC(14, 2) AS net_revenue
    FROM gold.order_360
    GROUP BY customer_id, order_date
),
channel_counts AS (
    SELECT
        customer_id,
        order_date AS metric_date,
        sales_channel,
        ROW_NUMBER() OVER (
            PARTITION BY customer_id, order_date
            ORDER BY COUNT(*) DESC, sales_channel
        ) AS channel_rank
    FROM gold.order_360
    GROUP BY customer_id, order_date, sales_channel
),
active_channels AS (
    SELECT customer_id, metric_date, sales_channel
    FROM channel_counts
    WHERE channel_rank = 1
),
refund_metrics AS (
    SELECT
        orders.customer_id,
        (events.occurred_at_utc AT TIME ZONE 'UTC')::DATE AS metric_date,
        SUM(events.amount)::NUMERIC(14, 2) AS refund_amount
    FROM silver.refund_events AS events
    JOIN silver.orders AS orders USING (order_id)
    WHERE events.event_type = 'REFUND_COMPLETED'
    GROUP BY orders.customer_id, (events.occurred_at_utc AT TIME ZONE 'UTC')::DATE
),
return_metrics AS (
    SELECT
        orders.customer_id,
        (events.occurred_at_utc AT TIME ZONE 'UTC')::DATE AS metric_date,
        COUNT(DISTINCT events.order_id)::INTEGER AS return_count
    FROM silver.return_events AS events
    JOIN silver.orders AS orders USING (order_id)
    GROUP BY orders.customer_id, (events.occurred_at_utc AT TIME ZONE 'UTC')::DATE
),
support_metrics AS (
    SELECT
        COALESCE(events.customer_id, orders.customer_id) AS customer_id,
        (events.occurred_at_utc AT TIME ZONE 'UTC')::DATE AS metric_date,
        COUNT(DISTINCT COALESCE(events.ticket_id, events.event_id))::INTEGER
            AS support_contacts
    FROM silver.support_events AS events
    LEFT JOIN silver.orders AS orders USING (order_id)
    WHERE events.event_type IN ('SUPPORT_TICKET_CREATED', 'SUPPORT_CONTACT_CREATED')
      AND COALESCE(events.customer_id, orders.customer_id) IS NOT NULL
    GROUP BY
        COALESCE(events.customer_id, orders.customer_id),
        (events.occurred_at_utc AT TIME ZONE 'UTC')::DATE
),
customer_dates AS (
    SELECT customer_id, metric_date FROM order_metrics
    UNION
    SELECT customer_id, metric_date FROM refund_metrics
    UNION
    SELECT customer_id, metric_date FROM return_metrics
    UNION
    SELECT customer_id, metric_date FROM support_metrics
),
customer_day_history AS (
    SELECT
        dates.customer_id,
        dates.metric_date,
        COUNT(orders.order_id)::INTEGER AS cumulative_order_count,
        MIN(orders.order_date) AS first_order_date
    FROM customer_dates AS dates
    LEFT JOIN gold.order_360 AS orders
        ON orders.customer_id = dates.customer_id
       AND orders.order_date <= dates.metric_date
    GROUP BY dates.customer_id, dates.metric_date
)
INSERT INTO gold.customer_daily (
    customer_id, metric_date, order_count, unit_quantity, gross_revenue,
    net_revenue, refund_amount, return_count, support_contacts, active_channel,
    new_customer_flag, repeat_customer_flag, pipeline_run_id
)
SELECT
    dates.customer_id,
    dates.metric_date,
    COALESCE(orders.order_count, 0),
    COALESCE(orders.unit_quantity, 0),
    COALESCE(orders.gross_revenue, 0),
    COALESCE(orders.net_revenue, 0),
    COALESCE(refunds.refund_amount, 0),
    COALESCE(returns.return_count, 0),
    COALESCE(support.support_contacts, 0),
    channels.sales_channel,
    COALESCE(history.first_order_date = dates.metric_date, FALSE),
    COALESCE(history.cumulative_order_count, 0) > 1,
    %s
FROM customer_dates AS dates
LEFT JOIN order_metrics AS orders
    ON orders.customer_id = dates.customer_id
   AND orders.metric_date = dates.metric_date
LEFT JOIN active_channels AS channels
    ON channels.customer_id = dates.customer_id
   AND channels.metric_date = dates.metric_date
LEFT JOIN refund_metrics AS refunds
    ON refunds.customer_id = dates.customer_id
   AND refunds.metric_date = dates.metric_date
LEFT JOIN return_metrics AS returns
    ON returns.customer_id = dates.customer_id
   AND returns.metric_date = dates.metric_date
LEFT JOIN support_metrics AS support
    ON support.customer_id = dates.customer_id
   AND support.metric_date = dates.metric_date
LEFT JOIN customer_day_history AS history
    ON history.customer_id = dates.customer_id
   AND history.metric_date = dates.metric_date
"""

BUILD_PRODUCT_DAILY_SQL = """
WITH order_product AS (
    SELECT
        orders.order_id,
        orders.ordered_at_utc,
        items.product_id,
        SUM(items.quantity)::INTEGER AS units_sold,
        SUM(items.quantity * items.unit_price)::NUMERIC(14, 2) AS gross_revenue,
        SUM(items.item_discount_amount)::NUMERIC(14, 2) AS item_discount_amount
    FROM silver.order_items AS items
    JOIN silver.orders AS orders USING (order_id)
    GROUP BY orders.order_id, orders.ordered_at_utc, items.product_id
),
order_product_totals AS (
    SELECT
        order_id,
        SUM(gross_revenue)::NUMERIC(14, 2) AS order_gross_revenue
    FROM order_product
    GROUP BY order_id
),
order_discounts AS (
    SELECT order_id, SUM(discount_amount)::NUMERIC(14, 2) AS discount_amount
    FROM silver.order_promotions
    GROUP BY order_id
),
order_refunds AS (
    SELECT
        order_id,
        SUM(amount)::NUMERIC(14, 2) AS refunded_amount
    FROM silver.refund_events
    WHERE event_type = 'REFUND_COMPLETED'
      AND order_id IS NOT NULL
    GROUP BY order_id
),
sales_by_product_day AS (
    SELECT
        product.product_id,
        (product.ordered_at_utc AT TIME ZONE 'UTC')::DATE AS metric_date,
        SUM(product.units_sold)::INTEGER AS units_sold,
        COUNT(DISTINCT product.order_id)::INTEGER AS order_count,
        SUM(product.gross_revenue)::NUMERIC(14, 2) AS gross_revenue,
        SUM(
            product.gross_revenue
            - product.item_discount_amount
            - COALESCE(
                discounts.discount_amount
                    * product.gross_revenue
                    / NULLIF(totals.order_gross_revenue, 0),
                0
            )
            - COALESCE(
                refunds.refunded_amount
                    * product.gross_revenue
                    / NULLIF(totals.order_gross_revenue, 0),
                0
            )
        )::NUMERIC(14, 2) AS net_revenue
    FROM order_product AS product
    JOIN order_product_totals AS totals USING (order_id)
    LEFT JOIN order_discounts AS discounts USING (order_id)
    LEFT JOIN order_refunds AS refunds USING (order_id)
    GROUP BY product.product_id, (product.ordered_at_utc AT TIME ZONE 'UTC')::DATE
),
promotion_by_product_day AS (
    SELECT
        product.product_id,
        (orders.ordered_at_utc AT TIME ZONE 'UTC')::DATE AS metric_date,
        COUNT(DISTINCT promotions.promotion_id)::INTEGER AS promotion_count
    FROM silver.order_promotions AS promotions
    JOIN silver.orders AS orders USING (order_id)
    JOIN silver.order_items AS product USING (order_id)
    GROUP BY product.product_id, (orders.ordered_at_utc AT TIME ZONE 'UTC')::DATE
),
inventory_by_product_day AS (
    SELECT
        product_id,
        snapshot_date AS metric_date,
        SUM(available_quantity)::INTEGER AS available_inventory,
        SUM(reserved_quantity)::INTEGER AS reserved_inventory,
        BOOL_OR(available_quantity = 0) AS stockout_flag
    FROM silver.inventory_snapshots
    GROUP BY product_id, snapshot_date
),
product_dates AS (
    SELECT product_id, metric_date FROM sales_by_product_day
    UNION
    SELECT product_id, metric_date FROM inventory_by_product_day
)
INSERT INTO gold.product_daily (
    product_id, metric_date, active_category, units_sold, order_count,
    gross_revenue, net_revenue, refunded_units, available_inventory,
    reserved_inventory, stockout_flag, promotion_count, pipeline_run_id
)
SELECT
    dates.product_id,
    dates.metric_date,
    category.category_name,
    COALESCE(sales.units_sold, 0),
    COALESCE(sales.order_count, 0),
    COALESCE(sales.gross_revenue, 0),
    COALESCE(sales.net_revenue, 0),
    0,
    inventory.available_inventory,
    inventory.reserved_inventory,
    CASE
        WHEN inventory.available_inventory IS NULL THEN NULL
        ELSE inventory.stockout_flag
    END,
    COALESCE(promotions.promotion_count, 0),
    %s
FROM product_dates AS dates
LEFT JOIN sales_by_product_day AS sales
    ON sales.product_id = dates.product_id
   AND sales.metric_date = dates.metric_date
LEFT JOIN promotion_by_product_day AS promotions
    ON promotions.product_id = dates.product_id
   AND promotions.metric_date = dates.metric_date
LEFT JOIN inventory_by_product_day AS inventory
    ON inventory.product_id = dates.product_id
   AND inventory.metric_date = dates.metric_date
LEFT JOIN LATERAL (
    SELECT categories.category_name
    FROM silver.product_categories AS categories
    WHERE categories.product_id = dates.product_id
      AND categories.valid_from_utc <= dates.metric_date::TIMESTAMP AT TIME ZONE 'UTC'
      AND (
          categories.valid_to_utc IS NULL
          OR categories.valid_to_utc > dates.metric_date::TIMESTAMP AT TIME ZONE 'UTC'
      )
    ORDER BY categories.valid_from_utc DESC
    LIMIT 1
) AS category ON TRUE
"""

BUILD_CHANNEL_CAMPAIGN_DAILY_SQL = """
WITH ranked_attributions AS (
    SELECT
        events.order_id,
        events.campaign_id,
        events.channel AS sales_channel,
        ROW_NUMBER() OVER (
            PARTITION BY events.order_id
            ORDER BY events.occurred_at_utc, events.event_id
        ) AS attribution_rank
    FROM silver.web_events AS events
    WHERE events.order_id IS NOT NULL
      AND events.campaign_id IS NOT NULL
      AND events.channel IS NOT NULL
),
attributed_orders AS (
    SELECT
        orders.order_date AS metric_date,
        attribution.sales_channel,
        attribution.campaign_id,
        orders.order_id,
        orders.customer_id,
        orders.gross_merchandise_value,
        orders.net_revenue,
        orders.refunded_amount
    FROM ranked_attributions AS attribution
    JOIN gold.order_360 AS orders USING (order_id)
    WHERE attribution.attribution_rank = 1
),
attribution_metrics AS (
    SELECT
        metric_date,
        sales_channel,
        campaign_id,
        COUNT(DISTINCT order_id)::INTEGER AS attributed_orders,
        COUNT(DISTINCT customer_id)::INTEGER AS attributed_customers,
        SUM(gross_merchandise_value)::NUMERIC(14, 2) AS gross_revenue,
        SUM(net_revenue)::NUMERIC(14, 2) AS net_revenue,
        SUM(refunded_amount)::NUMERIC(14, 2) AS refunds
    FROM attributed_orders
    GROUP BY metric_date, sales_channel, campaign_id
),
spend_metrics AS (
    SELECT
        spend_date AS metric_date,
        channel AS sales_channel,
        campaign_id,
        SUM(spend_amount)::NUMERIC(14, 2) AS campaign_spend
    FROM silver.campaign_spend
    GROUP BY spend_date, channel, campaign_id
),
session_metrics AS (
    SELECT
        (occurred_at_utc AT TIME ZONE 'UTC')::DATE AS metric_date,
        channel AS sales_channel,
        campaign_id,
        COUNT(DISTINCT session_id)::INTEGER AS campaign_sessions
    FROM silver.web_events
    WHERE campaign_id IS NOT NULL
      AND channel IS NOT NULL
      AND session_id IS NOT NULL
    GROUP BY
        (occurred_at_utc AT TIME ZONE 'UTC')::DATE,
        channel,
        campaign_id
),
campaign_keys AS (
    SELECT metric_date, sales_channel, campaign_id FROM spend_metrics
    UNION
    SELECT metric_date, sales_channel, campaign_id FROM attribution_metrics
    UNION
    SELECT metric_date, sales_channel, campaign_id FROM session_metrics
)
INSERT INTO gold.channel_campaign_daily (
    metric_date, sales_channel, campaign_id, campaign_spend,
    attributed_orders, attributed_customers, gross_revenue, net_revenue,
    refunds, roas, conversion_rate, pipeline_run_id
)
SELECT
    keys.metric_date,
    keys.sales_channel,
    keys.campaign_id,
    COALESCE(spend.campaign_spend, 0),
    COALESCE(attribution.attributed_orders, 0),
    COALESCE(attribution.attributed_customers, 0),
    COALESCE(attribution.gross_revenue, 0),
    COALESCE(attribution.net_revenue, 0),
    COALESCE(attribution.refunds, 0),
    CASE
        WHEN COALESCE(spend.campaign_spend, 0) = 0 THEN NULL
        ELSE COALESCE(attribution.net_revenue, 0) / spend.campaign_spend
    END,
    CASE
        WHEN COALESCE(sessions.campaign_sessions, 0) = 0 THEN NULL
        ELSE COALESCE(attribution.attributed_orders, 0)::NUMERIC
            / sessions.campaign_sessions
    END,
    %s
FROM campaign_keys AS keys
LEFT JOIN spend_metrics AS spend
    ON spend.metric_date = keys.metric_date
   AND spend.sales_channel = keys.sales_channel
   AND spend.campaign_id = keys.campaign_id
LEFT JOIN attribution_metrics AS attribution
    ON attribution.metric_date = keys.metric_date
   AND attribution.sales_channel = keys.sales_channel
   AND attribution.campaign_id = keys.campaign_id
LEFT JOIN session_metrics AS sessions
    ON sessions.metric_date = keys.metric_date
   AND sessions.sales_channel = keys.sales_channel
   AND sessions.campaign_id = keys.campaign_id
"""

BUILD_EXECUTIVE_KPIS_DAILY_SQL = """
WITH business_dates AS (
    SELECT order_date AS metric_date FROM gold.order_360
    UNION
    SELECT snapshot_date FROM silver.inventory_snapshots
    UNION
    SELECT (occurred_at_utc AT TIME ZONE 'UTC')::DATE FROM silver.support_events
    UNION
    SELECT (occurred_at_utc AT TIME ZONE 'UTC')::DATE FROM silver.refund_events
    UNION
    SELECT (occurred_at_utc AT TIME ZONE 'UTC')::DATE FROM silver.return_events
),
order_metrics AS (
    SELECT
        order_date AS metric_date,
        COUNT(*)::INTEGER AS total_orders,
        SUM(gross_merchandise_value)::NUMERIC(14, 2) AS gross_revenue,
        SUM(net_revenue)::NUMERIC(14, 2) AS net_revenue,
        AVG(gross_merchandise_value)::NUMERIC(14, 2) AS average_order_value,
        COUNT(*) FILTER (
            WHERE captured_payment_amount > 0 AND refunded_amount > 0
        )::NUMERIC AS refunded_captured_orders,
        COUNT(*) FILTER (WHERE captured_payment_amount > 0)::NUMERIC
            AS captured_orders,
        COUNT(*) FILTER (
            WHERE order_status NOT IN ('PENDING', 'PROCESSING', 'CREATED')
        )::NUMERIC AS resolved_orders
    FROM gold.order_360
    GROUP BY order_date
),
returned_orders AS (
    SELECT DISTINCT order_id
    FROM silver.return_events
    WHERE order_id IS NOT NULL
),
return_metrics AS (
    SELECT
        orders.order_date AS metric_date,
        COUNT(*) FILTER (WHERE returned.order_id IS NOT NULL)::NUMERIC
            AS returned_resolved_orders
    FROM gold.order_360 AS orders
    LEFT JOIN returned_orders AS returned USING (order_id)
    WHERE orders.order_status NOT IN ('PENDING', 'PROCESSING', 'CREATED')
    GROUP BY orders.order_date
),
customer_metrics AS (
    SELECT
        metric_date,
        COUNT(*) FILTER (WHERE order_count > 0)::INTEGER AS active_customers,
        COUNT(*) FILTER (
            WHERE order_count > 0 AND repeat_customer_flag
        )::NUMERIC AS repeat_customers,
        SUM(support_contacts)::NUMERIC AS support_contacts
    FROM gold.customer_daily
    GROUP BY metric_date
),
inventory_metrics AS (
    SELECT
        metric_date,
        COUNT(*) FILTER (WHERE stockout_flag IS TRUE)::NUMERIC AS stockout_products,
        COUNT(*) FILTER (WHERE stockout_flag IS NOT NULL)::NUMERIC
            AS products_with_inventory
    FROM gold.product_daily
    GROUP BY metric_date
)
INSERT INTO gold.executive_kpis_daily (
    metric_date, total_orders, gross_revenue, net_revenue,
    average_order_value, refund_rate, return_rate, repeat_customer_rate,
    stockout_rate, active_customers, support_contact_rate,
    data_freshness_utc, pipeline_run_id
)
SELECT
    dates.metric_date,
    COALESCE(orders.total_orders, 0),
    COALESCE(orders.gross_revenue, 0),
    COALESCE(orders.net_revenue, 0),
    COALESCE(orders.average_order_value, 0),
    CASE
        WHEN COALESCE(orders.captured_orders, 0) = 0 THEN 0
        ELSE COALESCE(orders.refunded_captured_orders, 0) / orders.captured_orders
    END,
    CASE
        WHEN COALESCE(orders.resolved_orders, 0) = 0 THEN 0
        ELSE COALESCE(returns.returned_resolved_orders, 0) / orders.resolved_orders
    END,
    CASE
        WHEN COALESCE(customers.active_customers, 0) = 0 THEN 0
        ELSE COALESCE(customers.repeat_customers, 0) / customers.active_customers
    END,
    CASE
        WHEN COALESCE(inventory.products_with_inventory, 0) = 0 THEN 0
        ELSE COALESCE(inventory.stockout_products, 0) / inventory.products_with_inventory
    END,
    COALESCE(customers.active_customers, 0),
    CASE
        WHEN COALESCE(orders.total_orders, 0) = 0 THEN 0
        ELSE COALESCE(customers.support_contacts, 0) / orders.total_orders
    END,
    CURRENT_TIMESTAMP,
    %s
FROM business_dates AS dates
LEFT JOIN order_metrics AS orders USING (metric_date)
LEFT JOIN return_metrics AS returns USING (metric_date)
LEFT JOIN customer_metrics AS customers USING (metric_date)
LEFT JOIN inventory_metrics AS inventory USING (metric_date)
"""

BUILD_STATEMENTS = (
    ("order_360", BUILD_ORDER_360_SQL),
    ("customer_daily", BUILD_CUSTOMER_DAILY_SQL),
    ("product_daily", BUILD_PRODUCT_DAILY_SQL),
    ("channel_campaign_daily", BUILD_CHANNEL_CAMPAIGN_DAILY_SQL),
    ("executive_kpis_daily", BUILD_EXECUTIVE_KPIS_DAILY_SQL),
)


def _run(
    pipeline_run_id: str | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Rebuild all Gold tables atomically from the current Silver contents."""
    del context
    run_id = pipeline_run_id or f"manual-{uuid4()}"
    results: dict[str, Any] = {
        "pipeline_run_id": run_id,
        "tables": {},
        "rows_loaded": 0,
        "limitations": [
            "product_daily.refunded_units is 0 because Silver refund events "
            "do not retain product or quantity details."
        ],
    }

    log.info(
        "Starting Gold build from Silver (tables=%d, pipeline_run_id=%s)",
        len(GOLD_TABLES),
        run_id,
    )
    with connect("local") as connection:
        log.info("Clearing existing Gold rows for an atomic full rebuild")
        for statement in DELETE_SQL:
            connection.execute(statement)

        for table_number, (table, statement) in enumerate(BUILD_STATEMENTS, start=1):
            log.info(
                "[%d/%d] Building gold.%s from Silver",
                table_number,
                len(BUILD_STATEMENTS),
                table,
            )
            connection.execute(statement, (run_id,))
            row = connection.execute(
                f"SELECT COUNT(*) FROM gold.{table}"
            ).fetchone()
            rows_loaded = int(row[0])
            results["tables"][table] = {"loaded": rows_loaded}
            results["rows_loaded"] += rows_loaded
            log.info(
                "[%d/%d] Finished gold.%s: loaded=%d",
                table_number,
                len(BUILD_STATEMENTS),
                table,
                rows_loaded,
            )

        diagnostic_row = connection.execute(GOLD_DIAGNOSTICS_SQL).fetchone()
        diagnostics = dict(
            zip(GOLD_DIAGNOSTIC_FIELDS, (int(value) for value in diagnostic_row), strict=True)
        )
        results["diagnostics"] = diagnostics
        log.info("Gold NULL/zero diagnostics: %s", diagnostics)
        violations = {
            field: diagnostics[field]
            for field in GOLD_DIAGNOSTIC_VIOLATIONS
            if diagnostics[field] > 0
        }
        if violations:
            raise ValueError(f"Gold NULL/zero metric checks failed: {violations}")

        log.info(
            "Expected values: NULL roas requires zero campaign spend; NULL active_channel "
            "requires no orders that day; NULL store_id is valid for non-STORE channels; "
            "stockout_rate counts product-days with at least one location at zero stock."
        )

    log.warning(
        "Gold metric limitation: %s",
        results["limitations"][0],
    )
    log.info("Gold build completed: %s", results)
    return results


def run(
    pipeline_run_id: str | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build Gold and persist the stage result to Ops."""
    run_id = pipeline_run_id or f"manual-{uuid4()}"
    dag_run = (context or {}).get("dag_run")
    return execute_tracked_stage(
        connect=connect,
        pipeline_run_id=run_id,
        task_name="build_gold",
        trigger_source="airflow" if dag_run is not None else "manual",
        dag_run_id=str(dag_run.run_id) if dag_run is not None else None,
        operation=lambda: _run(pipeline_run_id=run_id, context=context),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pipeline-run-id")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    result = run(pipeline_run_id=args.pipeline_run_id)
    log.info("Gold build completed: %s", result)


if __name__ == "__main__":
    main()
