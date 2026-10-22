from __future__ import annotations

import json

import pytest

from pipelines.bronze import build_bronze
from pipelines.ingestion import validate_raw_files


class FakeCursor:
    def __init__(self, rows=()):
        self._rows = list(rows)

    def fetchall(self):
        return self._rows


class FakeConnection:
    def __init__(self):
        self.records = {}
        self.files = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return None

    def execute(self, query, params=()):
        if "SELECT file_checksum" in query:
            source_file = params[0]
            checksums = {
                value["file_checksum"]
                for (stored_file, _), value in self.files.items()
                if stored_file == source_file
            }
            return FakeCursor((checksum,) for checksum in checksums)

        if "INSERT INTO bronze.source_records" in query:
            inserted = []
            for offset in range(0, len(params), 7):
                row = params[offset : offset + 7]
                key = (row[1], row[2])
                if key not in self.records:
                    self.records[key] = row
                    inserted.append((len(self.records),))
            return FakeCursor(inserted)

        if "INSERT INTO bronze.ingestion_files" in query:
            source_file, file_format, size, checksum, count, run_id = params
            self.files[(source_file, run_id)] = {
                "file_format": file_format,
                "file_size_bytes": size,
                "file_checksum": checksum,
                "row_count": count,
            }
            return FakeCursor()

        raise AssertionError(f"Unexpected SQL: {query}")


def test_loader_loads_json_and_csv_in_batches_and_is_idempotent(tmp_path, monkeypatch):
    raw_dir = tmp_path / "raw"
    (raw_dir / "operational").mkdir(parents=True)
    (raw_dir / "inventory").mkdir()
    orders = [
        {"order_id": "O-1", "source_row_id": "SRC-1", "amount": 10},
        {"order_id": "O-2", "source_row_id": "SRC-2", "amount": 20},
    ]
    orders_path = raw_dir / "operational" / "orders.json"
    orders_path.write_text(json.dumps(orders), encoding="utf-8")
    inventory_path = raw_dir / "inventory" / "snapshots.csv"
    inventory_path.write_text("product_id,quantity\nP-1,7\n", encoding="utf-8")
    (raw_dir / "manifest.json").write_text("not valid JSON and intentionally ignored")

    database = FakeConnection()
    monkeypatch.setattr(build_bronze, "connect", lambda target: database)

    first_run = build_bronze.run(
        pipeline_run_id="run-1", input_dir=raw_dir, batch_size=1
    )
    second_run = build_bronze.run(
        pipeline_run_id="run-2", input_dir=raw_dir, batch_size=2
    )

    assert first_run["rows_read"] == 3
    assert first_run["rows_inserted"] == 3
    assert second_run["rows_read"] == 3
    assert second_run["rows_inserted"] == 0
    assert second_run["rows_skipped_as_existing"] == 3
    assert len(database.records) == 3
    assert len(database.files) == 4
    assert database.records[("operational/orders.json", 1)][3] == "SRC-1"
    assert json.loads(database.records[("operational/orders.json", 1)][4]) == orders[0]


def test_loader_rejects_file_changed_since_previous_load(tmp_path, monkeypatch):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    source = raw_dir / "customers.json"
    source.write_text('[{"customer_id":"C-1"}]', encoding="utf-8")

    database = FakeConnection()
    monkeypatch.setattr(build_bronze, "connect", lambda target: database)

    build_bronze.run(input_dir=raw_dir, pipeline_run_id="first-run")
    source.write_text('[{"customer_id":"C-2"}]', encoding="utf-8")
    with pytest.raises(ValueError, match="changed since an earlier Bronze load"):
        build_bronze.run(input_dir=raw_dir, pipeline_run_id="second-run")


def test_loader_does_not_require_manifest(tmp_path, monkeypatch):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "items.json").write_text("[]", encoding="utf-8")

    database = FakeConnection()
    monkeypatch.setattr(build_bronze, "connect", lambda target: database)
    result = build_bronze.run(input_dir=raw_dir)

    assert result["files_processed"] == 1
    assert result["rows_read"] == 0
    assert ("items.json", result["pipeline_run_id"]) in database.files


def test_raw_validation_checks_required_files_and_ignores_manifest(tmp_path):
    for relative_path in validate_raw_files.REQUIRED_SOURCE_FILES:
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix == ".json":
            path.write_text("[]", encoding="utf-8")
        else:
            path.write_text("column\n", encoding="utf-8")
    (tmp_path / "manifest.json").write_text("invalid JSON, ignored", encoding="utf-8")

    result = validate_raw_files.run(input_dir=tmp_path)

    assert result["files_validated"] == len(validate_raw_files.REQUIRED_SOURCE_FILES)
    assert result["records_found"] == 0


def test_loader_rejects_non_positive_batch_size(tmp_path):
    with pytest.raises(ValueError, match="batch_size"):
        build_bronze.run(input_dir=tmp_path, batch_size=0)


def test_loader_rejects_batch_size_over_postgres_parameter_limit(tmp_path):
    with pytest.raises(ValueError, match="batch_size"):
        build_bronze.run(input_dir=tmp_path, batch_size=9001)
