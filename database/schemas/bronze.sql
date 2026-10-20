-- =====================================================================
-- BRONZE — source evidence, immutable, tanpa join / dedup / kalkulasi.
-- Setiap baris data pada file mentah = satu baris di bronze.source_records.
-- Rerun aman: UNIQUE (source_file, source_row_number) -> ON CONFLICT DO NOTHING.
-- =====================================================================

CREATE SCHEMA IF NOT EXISTS bronze;

-- Daftar file yang pernah di-ingest + checksum-nya (validasi manifest)
CREATE TABLE IF NOT EXISTS bronze.ingestion_files (
    file_id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_file       TEXT NOT NULL,             -- relatif terhadap data/raw/
    file_format       TEXT NOT NULL,             -- 'json' | 'csv'
    file_size_bytes   BIGINT,
    file_checksum     TEXT NOT NULL,             -- SHA-256 isi file
    manifest_checksum TEXT,                      -- checksum yang tercatat di manifest.json
    row_count         INTEGER,
    pipeline_run_id   TEXT NOT NULL,
    detected_at_utc   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_file, pipeline_run_id)
);

-- Seluruh record mentah. Payload TIDAK PERNAH diubah di layer ini.
CREATE TABLE IF NOT EXISTS bronze.source_records (
    record_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity           TEXT NOT NULL,              -- 'orders', 'payment_events', 'inventory', ...
    source_file      TEXT NOT NULL,              -- 'operational/orders.json'
    source_row_number BIGINT NOT NULL,           -- nomor baris data dalam file (1-based)
    source_record_id TEXT,                       -- source_row_id / event_id asli (jika ada)
    payload          JSONB NOT NULL,             -- objek/baris ASLI persis seperti sumber
    payload_checksum TEXT NOT NULL,              -- SHA-256 serialisasi payload
    pipeline_run_id  TEXT NOT NULL,
    ingested_at_utc  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_file, source_row_number)
);

CREATE INDEX IF NOT EXISTS idx_bronze_entity   ON bronze.source_records (entity);
CREATE INDEX IF NOT EXISTS idx_bronze_record   ON bronze.source_records (source_record_id);
CREATE INDEX IF NOT EXISTS idx_bronze_run      ON bronze.source_records (pipeline_run_id);
CREATE INDEX IF NOT EXISTS idx_bronze_payload  ON bronze.source_records USING gin (payload jsonb_path_ops);