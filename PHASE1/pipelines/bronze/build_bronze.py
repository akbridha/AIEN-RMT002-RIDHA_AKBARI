"""Load JSON and CSV source records into the append-only Bronze schema."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from uuid import uuid4

from pipelines.ingestion.db import connect
from pipelines.ingestion.run_tracking import execute_tracked_stage

log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_DIR = Path(os.getenv("RAW_DATA_DIR", str(PROJECT_ROOT / "data" / "raw")))
SUPPORTED_SUFFIXES = {".json", ".csv"}
MAX_BATCH_SIZE = 9000
SOURCE_ID_FIELDS = (
    "source_row_id",
    "event_id",
    "order_id",
    "order_item_id",
    "customer_id",
    "product_id",
    "store_id",
    "promotion_id",
    "category_id",
    "address_id",
    "channel_id",
    "campaign_id",
    "id",
)
INSERT_BATCH_SQL = """
INSERT INTO bronze.source_records (
    entity,
    source_file,
    source_row_number,
    source_record_id,
    payload,
    payload_checksum,
    pipeline_run_id
)
VALUES
"""
INSERT_BATCH_SUFFIX = """
ON CONFLICT (source_file, source_row_number) DO NOTHING
RETURNING record_id
"""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_stream:
        for chunk in iter(lambda: file_stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_relative_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _iter_json_records(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as file_stream:
        content = json.load(file_stream)

    if isinstance(content, dict):
        records = [content]
    elif isinstance(content, list):
        records = content
    else:
        raise ValueError(f"Expected a JSON object or array of objects in {path}")

    for row_number, record in enumerate(records, start=1):
        if not isinstance(record, dict) or any(not isinstance(key, str) for key in record):
            raise ValueError(f"Expected a JSON object at record {row_number} in {path}")
        yield record


def _iter_csv_records(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file_stream:
        reader = csv.DictReader(file_stream)
        if not reader.fieldnames or any(not name for name in reader.fieldnames):
            raise ValueError(f"CSV header is missing or contains an empty column name: {path}")
        if len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError(f"CSV contains duplicate column names: {path}")

        for row_number, record in enumerate(reader, start=1):
            if None in record:
                raise ValueError(f"CSV record {row_number} has more values than its header: {path}")
            yield record


def _iter_records(path: Path) -> Iterator[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        yield from _iter_json_records(path)
    elif suffix == ".csv":
        yield from _iter_csv_records(path)
    else:
        raise ValueError(f"Unsupported raw file format: {path}")


def _source_record_id(record: dict[str, Any]) -> str | None:
    for field in SOURCE_ID_FIELDS:
        value = record.get(field)
        if value is not None and str(value).strip():
            return str(value)
    return None


def _make_insert_statement(batch_size: int) -> str:
    row_placeholder = "(%s, %s, %s, %s, %s::jsonb, %s, %s)"
    values = ",\n".join(row_placeholder for _ in range(batch_size))
    return INSERT_BATCH_SQL + values + INSERT_BATCH_SUFFIX


def _insert_batch(connection: Any, rows: list[tuple[Any, ...]]) -> int:
    if not rows:
        return 0
    params = tuple(value for row in rows for value in row)
    inserted = connection.execute(_make_insert_statement(len(rows)), params).fetchall()
    return len(inserted)


def _existing_file_checksums(connection: Any, source_file: str) -> set[str]:
    rows = connection.execute(
        """
        SELECT file_checksum
        FROM bronze.ingestion_files
        WHERE source_file = %s
        """,
        (source_file,),
    ).fetchall()
    return {str(row[0]) for row in rows}


def _record_file_ingestion(
    connection: Any,
    *,
    source_file: str,
    file_format: str,
    file_size_bytes: int,
    file_checksum: str,
    row_count: int,
    pipeline_run_id: str,
) -> None:
    connection.execute(
        """
        INSERT INTO bronze.ingestion_files (
            source_file,
            file_format,
            file_size_bytes,
            file_checksum,
            row_count,
            pipeline_run_id
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (source_file, pipeline_run_id) DO UPDATE SET
            file_format = EXCLUDED.file_format,
            file_size_bytes = EXCLUDED.file_size_bytes,
            file_checksum = EXCLUDED.file_checksum,
            row_count = EXCLUDED.row_count
        """,
        (
            source_file,
            file_format,
            file_size_bytes,
            file_checksum,
            row_count,
            pipeline_run_id,
        ),
    )


def _run(
    pipeline_run_id: str | None = None,
    context: dict[str, Any] | None = None,
    input_dir: Path | str = DEFAULT_INPUT_DIR,
    batch_size: int = 500,
) -> dict[str, Any]:
    """Load all JSON/CSV files below ``input_dir`` into local Bronze.

    A stable file-relative path and 1-based record number form the idempotency
    key, matching ``UNIQUE (source_file, source_row_number)`` in bronze.sql.
    """
    del context
    if not 1 <= batch_size <= MAX_BATCH_SIZE:
        raise ValueError(f"batch_size must be between 1 and {MAX_BATCH_SIZE}.")

    raw_root = Path(input_dir).resolve()
    if not raw_root.is_dir():
        raise NotADirectoryError(f"Raw data directory does not exist: {raw_root}")

    source_files = sorted(
        (
            path
            for path in raw_root.rglob("*")
            if path.is_file()
            and path.name != "manifest.json"
            and path.suffix.lower() in SUPPORTED_SUFFIXES
        ),
        key=lambda path: path.as_posix().lower(),
    )
    if not source_files:
        raise FileNotFoundError(f"No JSON or CSV source files found under {raw_root}")

    run_id = pipeline_run_id or f"manual-{uuid4()}"
    totals = {
        "pipeline_run_id": run_id,
        "files_processed": 0,
        "rows_read": 0,
        "rows_inserted": 0,
        "rows_skipped_as_existing": 0,
    }

    with connect("local") as connection:
        for path in source_files:
            source_file = _source_relative_path(path, raw_root)
            file_checksum = _sha256_file(path)
            prior_checksums = _existing_file_checksums(connection, source_file)
            changed_checksums = prior_checksums - {file_checksum}
            if changed_checksums:
                raise ValueError(
                    f"{source_file} has changed since an earlier Bronze load. "
                    "The current Bronze key cannot distinguish file versions; "
                    "restore the original file or assign the new version a distinct source path."
                )

            pending: list[tuple[Any, ...]] = []
            file_rows_read = 0
            file_rows_inserted = 0
            for row_number, record in enumerate(_iter_records(path), start=1):
                payload = json.dumps(
                    record, ensure_ascii=False, separators=(",", ":"), sort_keys=True
                )
                payload_checksum = hashlib.sha256(payload.encode("utf-8")).hexdigest()
                pending.append(
                    (
                        path.stem,
                        source_file,
                        row_number,
                        _source_record_id(record),
                        payload,
                        payload_checksum,
                        run_id,
                    )
                )
                file_rows_read += 1

                if len(pending) >= batch_size:
                    file_rows_inserted += _insert_batch(connection, pending)
                    pending.clear()

            if pending:
                file_rows_inserted += _insert_batch(connection, pending)

            if _sha256_file(path) != file_checksum:
                raise ValueError(f"Raw file changed while it was being loaded: {source_file}")

            _record_file_ingestion(
                connection,
                source_file=source_file,
                file_format=path.suffix.lower().lstrip("."),
                file_size_bytes=path.stat().st_size,
                file_checksum=file_checksum,
                row_count=file_rows_read,
                pipeline_run_id=run_id,
            )
            totals["files_processed"] += 1
            totals["rows_read"] += file_rows_read
            totals["rows_inserted"] += file_rows_inserted
            totals["rows_skipped_as_existing"] += file_rows_read - file_rows_inserted
            log.info(
                "Loaded %s: read=%d inserted=%d already_present=%d",
                source_file,
                file_rows_read,
                file_rows_inserted,
                file_rows_read - file_rows_inserted,
            )

    return totals


def run(
    pipeline_run_id: str | None = None,
    context: dict[str, Any] | None = None,
    input_dir: Path | str = DEFAULT_INPUT_DIR,
    batch_size: int = 500,
) -> dict[str, Any]:
    """Load Bronze records and persist the stage result to Ops."""
    if not 1 <= batch_size <= MAX_BATCH_SIZE:
        raise ValueError(f"batch_size must be between 1 and {MAX_BATCH_SIZE}.")
    run_id = pipeline_run_id or f"manual-{uuid4()}"
    dag_run = (context or {}).get("dag_run")
    return execute_tracked_stage(
        connect=connect,
        pipeline_run_id=run_id,
        task_name="build_bronze",
        trigger_source="airflow" if dag_run is not None else "manual",
        dag_run_id=str(dag_run.run_id) if dag_run is not None else None,
        operation=lambda: _run(
            pipeline_run_id=run_id,
            context=context,
            input_dir=input_dir,
            batch_size=batch_size,
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--pipeline-run-id")
    parser.add_argument("--batch-size", type=int, default=500)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    result = run(
        pipeline_run_id=args.pipeline_run_id,
        input_dir=args.input,
        batch_size=args.batch_size,
    )
    log.info("Bronze load completed: %s", result)


if __name__ == "__main__":
    main()
