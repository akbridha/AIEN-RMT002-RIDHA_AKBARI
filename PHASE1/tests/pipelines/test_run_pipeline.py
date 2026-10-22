from __future__ import annotations

import pytest

from pipelines import run_pipeline


class FakeConnection:
    def __init__(self):
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return None

    def execute(self, query, params=()):
        self.calls.append((" ".join(query.split()), params))


def test_runner_shares_run_id_and_marks_pipeline_success(monkeypatch):
    connection = FakeConnection()
    monkeypatch.setattr(run_pipeline, "connect", lambda target: connection)
    monkeypatch.setattr(run_pipeline, "initialize_database", lambda: [])
    monkeypatch.setattr(
        run_pipeline,
        "validate_raw_files",
        lambda **kwargs: {"files_validated": 3},
    )
    monkeypatch.setattr(
        run_pipeline.build_bronze,
        "run",
        lambda **kwargs: {"pipeline_run_id": kwargs["pipeline_run_id"]},
    )
    monkeypatch.setattr(
        run_pipeline.build_silver,
        "run",
        lambda **kwargs: {"pipeline_run_id": kwargs["pipeline_run_id"]},
    )
    monkeypatch.setattr(
        run_pipeline,
        "quality_gate",
        lambda **kwargs: {"pipeline_run_id": kwargs["pipeline_run_id"], "passed": True},
    )
    monkeypatch.setattr(
        run_pipeline.build_gold,
        "run",
        lambda **kwargs: {"pipeline_run_id": kwargs["pipeline_run_id"]},
    )

    result = run_pipeline.run(pipeline_run_id="run-manual-1")

    assert result["pipeline_run_id"] == "run-manual-1"
    assert [stage["pipeline_run_id"] for stage in result["stages"].values() if "pipeline_run_id" in stage] == [
        "run-manual-1",
        "run-manual-1",
        "run-manual-1",
        "run-manual-1",
    ]
    assert any(
        query.startswith("UPDATE ops.pipeline_runs")
        and params == ("SUCCESS", None, "run-manual-1")
        for query, params in connection.calls
    )


def test_runner_marks_pipeline_failed_when_a_stage_raises(monkeypatch):
    connection = FakeConnection()
    monkeypatch.setattr(run_pipeline, "connect", lambda target: connection)
    monkeypatch.setattr(run_pipeline, "initialize_database", lambda: [])

    def fail_validation(**kwargs):
        raise ValueError("missing input file")

    monkeypatch.setattr(run_pipeline, "validate_raw_files", fail_validation)

    with pytest.raises(ValueError, match="missing input file"):
        run_pipeline.run(pipeline_run_id="run-manual-failed")

    assert any(
        query.startswith("UPDATE ops.pipeline_runs")
        and params[0] == "FAILED"
        and params[1] == "missing input file"
        and params[2] == "run-manual-failed"
        for query, params in connection.calls
    )
