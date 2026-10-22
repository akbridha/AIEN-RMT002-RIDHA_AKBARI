-- =====================================================================
-- OPS — metadata pipeline: status run, status tiap task, dan hasil
-- quality check. Dibaca oleh Airflow / DAG untuk quality gate.
-- =====================================================================

CREATE SCHEMA IF NOT EXISTS ops;

-- Satu baris per kali pipeline dijalankan (satu DAG run)
CREATE TABLE IF NOT EXISTS ops.pipeline_runs (
    pipeline_run_id   TEXT PRIMARY KEY,
    dag_run_id        TEXT,
    status            TEXT NOT NULL DEFAULT 'RUNNING',  -- RUNNING | SUCCESS | FAILED
    trigger_source    TEXT,                             -- 'airflow' | 'manual'
    started_at_utc    TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at_utc   TIMESTAMPTZ,
    error_message     TEXT,
    notes             TEXT
);

-- Status tiap tahap DAG (validate -> init -> bronze -> silver -> gate -> gold -> validate)
CREATE TABLE IF NOT EXISTS ops.pipeline_tasks (
    task_id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pipeline_run_id   TEXT NOT NULL REFERENCES ops.pipeline_runs (pipeline_run_id),
    task_name         TEXT NOT NULL,      -- 'validate_raw_files', 'build_bronze', ...
    status            TEXT NOT NULL,      -- 'RUNNING' | 'SUCCESS' | 'FAILED' | 'SKIPPED'
    started_at_utc    TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at_utc   TIMESTAMPTZ,
    rows_read         BIGINT,
    rows_written      BIGINT,
    rows_rejected     BIGINT,
    error_message     TEXT,
    UNIQUE (pipeline_run_id, task_name)
);

-- Hasil setiap quality check / reconciliation (per hitungan)
CREATE TABLE IF NOT EXISTS ops.quality_checks (
    check_id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pipeline_run_id   TEXT NOT NULL REFERENCES ops.pipeline_runs (pipeline_run_id),
    check_name        TEXT NOT NULL,      -- 'order_id_unique', 'net_revenue_match', ...
    check_type        TEXT NOT NULL,      -- 'uniqueness' | 'reconciliation' | 'business_rule'
    target_table      TEXT,
    expected_value    NUMERIC(20, 4),
    actual_value      NUMERIC(20, 4),
    passed            BOOLEAN NOT NULL,
    detail            TEXT,
    executed_at_utc   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Keputusan akhir quality gate: DAG membaca baris terakhir ini
-- untuk menentukan apakah tahap Gold boleh jalan.
CREATE TABLE IF NOT EXISTS ops.quality_gates (
    gate_id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pipeline_run_id   TEXT NOT NULL REFERENCES ops.pipeline_runs (pipeline_run_id),
    gate_name         TEXT NOT NULL,      -- 'silver_gate', 'gold_gate'
    passed            BOOLEAN NOT NULL,
    failed_checks     INTEGER NOT NULL DEFAULT 0,
    evaluated_at_utc  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (pipeline_run_id, gate_name)
);

CREATE INDEX IF NOT EXISTS idx_ops_runs_status  ON ops.pipeline_runs (status, started_at_utc);
CREATE INDEX IF NOT EXISTS idx_ops_checks_run   ON ops.quality_checks (pipeline_run_id, passed);
