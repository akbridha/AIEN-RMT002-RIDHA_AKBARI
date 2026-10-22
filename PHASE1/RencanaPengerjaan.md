 Persiapan dan Bronze	Pahami kontrak Gold dan struktur data. Unduh data ke data/raw/, periksa manifest, jumlah file, dan struktur direktori.	

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


    Q = Untuk schema bronze pakai desain 'shred & load' atau pakai JSONB ?
    A = pakai JSONB saja sesuai arahan Readme.
    
    Q = Bagaimana cara buat script untuk eksekusi schema yang sudah dibuat agar tablenya masuk di database yang sebenarnya?

    Q = Bagaimana cara mengeksekusi satu FIle .py saja tanpa harus lewat Pipeline?
    
    Q = Bagaimana cara memastikan dalam satu batch data yang sama tidak terambil 2 kali pada batch berbeda.


    Q = <Silver> Bagaimana cara untuk mendeteksi DUplikasi pada data.
    A = Pakai perbandingan beberpa kolom dari row 

    Q =  Setelah masuk silver apakah struktur kolom akan berubah?

    Q = Bagaimana memastikan 	Tipe data, UTC, deduplication, referential checks, rejection, dan temporal logic benar?


     Q = Bagaimana cara setting airflow agar mengikut sertakan suatu script atau tidak


    Q = Bagaiamana passing argument ketika menjalanakan suatu script .py ?


















## Hasil audit repo (sudah ada vs belum ada)

__Sudah disediakan (jangan dibuat ulang):__

- `engine/` (NL-to-SQL), `ui/` (Streamlit), `shared/db.py`, `docs/`, `tests/`
- `database/schemas/gold.sql` — kontrak Gold yang tidak boleh diubah
- `pyproject.toml` + `uv.lock`, `docker-compose.yml` (Postgres 16 lokal), `.env.example`, `.gitignore`
- `uv 0.12.20` dan `Docker 27.5.1` sudah terpasang di mesin Anda

__Belum ada — ini "dasar" yang harus Anda buat ( Hari ke-1 ):__

```text
data/raw/                                ← unduh dari Google Drive (manifest.json + 4 folder)
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




## Temuan penting (jebakan yang saya temukan saat audit)

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

__Fase 1 (Hari 1, sesuai RencanaPengerjaan):__ unduh data Google Drive ke `data/raw/`, validasi `manifest.json` (test sudah ada: checksum SHA-256 + rentang tanggal `2026-06-22`–`2026-09-19`), lalu implementasi Bronze sungguhan.

Satu hal yang perlu saya konfirmasi sebelum eksekusi: __untuk Airflow, jalur mana yang Anda inginkan — WSL2, Docker Compose, atau venv terpisah?__ (Ini menentukan isi Fase 0 langkah 7–8.) Setelah itu, silakan __toggle ke Act mode__ dan saya akan scaffold seluruh fondasi di atas.
