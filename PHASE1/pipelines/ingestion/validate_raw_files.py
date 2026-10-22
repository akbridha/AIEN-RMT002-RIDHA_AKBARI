"""Check that raw JSON/CSV files exist and can be parsed."""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
from typing import Any

from pipelines.bronze.build_bronze import SUPPORTED_SUFFIXES, _iter_records

log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_DIR = Path(os.getenv("RAW_DATA_DIR", str(PROJECT_ROOT / "data" / "raw")))
REQUIRED_SOURCE_FILES = {
    "operational/customers.json",
    "operational/customer_profiles.json",
    "operational/customer_addresses.json",
    "operational/products.json",
    "operational/product_categories.json",
    "operational/stores.json",
    "operational/sales_channels.json",
    "operational/promotions.json",
    "operational/orders.json",
    "operational/order_items.json",
    "operational/order_promotions.json",
    "events/payment_events.json",
    "events/refund_events.json",
    "events/return_events.json",
    "events/support_events.json",
    "events/web_events.json",
    "inventory/inventory_snapshots.csv",
    "reference/campaign_spend.csv",
    "reference/city_reference.json",
}


def run(
    pipeline_run_id: str | None = None,
    context: dict[str, Any] | None = None,
    input_dir: Path | str = DEFAULT_INPUT_DIR,
) -> dict[str, Any]:
    """Validate the available source files without reading or requiring a manifest."""
    del context
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

    discovered_paths = {path.relative_to(raw_root).as_posix() for path in source_files}
    missing_files = sorted(REQUIRED_SOURCE_FILES - discovered_paths)
    if missing_files:
        raise FileNotFoundError(
            "Required raw source file(s) are missing: " + ", ".join(missing_files)
        )

    rows_by_file: dict[str, int] = {}
    for path in source_files:
        relative_path = path.relative_to(raw_root).as_posix()
        rows_by_file[relative_path] = sum(1 for _ in _iter_records(path))

    result = {
        "pipeline_run_id": pipeline_run_id,
        "files_validated": len(rows_by_file),
        "records_found": sum(rows_by_file.values()),
        "rows_by_file": rows_by_file,
    }
    log.info(
        "Validated %d raw files and %d records under %s",
        result["files_validated"],
        result["records_found"],
        raw_root,
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_DIR)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    result = run(input_dir=args.input)
    log.info(
        "Raw validation succeeded: %d files, %d records",
        result["files_validated"],
        result["records_found"],
    )


if __name__ == "__main__":
    main()
