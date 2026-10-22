# Simulasi Airflow (mode `PIPELINE_MODE=simulate`)

Konfigurasi ini menjalankan Airflow 2.10.4 di Docker untuk **mensimulasikan**
seluruh tahap pipeline milestone P1M1 **tanpa operasi ingestion/build/transform
nyata**: tidak ada koneksi database, tidak ada baris yang dimuat, tidak ada
tabel yang ditulis. Setiap task hanya menulis log simulasi dan pemeriksaan
file read-only (keberadaan `manifest.json`, file skema `database/schemas/*.sql`).

## Menjalankan

```powershell
docker compose up airflow-init            # sekali: migrate SQLite + user admin
docker compose up -d airflow-webserver airflow-scheduler
```

Buka **http://localhost:8081** → login `airflow` / `airflow`
(8080 dipakai aplikasi lain di host, jadi webserver dipetakan ke 8081).

## Menjalankan DAG

1. Buka DAG `milestone1_omnichannel_pipeline` (langsung unpaused, schedule manual).
2. Klik **Trigger DAG** — tujuh tahap berjalan berurutan:
   `validate_manifest_and_raw → initialize_postgres_schemas → load_bronze →
   build_silver → quality_gate → build_gold → validate_gold_and_record_metadata`.
3. Klik task → **Log** untuk melihat output `[SIMULASI] ...` beserta
   `pipeline_run_id` yang diteruskan antar tahap.

Atau via CLI:

```powershell
docker compose exec airflow-scheduler airflow dags trigger milestone1_omnichannel_pipeline
docker compose exec airflow-scheduler airflow tasks states-for-dag-run milestone1_omnichannel_pipeline <run_id>
```

## Menguji quality gate menghentikan pipeline

```powershell
docker compose exec airflow-scheduler airflow dags trigger milestone1_omnichannel_pipeline --conf '{\"simulate_gate_failure\":true}'
```

Hasil yang diharapkan: `quality_gate=failed`, lalu `build_gold` dan
`validate_gold_and_record_metadata` menjadi `upstream_failed` (tidak
dijalankan). Escape `\"` diperlukan karena PowerShell membuang quote inner.

## Beralih ke mode real (Hari 2–4)

Set `PIPELINE_MODE=real` di environment compose (mis. di `.env`), lalu
`docker compose up -d` ulang. Mode memanggil modul sesuai pemetaan di
`dags/dag.py`:

| Tahap | Modul |
|---|---|
| validate_manifest_and_raw | `pipelines.ingestion.validate_manifest:run` |
| initialize_postgres_schemas | `pipelines.ingestion.initialize_database:run` |
| load_bronze | `pipelines.bronze.build_bronze:run` |
| build_silver | `pipelines.silver.build_silver:run` |
| build_gold | `pipelines.gold.build_gold:run` |
| validate_gold_and_record_metadata | `pipelines.quality.validate_gold:run` |

Modul yang belum ada menghasilkan error eksplisit (bukan sukses palsu).

## Catatan teknis

- Metadata Airflow memakai SQLite di named volume `airflow_data` (cukup untuk
  simulasi lokal); executor `SequentialExecutor`; contoh DAG dimatikan.
- Volume: `./dags` → `/opt/airflow/dags`, `./logs` → `/opt/airflow/logs`,
  repo → `/app` (agar `RAW_DATA_DIR=/app/data/raw` dan
  `SCHEMAS_DIR=/app/database/schemas` terbaca; `PYTHONPATH=/app` disiapkan
  untuk mode real).
- Image kustom di `docker/airflow/Dockerfile` (base `apache/airflow:2.10.4-python3.12`).
- Reset penuh: `docker compose down -v` (volume `airflow_data` ikut terhapus).
