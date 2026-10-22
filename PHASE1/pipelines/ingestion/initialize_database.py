"""Create the milestone schemas in the local PostgreSQL database."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any

from pipelines.ingestion.db import apply_sql_file, connect

log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCHEMA_DIR = PROJECT_ROOT / "database" / "schemas"
REQUIRED_SCHEMA_FILES = ("bronze.sql", "silver.sql", "gold.sql", "ops.sql")


def run(
    pipeline_run_id: str | None = None,
    context: dict[str, Any] | None = None,
    schema_dir: Path | str = DEFAULT_SCHEMA_DIR,
) -> list[str]:
    """Apply all schema files to the local database in one transaction.

    ``pipeline_run_id`` and ``context`` are accepted so Airflow can call this
    function through the same interface as the other pipeline stages.
    """
    del pipeline_run_id, context
    schema_path = Path(schema_dir).resolve()
    missing = [name for name in REQUIRED_SCHEMA_FILES if not (schema_path / name).is_file()]
    if missing:
        missing_list = ", ".join(missing)
        raise FileNotFoundError(f"Schema file(s) missing in {schema_path}: {missing_list}")

    applied: list[str] = []
    with connect("local") as connection:
        for filename in REQUIRED_SCHEMA_FILES:
            path = schema_path / filename
            log.info("Applying schema file %s", path)
            apply_sql_file(connection, path)
            applied.append(filename)

    log.info("Initialized local PostgreSQL schemas: %s", ", ".join(applied))
    return applied


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create Bronze, Silver, Gold, and Ops schemas in local PostgreSQL."
    )
    parser.add_argument(
        "--schema-dir",
        type=Path,
        default=DEFAULT_SCHEMA_DIR,
        help=f"Directory containing schema SQL files (default: {DEFAULT_SCHEMA_DIR})",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    run(schema_dir=args.schema_dir)


if __name__ == "__main__":
    main()
