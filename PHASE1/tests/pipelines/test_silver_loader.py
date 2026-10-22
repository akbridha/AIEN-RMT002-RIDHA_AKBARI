from __future__ import annotations

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
