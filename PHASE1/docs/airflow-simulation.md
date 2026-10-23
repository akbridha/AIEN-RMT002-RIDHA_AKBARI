# Menjalankan DAG Airflow

Konfigurasi ini menjalankan Airflow 2.10.4 di Docker. Setiap DAG run memiliki
parameter `mode` dan `simulate_gate_failure`; mode dapat dipilih tanpa mengubah
environment/container.

## Menjalankan

```powershell
docker compose up airflow-init            # sekali: migrate SQLite + user admin
docker compose up -d airflow-webserver airflow-scheduler
```

Buka **http://localhost:8081** → login `airflow` / `airflow`
(8080 dipakai aplikasi lain di host, jadi webserver dipetakan ke 8081).

## Menjalankan DAG

1. Buka DAG `milestone1_omnichannel_pipeline` (schedule manual).
2. Klik **Trigger DAG** dan pilih parameter:
   - `mode=simulate` untuk menjalankan simulasi formalitas. Tahap hanya menulis
     log dan melakukan pemeriksaan file read-only; tidak ada koneksi database,
     ingestion, transformasi, atau penulisan tabel.
   - `mode=real` untuk menjalankan pipeline sungguhan. Ini default-nya, kecuali
     `PIPELINE_MODE` di environment mengubah default.
   - `simulate_gate_failure=false` secara default. Atur ke `true` hanya untuk
     memaksa quality gate gagal pada mode simulasi; pada mode real parameter
     ini tidak digunakan.
3. Klik **Trigger** — tujuh tahap berjalan berurutan:
   `validate_raw_files → initialize_postgres_schemas → load_bronze →
   build_silver → quality_gate → build_gold → validate_gold_and_record_metadata`.
4. Klik task → **Log** untuk melihat output `[SIMULASI] ...` atau `[REAL] ...` beserta
   `pipeline_run_id` yang diteruskan antar tahap.

Atau via CLI:

```powershell
docker compose exec airflow-scheduler airflow dags trigger milestone1_omnichannel_pipeline --conf '{"mode":"simulate","simulate_gate_failure":false}'
docker compose exec airflow-scheduler airflow dags trigger milestone1_omnichannel_pipeline --conf '{"mode":"real"}'
docker compose exec airflow-scheduler airflow tasks states-for-dag-run milestone1_omnichannel_pipeline <run_id>
```

Jika `mode` tidak diberikan, default-nya `PIPELINE_MODE` (atau `real` bila
environment variable tidak diatur).

## Menguji quality gate menghentikan pipeline

```powershell
docker compose exec airflow-scheduler airflow dags trigger milestone1_omnichannel_pipeline --conf '{"mode":"simulate","simulate_gate_failure":true}'
```

Hasil yang diharapkan: `quality_gate=failed`, lalu `build_gold` dan
`validate_gold_and_record_metadata` menjadi `upstream_failed` (tidak
dijalankan).

## Mode default lewat environment

Untuk mengganti default bagi run yang tidak menentukan `mode`, set
`PIPELINE_MODE=real` atau `PIPELINE_MODE=simulate` di environment compose.
Override per-run melalui parameter Trigger DAG tetap dapat memilih mode yang
berbeda. Mode real memanggil modul sesuai pemetaan di `dags/dag.py`:

| Tahap | Modul |
|---|---|
| validate_raw_files | `pipelines.ingestion.validate_raw_files:run` |
| initialize_postgres_schemas | `pipelines.ingestion.initialize_database:run` |
| load_bronze | `pipelines.bronze.build_bronze:run` |
| build_silver | `pipelines.silver.build_silver:run` |
| quality_gate | `pipelines.quality.quality_gate:run` |
| build_gold | `pipelines.gold.build_gold:run` |
| validate_gold_and_record_metadata | `pipelines.quality.validate_gold:run` |

Modul yang belum ada menghasilkan error eksplisit (bukan sukses palsu).

Quality gate real memeriksa ketersediaan tabel Silver yang menjadi input Gold,
memastikan order dan item diproduksi pada run tersebut, memvalidasi referensi
customer/channel/order/product/promotion/inventory, lalu mencatat hasil tiap
pemeriksaan dan keputusan `silver_gate` ke `ops.quality_checks` dan
`ops.quality_gates`. Record yang ditolak tetap dihitung dan dirinci sebagai
informasi; record tersebut dikarantina di Silver dan tidak otomatis menggagalkan
gate. Pemeriksaan yang gagal menyebabkan task Airflow gagal sehingga Gold
tidak dijalankan.

Gate juga dapat dijalankan langsung dari folder `PHASE1` setelah schema Ops
diinisialisasi:

```powershell
python -m pipelines.quality.quality_gate --pipeline-run-id <pipeline_run_id>
```

Gunakan `pipeline_run_id` yang sama dengan tahap Silver. Jika opsi ID tidak
diberikan, gate memilih run Silver terbaru yang berstatus sukses dan memiliki
baris `orders` serta `order_items`. Jika tidak ada run yang cocok, gate
memberikan pesan error dan menyarankan menjalankan pipeline lengkap atau
memberikan ID secara eksplisit. Koneksi database lokal mengikuti konfigurasi
`LOCAL_DATABASE_URL` atau variabel `LOCAL_POSTGRES_*`.

Untuk menjalankan pipeline lokal lengkap tanpa Airflow, gunakan
`python -m pipelines.run_pipeline`. Runner meneruskan satu ID ke seluruh tahap,
mencatat status run `SUCCESS`/`FAILED`, dan builder juga mencatat status tahap
ke `ops.pipeline_tasks` saat dipanggil sendiri. Lihat bagian “Menjalankan
pipeline lokal tanpa Airflow” di README untuk contoh opsi perintah.

## Catatan teknis

- Metadata Airflow memakai SQLite di named volume `airflow_data` (cukup untuk
  simulasi lokal); executor `SequentialExecutor`; contoh DAG dimatikan.
- Volume: `./dags` → `/opt/airflow/dags`, `./logs` → `/opt/airflow/logs`,
  repo → `/app` (agar `RAW_DATA_DIR=/app/data/raw` dan
  `SCHEMAS_DIR=/app/database/schemas` terbaca; `PYTHONPATH=/app` disiapkan
  untuk mode real).
- Image kustom di `docker/airflow/Dockerfile` (base `apache/airflow:2.10.4-python3.12`).
- Reset penuh: `docker compose down -v` (volume `airflow_data` ikut terhapus).
