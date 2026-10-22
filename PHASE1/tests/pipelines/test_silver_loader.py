from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from pipelines.silver import build_silver


def test_standardize_time_utc_converts_offsets_to_utc():
    result = build_silver.standardize_time_utc("2026-10-22T23:30:00+07:00")

    assert result == datetime(2026, 10, 22, 16, 30, tzinfo=UTC)


def test_standardize_time_utc_rejects_timezone_free_values():
    with pytest.raises(ValueError, match="must include a timezone"):
        build_silver.standardize_time_utc("2026-10-22T23:30:00")


def test_standardize_uppercase_trims_and_preserves_null():
    assert build_silver.standardize_uppercase("  mobile_app ") == "MOBILE_APP"
    assert build_silver.standardize_uppercase(None) is None
    assert build_silver.standardize_uppercase("  ") is None


def test_normalize_order_maps_status_and_converts_typed_fields():
    spec = build_silver.ENTITY_SPECS["orders"]
    record = {
        "payload": {
            "order_id": " ORD-1 ",
            "customer_id": " CUST-1 ",
            "ordered_at_utc": "2026-10-22T10:00:00+07:00",
            "sales_channel": " mobile_app ",
            "store_id": None,
            "shipping_revenue": "12.50",
            "status": " fulfilled ",
            "updated_at_utc": "2026-10-22T11:00:00Z",
        },
        "ingested_at_utc": datetime(2026, 10, 22, tzinfo=UTC),
    }

    values = build_silver._normalize_record(record, spec)

    assert values["order_id"] == "ORD-1"
    assert values["order_status"] == "FULFILLED"
    assert values["sales_channel"] == "MOBILE_APP"
    assert values["shipping_revenue"] == Decimal("12.50")
    assert values["ordered_at_utc"] == datetime(2026, 10, 22, 3, tzinfo=UTC)


def test_normalize_event_flattens_payload_and_uses_bronze_ingestion_time():
    spec = build_silver.ENTITY_SPECS["payment_events"]
    bronze_ingested_at = datetime(2026, 10, 22, tzinfo=UTC)
    record = {
        "payload": {
            "event_id": "EVT-1",
            "event_type": "payment_captured",
            "occurred_at_utc": "2026-10-22T08:00:00Z",
            "payload": {"order_id": "ORD-1", "payment_id": "PAY-1", "amount": "9.25"},
        },
        "ingested_at_utc": bronze_ingested_at,
    }

    values = build_silver._normalize_record(record, spec)

    assert values["event_type"] == "PAYMENT_CAPTURED"
    assert values["order_id"] == "ORD-1"
    assert values["amount"] == Decimal("9.25")
    assert values["ingested_at_utc"] == bronze_ingested_at


def test_insert_rows_uses_configured_batch_size():
    class FakeConnection:
        def __init__(self):
            self.calls = []

        def execute(self, query, params):
            self.calls.append((query, params))

    connection = FakeConnection()
    rows = [
        {"id": f"ID-{number}", "bronze_record_id": number, "pipeline_run_id": "run-1"}
        for number in range(3)
    ]

    count = build_silver._insert_rows(
        connection,
        table="example",
        columns=["id"],
        keys=("id",),
        rows=rows,
        batch_size=2,
    )

    assert count == 3
    assert [len(params) // 3 for _, params in connection.calls] == [2, 1]


def test_insert_rejections_types_bronze_id_as_bigint_and_includes_reason_detail():
    class FakeCursor:
        def fetchall(self):
            return [(1,)]

    class FakeConnection:
        def __init__(self):
            self.query = ""
            self.params = ()

        def execute(self, query, params):
            self.query = query
            self.params = params
            return FakeCursor()

    connection = FakeConnection()
    rejections = [
        {
            "entity": "order_items",
            "source_file": "operational/order_items.json",
            "source_row_number": 12,
            "reason_code": "MISSING_FK",
            "reason_detail": "product_id='P-1' does not exist",
            "payload": {"order_item_id": "ITEM-1"},
            "rejected_stage": "silver.order_items",
            "bronze_record_id": 9876543210,
        }
    ]

    count = build_silver._insert_rejections(connection, rejections, "run-1")

    assert count == 1
    assert "%s::BIGINT" in connection.query
    assert "existing.bronze_record_id = v.bronze_record_id" in connection.query
    assert "reason_detail" in connection.query
    assert connection.params[7] == 9876543210


def test_run_logs_entity_progress_and_counts(monkeypatch, caplog):
    class FakeCursor:
        def __init__(self, rows=()):
            self.rows = rows

        def fetchall(self):
            return self.rows

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return None

        def execute(self, query, params=()):
            if "FROM bronze.source_records" in query:
                return FakeCursor(
                    [
                        (
                            1,
                            "city_reference",
                            "reference/city_reference.json",
                            1,
                            {"city_id": "JKT", "city_name": "Jakarta", "country": "ID"},
                            datetime(2026, 10, 22, tzinfo=UTC),
                        )
                    ]
                )
            if query.startswith("SELECT"):
                return FakeCursor()
            return FakeCursor()

    monkeypatch.setattr(build_silver, "connect", lambda _target: FakeConnection())

    with caplog.at_level(logging.INFO):
        results = build_silver.run(pipeline_run_id="run-1")

    assert results["tables"]["cities"] == {
        "read": 1,
        "loaded": 1,
        "deduplicated": 0,
        "rejected": 0,
    }
    assert "[1/19] Processing city_reference -> silver.cities (1 Bronze records)" in caplog.text
    assert "[1/19] Finished silver.cities: read=1 loaded=1 deduplicated=0 rejected=0" in caplog.text


@pytest.mark.parametrize("batch_size", [0, -1, 5001, 1.5, True])
def test_run_rejects_invalid_batch_size_before_connecting(batch_size, monkeypatch):
    def unexpected_connect(_target):
        raise AssertionError("Database should not be connected for an invalid batch size")

    monkeypatch.setattr(build_silver, "connect", unexpected_connect)

    with pytest.raises(ValueError, match="batch_size"):
        build_silver.run(batch_size=batch_size)
