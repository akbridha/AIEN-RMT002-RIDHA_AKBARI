 Persiapan dan Bronze	Pahami kontrak Gold dan struktur data. Unduh data ke data/raw/, periksa jumlah dan struktur file, serta pastikan semua file dapat dibaca. Pipeline mengabaikan manifest.	

Rancang tabel Bronze dan metadata lineage. Buat schema serta aturan penyimpanan payload sumber secara utuh.

Implementasikan pemuatan Bronze. Uji kelengkapan data, lineage, dan perilaku saat proses dijalankan ulang.

— Silver	Rancang tabel bertipe, kunci deduplikasi, validasi referensi, dan aturan penolakan data.

Implementasikan normalisasi timestamp ke UTC, deduplikasi deterministik, validasi, dan penanganan record invalid.	Tangani event, perubahan profil berbasis waktu, dan late-arriving records. 
        
Jalankan pengujian Silver dan tinjau catatan record yang ditolak.

Gold dan metrik	Pastikan grain dan definisi metrik untuk lima tabel Gold. 

Rencanakan transformasi agar join tidak menggandakan fakta.	Bangun transformasi Gold: order, customer harian, produk harian, channel/campaign, dan KPI eksekutif.	

Uji grain, metrik, revenue/refund, campaign, inventory, serta rekonsiliasi terhadap Silver. Perbaiki mismatch yang ditemukan.

Orkestrasi dan finalisasi	Lengkapi DAG Airflow dan dependency: validasi data → inisialisasi schema → Bronze → Silver → quality gate → Gold → validasi/metadata.

Jalankan pipeline end-to-end dari awal. Uji rerun, kegagalan quality gate, dan pencatatan status/error. Perbaiki bug integrasi.	 
Jalankan pertanyaan analitik melalui engine/UI, simpan bukti run Airflow dan contoh query, lalu periksa kelengkapan submission serta pastikan tidak ada kredensial ikut terunggah.




    ###### ======== Q & A ======== #####
    Q = apakah perlu buat directory baru lagi?
    A = __Tidak perlu directory baru, tidak perlu generate project baru.__ Repo yang sekarang sudah ADALAH "dasar" milestone ini — ini paket participant yang sudah disiapkan instructor (berbasis __uv__, Python ≥3.11, FastAPI engine + Streamlit UI + `gold.sql` contract + test harness). Yang harus Anda lakukan adalah __mengisi bagian yang hilang di dalam repo ini__, bukan scaffold proyek baru.


        Q = Bagaimana menghubungkan file-file python di repo ini agar bisa      berinteraksi dengan database postgre?
        Bagaimana membuat file koneksi agar file file python ini bisa berhubungan dengan database apakah harus buat connection.py? dan bagiamana nanti jika saya eksekusi 'loader_bronze.py' apakah saya harus run file connection dan bagaimana jika saya melakukan via DAG nantinya bagaimana membuat koneksi tetap valid?
        A = MEnggunakan file shared/db.py. aman digunakan jika secara file terpisah atau secara beruntun/pipepline dengan airflow.
        Tidak perlu membuat atau menjalankan `connection.py` terpisah. Gunakan helper `shared/db.py` melalui `pipelines.ingestion.db`. Loader meminta koneksi saat fungsi loader berjalan, misalnya dengan `connect("local")`, lalu koneksi ditutup setelah pekerjaan selesai. Untuk eksekusi manual, konfigurasi database harus tersedia di `.env` atau environment. Untuk Airflow, konfigurasi yang sama harus tersedia di lingkungan worker/container Airflow juga; `localhost` di dalam container menunjuk ke container itu sendiri, bukan otomatis ke komputer host. Pipeline milestone harus memakai PostgreSQL lokal, bukan Neon. Jangan menulis password ke kode atau log.

    Q = Untuk schema bronze pakai desain 'shred & load' atau pakai JSONB ?
    A = pADA file readmie ada anjuran JSONB. README memperbolehkan payload Bronze disimpan sebagai JS   raw tetap disimpan tanpa perubahan di `data/raw/`.

    Q = Bagaimana cara membuat script untuk menjalankan schema agar tabel benar-benar dibuat di     database?
    A = PostgreSQL dan database tujuan harus sudah hidup/tersedia terlebih dahulu. File SQL adalah resep pembentukan schema/tabel; untuk menerapkannya gunakan `uv run python -m pipelines.ingestion.initialize_database` dari folder `PHASE1`. Script tersebut memakai `shared/db.py`, memilih koneksi `local`, lalu menjalankan `bronze.sql`, `silver.sql`, `gold.sql`, dan `ops.sql` dalam satu koneksi/transaksi. Script dapat dijalankan manual untuk pengembangan, dan fungsi `run()` yang sama dapat dipanggil sebagai task inisialisasi dari DAG. Jika salah satu file

    cara reset DB = DROP SCHEMA IF EXISTS bronze, silver, gold, ops CASCADE;


    Q = Apa perbedaan `pipelines/__init__.py` dan `pipelines/ingestion/__init__.py`?
    A = Keduanya adalah penanda/pengaturan package Python, bukan script koneksi atau inisialisasi database. File pertama menandai folder `pipelines` sebagai package utama. File kedua menandai subpackage `pipelines.ingestion`. Keduanya membantu import seperti `from pipelines.ingestion.db import connect`. Untuk membuat tabel, gunakan modul terpisah `pipelines.ingestion.initialize_database`.

    Q = Apakah tabel `bronze.ingestion_files` memang diperlukan?
    A = Tidak wajib secara teori, tetapi berguna dan sesuai schema Bronze saat ini. `bronze.source_records` mencatat lineage per record; `bronze.ingestion_files` mencatat metadata per file dan per run, seperti SHA-256 hasil hitung loader, ukuran, jumlah record, dan `pipeline_run_id`. Tabel ini tidak menyimpan checksum manifest karena manifest diabaikan.


    ==== Bronze=====



    Q = Bagaimana menjalankan loader Bronze yang sesuai dengan schema?
    A = Jalankan dari folder `PHASE1` dengan `uv run python -m pipelines.bronze.build_bronze --input data/raw --batch-size 500 --pipeline-run-id manual-test`. Loader tidak membaca atau membutuhkan manifest. Loader membaca JSON/CSV, memasukkan satu record per baris ke `bronze.source_records`, menghitung checksum file dan payload, serta mencatat metadata file ke `bronze.ingestion_files`. Pastikan tabel sudah dibuat dengan modul inisialisasi schema terlebih dahulu.
    
    schema hilang atau eksekusi SQL gagal, proses akan gagal dan transaksi dibatalkan.

    Q = Bagaimana cara mengeksekusi satu FIle .py saja tanpa harus lewat Pipeline?
    A = File harus menyediakan fungsi kerja dan entry point `if __name__ == "__main__":`. Jalankan dari folder `PHASE1` dengan `uv run python -m nama_paket.nama_modul`, misalnya `uv run python -m pipelines.ingestion.initialize_database`. Untuk loader, setelah modulnya tersedia, contoh bentuknya `uv run python -m pipelines.bronze.build_bronze --input data/raw`; argumen yang tersedia ditentukan oleh parser loader. Menjalankan satu modul manual tidak mengharuskan menjalankan DAG, tetapi PostgreSQL, schema, dan konfigurasi koneksi tetap harus siap.

    RUN LOADER BRONZE `uv run python -m pipelines.bronze.build_bronze --input data/raw`

    
    Q = Bagaimana cara memastikan dalam satu batch data yang sama tidak terambil 2 kali pada batch berbeda.
    A = Batch adalah cara mengirim data dalam potongan-potongan; batch ID saja tidak mencegah record yang sama terkirim ulang. Berikan setiap record kunci sumber yang stabil, misalnya pasangan `(source_file, source_row_number)`, buat pasangan itu `UNIQUE` di PostgreSQL, dan lakukan insert dengan `ON CONFLICT DO NOTHING` (atau strategi upsert yang disengaja). Nomor baris harus dihitung dari posisi record di seluruh file, bukan dimulai ulang dari 1 pada setiap batch. Dengan demikian, bila batas batch tumpang tindih atau run diulang, database menolak record yang sama. Skema Bronze saat ini sudah memiliki `UNIQUE (source_file, source_row_number)`. Batasannya: jika isi file berubah tetapi nama dan nomor baris sama, record baru akan dianggap konflik; untuk input yang dapat berubah, gunakan identitas versi/checksum file dalam kunci atau perlakukan setiap versi sebagai file berbeda. Tetap rekonsiliasikan jumlah yang dibaca, dimasukkan, dan dilewati.

    Q = query sederhana untuk memastikan tidak ada duplikat antar batch
    A = SELECT source_file, source_row_number, COUNT(*) AS jumlah
        FROM bronze.source_records
        GROUP BY source_file, source_row_number
        HAVING COUNT(*) > 1;

    Q = apa fungis file init di setiap directory script?
    A = “dua file init” sebagai pipelines/__init__.py dan pipelines/ingestion/__init__.py. Keduanya bukan program yang membuat tabel atau membuka koneksi. Keduanya     membantu Python mengenali folder sebagai package agar import seperti from pipelines.ingestion.db import connect dapat digunakan.

    Q = Ketika build bronze bekerja dalam beberapa batch, Bagaimana mengetahui suatu data raw sudah ingested semua. secara kita eksekusi terus menerus. Pada kasus di dalam pipeline chaining bagaimana DAG mengetahui kapan harus melanjutkan ke fase berikutny?


    A = Pada baris 211 terdapat kode untuk mengumpulkan semua file yang ada 
    ``raw_root.rglob("*")` mengumpulkan __semua__ file lalu masuk ke variable 'source_files'
    dari situ acuan untuk loop ingestion
` 
    
    Jika tidak ada file sama sekali → FileNotFoundError → task DAG gagal (tidak lanjut). ` raise FileNotFoundError(f"No JSON or CSV source files found under {raw_root}")`

    ====== Silver ==========

    Q = <Silver> Bagaimana cara untuk mendeteksi DUplikasi pada data.
    A = Pakai perbandingan beberpa kolom dari row 

    Q =  Setelah masuk silver apakah struktur kolom akan berubah?

    Q = Bagaimana memastikan 	Tipe data, UTC, deduplication, referential checks, rejection, dan temporal logic benar?

    Q = bagaimana eksekusi build_silver? (parameternya)?
    A = uv run python -m pipelines.silver.build_silver 
     uv run python -m pipelines.silver.build_silver --pipeline-run-id manual-test-01

    Q = apakah build silver memakai method batching juga?


    Q =  silver memiliki banyak table yang harus diisi, bagaimana kodenya? apakah permethod untuk satu table dan beberapa method universal untuk urus Tipe data, UTC, deduplication, referential checks, rejection ?



    ====== DAG =====
     Q = Bagaimana cara setting airflow agar mengikut sertakan suatu script atau tidak


    Q = Bagaiamana passing argument ketika menjalanakan suatu script .py ?


    Q = saat semua script per proses dieksekusi DAG apakah per satu batch ingestion akan diproses sampai gold per iterasi secara 
        waterfall/ sequensial.
    A = Alur pengerjaan tidak iterasi satu cyclce per batch, iterasi semua fase hanya satu kali. namun per fase yang diiterasi sampai datanya habis dahulu baru lanjut ke fase berikutnya . proses suatu fase tidak dilanjutkan sebeleum iterasi di fase   itu menghabiskan semua data.










| Tantangan | Mekanisme yang menangani | Cakupan saat ini |
|---|---|---|
| Duplicate order | Silver mengelompokkan berdasarkan `order_id`, memilih record dengan `updated_at_utc` terbaru, lalu `bronze_record_id` terbesar sebagai pemecah seri. Record duplikat dicatat di `silver.rejected_records`. | Ditangani di Silver. |
| Duplicate event | Tabel event memakai `event_id` sebagai key. Jika ada duplikat, Silver memilih `bronze_record_id` terkecil dan mencatat sisanya sebagai rejection. | Ditangani di Silver. |
| Split payment dan partial refund | Silver mempertahankan setiap payment/refund sebagai baris event terpisah dengan `event_id`, `order_id`, waktu, dan `amount`. Gold harus menjumlahkan event yang relevan per order; jangan menganggap satu event selalu mewakili pembayaran atau refund penuh. | Event disimpan di Silver; agregasi dan rekonsiliasi harus dilakukan di Gold. |
| Event terlambat dan timestamp tidak berurutan | Bronze menyimpan waktu kejadian dan waktu ingest. Silver membaca ulang seluruh `bronze.source_records` setiap eksekusi dan menyimpan keduanya pada tabel event, sehingga event yang baru masuk ke Bronze dapat ditemukan saat Silver dijalankan ulang. Analisis urutan kejadian di Gold harus menggunakan `occurred_at_utc`, bukan urutan ingest atau ID record. | Data pendukung tersedia di Silver; belum ada pemrosesan incremental atau rekonstruksi state event khusus. |
| Timestamp dengan timezone berbeda | `standardize_time_utc()` mengonversi timestamp yang memiliki timezone ke UTC. Timestamp tanpa timezone ditolak karena zona waktunya tidak bisa ditebak dengan aman. | Ditangani di Silver; timestamp tanpa zona dicatat sebagai record invalid. |
| Missing reference ke customer, product, atau order | Silver memeriksa ID referensi terhadap tabel Silver terkait. Referensi yang tidak ditemukan menghasilkan rejection dengan kode `MISSING_FK`, bukan membuat entitas pengganti. | Ditangani di Silver untuk referensi yang dikonfigurasi pada `ENTITY_SPECS`. |
| Negative quantity | Silver memeriksa `order_items.quantity`; nilai nol atau negatif ditolak dengan kode `NEGATIVE_QTY`. Bronze tetap mempertahankan payload sumbernya. | Ditangani di Silver. |
| Perubahan profil customer dan kategori product | Silver menyimpan `customer_profiles` dan `product_categories` dengan `valid_from_utc` serta `valid_to_utc`, dan key yang mencakup waktu mulai berlaku. Gold harus memilih versi yang berlaku pada tanggal transaksi/aktivitas. | Riwayat versi tersimpan di Silver; pemilihan versi berdasarkan waktu transaksi dan pemeriksaan periode tumpang tindih masih harus diterapkan. |
| Order dibatalkan tetapi payment sudah captured | Silver menyimpan status order dan payment event secara terpisah; event payment tidak dihapus hanya karena status order `CANCELLED`. Gold harus menghitung payment berdasarkan event captured dan menerapkan definisi metric yang sesuai, bukan menyimpulkan bahwa order batal berarti tidak ada payment. | Pemisahan data tersedia di Silver; aturan rekonsiliasi order/payment harus diterapkan di Gold. |
| Inventory snapshot yang hilang | Silver hanya menyimpan snapshot yang benar-benar tersedia; baris snapshot yang hilang tidak dibuat otomatis. Gold perlu mempertahankan baris produk/tanggal yang relevan dan membedakan nilai inventory `NULL` (tidak ada snapshot) dari `0` (snapshot ada, stok kosong). | Belum diisi atau disimpulkan oleh Silver; penanganan cakupan dan metric dilakukan di Gold. |
| Banyak promotion/campaign yang berpotensi menggandakan fact | Silver mempertahankan grain relasi promotion per `(order_id, promotion_id)` dan spend per `(spend_date, campaign_id, channel)`. Gold harus mengagregasi fact pada grain yang sesuai sebelum join ke promotion, campaign, inventory, atau event. | Grain sumber tersedia di Silver; pencegahan fact multiplication wajib diterapkan dan diuji di Gold. |






## Hasil audit repo (sudah ada vs belum ada)

__Sudah disediakan (jangan dibuat ulang):__

- `engine/` (NL-to-SQL), `ui/` (Streamlit), `shared/db.py`, `docs/`, `tests/`
- `database/schemas/gold.sql` — kontrak Gold yang tidak boleh diubah
- `pyproject.toml` + `uv.lock`, `docker-compose.yml` (Postgres 16 lokal), `.env.example`, `.gitignore`
- `uv 0.12.20` dan `Docker 27.5.1` sudah terpasang di mesin Anda

__Belum ada — ini "dasar" yang harus Anda buat ( Hari ke-1 ):__

```text
data/raw/                                ← unduh file sumber dari Google Drive (4 folder)
database/schemas/bronze.sql              ← rancang sendiri
database/schemas/silver.sql
database/schemas/ops.sql
pipelines/__init__.py
pipelines/ingestion/db.py                ← wajib: tests meng-import dsn_from_environment dari sini
pipelines/ingestion/initialize_database.py
pipelines/bronze/build_bronze.py
pipelines/silver/build_silver.sql (+ .py runner)
pipelines/gold/build_gold.sql   (+ .py runner)
pipelines/run_pipeline.py
dags/dag.py                              ← entrypoint utama Airflow
evidence/
```




## Temuan penting 
1. __Test suite Anda saat ini pasti gagal saat koleksi__ — `tests/pipelines/test_database_profiles.py` meng-import `pipelines.ingestion.db` dan `tests/pipelines/test_generator.py` meng-import `pipelines.generator.generate_data`, tetapi folder `pipelines/` belum ada sama sekali. Jadi langkah pertama scaffold harus membuat modul-modul ini (minimal `ingestion/db.py` cukup memetakan fungsi `dsn_from_environment` ke `shared/db.py`).

2. __Konflik nama file antara README dan tests__ — README menyebut submission `build_silver.py` / `build_gold.py`, tetapi `tests/pipelines/test_contract.py` dan `database/README.md` mensyaratkan `build_silver.sql` / `build_gold.sql`. Solusi aman: sediakan __keduanya__ — file `.sql` berisi query utama + file `.py` sebagai runner yang mengeksekusinya. Ini memenuhi kedua kontrak sekaligus.

3. __Airflow belum ada di dependency, dan Anda di Windows__ — Airflow tidak mendukung Windows native. Pilihan yang realistis: (a) jalankan Airflow via __WSL2__, atau (b) via __Docker Compose__ (compose file sudah ada, tinggal ditambah service airflow), atau (c) venv terpisah khusus Airflow agar tidak bentrok dengan `uv.lock`. Ini keputusan desain yang perlu dipilih di awal Hari-4 (atau lebih baik dari sekarang).

4. __Postgres lokal__ sudah tersedia via `docker compose up -d postgres` (db `retail_analytics`, user `retail`) — cukup jalankan service `postgres` saja, tidak perlu seluruh compose stack.

## Rencana eksekusi yang saya usulkan (untuk dijalankan setelah Anda toggle ke Act mode)

__Fase 0 — Fondasi (setara "dasar milestone"):__

1. Salin `.env.example` → `.env`, isi `ANALYTICS_DB_TARGET=local` + `LOCAL_DATABASE_URL`
2. `uv sync` untuk memastikan environment terpasang
3. Buat kerangka folder `pipelines/` + `dags/` beserta `__init__.py`
4. Buat `pipelines/ingestion/db.py` (delegasi ke `shared/db.py`) agar `pytest tests/pipelines` bisa terkoleksi
5. Buat `pipelines/ingestion/initialize_database.py` yang membaca 4 file `database/schemas/*.sql` (bronze/silver/ops yang masih placeholder + gold contract)
6. Buat placeholder `bronze.sql` / `silver.sql` / `ops.sql` dan starter `build_bronze.py`, `build_silver.sql`, `build_gold.sql` (+ wrapper `.py`)
7. Buat kerangka `dags/dag.py` dengan 7 tahap dependency persis seperti kontrak README
8. Jalankan `uv run pytest tests/pipelines -q` untuk membuktikan fondasi hijau

__Fase 1 (Hari 1, sesuai RencanaPengerjaan):__ unduh file sumber dari Google Drive ke `data/raw/`, pastikan struktur dan jumlah file sesuai, lalu implementasi Bronze sungguhan. Pipeline peserta mengabaikan manifest dan menghitung checksum file secara langsung.

Satu hal yang perlu saya konfirmasi sebelum eksekusi: __untuk Airflow, jalur mana yang Anda inginkan — WSL2, Docker Compose, atau venv terpisah?__ (Ini menentukan isi Fase 0 langkah 7–8.) Setelah itu, silakan __toggle ke Act mode__ dan saya akan scaffold seluruh fondasi di atas.
