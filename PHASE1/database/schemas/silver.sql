-- =====================================================================
-- SILVER — tabel bertipe, ternormalisasi, tervalidasi, punya lineage
-- ke bronze.source_records. Semua timestamp TIMESTAMPTZ (disimpan UTC).
-- Record yang gagal validasi masuk ke silver.rejected_records.
-- =====================================================================

CREATE SCHEMA IF NOT EXISTS silver;

-- =================--------- DIMENSION -------------------------------

CREATE TABLE IF NOT EXISTS silver.cities (
    city_id           TEXT PRIMARY KEY,
    city_name         TEXT,
    country           TEXT,
    bronze_record_id  BIGINT REFERENCES bronze.source_records (record_id),
    pipeline_run_id   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS silver.customers (
    customer_id       TEXT PRIMARY KEY,
    city_id           TEXT,
    customer_segment  TEXT,
    created_at_utc    TIMESTAMPTZ,
    bronze_record_id  BIGINT REFERENCES bronze.source_records (record_id),
    pipeline_run_id   TEXT NOT NULL
);

-- Versi profil customer (temporal version selection)
CREATE TABLE IF NOT EXISTS silver.customer_profiles (
    customer_id       TEXT NOT NULL,
    valid_from_utc    TIMESTAMPTZ NOT NULL,
    valid_to_utc      TIMESTAMPTZ,               -- NULL = versi aktif
    city_id           TEXT,
    customer_segment  TEXT,
    bronze_record_id  BIGINT REFERENCES bronze.source_records (record_id),
    pipeline_run_id   TEXT NOT NULL,
    PRIMARY KEY (customer_id, valid_from_utc)
);

CREATE TABLE IF NOT EXISTS silver.customer_addresses (
    address_id        TEXT PRIMARY KEY,
    customer_id       TEXT NOT NULL,
    city_id           TEXT,
    valid_from_utc    TIMESTAMPTZ,
    valid_to_utc      TIMESTAMPTZ,
    bronze_record_id  BIGINT REFERENCES bronze.source_records (record_id),
    pipeline_run_id   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS silver.products (
    product_id        TEXT PRIMARY KEY,
    product_name      TEXT,
    sku               TEXT,
    unit_price        NUMERIC(14, 2),
    bronze_record_id  BIGINT REFERENCES bronze.source_records (record_id),
    pipeline_run_id   TEXT NOT NULL
);

-- Versi kategori product (temporal version selection)
CREATE TABLE IF NOT EXISTS silver.product_categories (
    product_id        TEXT NOT NULL,
    valid_from_utc    TIMESTAMPTZ NOT NULL,
    valid_to_utc      TIMESTAMPTZ,
    category_id       TEXT,
    category_name     TEXT,
    bronze_record_id  BIGINT REFERENCES bronze.source_records (record_id),
    pipeline_run_id   TEXT NOT NULL,
    PRIMARY KEY (product_id, valid_from_utc)
);

CREATE TABLE IF NOT EXISTS silver.stores (
    store_id          TEXT PRIMARY KEY,
    store_name        TEXT,
    city_id           TEXT,
    location_type     TEXT,
    bronze_record_id  BIGINT REFERENCES bronze.source_records (record_id),
    pipeline_run_id   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS silver.sales_channels (
    channel_id        TEXT PRIMARY KEY,
    channel_name      TEXT,
    bronze_record_id  BIGINT REFERENCES bronze.source_records (record_id),
    pipeline_run_id   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS silver.promotions (
    promotion_id      TEXT PRIMARY KEY,
    promotion_code    TEXT,
    promotion_type    TEXT,
    discount_rate     NUMERIC(6, 4),
    start_date        DATE,
    end_date          DATE,
    bronze_record_id  BIGINT REFERENCES bronze.source_records (record_id),
    pipeline_run_id   TEXT NOT NULL
);

-- =================--------- FACT ------------------------------------

-- Dedup: satu baris per order_id (deterministic key = order_id,
-- pilih versi updated_at_utc terbaru) — duplikat masuk rejected_records.
CREATE TABLE IF NOT EXISTS silver.orders (
    order_id          TEXT PRIMARY KEY,
    customer_id       TEXT NOT NULL,
    ordered_at_utc    TIMESTAMPTZ NOT NULL,
    sales_channel     TEXT NOT NULL,
    store_id          TEXT,
    shipping_revenue  NUMERIC(14, 2) NOT NULL DEFAULT 0,
    order_status      TEXT NOT NULL,
    updated_at_utc    TIMESTAMPTZ,
    bronze_record_id  BIGINT REFERENCES bronze.source_records (record_id),
    pipeline_run_id   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS silver.order_items (
    order_item_id        TEXT PRIMARY KEY,
    order_id             TEXT NOT NULL REFERENCES silver.orders (order_id),
    product_id           TEXT NOT NULL,
    quantity             INTEGER NOT NULL,       -- negatif -> rejected_records
    unit_price           NUMERIC(14, 2) NOT NULL,
    item_discount_amount NUMERIC(14, 2) NOT NULL DEFAULT 0,
    bronze_record_id     BIGINT REFERENCES bronze.source_records (record_id),
    pipeline_run_id      TEXT NOT NULL
);

-- Grain: satu order per promotion (duplikat = fact multiplication, ditolak)
CREATE TABLE IF NOT EXISTS silver.order_promotions (
    order_id          TEXT NOT NULL REFERENCES silver.orders (order_id),
    promotion_id      TEXT NOT NULL REFERENCES silver.promotions (promotion_id),
    discount_amount   NUMERIC(14, 2) NOT NULL DEFAULT 0,
    bronze_record_id  BIGINT REFERENCES bronze.source_records (record_id),
    pipeline_run_id   TEXT NOT NULL,
    PRIMARY KEY (order_id, promotion_id)
);

-- =================--------- EVENTS ----------------------------------
-- Event identity resolution: event_id unik -> duplikat ditolak.
-- occurred_at_utc = kapan kejadian; ingested_at_utc = kapan diterima
-- (dipakai untuk late-arriving records).

CREATE TABLE IF NOT EXISTS silver.payment_events (
    event_id          TEXT PRIMARY KEY,
    event_type        TEXT NOT NULL,
    occurred_at_utc   TIMESTAMPTZ NOT NULL,
    ingested_at_utc   TIMESTAMPTZ NOT NULL,
    order_id          TEXT,
    payment_id        TEXT,
    amount            NUMERIC(14, 2),
    bronze_record_id  BIGINT REFERENCES bronze.source_records (record_id),
    pipeline_run_id   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS silver.refund_events (
    event_id          TEXT PRIMARY KEY,
    event_type        TEXT NOT NULL,
    occurred_at_utc   TIMESTAMPTZ NOT NULL,
    ingested_at_utc   TIMESTAMPTZ NOT NULL,
    order_id          TEXT,
    refund_id         TEXT,
    amount            NUMERIC(14, 2),
    bronze_record_id  BIGINT REFERENCES bronze.source_records (record_id),
    pipeline_run_id   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS silver.return_events (
    event_id          TEXT PRIMARY KEY,
    event_type        TEXT NOT NULL,
    occurred_at_utc   TIMESTAMPTZ NOT NULL,
    ingested_at_utc   TIMESTAMPTZ NOT NULL,
    order_id          TEXT,
    return_id         TEXT,
    bronze_record_id  BIGINT REFERENCES bronze.source_records (record_id),
    pipeline_run_id   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS silver.support_events (
    event_id          TEXT PRIMARY KEY,
    event_type        TEXT NOT NULL,
    occurred_at_utc   TIMESTAMPTZ NOT NULL,
    ingested_at_utc   TIMESTAMPTZ NOT NULL,
    customer_id       TEXT,
    order_id          TEXT,
    ticket_id         TEXT,
    reason            TEXT,
    bronze_record_id  BIGINT REFERENCES bronze.source_records (record_id),
    pipeline_run_id   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS silver.web_events (
    event_id          TEXT PRIMARY KEY,
    event_type        TEXT NOT NULL,
    occurred_at_utc   TIMESTAMPTZ NOT NULL,
    ingested_at_utc   TIMESTAMPTZ NOT NULL,
    session_id        TEXT,
    customer_id       TEXT,
    order_id          TEXT,
    channel           TEXT,
    campaign_id       TEXT,
    bronze_record_id  BIGINT REFERENCES bronze.source_records (record_id),
    pipeline_run_id   TEXT NOT NULL
);

-- =================--- INVENTORY & CAMPAIGN --------------------------
-- Dibuat terpisah dari fact order agar join ke Gold tidak
-- menggandakan fakta (fact multiplication).

CREATE TABLE IF NOT EXISTS silver.inventory_snapshots (
    snapshot_date       DATE NOT NULL,
    product_id          TEXT NOT NULL,
    location_id         TEXT NOT NULL,
    available_quantity  INTEGER NOT NULL,
    reserved_quantity   INTEGER NOT NULL,
    unit_cost           NUMERIC(14, 2),
    bronze_record_id    BIGINT REFERENCES bronze.source_records (record_id),
    pipeline_run_id     TEXT NOT NULL,
    PRIMARY KEY (snapshot_date, product_id, location_id)
);

CREATE TABLE IF NOT EXISTS silver.campaign_spend (
    spend_date        DATE NOT NULL,
    campaign_id       TEXT NOT NULL,
    channel           TEXT NOT NULL,
    spend_amount      NUMERIC(14, 2) NOT NULL,
    bronze_record_id  BIGINT REFERENCES bronze.source_records (record_id),
    pipeline_run_id   TEXT NOT NULL,
    PRIMARY KEY (spend_date, campaign_id, channel)
);

-- =================--- REJECTED RECORDS ------------------------------
-- Wajib per README: setiap record yang ditolak punya alasan.

CREATE TABLE IF NOT EXISTS silver.rejected_records (
    rejected_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity            TEXT NOT NULL,
    source_file       TEXT NOT NULL,
    source_row_number BIGINT NOT NULL,
    reason_code       TEXT NOT NULL,   -- DUPLICATE, NEGATIVE_QTY, MISSING_FK, INVALID_TIMESTAMP, ...
    reason_detail     TEXT,
    payload           JSONB NOT NULL,  -- record asli yang ditolak (bukti)
    rejected_stage    TEXT NOT NULL,   -- 'silver.orders', 'silver.order_items', ...
    bronze_record_id  BIGINT REFERENCES bronze.source_records (record_id),
    pipeline_run_id   TEXT NOT NULL,
    rejected_at_utc   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_silver_orders_date   ON silver.orders (ordered_at_utc);
CREATE INDEX IF NOT EXISTS idx_silver_orders_cust   ON silver.orders (customer_id);
CREATE INDEX IF NOT EXISTS idx_silver_items_prod    ON silver.order_items (product_id);
CREATE INDEX IF NOT EXISTS idx_silver_pay_order     ON silver.payment_events (order_id, occurred_at_utc);
CREATE INDEX IF NOT EXISTS idx_silver_refund_order  ON silver.refund_events (order_id, occurred_at_utc);
CREATE INDEX IF NOT EXISTS idx_silver_return_order  ON silver.return_events (order_id, occurred_at_utc);
CREATE INDEX IF NOT EXISTS idx_silver_support_cust  ON silver.support_events (customer_id, occurred_at_utc);
CREATE INDEX IF NOT EXISTS idx_silver_web_date      ON silver.web_events (occurred_at_utc);
CREATE INDEX IF NOT EXISTS idx_silver_rej_run       ON silver.rejected_records (pipeline_run_id);
