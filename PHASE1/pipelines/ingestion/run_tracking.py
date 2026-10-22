"""Shared Ops tracking for manually and Airflow-orchestrated pipeline stages."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, TypeVar

log = logging.getLogger(__name__)
ResultT = TypeVar("ResultT")


def ensure_pipeline_run(
    connection: Any,
    pipeline_run_id: str,
    *,
    trigger_source: str,
    dag_run_id: str | None = None,
) -> None:
    """Create a run row if it does not exist without resetting an active run."""
    connection.execute(
        """
        INSERT INTO ops.pipeline_runs (
            pipeline_run_id, dag_run_id, status, trigger_source
        )
        VALUES (%s, %s, 'RUNNING', %s)
        ON CONFLICT (pipeline_run_id) DO NOTHING
        """,
        (pipeline_run_id, dag_run_id, trigger_source),
    )


def start_pipeline_run(
    connection: Any,
    pipeline_run_id: str,
    *,
    trigger_source: str = "manual",
) -> None:
    """Start or explicitly resume the overall pipeline lifecycle."""
    connection.execute(
        """
        INSERT INTO ops.pipeline_runs (
            pipeline_run_id, status, trigger_source
        )
        VALUES (%s, 'RUNNING', %s)
        ON CONFLICT (pipeline_run_id) DO UPDATE SET
            dag_run_id = NULL,
            status = 'RUNNING',
            trigger_source = EXCLUDED.trigger_source,
            started_at_utc = now(),
            finished_at_utc = NULL,
            error_message = NULL,
            notes = NULL
        """,
        (pipeline_run_id, trigger_source),
    )


def finish_pipeline_run(
    connection: Any,
    pipeline_run_id: str,
    *,
    status: str,
    error_message: str | None = None,
) -> None:
    if status not in {"SUCCESS", "FAILED"}:
        raise ValueError("Pipeline run status must be SUCCESS or FAILED.")
    connection.execute(
        """
        UPDATE ops.pipeline_runs
        SET status = %s,
            finished_at_utc = now(),
            error_message = %s
        WHERE pipeline_run_id = %s
        """,
        (status, error_message, pipeline_run_id),
    )


def _start_task(
    connection: Any,
    pipeline_run_id: str,
    task_name: str,
    *,
    trigger_source: str,
    dag_run_id: str | None,
) -> None:
    ensure_pipeline_run(
        connection,
        pipeline_run_id,
        trigger_source=trigger_source,
        dag_run_id=dag_run_id,
    )
    connection.execute(
        """
        INSERT INTO ops.pipeline_tasks (pipeline_run_id, task_name, status)
        VALUES (%s, %s, 'RUNNING')
        ON CONFLICT (pipeline_run_id, task_name) DO UPDATE SET
            status = 'RUNNING',
            started_at_utc = now(),
            finished_at_utc = NULL,
            rows_read = NULL,
            rows_written = NULL,
            rows_rejected = NULL,
            error_message = NULL
        """,
        (pipeline_run_id, task_name),
    )


def _finish_task(
    connection: Any,
    pipeline_run_id: str,
    task_name: str,
    *,
    status: str,
    result: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> None:
    values = result or {}
    connection.execute(
        """
        UPDATE ops.pipeline_tasks
        SET status = %s,
            finished_at_utc = now(),
            rows_read = %s,
            rows_written = %s,
            rows_rejected = %s,
            error_message = %s
        WHERE pipeline_run_id = %s AND task_name = %s
        """,
        (
            status,
            values.get("rows_read", values.get("source_records_read")),
            values.get("rows_written", values.get("rows_inserted", values.get("rows_loaded"))),
            values.get("rows_rejected"),
            error_message,
            pipeline_run_id,
            task_name,
        ),
    )


def execute_tracked_stage(
    *,
    connect: Callable[[str], Any],
    pipeline_run_id: str,
    task_name: str,
    operation: Callable[[], ResultT],
    trigger_source: str = "manual",
    dag_run_id: str | None = None,
) -> ResultT:
    """Persist stage state around an operation while preserving its exception."""
    with connect("local") as connection:
        _start_task(
            connection,
            pipeline_run_id,
            task_name,
            trigger_source=trigger_source,
            dag_run_id=dag_run_id,
        )

    try:
        result = operation()
    except Exception as exc:
        try:
            with connect("local") as connection:
                _finish_task(
                    connection,
                    pipeline_run_id,
                    task_name,
                    status="FAILED",
                    error_message=str(exc),
                )
                finish_pipeline_run(
                    connection,
                    pipeline_run_id,
                    status="FAILED",
                    error_message=str(exc),
                )
        except Exception:
            log.exception(
                "Could not persist failure for task %s (pipeline_run_id=%s)",
                task_name,
                pipeline_run_id,
            )
        raise

    result_values = result if isinstance(result, dict) else {}
    with connect("local") as connection:
        _finish_task(
            connection,
            pipeline_run_id,
            task_name,
            status="SUCCESS",
            result=result_values,
        )
    return result
