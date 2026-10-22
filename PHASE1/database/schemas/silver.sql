
-- SILVER  goal => table sudah bertipe, ternormalisasi, tervalidasi, punya lineage
-- TODo jangan lupa ubah disimpan UTC.


-- kode untuk grain 

-- gold.order_360	---- #A
-- gold.customer_daily	---- #B
-- gold.product_daily ---- #C
-- gold.channel_campaign_daily	---- #D
-- gold.executive_kpis_daily	---- #E

-- Pemetaan kebutuhan Gold -> Silver:
-- #B customer_daily: customers, orders, order_items, refund_events,
--    return_events, support_events.
-- #C product_daily: products, product_categories, orders, order_items,
--    order_promotions, refund_events, inventory_snapshots.
-- #D channel_campaign_daily: sales_channels, orders, order_items,
--    refund_events, web_events, campaign_spend.
-- #E executive_kpis_daily: customers, products, orders, order_items,
--    payment_events, refund_events, return_events, support_events,
--    inventory_snapshots.
-- Pemetaan ini menunjukkan sumber yang diperlukan untuk menghitung metrik;
-- agregasikan event/item sebelum join agar grain Gold tidak berlipat.


CREATE SCHEMA IF NOT EXISTS silver;  /* jangan lupa skema */

-- =================--------- DIMENSION -------------------------------

CREATE TABLE IF NOT EXISTS silver.cities (  /* 1 -  A.1  */
    city_id           TEXT PRIMARY KEY,
    city_name         TEXT,
    country           TEXT,
    bronze_record_id  BIGINT REFERENCES bronze.source_records (record_id),
    pipeline_run_id   TEXT NOT NULL
);

-- Dibutuhkan Gold #B dan #E: validasi customer dan tanggal pembuatan customer
-- untuk menentukan metrik customer baru/repeat.
CREATE TABLE IF NOT EXISTS silver.customers ( /* 2 - A.2*/
    customer_id       TEXT PRIMARY KEY,
    city_id           TEXT,
    customer_segment  TEXT,
    created_at_utc    TIMESTAMPTZ,
    bronze_record_id  BIGINT REFERENCES bronze.source_records (record_id),
    pipeline_run_id   TEXT NOT NULL
);



-- Versi profil customer (temporal version selection)
CREATE TABLE IF NOT EXISTS silver.customer_profiles ( /* 3 - B.1 */
    customer_id       TEXT NOT NULL,
    valid_from_utc    TIMESTAMPTZ NOT NULL,
    valid_to_utc      TIMESTAMPTZ,               -- NULL = versi aktif
    city_id           TEXT,
    customer_segment  TEXT,
    bronze_record_id  BIGINT REFERENCES bronze.source_records (record_id),
    pipeline_run_id   TEXT NOT NULL,
    PRIMARY KEY (customer_id, valid_from_utc)
);

CREATE TABLE IF NOT EXISTS silver.customer_addresses ( /* 4 - B.2*/
    address_id        TEXT PRIMARY KEY,
    customer_id       TEXT NOT NULL,
    city_id           TEXT,
    valid_from_utc    TIMESTAMPTZ,
    valid_to_utc      TIMESTAMPTZ,
    bronze_record_id  BIGINT REFERENCES bronze.source_records (record_id),
    pipeline_run_id   TEXT NOT NULL
);

-- Dibutuhkan Gold #C dan #E: referensi produk dan populasi stockout.
CREATE TABLE IF NOT EXISTS silver.products ( /* 5 - B.3*/
    product_id        TEXT PRIMARY KEY,
    product_name      TEXT,
    sku               TEXT,
    unit_price        NUMERIC(14, 2),
    bronze_record_id  BIGINT REFERENCES bronze.source_records (record_id),
    pipeline_run_id   TEXT NOT NULL
);

-- Versi kategori product (temporal version selection)
-- Dibutuhkan Gold #C: kategori yang berlaku pada tanggal aktivitas produk.
CREATE TABLE IF NOT EXISTS silver.product_categories ( /* 6 - B.4*/
    product_id        TEXT NOT NULL,
    valid_from_utc    TIMESTAMPTZ NOT NULL,
    valid_to_utc      TIMESTAMPTZ,
    category_id       TEXT,
    category_name     TEXT,
    bronze_record_id  BIGINT REFERENCES bronze.source_records (record_id),
    pipeline_run_id   TEXT NOT NULL,
    PRIMARY KEY (product_id, valid_from_utc)
);

CREATE TABLE IF NOT EXISTS silver.stores ( /* 7 - B.5*/
    store_id          TEXT PRIMARY KEY,
    store_name        TEXT,
    city_id           TEXT,
    location_type     TEXT,
    bronze_record_id  BIGINT REFERENCES bronze.source_records (record_id),
    pipeline_run_id   TEXT NOT NULL
);




-- Dibutuhkan Gold #D (dan #B bila active_channel memakai nama channel):
-- menyelaraskan label channel dari berbagai sumber.
CREATE TABLE IF NOT EXISTS silver.sales_channels ( /* 8 - B.6 */
    channel_id        TEXT PRIMARY KEY,
    channel_name      TEXT,
    bronze_record_id  BIGINT REFERENCES bronze.source_records (record_id),
    pipeline_run_id   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS silver.promotions ( /* 9 - B.7*/
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


-- table ini diubuthkan untuk table : order.360(#A)
-- Dibutuhkan Gold #B, #C, #D, dan #E: tanggal, customer, channel, status,
-- dan grain order menjadi dasar agregasi harian.
CREATE TABLE IF NOT EXISTS silver.orders ( /* 10 - C.1 */
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
-- table ini DIBUTUHkan untuk table : order.360(#A)
-- Dibutuhkan Gold #B, #C, #D, dan #E: unit, item count, dan nilai penjualan.
CREATE TABLE IF NOT EXISTS silver.order_items ( /* 11 - C.2 */
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
-- table ini diubuthkan untuk table : order.360(#A)
-- Dibutuhkan Gold #C: menghubungkan promosi order ke produk untuk promotion
-- count; agregasikan sebelum join agar baris item tidak berganda.
CREATE TABLE IF NOT EXISTS silver.order_promotions ( /* 12 - C.3 */
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


-- table ini diubuthkan untuk table : order.360(#A)
-- Dibutuhkan Gold #E: captured payment menjadi dasar refund rate.
CREATE TABLE IF NOT EXISTS silver.payment_events ( /* 13  - D.1*/
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


-- table ini diubuthkan untuk table : order.360(#A)
-- Dibutuhkan Gold #B, #C, #D, dan #E untuk nilai refund/refunded units.
CREATE TABLE IF NOT EXISTS silver.refund_events ( /* 14 - D.2*/
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


-- table ini diubuthkan untuk table : order.360(#A)
-- Dibutuhkan Gold #B dan #E untuk jumlah return dan return rate.
CREATE TABLE IF NOT EXISTS silver.return_events ( /* 15 - D.3*/
    event_id          TEXT PRIMARY KEY,
    event_type        TEXT NOT NULL,
    occurred_at_utc   TIMESTAMPTZ NOT NULL,
    ingested_at_utc   TIMESTAMPTZ NOT NULL,
    order_id          TEXT,
    return_id         TEXT,
    bronze_record_id  BIGINT REFERENCES bronze.source_records (record_id),
    pipeline_run_id   TEXT NOT NULL
);

-- Dibutuhkan Gold #B dan #E untuk support contacts/contact rate.
CREATE TABLE IF NOT EXISTS silver.support_events ( /* 16  - D.4*/
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

-- Dibutuhkan Gold #D untuk campaign/channel/order attribution.
CREATE TABLE IF NOT EXISTS silver.web_events ( /* 17 - D.5*/
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

-- Dibutuhkan Gold #C dan #E untuk available stock dan stockout rate.
CREATE TABLE IF NOT EXISTS silver.inventory_snapshots ( /* 18  - E.1*/
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

-- Dibutuhkan Gold #D: spend per campaign/channel/date menjadi dasar ROAS.
CREATE TABLE IF NOT EXISTS silver.campaign_spend ( /* 19 - E.2 */
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

CREATE TABLE IF NOT EXISTS silver.rejected_records ( /* 20  - E.3*/
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
