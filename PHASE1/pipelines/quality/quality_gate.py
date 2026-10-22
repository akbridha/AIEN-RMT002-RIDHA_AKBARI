"""Validate Silver data before allowing the Gold build to run."""

from __future__ import annotations

import argparse
import logging
from typing import Any
from uuid import uuid4

from pipelines.ingestion.db import connect
from pipelines.ingestion.run_tracking import ensure_pipeline_run, execute_tracked_stage

log = logging.getLogger(__name__)

LATEST_SILVER_RUN_SQL = """
SELECT task.pipeline_run_id
FROM ops.pipeline_tasks AS task
WHERE task.task_name = 'build_silver'
  AND task.status = 'SUCCESS'
  AND task.finished_at_utc IS NOT NULL
  AND EXISTS (
      SELECT 1
      FROM silver.orders AS orders
      WHERE orders.pipeline_run_id = task.pipeline_run_id
  )
  AND EXISTS (
      SELECT 1
      FROM silver.order_items AS items
      WHERE items.pipeline_run_id = task.pipeline_run_id
  )
ORDER BY task.finished_at_utc DESC, task.task_id DESC
LIMIT 1
"""

REQUIRED_SILVER_TABLES = (
    "silver.orders",
    "silver.order_items",
    "silver.order_promotions",
    "silver.promotions",
    "silver.payment_events",
    "silver.refund_events",
    "silver.return_events",
    "silver.support_events",
    "silver.web_events",
    "silver.inventory_snapshots",
    "silver.campaign_spend",
    "silver.product_categories",
    "silver.customers",
    "silver.products",
    "silver.sales_channels",
    "silver.rejected_records",
)

REFERENCE_CHECKS = (
    (
        "orders_customer_reference",
        """
        SELECT COUNT(*)
        FROM silver.orders AS orders
        LEFT JOIN silver.customers AS customers USING (customer_id)
        WHERE customers.customer_id IS NULL
        """,
        "Orders without a matching customer",
    ),
    (
        "orders_sales_channel_reference",
        """
        SELECT COUNT(*)
        FROM silver.orders AS orders
        LEFT JOIN silver.sales_channels AS channels
            ON channels.channel_name = orders.sales_channel
        WHERE channels.channel_id IS NULL
        """,
        "Orders without a matching sales channel",
    ),
    (
        "order_items_order_reference",
        """
        SELECT COUNT(*)
        FROM silver.order_items AS items
        LEFT JOIN silver.orders AS orders USING (order_id)
        WHERE orders.order_id IS NULL
        """,
        "Order items without a matching order",
    ),
    (
        "order_items_product_reference",
        """
        SELECT COUNT(*)
        FROM silver.order_items AS items
        LEFT JOIN silver.products AS products USING (product_id)
        WHERE products.product_id IS NULL
        """,
        "Order items without a matching product",
    ),
    (
        "order_promotions_references",
        """
        SELECT COUNT(*)
        FROM silver.order_promotions AS order_promotions
        LEFT JOIN silver.orders AS orders USING (order_id)
        LEFT JOIN silver.promotions AS promotions USING (promotion_id)
        WHERE orders.order_id IS NULL OR promotions.promotion_id IS NULL
        """,
        "Order promotions with missing order or promotion",
    ),
    (
        "inventory_product_reference",
        """
        SELECT COUNT(*)
        FROM silver.inventory_snapshots AS inventory
        LEFT JOIN silver.products AS products USING (product_id)
        WHERE products.product_id IS NULL
        """,
        "Inventory snapshots without a matching product",
    ),
)


def _latest_silver_run_id() -> str:
    """Find the newest tracked successful Silver run that has gate inputs."""
    with connect("local") as connection:
        row = connection.execute(LATEST_SILVER_RUN_SQL).fetchone()
    if row is None or not row[0]:
        raise RuntimeError(
            "No successful Silver run with orders and order_items was found. "
            "Run `python -m pipelines.run_pipeline` for an end-to-end execution, "
            "or pass the same --pipeline-run-id used by build_silver."
        )
    run_id = str(row[0])
    log.info(
        "No pipeline_run_id supplied; using latest successful Silver run %s",
        run_id,
    )
    return run_id


def _result(
    name: str,
    check_type: str,
    expected: int,
    actual: int,
    detail: str,
    *,
    passed: bool,
) -> dict[str, Any]:
    return {
        "check_name": f"silver_gate:{name}",
        "check_type": check_type,
        "target_table": "silver",
        "expected_value": expected,
        "actual_value": actual,
        "passed": passed,
        "detail": detail,
    }


def _record_results(
    connection: Any,
    pipeline_run_id: str,
    checks: list[dict[str, Any]],
) -> None:
    failed_checks = sum(not check["passed"] for check in checks)
    connection.execute(
        """
        DELETE FROM ops.quality_checks
        WHERE pipeline_run_id = %s AND check_name LIKE %s
        """,
        (pipeline_run_id, "silver_gate:%"),
    )
    for check in checks:
        connection.execute(
            """
            INSERT INTO ops.quality_checks (
                pipeline_run_id, check_name, check_type, target_table,
                expected_value, actual_value, passed, detail
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                pipeline_run_id,
                check["check_name"],
                check["check_type"],
                check["target_table"],
                check["expected_value"],
                check["actual_value"],
                check["passed"],
                check["detail"],
            ),
        )
    connection.execute(
        """
        INSERT INTO ops.quality_gates (
            pipeline_run_id, gate_name, passed, failed_checks
        )
        VALUES (%s, 'silver_gate', %s, %s)
        ON CONFLICT (pipeline_run_id, gate_name) DO UPDATE SET
            passed = EXCLUDED.passed,
            failed_checks = EXCLUDED.failed_checks,
            evaluated_at_utc = now()
        """,
        (pipeline_run_id, failed_checks == 0, failed_checks),
    )


def _run(
    pipeline_run_id: str | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run Silver pre-Gold checks and persist the gate decision to ``ops``."""
    run_id = pipeline_run_id or f"manual-{uuid4()}"
    dag_run = (context or {}).get("dag_run")
    dag_run_id = str(dag_run.run_id) if dag_run is not None else None
    trigger_source = "airflow" if dag_run is not None else "manual"
    checks: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    error_message = ""

    with connect("local") as connection:
        missing_tables = [
            table
            for table in (
                *REQUIRED_SILVER_TABLES,
                "ops.pipeline_runs",
                "ops.quality_checks",
                "ops.quality_gates",
            )
            if connection.execute("SELECT to_regclass(%s)", (table,)).fetchone()[0] is None
        ]
        silver_tables_missing = [
            table for table in missing_tables if table in REQUIRED_SILVER_TABLES
        ]
        checks.append(
            _result(
                "required_tables_available",
                "schema",
                0,
                len(silver_tables_missing),
                (
                    "All Silver inputs required by the Gold build are available."
                    if not silver_tables_missing
                    else f"Missing Silver tables: {', '.join(silver_tables_missing)}"
                ),
                passed=not silver_tables_missing,
            )
        )
        if any(table.startswith("ops.") for table in missing_tables):
            raise RuntimeError(
                "Quality gate cannot persist its result: "
                f"missing Ops tables {', '.join(table for table in missing_tables if table.startswith('ops.'))}. "
                "Apply database/schemas/ops.sql first."
            )
        ensure_pipeline_run(
            connection,
            run_id,
            trigger_source=trigger_source,
            dag_run_id=dag_run_id,
        )

        if not silver_tables_missing:
            for table_name, table in (
                ("orders_present_for_run", "silver.orders"),
                ("order_items_present_for_run", "silver.order_items"),
            ):
                row = connection.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE pipeline_run_id = %s",
                    (run_id,),
                ).fetchone()
                count = int(row[0])
                checks.append(
                    _result(
                        table_name,
                        "completeness",
                        1,
                        count,
                        f"{table} rows produced by pipeline run {run_id}: {count}",
                        passed=count > 0,
                    )
                )

            for name, query, description in REFERENCE_CHECKS:
                count = int(connection.execute(query).fetchone()[0])
                checks.append(
                    _result(
                        name,
                        "referential_integrity",
                        0,
                        count,
                        f"{description}: {count}",
                        passed=count == 0,
                    )
                )

            rejected_rows = int(
                connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM silver.rejected_records
                    WHERE pipeline_run_id = %s
                    """,
                    (run_id,),
                ).fetchone()[0]
            )
            reason_rows = connection.execute(
                """
                SELECT reason_code, COUNT(*)
                FROM silver.rejected_records
                WHERE pipeline_run_id = %s
                GROUP BY reason_code
                ORDER BY reason_code
                """,
                (run_id,),
            ).fetchall()
            reasons = ", ".join(f"{reason}: {count}" for reason, count in reason_rows)
            rejection_detail = (
                f"{rejected_rows} records quarantined"
                + (f" ({reasons})" if reasons else "")
                + "; expected invalid/duplicate records remain reported, not loaded."
            )
            checks.append(
                _result(
                    "rejected_records_reported",
                    "observability",
                    rejected_rows,
                    rejected_rows,
                    rejection_detail,
                    passed=True,
                )
            )

        _record_results(connection, run_id, checks)
        failed = [check for check in checks if not check["passed"]]
        if failed:
            names = ", ".join(check["check_name"] for check in failed)
            error_message = (
                f"Silver quality gate failed: {len(failed)} check(s) failed ({names}). "
                "Gold build is blocked."
            )
            connection.execute(
                """
                UPDATE ops.pipeline_runs
                SET status = 'FAILED', finished_at_utc = now(), error_message = %s
                WHERE pipeline_run_id = %s
                """,
                (error_message, run_id),
            )

    for check in checks:
        log.info(
            "%s: %s (expected=%s, actual=%s) — %s",
            check["check_name"],
            "PASS" if check["passed"] else "FAIL",
            check["expected_value"],
            check["actual_value"],
            check["detail"],
        )
    result = {
        "stage": "quality_gate",
        "gate_name": "silver_gate",
        "pipeline_run_id": run_id,
        "passed": not failed,
        "failed_checks": len(failed),
        "checks": checks,
    }
    if failed:
        names = ", ".join(check["check_name"] for check in failed)
        log.error("Silver quality gate failed for run %s: %s", run_id, names)
        raise RuntimeError(f"Silver quality gate failed for pipeline run {run_id}: {error_message}")
    log.info("Silver quality gate passed for run %s: %d checks", run_id, len(checks))
    return result


def run(
    pipeline_run_id: str | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run Silver checks and persist this stage's Ops status."""
    run_id = pipeline_run_id or _latest_silver_run_id()
    dag_run = (context or {}).get("dag_run")
    return execute_tracked_stage(
        connect=connect,
        pipeline_run_id=run_id,
        task_name="quality_gate",
        trigger_source="airflow" if dag_run is not None else "manual",
        dag_run_id=str(dag_run.run_id) if dag_run is not None else None,
        operation=lambda: _run(pipeline_run_id=run_id, context=context),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pipeline-run-id")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    run(pipeline_run_id=args.pipeline_run_id)


if __name__ == "__main__":
    main()
