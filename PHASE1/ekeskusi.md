



==== Ulang PIPELINE===================
Bronze: bersifat append-only. Loader menghindari duplikat dengan kunci (source_file, source_row_number) dan ON CONFLICT DO NOTHING; record yang sudah ada dilewati, bukan dihapus atau dimuat ulang. Jika isi file berubah tetapi nama/path-nya sama, loader akan gagal karena checksum berbeda. Lihat build_bronze.py.
Silver: tidak melakukan DELETE atau TRUNCATE. Loader melakukan upsert berdasarkan key tiap tabel, jadi baris yang cocok diperbarui; baris lama yang tak lagi ada di Bronze tidak otomatis dibersihkan. Lihat build_silver.py.
Gold: berbeda—builder menghapus isi lima tabel Gold, lalu membangunnya kembali dari Silver. Lihat build_gold.py dan bagian rebuild.
======================



hapus semua skema. DROP SCHEMA IF EXISTS bronze, silver, gold, ops CASCADE;

uv run python -m pipelines.bronze.build_bronze
uv run python -m pipelines.silver.build_silver

docker compose exec airflow-scheduler airflow dags trigger xbar

DAG parsing parameter lebih ribet  karena tersandung di pengiriman parameter

    $conf = '{"mode":"simulate","simulate_gate_failure":true}'
    $confB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($conf))

    docker compose exec -T airflow-scheduler python -c "import base64, json, subprocess; conf = base64.b64decode('$confB64').decode('utf-8'); json.loads(conf); raise SystemExit(subprocess.call(['airflow', 'dags', 'trigger', 'xbar', '--conf', conf]))"


=======catatan kolom bronze dalam mendukung kualitas data==========

Berikut poin-poin yang menunjukkan kriteria Bronze, beserta catatan atas hal yang belum dijamin langsung oleh DDL:

Nama file sumber dapat dilihat.
Tabel bronze.ingestion_files mencatat file yang diproses; source_file menyimpan path relatif terhadap data/raw/. Nama file juga disimpan pada setiap record di bronze.source_records.
Bukti: bronze.sql:10 · bronze.sql:12 · bronze.sql:26

Nomor baris sumber tersedia untuk identifikasi record.
source_row_number menyimpan nomor record dalam file, dimulai dari 1.
Bukti: bronze.sql:27

Record yang sama tidak masuk lagi hanya karena batch atau run berbeda.
Constraint UNIQUE (source_file, source_row_number) tidak memasukkan pipeline_run_id sebagai bagian kunci. Jadi, file dan nomor record yang sama akan berbenturan meskipun berasal dari run berbeda. Loader juga memakai ON CONFLICT ... DO NOTHING; nomor baris dihitung dari seluruh file sebelum record dikirim per batch.
Bukti SQL: bronze.sql:33
Bukti loader: build_bronze.py:78 · build_bronze.py:265

Payload asli dan source record identifier tersedia.
payload bertipe JSONB untuk menyimpan isi record; source_record_id disediakan untuk ID asli dari sumber jika tersedia.
Bukti: bronze.sql:28 · bronze.sql:29

Checksum dan jejak ingestion tercatat.
Tabel file mencatat checksum file, jumlah baris, serta pipeline_run_id; tabel record juga mencatat checksum payload dan run ID. Tabel operasional menyimpan status dan waktu setiap pipeline run.
Bukti: bronze.sql:15 · bronze.sql:16 · bronze.sql:17 · bronze.sql:30 · bronze.sql:31 · ops.sql:9 · ops.sql:14

Catatan: DDL menyatakan Bronze sebagai immutable dan menyimpan payload asli, tetapi definisi tabel ini sendiri belum mencegah UPDATE atau DELETE secara teknis. Jadi, kriteria penyimpanan evidence dan deduplikasi sudah didukung skema; jaminan immutable perlu ditegakkan melalui hak akses database atau mekanisme lain. Selain itu, kunci deduplikasi mengasumsikan path file tetap sama: file dengan isi berubah pada path yang sama tidak dianggap versi baru.


validate_raw_files
initialize_database
build_bronze
build_silver
quality_gate
gold.build_gold
validate_gold



