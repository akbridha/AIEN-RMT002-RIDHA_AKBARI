"""Transform append-only Bronze records into validated, typed Silver tables."""

from __future__ import annotations

import argparse
import json
import logging
from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import uuid4

from pipelines.ingestion.db import connect

log = logging.getLogger(__name__)

MAX_BATCH_SIZE = 500


def standardize_time_utc(value: Any) -> datetime | None:
    """Parse a timestamp and return an aware UTC datetime; reject ambiguous local times."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"Timestamp must include a timezone: {value!r}")
    return parsed.astimezone(UTC)


def standardize_uppercase(value: Any) -> str | None:
    """Trim a text value and normalize it to uppercase; preserve nulls."""
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized.upper() if normalized else None


def _to_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Expected a numeric value, got {value!r}") from exc


def _to_integer(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Expected an integer, got {value!r}") from exc
    if number != number.to_integral_value():
        raise ValueError(f"Expected an integer, got {value!r}")
    return int(number)


def _to_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value).strip())


def _text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _not_null(value: Any) -> bool:
    return value is not None and value != ""


def _merge_payload(payload: dict[str, Any]) -> dict[str, Any]:
    nested = payload.get("payload")
    if isinstance(nested, dict):
        return {**payload, **nested}
    return payload


def _copy_fields(
    payload: dict[str, Any],
    field_map: dict[str, str],
    record: dict[str, Any],
) -> dict[str, Any]:
    result = {
        target: payload.get(source)
        for target, source in field_map.items()
    }
    if "ingested_at_utc" in result and result["ingested_at_utc"] is None:
        result["ingested_at_utc"] = record["ingested_at_utc"]
    return result


class EntitySpec:
    def __init__(
        self,
        table: str,
        field_map: dict[str, str],
        keys: tuple[str, ...],
        *,
        required: tuple[str, ...] = (),
        timestamps: tuple[str, ...] = (),
        dates: tuple[str, ...] = (),
        decimals: tuple[str, ...] = (),
        integers: tuple[str, ...] = (),
        uppercase: tuple[str, ...] = (),
        references: dict[str, str] | None = None,
    ) -> None:
        self.table = table
        self.field_map = field_map
        self.keys = keys
        self.required = required
        self.timestamps = timestamps
        self.dates = dates
        self.decimals = decimals
        self.integers = integers
        self.uppercase = uppercase
        self.references = references or {}


def _spec(
    table: str,
    fields: tuple[str, ...],
    *,
    keys: tuple[str, ...],
    required: tuple[str, ...] = (),
    timestamps: tuple[str, ...] = (),
    dates: tuple[str, ...] = (),
    decimals: tuple[str, ...] = (),
    integers: tuple[str, ...] = (),
    uppercase: tuple[str, ...] = (),
    references: dict[str, str] | None = None,
    source_fields: dict[str, str] | None = None,
) -> EntitySpec:
    return EntitySpec(
        table,
        source_fields or {field: field for field in fields},
        keys,
        required=required,
        timestamps=timestamps,
        dates=dates,
        decimals=decimals,
        integers=integers,
        uppercase=uppercase,
        references=references,
    )


ENTITY_SPECS = {
    "city_reference": _spec(
        "cities",
        ("city_id", "city_name", "country"),
        keys=("city_id",),
        required=("city_id", "city_name",),
    ),
    "customers": _spec(
        "customers",
        ("customer_id", "city_id", "customer_segment", "created_at_utc"),
        keys=("customer_id",),
        required=("customer_id",),
        timestamps=("created_at_utc",),
        references={"city_id": "cities.city_id"},
    ),
    "customer_profiles": _spec(
        "customer_profiles",
        ("customer_id", "valid_from_utc", "valid_to_utc", "city_id", "customer_segment"),
        keys=("customer_id", "valid_from_utc"),
        required=("customer_id", "valid_from_utc"),
        timestamps=("valid_from_utc", "valid_to_utc"),
        references={"customer_id": "customers.customer_id", "city_id": "cities.city_id"},
    ),
    "customer_addresses": _spec(
        "customer_addresses",
        ("address_id", "customer_id", "city_id", "valid_from_utc", "valid_to_utc"),
        keys=("address_id",),
        required=("address_id", "customer_id"),
        timestamps=("valid_from_utc", "valid_to_utc"),
        references={"customer_id": "customers.customer_id", "city_id": "cities.city_id"},
    ),
    "products": _spec(
        "products",
        ("product_id", "product_name", "sku", "unit_price"),
        keys=("product_id",),
        required=("product_id",),
        decimals=("unit_price",),
    ),
    "product_categories": _spec(
        "product_categories",
        ("product_id", "valid_from_utc", "valid_to_utc", "category_id", "category_name"),
        keys=("product_id", "valid_from_utc"),
        required=("product_id", "valid_from_utc"),
        timestamps=("valid_from_utc", "valid_to_utc"),
        references={"product_id": "products.product_id"},
    ),
    "stores": _spec(
        "stores",
        ("store_id", "store_name", "city_id", "location_type"),
        keys=("store_id",),
        required=("store_id",),
        references={"city_id": "cities.city_id"},
    ),
    "sales_channels": _spec(
        "sales_channels",
        ("channel_id", "channel_name"),
        keys=("channel_id",),
        required=("channel_id", "channel_name"),
        uppercase=("channel_id", "channel_name"),
    ),
    "promotions": _spec(
        "promotions",
        (
            "promotion_id",
            "promotion_code",
            "promotion_type",
            "discount_rate",
            "start_date",
            "end_date",
        ),
        keys=("promotion_id",),
        required=("promotion_id",),
        dates=("start_date", "end_date"),
        decimals=("discount_rate",),
        uppercase=("promotion_type",),
    ),
    "orders": _spec(
        "orders",
        (
            "order_id",
            "customer_id",
            "ordered_at_utc",
            "sales_channel",
            "store_id",
            "shipping_revenue",
            "order_status",
            "updated_at_utc",
        ),
        keys=("order_id",),
        required=(
            "order_id",
            "customer_id",
            "ordered_at_utc",
            "sales_channel",
            "order_status",
        ),
        timestamps=("ordered_at_utc", "updated_at_utc"),
        decimals=("shipping_revenue",),
        uppercase=("sales_channel", "order_status"),
        references={
            "customer_id": "customers.customer_id",
            "sales_channel": "sales_channels.channel_name",
            "store_id": "stores.store_id",
        },
        source_fields={"order_status": "status", **{
            field: field
            for field in (
                "order_id",
                "customer_id",
                "ordered_at_utc",
                "sales_channel",
                "store_id",
                "shipping_revenue",
                "updated_at_utc",
            )
        }},
    ),
    "order_items": _spec(
        "order_items",
        ("order_item_id", "order_id", "product_id", "quantity", "unit_price", "item_discount_amount"),
        keys=("order_item_id",),
        required=("order_item_id", "order_id", "product_id", "quantity", "unit_price"),
        decimals=("unit_price", "item_discount_amount"),
        integers=("quantity",),
        references={"order_id": "orders.order_id", "product_id": "products.product_id"},
    ),
    "order_promotions": _spec(
        "order_promotions",
        ("order_id", "promotion_id", "discount_amount"),
        keys=("order_id", "promotion_id"),
        required=("order_id", "promotion_id"),
        decimals=("discount_amount",),
        references={"order_id": "orders.order_id", "promotion_id": "promotions.promotion_id"},
    ),
    "payment_events": _spec(
        "payment_events",
        (
            "event_id",
            "event_type",
            "occurred_at_utc",
            "ingested_at_utc",
            "order_id",
            "payment_id",
            "amount",
        ),
        keys=("event_id",),
        required=("event_id", "event_type", "occurred_at_utc", "ingested_at_utc"),
        timestamps=("occurred_at_utc", "ingested_at_utc"),
        decimals=("amount",),
        uppercase=("event_type",),
        references={"order_id": "orders.order_id"},
    ),
    "refund_events": _spec(
        "refund_events",
        (
            "event_id",
            "event_type",
            "occurred_at_utc",
            "ingested_at_utc",
            "order_id",
            "refund_id",
            "amount",
        ),
        keys=("event_id",),
        required=("event_id", "event_type", "occurred_at_utc", "ingested_at_utc"),
        timestamps=("occurred_at_utc", "ingested_at_utc"),
        decimals=("amount",),
        uppercase=("event_type",),
        references={"order_id": "orders.order_id"},
    ),
    "return_events": _spec(
        "return_events",
        ("event_id", "event_type", "occurred_at_utc", "ingested_at_utc", "order_id", "return_id"),
        keys=("event_id",),
        required=("event_id", "event_type", "occurred_at_utc", "ingested_at_utc"),
        timestamps=("occurred_at_utc", "ingested_at_utc"),
        uppercase=("event_type",),
        references={"order_id": "orders.order_id"},
    ),
    "support_events": _spec(
        "support_events",
        (
            "event_id",
            "event_type",
            "occurred_at_utc",
            "ingested_at_utc",
            "customer_id",
            "order_id",
            "ticket_id",
            "reason",
        ),
        keys=("event_id",),
        required=("event_id", "event_type", "occurred_at_utc", "ingested_at_utc"),
        timestamps=("occurred_at_utc", "ingested_at_utc"),
        uppercase=("event_type",),
        references={
            "customer_id": "customers.customer_id",
            "order_id": "orders.order_id",
        },
    ),
    "web_events": _spec(
        "web_events",
        (
            "event_id",
            "event_type",
            "occurred_at_utc",
            "ingested_at_utc",
            "session_id",
            "customer_id",
            "order_id",
            "channel",
            "campaign_id",
        ),
        keys=("event_id",),
        required=("event_id", "event_type", "occurred_at_utc", "ingested_at_utc"),
        timestamps=("occurred_at_utc", "ingested_at_utc"),
        uppercase=("event_type", "channel"),
        references={
            "customer_id": "customers.customer_id",
            "order_id": "orders.order_id",
        },
    ),
    "inventory_snapshots": _spec(
        "inventory_snapshots",
        (
            "snapshot_date",
            "product_id",
            "location_id",
            "available_quantity",
            "reserved_quantity",
            "unit_cost",
        ),
        keys=("snapshot_date", "product_id", "location_id"),
        required=("snapshot_date", "product_id", "location_id", "available_quantity", "reserved_quantity"),
        dates=("snapshot_date",),
        integers=("available_quantity", "reserved_quantity"),
        decimals=("unit_cost",),
        references={"product_id": "products.product_id"},
    ),
    "campaign_spend": _spec(
        "campaign_spend",
        ("spend_date", "campaign_id", "channel", "spend_amount"),
        keys=("spend_date", "campaign_id", "channel"),
        required=("spend_date", "campaign_id", "channel", "spend_amount"),
        dates=("spend_date",),
        decimals=("spend_amount",),
        uppercase=("channel",),
    ),
}

REFERENCE_QUERIES = {
    "cities.city_id": ("silver.cities", "city_id"),
    "customers.customer_id": ("silver.customers", "customer_id"),
    "products.product_id": ("silver.products", "product_id"),
    "stores.store_id": ("silver.stores", "store_id"),
    "sales_channels.channel_name": ("silver.sales_channels", "channel_name"),
    "promotions.promotion_id": ("silver.promotions", "promotion_id"),
    "orders.order_id": ("silver.orders", "order_id"),
}


def _normalize_record(record: dict[str, Any], spec: EntitySpec) -> dict[str, Any]:
    payload = _merge_payload(record["payload"])
    values = _copy_fields(payload, spec.field_map, record)
    for field in spec.timestamps:
        values[field] = standardize_time_utc(values[field])
    for field in spec.dates:
        values[field] = _to_date(values[field])
    for field in spec.decimals:
        values[field] = _to_decimal(values[field])
    for field in spec.integers:
        values[field] = _to_integer(values[field])
    for field in spec.uppercase:
        values[field] = standardize_uppercase(values[field])
    for field in values:
        if field not in spec.timestamps and field not in spec.dates and field not in spec.decimals and field not in spec.integers:
            values[field] = _text(values[field])
    missing = [field for field in spec.required if not _not_null(values[field])]
    if missing:
        raise ValueError(f"Missing required field(s): {', '.join(missing)}")
    if spec.table == "order_items" and values["quantity"] <= 0:
        raise ValueError("quantity must be positive")
    if spec.table == "inventory_snapshots" and (
        values["available_quantity"] < 0 or values["reserved_quantity"] < 0
    ):
        raise ValueError("inventory quantities cannot be negative")
    return values


def _load_reference_values(connection: Any) -> dict[str, set[Any]]:
    references: dict[str, set[Any]] = {}
    for reference, (table, column) in REFERENCE_QUERIES.items():
        rows = connection.execute(f"SELECT {column} FROM {table}").fetchall()
        references[reference] = {row[0] for row in rows if row[0] is not None}
    return references


def _insert_rows(
    connection: Any,
    *,
    table: str,
    columns: list[str],
    keys: tuple[str, ...],
    rows: list[dict[str, Any]],
) -> int:
    if not rows:
        return 0
    inserted_count = 0
    for start in range(0, len(rows), MAX_BATCH_SIZE):
        batch = rows[start : start + MAX_BATCH_SIZE]
        insert_columns = [*columns, "bronze_record_id", "pipeline_run_id"]
        row_placeholder = "(" + ", ".join(["%s"] * len(insert_columns)) + ")"
        values_clause = ", ".join([row_placeholder] * len(batch))
        conflict_columns = ", ".join(keys)
        updates = [column for column in insert_columns if column not in keys]
        update_clause = ", ".join(f"{column} = EXCLUDED.{column}" for column in updates)
        sql = (
            f"INSERT INTO silver.{table} ({', '.join(insert_columns)}) "
            f"VALUES {values_clause} ON CONFLICT ({conflict_columns}) "
            f"DO UPDATE SET {update_clause}"
        )
        params = tuple(
            value
            for row in batch
            for value in (
                *(row[column] for column in columns),
                row["bronze_record_id"],
                row["pipeline_run_id"],
            )
        )
        connection.execute(sql, params)
        inserted_count += len(batch)
    return inserted_count


def _insert_rejections(connection: Any, rejections: list[dict[str, Any]], run_id: str) -> int:
    if not rejections:
        return 0
    inserted = 0
    for start in range(0, len(rejections), MAX_BATCH_SIZE):
        batch = rejections[start : start + MAX_BATCH_SIZE]
        placeholder = "(%s, %s, %s, %s, %s::jsonb, %s, %s, %s)"
        values_clause = ", ".join([placeholder] * len(batch))
        params = tuple(
            value
            for item in batch
            for value in (
                item["entity"],
                item["source_file"],
                item["source_row_number"],
                item["reason_code"],
                json.dumps(item["payload"], ensure_ascii=False, separators=(",", ":")),
                item["rejected_stage"],
                item["bronze_record_id"],
                run_id,
            )
        )
        query = f"""
            INSERT INTO silver.rejected_records (
                entity, source_file, source_row_number, reason_code, payload,
                rejected_stage, bronze_record_id, pipeline_run_id
            )
            SELECT DISTINCT ON (v.bronze_record_id, v.rejected_stage, v.reason_code)
                v.entity, v.source_file, v.source_row_number, v.reason_code,
                v.payload, v.rejected_stage, v.bronze_record_id, v.pipeline_run_id
            FROM (VALUES {values_clause}) AS v(
                entity, source_file, source_row_number, reason_code, payload,
                rejected_stage, bronze_record_id, pipeline_run_id
            )
            WHERE NOT EXISTS (
                SELECT 1 FROM silver.rejected_records existing
                WHERE existing.bronze_record_id = v.bronze_record_id
                  AND existing.rejected_stage = v.rejected_stage
                  AND existing.reason_code = v.reason_code
            )
            ORDER BY v.bronze_record_id, v.rejected_stage, v.reason_code
            RETURNING rejected_id
        """
        inserted += len(connection.execute(query, params).fetchall())
    return inserted


def _reject(
    record: dict[str, Any],
    *,
    entity: str,
    stage: str,
    reason_code: str,
    detail: str,
) -> dict[str, Any]:
    return {
        "entity": entity,
        "source_file": record["source_file"],
        "source_row_number": record["source_row_number"],
        "reason_code": reason_code,
        "reason_detail": detail,
        "payload": record["payload"],
        "rejected_stage": f"silver.{stage}",
        "bronze_record_id": record["record_id"],
    }


def _winner_order(spec: EntitySpec, record: dict[str, Any], values: dict[str, Any]) -> tuple[Any, ...]:
    if spec.table == "orders":
        return (values.get("updated_at_utc") or datetime.min.replace(tzinfo=UTC), record["record_id"])
    return (-record["record_id"],)


def run(
    pipeline_run_id: str | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build all Silver tables from Bronze, preserving lineage and rejected rows."""
    del context
    run_id = pipeline_run_id or f"manual-{uuid4()}"
    results: dict[str, Any] = {
        "pipeline_run_id": run_id,
        "source_records_read": 0,
        "rows_loaded": 0,
        "rows_rejected": 0,
        "rows_deduplicated": 0,
        "tables": {},
    }
    with connect("local") as connection:
        entities = tuple(ENTITY_SPECS)
        placeholders = ", ".join(["%s"] * len(entities))
        source_rows = connection.execute(
            f"""
                SELECT record_id, entity, source_file, source_row_number,
                       payload, ingested_at_utc
                FROM bronze.source_records
                WHERE entity IN ({placeholders})
                ORDER BY record_id
            """,
            entities,
        ).fetchall()
        by_entity: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in source_rows:
            payload = row[4] if isinstance(row[4], dict) else json.loads(row[4])
            by_entity[row[1]].append(
                {
                    "record_id": row[0],
                    "entity": row[1],
                    "source_file": row[2],
                    "source_row_number": row[3],
                    "payload": payload,
                    "ingested_at_utc": row[5],
                }
            )
        results["source_records_read"] = len(source_rows)
        references = _load_reference_values(connection)
        rejections: list[dict[str, Any]] = []

        for entity, spec in ENTITY_SPECS.items():
            candidates: list[tuple[dict[str, Any], dict[str, Any]]] = []
            for record in by_entity[entity]:
                try:
                    values = _normalize_record(record, spec)
                except (ValueError, TypeError, InvalidOperation) as exc:
                    code = "INVALID_TIMESTAMP" if any(
                        field in str(exc).lower() for field in ("timestamp", "isoformat")
                    ) else "NEGATIVE_QTY" if "quantity must be positive" in str(exc) else "INVALID_VALUE"
                    rejections.append(
                        _reject(
                            record,
                            entity=entity,
                            stage=spec.table,
                            reason_code=code,
                            detail=str(exc),
                        )
                    )
                    continue

                missing_reference = next(
                    (
                        (field, reference)
                        for field, reference in spec.references.items()
                        if values[field] is not None and values[field] not in references[reference]
                    ),
                    None,
                )
                if missing_reference:
                    field, reference = missing_reference
                    rejections.append(
                        _reject(
                            record,
                            entity=entity,
                            stage=spec.table,
                            reason_code="MISSING_FK",
                            detail=f"{field}={values[field]!r} does not exist in {reference}",
                        )
                    )
                    continue
                candidates.append((record, values))

            grouped: dict[tuple[Any, ...], list[tuple[dict[str, Any], dict[str, Any]]]] = defaultdict(list)
            for record, values in candidates:
                grouped[tuple(values[key] for key in spec.keys)].append((record, values))

            selected: list[tuple[dict[str, Any], dict[str, Any]]] = []
            for group in grouped.values():
                winner = max(group, key=lambda item: _winner_order(spec, *item))
                selected.append(winner)
                for duplicate_record, _ in group:
                    if duplicate_record["record_id"] != winner[0]["record_id"]:
                        rejections.append(
                            _reject(
                                duplicate_record,
                                entity=entity,
                                stage=spec.table,
                                reason_code="DUPLICATE",
                                detail=(
                                    "Kept the record with the latest updated_at_utc, "
                                    "then highest Bronze record_id."
                                    if spec.table == "orders"
                                    else (
                                        "Kept the lowest Bronze record_id for key "
                                        f"{tuple(winner[1][key] for key in spec.keys)!r}."
                                    )
                                ),
                            )
                        )

            insert_rows = [
                {
                    **values,
                    "bronze_record_id": record["record_id"],
                    "pipeline_run_id": run_id,
                }
                for record, values in selected
            ]
            loaded = _insert_rows(
                connection,
                table=spec.table,
                columns=list(spec.field_map),
                keys=spec.keys,
                rows=insert_rows,
            )
            results["rows_loaded"] += loaded
            results["rows_deduplicated"] += len(candidates) - len(selected)
            results["tables"][spec.table] = {
                "read": len(by_entity[entity]),
                "loaded": loaded,
                "deduplicated": len(candidates) - len(selected),
            }

            reference = next(
                (reference for reference in REFERENCE_QUERIES if reference.endswith(f".{spec.keys[0]}")),
                None,
            )
            if reference and spec.table in {"cities", "customers", "products", "stores", "sales_channels", "promotions", "orders"}:
                for _, values in selected:
                    value = values.get(spec.keys[0])
                    if value is not None:
                        references[reference].add(value)
            if spec.table == "sales_channels":
                references["sales_channels.channel_name"].update(
                    values["channel_name"] for _, values in selected if values["channel_name"] is not None
                )

        results["rows_rejected"] = len(rejections)
        results["rejection_rows_added"] = _insert_rejections(connection, rejections, run_id)
        results["rejection_candidates"] = len(rejections)
    log.info("Silver build completed: %s", results)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pipeline-run-id")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    run(pipeline_run_id=args.pipeline_run_id)


if __name__ == "__main__":
    main()
