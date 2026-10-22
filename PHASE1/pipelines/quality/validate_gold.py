"""Validate the Gold output for a pipeline run and finalize its Ops metadata."""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from pipelines.ingestion.db import connect
from pipelines.ingestion.run_tracking import execute_tracked_stage, finish_pipeline_run

log = logging.getLogger(__name__)

GOLD_TABLES = (
    "gold.order_360",
    "gold.customer_daily",
    "gold.product_daily",
    "gold.channel_campaign_daily",
    "gold.executive_kpis_daily",
)


def _validate(
    pipeline_run_id: str,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    with connect("local") as connection:
        for table in GOLD_TABLES:
            exists = connection.execute(
                "SELECT to_regclass(%s)",
                (table,),
            ).fetchone()[0] is not None
            row_count = (
                int(
                    connection.execute(
                        f"SELECT COUNT(*) FROM {table} WHERE pipeline_run_id = %s",
                        (pipeline_run_id,),
                    ).fetchone()[0]
                )
                if exists
                else 0
            )
            checks.append(
                {
                    "check_name": f"gold_validation:{table.split('.', 1)[1]}",
                    "check_type": "completeness",
                    "target_table": table,
                    "expected_value": 1,
                    "actual_value": row_count,
                    "passed": exists and row_count > 0,
                    "detail": (
                        f"{row_count} row(s) for pipeline run {pipeline_run_id}"
                        if exists
                        else f"Required table {table} does not exist"
                    ),
                }
            )

        passed = all(check["passed"] for check in checks)
        failed_checks = sum(not check["passed"] for check in checks)
        connection.execute(
            """
            DELETE FROM ops.quality_checks
            WHERE pipeline_run_id = %s AND check_name LIKE %s
            """,
            (pipeline_run_id, "gold_validation:%"),
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
            VALUES (%s, 'gold_gate', %s, %s)
            ON CONFLICT (pipeline_run_id, gate_name) DO UPDATE SET
                passed = EXCLUDED.passed,
                failed_checks = EXCLUDED.failed_checks,
                evaluated_at_utc = now()
            """,
            (pipeline_run_id, passed, failed_checks),
        )

    if failed_checks:
        failed_tables = ", ".join(
            check["target_table"] for check in checks if not check["passed"]
        )
        raise RuntimeError(
            f"Gold validation failed for pipeline run {pipeline_run_id}; "
            f"missing output for: {failed_tables}"
        )

    result = {
        "stage": "validate_gold_and_record_metadata",
        "pipeline_run_id": pipeline_run_id,
        "passed": True,
        "row_counts": {
            check["target_table"]: check["actual_value"] for check in checks
        },
    }
    log.info("Gold validation passed for pipeline run %s", pipeline_run_id)
    return result


def run(
    pipeline_run_id: str | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate all five Gold tables, persist the Gold gate, and finish the run."""
    run_id = pipeline_run_id or f"manual-{uuid4()}"
    dag_run = (context or {}).get("dag_run")
    result = execute_tracked_stage(
        connect=connect,
        pipeline_run_id=run_id,
        task_name="validate_gold_and_record_metadata",
        trigger_source="airflow" if dag_run is not None else "manual",
        dag_run_id=str(dag_run.run_id) if dag_run is not None else None,
        operation=lambda: _validate(run_id),
    )
    with connect("local") as connection:
        finish_pipeline_run(connection, run_id, status="SUCCESS")
    return result
