from __future__ import annotations

import pytest

from pipelines.quality import quality_gate


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, *, orders_for_run=2):
        self.orders_for_run = orders_for_run
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return None

    def execute(self, query, params=()):
        normalized = " ".join(query.split())
        self.calls.append((normalized, params))
        if normalized == "SELECT to_regclass(%s)":
            return FakeCursor([(params[0],)])
        if "GROUP BY reason_code" in normalized:
            return FakeCursor([("DUPLICATE", 1)])
        if "COUNT(*)" in normalized:
            if "FROM silver.orders WHERE pipeline_run_id" in normalized:
                return FakeCursor([(self.orders_for_run,)])
            if "FROM silver.order_items WHERE pipeline_run_id" in normalized:
                return FakeCursor([(2,)])
            if "FROM silver.rejected_records" in normalized:
                return FakeCursor([(1,)])
            return FakeCursor([(0,)])
        return FakeCursor([])


def test_quality_gate_persists_passed_checks(monkeypatch):
    connection = FakeConnection()
    monkeypatch.setattr(quality_gate, "connect", lambda target: connection)

    result = quality_gate.run(pipeline_run_id="run-1")

    assert result["passed"] is True
    assert result["failed_checks"] == 0
    assert result["pipeline_run_id"] == "run-1"
    assert any(
        "INSERT INTO ops.pipeline_runs" in query
        and params == ("run-1", None, "manual")
        for query, params in connection.calls
    )
    assert any(
        "INSERT INTO ops.quality_gates" in query and params == ("run-1", True, 0)
        for query, params in connection.calls
    )
    rejection_check = next(
        check for check in result["checks"]
        if check["check_name"] == "silver_gate:rejected_records_reported"
    )
    assert rejection_check["passed"] is True
    assert "DUPLICATE: 1" in rejection_check["detail"]


def test_quality_gate_records_failure_then_blocks_gold(monkeypatch):
    connection = FakeConnection(orders_for_run=0)
    monkeypatch.setattr(quality_gate, "connect", lambda target: connection)

    with pytest.raises(RuntimeError, match="Gold build is blocked"):
        quality_gate.run(pipeline_run_id="run-2")

    assert any(
        "UPDATE ops.pipeline_runs" in query and params[1] == "run-2"
        for query, params in connection.calls
    )
    assert any(
        "INSERT INTO ops.quality_gates" in query and params == ("run-2", False, 1)
        for query, params in connection.calls
    )
    assert any(
        "INSERT INTO ops.quality_checks" in query
        and params[0] == "run-2"
        and params[1] == "silver_gate:orders_present_for_run"
        and params[6] is False
        for query, params in connection.calls
    )
