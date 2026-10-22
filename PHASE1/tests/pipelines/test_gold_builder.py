from __future__ import annotations

import logging

from pipelines.gold import build_gold


def test_run_rebuilds_all_gold_tables_and_logs_progress(monkeypatch, caplog):
    class FakeCursor:
        def __init__(self, row=None):
            self.row = row

        def fetchone(self):
            return self.row

    class FakeConnection:
        def __init__(self):
            self.calls = []

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return None

        def execute(self, query, params=()):
            self.calls.append((query, params))
            if query.startswith("SELECT COUNT(*)"):
                return FakeCursor((3,))
            return FakeCursor()

    connection = FakeConnection()
    monkeypatch.setattr(build_gold, "connect", lambda target: connection)

    with caplog.at_level(logging.INFO):
        results = build_gold.run(pipeline_run_id="run-1")

    assert results["pipeline_run_id"] == "run-1"
    assert results["rows_loaded"] == 15
    assert {
        table: metrics["loaded"] for table, metrics in results["tables"].items()
    } == {table: 3 for table in build_gold.GOLD_TABLES}
    delete_calls = [
        query for query, _ in connection.calls if query in build_gold.DELETE_SQL
    ]
    assert delete_calls == list(build_gold.DELETE_SQL)
    assert any("INSERT INTO ops.pipeline_runs" in query for query, _ in connection.calls)
    assert any("INSERT INTO ops.pipeline_tasks" in query for query, _ in connection.calls)
    assert sum("INSERT INTO gold." in query for query, _ in connection.calls) == 5
    assert all(
        params == ("run-1",)
        for query, params in connection.calls
        if query.lstrip().startswith("WITH")
    )
    assert "[1/5] Building gold.order_360 from Silver" in caplog.text
    assert "[5/5] Finished gold.executive_kpis_daily: loaded=3" in caplog.text
    assert "refunded_units" in caplog.text


def test_gold_build_statements_populate_the_fixed_contract():
    insert_targets = [
        statement.split("INSERT INTO ", maxsplit=1)[1].split("(", maxsplit=1)[0].strip()
        for _, statement in build_gold.BUILD_STATEMENTS
    ]

    assert insert_targets == [f"gold.{table}" for table in build_gold.GOLD_TABLES]
    assert all("%s" in statement for _, statement in build_gold.BUILD_STATEMENTS)
