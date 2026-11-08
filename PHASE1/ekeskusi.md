



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


1. Gold — build_gold.py
Tujuan: membangun tabel analitik Gold dari data Silver.
Menghasilkan lima tabel: order_360, customer_daily, product_daily, channel_campaign_daily, dan executive_kpis_daily.
Setiap tabel menghitung metrik dengan grain tertentu, misalnya per order, per pelanggan per hari, atau per produk per hari.
Saat dijalankan, isi tabel Gold dihapus lalu dibangun ulang dari Silver.
Setelah pembangunan, kode memeriksa konsistensi metrik dan kondisi NULL/nol; pelanggaran tertentu akan menggagalkan proses.
Bagian kode: daftar tabel dan DELETE (baris 15–23); query pembentuk tabel (baris 86–672); proses rebuild dan validasi (baris 682–755).
File: build_gold.py
2. Bronze — build_bronze.py
Tujuan: memasukkan data mentah dari file JSON/CSV ke PostgreSQL tanpa mengubah payload sumber.
Menyimpan record beserta entity, nama file, nomor baris, checksum, dan pipeline_run_id.
Pemrosesan dilakukan dalam batch.
Kunci (source_file, source_row_number) mencegah record yang sama dimasukkan dua kali saat rerun.
Checksum file digunakan untuk mendeteksi perubahan isi file; perubahan pada file dengan path yang sama menyebabkan proses gagal.
Metadata ingestion file dicatat di bronze.ingestion_files.
Bagian kode: parser file dan checksum (baris 83–142); insert batch dan metadata file (baris 144–206); proses ingestion utama (baris 208–315); fungsi run dan CLI (baris 317–360).
File: build_bronze.py
3. Silver — build_silver.py
Tujuan: mengubah record Bronze menjadi tabel yang bertipe dan tervalidasi.
Menstandarkan timestamp ke UTC serta mengonversi tanggal, angka, teks, dan nilai integer.
Menggunakan spesifikasi per entitas untuk menentukan tabel tujuan, kolom, key, kolom wajib, serta referensi.
Memeriksa duplikasi dan referensi antarentitas; record yang ditolak dicatat di silver.rejected_records.
Menggunakan upsert berdasarkan key tabel, sehingga record yang cocok diperbarui saat proses dijalankan ulang.
Bagian kode: fungsi normalisasi nilai (baris 77–167); spesifikasi entitas dan referensi (baris 169–498); normalisasi record dan penulisan batch (baris 499–674); proses transformasi utama (baris 676–910); fungsi run dan CLI (baris 912–953).
File: build_silver.py
4. Validasi Raw — validate_raw_files.py
Tujuan: memeriksa kesiapan file sumber sebelum data dimuat ke Bronze.
Memastikan direktori input tersedia dan berisi file JSON/CSV.
Memeriksa bahwa semua file sumber yang diwajibkan tersedia.
Membaca file untuk memastikan record dapat diparse, lalu menghitung jumlah file dan record.
Jika direktori, file wajib, atau parsing bermasalah, proses gagal sebelum ingestion.
Bagian kode: daftar file wajib (baris 17–37); pencarian dan validasi direktori/file (baris 40–68); parsing dan perhitungan hasil (baris 71–86); CLI (baris 91–107).
File: validate_raw_files.py
5. Orkestrasi Airflow — dag.py
Tujuan: mengatur urutan eksekusi pipeline melalui Airflow.
Urutan tahap: validasi raw → inisialisasi schema → Bronze → Silver → quality gate → Gold → validasi Gold.
Mendukung mode real untuk menjalankan pipeline sesungguhnya dan simulate untuk simulasi formalitas.
Parameter simulate_gate_failure dapat digunakan untuk membuat quality gate gagal saat mode simulasi.
Jika quality gate gagal, task Gold dan validasi Gold berikutnya tidak dijalankan.
DAG hanya berjalan saat di-trigger manual, bukan berulang berdasarkan jadwal.
Bagian kode: pemetaan task ke modul pipeline (baris 59–68); pemilihan mode dan dispatch (baris 75–140); fungsi tiap tahap (baris 145–278); parameter DAG (baris 281–310); dependency dan urutan task (baris 313–351).
File: dag.py
6. Validasi Gold — validate_gold.py
Tujuan: memastikan output Gold tersedia untuk pipeline_run_id yang sedang diperiksa.
Memeriksa keberadaan kelima tabel Gold.
Menghitung jumlah baris dengan pipeline_run_id tersebut pada setiap tabel; tabel dianggap lulus jika tersedia dan memiliki baris.
Mencatat hasil tiap pemeriksaan ke ops.quality_checks dan keputusan akhir ke ops.quality_gates.
Jika satu atau lebih tabel tidak memiliki output untuk run tersebut, validasi gagal.
Jika semua pemeriksaan lulus, status keseluruhan pipeline ditandai SUCCESS.
Bagian kode: daftar tabel Gold (baris 14–20); pemeriksaan tabel dan jumlah baris (baris 23–59); pencatatan hasil gate (baris 60–109); fungsi run dan penyelesaian status pipeline (baris 124–142).
File: validate_gold.py
Ringkasan alur






=========

xbar

4. Validasi Raw — validate_raw_files.py
Tujuan: memeriksa kesiapan file sumber sebelum data dimuat ke Bronze.
Memastikan direktori input tersedia dan berisi file JSON/CSV.
Memeriksa bahwa semua file sumber yang diwajibkan tersedia.
Membaca file untuk memastikan record dapat diparse, lalu menghitung jumlah file dan record.
Jika direktori, file wajib, atau parsing bermasalah, proses gagal sebelum ingestion.
Bagian kode: daftar file wajib (baris 17–37); pencarian dan validasi direktori/file (baris 40–68); parsing dan perhitungan hasil (baris 71–86); CLI (baris 91–107).

2. Bronze — build_bronze.py
Tujuan: memasukkan data mentah dari file JSON/CSV ke PostgreSQL tanpa mengubah payload sumber.
Menyimpan record beserta entity, nama file, nomor baris, checksum, dan pipeline_run_id.
Pemrosesan dilakukan dalam batch.
Kunci (source_file, source_row_number) mencegah record yang sama dimasukkan dua kali saat rerun.
Checksum file digunakan untuk mendeteksi perubahan isi file; perubahan pada file dengan path yang sama menyebabkan proses gagal.
Metadata ingestion file dicatat di bronze.ingestion_files.
Bagian kode: parser file dan checksum (baris 83–142); insert batch dan metadata file (baris 144–206); proses ingestion utama (baris 208–315); fungsi run dan CLI (baris 317–360).
File: build_bronze.py


3. Silver — build_silver.py
Tujuan: mengubah record Bronze menjadi tabel yang bertipe dan tervalidasi.
Menstandarkan timestamp ke UTC serta mengonversi tanggal, angka, teks, dan nilai integer.
Menggunakan spesifikasi per entitas untuk menentukan tabel tujuan, kolom, key, kolom wajib, serta referensi.
Memeriksa duplikasi dan referensi antarentitas; record yang ditolak dicatat di silver.rejected_records.
Menggunakan upsert berdasarkan key tabel, sehingga record yang cocok diperbarui saat proses dijalankan ulang.
Bagian kode: fungsi normalisasi nilai (baris 77–167); spesifikasi entitas dan referensi (baris 169–498); normalisasi record dan penulisan batch (baris 499–674); proses transformasi utama (baris 676–910); fungsi run dan CLI (baris 912–953).
File: build_silver.py
File: validate_raw_files.py

1. Gold — build_gold.py
Tujuan: membangun tabel analitik Gold dari data Silver.
Menghasilkan lima tabel: order_360, customer_daily, product_daily, channel_campaign_daily, dan executive_kpis_daily.
Setiap tabel menghitung metrik dengan grain tertentu, misalnya per order, per pelanggan per hari, atau per produk per hari.
Saat dijalankan, isi tabel Gold dihapus lalu dibangun ulang dari Silver.
Setelah pembangunan, kode memeriksa konsistensi metrik dan kondisi NULL/nol; pelanggaran tertentu akan menggagalkan proses.
Bagian kode: daftar tabel dan DELETE (baris 15–23); query pembentuk tabel (baris 86–672); proses rebuild dan validasi (baris 682–755).
File: build_gold.py



6. Validasi Gold — validate_gold.py
Tujuan: memastikan output Gold tersedia untuk pipeline_run_id yang sedang diperiksa.
Memeriksa keberadaan kelima tabel Gold.
Menghitung jumlah baris dengan pipeline_run_id tersebut pada setiap tabel; tabel dianggap lulus jika tersedia dan memiliki baris.
Mencatat hasil tiap pemeriksaan ke ops.quality_checks dan keputusan akhir ke ops.quality_gates.
Jika satu atau lebih tabel tidak memiliki output untuk run tersebut, validasi gagal.
Jika semua pemeriksaan lulus, status keseluruhan pipeline ditandai SUCCESS.
Bagian kode: daftar tabel Gold (baris 14–20); pemeriksaan tabel dan jumlah baris (baris 23–59); pencatatan hasil gate (baris 60–109); fungsi run dan penyelesaian status pipeline (baris 124–142).
File: validate_gold.py
Ringkasan alur
File raw → Validasi Raw → Bronze (simpan data mentah) → Silver (normalisasi dan validasi) → Quality Gate → Gold (hitung metrik) → Validasi Gold



5. Orkestrasi Airflow — dag.py
Tujuan: mengatur urutan eksekusi pipeline melalui Airflow.
Urutan tahap: validasi raw → inisialisasi schema → Bronze → Silver → quality gate → Gold → validasi Gold.
Mendukung mode real untuk menjalankan pipeline sesungguhnya dan simulate untuk simulasi formalitas.
Parameter simulate_gate_failure dapat digunakan untuk membuat quality gate gagal saat mode simulasi.
Jika quality gate gagal, task Gold dan validasi Gold berikutnya tidak dijalankan.
DAG hanya berjalan saat di-trigger manual, bukan berulang berdasarkan jadwal.
Bagian kode: pemetaan task ke modul pipeline (baris 59–68); pemilihan mode dan dispatch (baris 75–140); fungsi tiap tahap (baris 145–278); parameter DAG (baris 281–310); dependency dan urutan task (baris 313–351).
File: dag.py