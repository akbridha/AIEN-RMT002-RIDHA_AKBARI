from __future__ import annotations

import pytest

from pipelines.quality import validate_gold


class FakeResult:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class FakeConnection:
    def __init__(self, row_counts=None):
        self.row_counts = row_counts or {}
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return None

    def execute(self, query, params=()):
        normalized_query = " ".join(query.split())
        self.calls.append((normalized_query, params))
        if normalized_query == "SELECT to_regclass(%s)":
            return FakeResult((params[0],))
        if normalized_query.startswith("SELECT COUNT(*) FROM gold."):
            table = normalized_query.split(" FROM ", 1)[1].split(" WHERE", 1)[0]
            return FakeResult((self.row_counts.get(table, 1),))
        return FakeResult(None)


def test_validate_gold_records_gate_and_finishes_pipeline(monkeypatch):
    connection = FakeConnection()
    monkeypatch.setattr(validate_gold, "connect", lambda target: connection)

    result = validate_gold.run(pipeline_run_id="gold-run-1")

    assert result["passed"] is True
    assert set(result["row_counts"]) == set(validate_gold.GOLD_TABLES)
    assert any(
        "VALUES (%s, 'gold_gate', %s, %s)" in query
        and params == ("gold-run-1", True, 0)
        for query, params in connection.calls
    )
    assert any(
        query.startswith("UPDATE ops.pipeline_runs")
        and params == ("SUCCESS", None, "gold-run-1")
        for query, params in connection.calls
    )


def test_validate_gold_fails_and_records_failed_gate(monkeypatch):
    connection = FakeConnection({"gold.order_360": 0})
    monkeypatch.setattr(validate_gold, "connect", lambda target: connection)

    with pytest.raises(RuntimeError, match="gold.order_360"):
        validate_gold.run(pipeline_run_id="gold-run-failed")

    assert any(
        "VALUES (%s, 'gold_gate', %s, %s)" in query
        and params == ("gold-run-failed", False, 1)
        for query, params in connection.calls
    )
    assert any(
        query.startswith("UPDATE ops.pipeline_runs")
        and params[0] == "FAILED"
        and params[2] == "gold-run-failed"
        for query, params in connection.calls
    )
