"""Run the local retail pipeline end-to-end outside Airflow."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any
from uuid import uuid4

from pipelines.bronze import build_bronze
from pipelines.gold import build_gold
from pipelines.ingestion.db import connect
from pipelines.ingestion.initialize_database import run as initialize_database
from pipelines.ingestion.run_tracking import (
    execute_tracked_stage,
    finish_pipeline_run,
    start_pipeline_run,
)
from pipelines.ingestion.validate_raw_files import run as validate_raw_files
from pipelines.quality.quality_gate import run as quality_gate
from pipelines.silver import build_silver

log = logging.getLogger(__name__)


def run(
    pipeline_run_id: str | None = None,
    input_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Initialize schemas, then run Bronze, Silver, gate, and Gold under one ID."""
    run_id = pipeline_run_id or f"manual-{uuid4()}"
    results: dict[str, Any] = {"pipeline_run_id": run_id, "stages": {}}

    # Ops must exist before the overall run can be tracked.
    initialize_database()
    with connect("local") as connection:
        start_pipeline_run(connection, run_id)

    try:
        validate_kwargs: dict[str, Any] = {"pipeline_run_id": run_id}
        bronze_kwargs: dict[str, Any] = {"pipeline_run_id": run_id}
        if input_dir is not None:
            validate_kwargs["input_dir"] = input_dir
            bronze_kwargs["input_dir"] = input_dir

        results["stages"]["validate_raw_files"] = execute_tracked_stage(
            connect=connect,
            pipeline_run_id=run_id,
            task_name="validate_raw_files",
            operation=lambda: validate_raw_files(**validate_kwargs),
        )
        results["stages"]["build_bronze"] = build_bronze.run(**bronze_kwargs)
        results["stages"]["build_silver"] = build_silver.run(
            pipeline_run_id=run_id
        )
        results["stages"]["quality_gate"] = quality_gate(
            pipeline_run_id=run_id
        )
        results["stages"]["build_gold"] = build_gold.run(
            pipeline_run_id=run_id
        )
        with connect("local") as connection:
            finish_pipeline_run(connection, run_id, status="SUCCESS")
    except Exception as exc:
        try:
            with connect("local") as connection:
                finish_pipeline_run(
                    connection,
                    run_id,
                    status="FAILED",
                    error_message=str(exc),
                )
        except Exception:
            log.exception("Could not persist failed pipeline status for %s", run_id)
        raise

    log.info("Pipeline completed successfully (pipeline_run_id=%s)", run_id)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pipeline-run-id")
    parser.add_argument("--input", type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    result = run(pipeline_run_id=args.pipeline_run_id, input_dir=args.input)
    log.info("Pipeline result: %s", result)


if __name__ == "__main__":
    main()
