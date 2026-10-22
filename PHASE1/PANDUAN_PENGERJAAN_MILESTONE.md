# Panduan Pengerjaan Milestone: Perjalanan Data dari Raw sampai Gold

Panduan ini ditujukan untuk peserta yang baru mengenal data engineering. Ikuti
langkahnya berurutan. Jangan mencoba membangun semua bagian sekaligus: pastikan
satu tahap bekerja dan hasilnya bisa diperiksa sebelum melanjutkan ke tahap
berikutnya.

## 1. Gambaran singkat

Bayangkan perusahaan menerima banyak dokumen dari berbagai bagian:

- Data customer, produk, toko, order, dan promosi.
- Catatan pembayaran, refund, return, dan bantuan customer.
- Snapshot persediaan barang.
- Pengeluaran campaign pemasaran.

Data itu melewati tiga tempat:

```text
File raw
   |
   v
Bronze  = arsip data sumber beserta label asal-usulnya
   |
   v
Silver  = data yang sudah dibaca, dirapikan, dan diperiksa
   |
   v
Gold    = tabel ringkasan yang siap dipakai untuk analisis
   |
   v
Engine dan UI = cara mengajukan pertanyaan bisnis atas tabel Gold
```

**Airflow bukan tempat penyimpanan data.** Airflow mengatur urutan dan waktu
program-program di atas dijalankan. PostgreSQL adalah tempat menyimpan tabel
Bronze, Silver, Gold, dan Ops.

## 2. Istilah penting dengan bahasa sederhana

| Istilah | Arti sederhana |
|---|---|
| Raw | File sumber yang belum diolah, seperti JSON dan CSV. |
| Database | Tempat PostgreSQL menyimpan tabel. Server PostgreSQL harus hidup dan database tujuan harus tersedia. |
| Schema | Kelompok tabel dalam database, seperti folder. Milestone ini memakai `bronze`, `silver`, `gold`, dan `ops`. |
| SQL schema file | Instruksi tertulis untuk membuat kelompok, tabel, kolom, dan aturan database. File SQL belum membuat tabel sampai dijalankan. |
| Loader | Program Python yang membaca file raw lalu memasukkan record ke tabel Bronze. |
| Record | Satu objek data JSON atau satu baris data CSV. |
| Payload | Isi record sumber, misalnya atribut order dalam JSON. |
| Lineage | Keterangan asal-usul record: file asal, nomor baris, ID sumber, dan ID run pipeline. |
| Transformasi | Program yang mengubah data dari satu layer ke layer berikutnya. |
| Grain | Tingkat detail satu baris tabel. Contoh: satu baris per order atau satu baris per customer per tanggal. |
| Idempotent / aman diulang | Menjalankan proses yang sama lagi tidak membuat data yang sama terduplikasi. |
| Quality gate | Pemeriksaan yang menentukan apakah data boleh diteruskan ke tahap berikutnya. |
| `pipeline_run_id` | ID unik satu proses pipeline, dipakai untuk menelusuri data dan log dari run tersebut. |

## 3. Siapkan lingkungan sebelum mengolah data

### Yang dikerjakan

1. Gunakan repository yang sudah disediakan; jangan membuat project baru.
2. Pastikan Python dan dependency proyek tersedia melalui `uv`.
3. Jalankan PostgreSQL lokal. Database target harus sudah ada dan bisa dihubungi.
4. Atur koneksi lokal melalui konfigurasi environment yang dipakai repository.
   Jangan pernah menyimpan password atau API key dalam file yang diunggah.
5. Tentukan runtime Airflow yang sesuai dengan komputer. Airflow tidak berjalan
   native di Windows; gunakan lingkungan yang didukung proyek, misalnya Docker
   atau WSL2.

### Hasil yang harus terlihat

- PostgreSQL lokal berjalan.
- Koneksi ke database lokal berhasil.
- File konfigurasi rahasia tetap lokal dan tidak masuk GitHub.

Menjalankan PostgreSQL **belum otomatis membuat tabel**. Membuat tabel adalah
tahap berikutnya.

## 4. Langkah 1 — Siapkan dan periksa file raw

### Yang dikerjakan

Unduh file sumber ke `data/raw/`. Struktur folder yang diminta README berisi
subfolder `operational/`, `events/`, `inventory/`, dan `reference/`.
`manifest.json`, jika ikut terunduh, diabaikan oleh pipeline.

Periksa:

- Semua file sumber yang diwajibkan README tersedia.
- File berada di folder yang benar.
- File bisa dibaca sebagai JSON atau CSV.
- Loader menghitung checksum SHA-256 dan jumlah record secara langsung.

### Hasil yang harus terlihat

```text
data/raw/
├── operational/
├── events/
├── inventory/
└── reference/
```

Pada tahap ini data masih berupa file. Belum ada data yang dimuat ke PostgreSQL.

### Jebakan

- Menganggap unduhan selesai hanya karena beberapa file terlihat.
- Mengubah file raw sebelum memasukkannya ke Bronze.
- Menganggap `manifest.json` sebagai validasi kelengkapan. Pipeline tidak
  membacanya; kelengkapan perlu dicek dengan daftar sumber yang diwajibkan.

## 5. Langkah 2 — Rancang schema dan tabel

Schema berarti rancangan struktur database. Tentukan kolom, tipe data, kunci,
dan aturan tabel dalam file SQL.

### File yang menjadi tanggung jawab peserta

- `database/schemas/bronze.sql`
- `database/schemas/silver.sql`
- `database/schemas/ops.sql`

`database/schemas/gold.sql` sudah disediakan sebagai kontrak. Jangan mengubah
nama tabel/kolom, tipe data, grain, atau makna metriknya.

### Rancangan sederhana tiap layer

**Bronze**

- `bronze.source_records`: satu baris database untuk satu record sumber.
- `payload`: isi record sebagai JSON.
- Kolom lineage: file asal, nomor record/baris, ID sumber jika ada,
  checksum, waktu muat, dan `pipeline_run_id`.
- `bronze.ingestion_files`: catatan file yang diproses, misalnya format,
  checksum file, jumlah record, dan run yang memprosesnya.

Kolom bisnis sumber tidak harus dibuat satu per satu di Bronze. Misalnya,
record order dapat disimpan di `payload`; kolom lineage tetap menjadi kolom
terpisah. Record duplikat dan invalid tetap dipertahankan di Bronze.

**Silver**

- Buat tabel bertipe untuk entitas dan event yang akan dipakai: misalnya order,
  order item, customer, produk, pembayaran, refund, return, dan inventory.
- Simpan hubungan kembali ke record Bronze agar asal data tetap bisa dilacak.
- Sediakan tabel seperti `silver.rejected_records` untuk record yang tidak
  dapat dipakai, lengkap dengan alasan penolakannya.

**Ops**

- Simpan status pipeline, waktu mulai/selesai, `pipeline_run_id`, serta
  informasi error dan hasil pemeriksaan kualitas.

### Hasil yang harus terlihat

File SQL Bronze, Silver, dan Ops sudah ditulis dan diperiksa. Pada saat ini
file tersebut masih berupa instruksi; tabel PostgreSQL belum tentu terbentuk.

### Jebakan

- Mengubah Gold karena ingin menyesuaikan pipeline.
- Menganggap menulis file `.sql` sama dengan membuat tabel di database.
- Mendesain Bronze sebagai tabel analitik yang sudah dibersihkan. Pembersihan
  dilakukan di Silver, bukan Bronze.

## 6. Langkah 3 — Buat tabel di PostgreSQL

### Yang dikerjakan

Buat tahap inisialisasi yang membaca dan menjalankan file schema pada database
PostgreSQL lokal. Database itu sendiri harus sudah hidup dan tersedia lebih
dahulu.

Urutan umumnya:

```text
PostgreSQL/database tersedia
        |
        v
jalankan bronze.sql, silver.sql, gold.sql, dan ops.sql
        |
        v
tabel sudah terbentuk dan siap diisi
```

Inisialisasi boleh dijalankan manual untuk pengembangan atau pemeriksaan.
Namun, pada hasil akhir, tahap tersebut juga harus ada di DAG agar alur
pipeline dapat dijalankan secara konsisten dari Airflow.

### Hasil yang harus terlihat

Di PostgreSQL lokal terdapat schema `bronze`, `silver`, `gold`, dan `ops`,
beserta tabel-tabel yang didefinisikan di file SQL.

### Jebakan

- Menjalankan SQL ke database yang berbeda dari database yang dipakai loader.
- Database hidup tetapi schema belum pernah dijalankan.
- SQL gagal, tetapi proses pipeline tetap lanjut seolah tabel sudah tersedia.

## 7. Langkah 4 — Bangun loader Bronze

Loader adalah program Python yang membaca file raw dan menyalin record ke
Bronze. Pandas boleh digunakan, tetapi tidak wajib. Modul Python `json` dan
`csv` sudah dapat membaca file JSON dan CSV.

### Alur loader

```text
buka file
  -> baca satu record
  -> buat payload dan catatan lineage
  -> masukkan record ke bronze.source_records
  -> catat ringkasan file ke bronze.ingestion_files
```

Contoh isi file order:

```json
{"order_id": "O-1", "customer_id": "C-1", "total": 50000}
```

Contoh yang disimpan di Bronze:

| Kolom | Contoh isi |
|---|---|
| `source_file` | `operational/orders.json` |
| `source_row_number` | `1` |
| `source_record_id` | `O-1` |
| `payload` | `{"order_id":"O-1","customer_id":"C-1","total":50000}` |
| `pipeline_run_id` | ID run Airflow atau run lokal |

Untuk CSV, satu baris CSV menjadi satu record/payload. Untuk JSON, satu objek
di dalam file menjadi satu record. Loader juga menghitung checksum dan jumlah
record file, tanpa membaca manifest.

### Aturan penting

- Jangan deduplikasi, mengubah status, memperbaiki nilai, atau menghitung
  metrik di Bronze.
- Simpan record invalid maupun duplikat; keputusan pemakaiannya ada di Silver.
- Gunakan parameter yang jelas seperti folder input dan `pipeline_run_id`.
- Gunakan parameter SQL untuk nilai data, bukan menyisipkan isi record ke
  string query SQL.
- Masukkan record secara berkelompok/batch agar file besar tidak harus
  dikirim satu per satu ke database.
- Pastikan memuat ulang file yang sama tidak menggandakan record.
- Jika file dengan nama yang sama berubah isinya, jangan mengabaikan perubahan
  secara diam-diam. Bandingkan checksum dan tentukan aturan pencatatan versi
  file.

### Hasil yang harus terlihat

- Semua file yang diharapkan tercatat di `bronze.ingestion_files`.
- Jumlah record di Bronze dapat direkonsiliasi dengan jumlah record yang
  dihitung langsung dari setiap file.
- Record Bronze dapat ditelusuri ke file dan posisi sumbernya.
- Rerun file yang sama tidak menambah duplikat yang tidak diinginkan.

### Jebakan

- Menganggap satu file adalah satu baris Bronze. Umumnya satu baris Bronze
  mewakili satu objek JSON atau baris CSV.
- Menyimpan payload tetapi lupa nama file dan nomor baris.
- Menggunakan `JSONB` dengan asumsi ia mempertahankan format teks mentah persis.
  `JSONB` mempertahankan nilai JSON, tetapi bukan spasi atau urutan teks asli.
  File raw tetap menjadi salinan sumber yang tidak diubah.

## 8. Langkah 5 — Bangun Silver

Silver mengubah arsip Bronze menjadi data yang lebih mudah dipakai dan aman
untuk dihitung. Tahap ini harus membaca Bronze, bukan membaca file raw secara
langsung.

### Yang dikerjakan

1. Ekstrak field dari payload ke kolom bertipe, misalnya ID sebagai teks,
   tanggal sebagai tanggal/waktu, jumlah sebagai angka, dan flag sebagai
   boolean.
2. Normalisasi timestamp menjadi UTC.
3. Deduplikasi dengan aturan deterministik: jika dijalankan ulang, record
   pilihan harus tetap sama.
4. Periksa referensi. Contoh: order mengacu ke customer atau product yang ada.
5. Normalisasi status ke daftar nilai yang konsisten.
6. Catat record yang ditolak dan alasannya; jangan menghilangkannya tanpa jejak.
7. Tangani perubahan customer/product dari waktu ke waktu sesuai tanggal
   berlakunya.
8. Perhitungkan event yang datang terlambat dan event yang timestamp-nya tidak
   berurutan.
9. Pertahankan referensi/lineage ke record Bronze.

### Contoh aturan penanganan

- Dua record order identik: simpan keduanya di Bronze; pilih/resolve satu di
  Silver dengan aturan deduplikasi yang terdokumentasi.
- Quantity negatif: simpan di Bronze; tolak atau tangani di Silver sesuai
  aturan bisnis, lalu catat alasannya.
- Customer tidak ditemukan: jangan membuat customer palsu; tandai record
  sebagai rejected atau gunakan aturan eksplisit yang disepakati.
- Timestamp dengan zona waktu: konversikan berdasarkan timezone sumber ke UTC,
  bukan sekadar menghapus informasi zona waktu.

### Hasil yang harus terlihat

- Tabel Silver berisi data yang sudah bertipe dan tervalidasi.
- Record yang bermasalah dapat ditemukan di tabel rejected beserta sebabnya.
- Record Silver dapat ditelusuri kembali ke Bronze.
- Jumlah record yang masuk, diterima, dideduplikasi, dan ditolak dapat
  dijelaskan.

### Jebakan

- Menghapus record invalid tanpa catatan.
- Menganggap setiap payment event adalah pembayaran penuh; pembayaran bisa
  terbagi dan refund bisa sebagian.
- Menggunakan profil customer terbaru untuk transaksi lama tanpa aturan waktu.
- Memilih record terbaru dengan urutan file, bukan timestamp/aturan yang benar.

## 9. Langkah 6 — Tetapkan dan bangun Gold

Gold adalah antarmuka analitik untuk engine/UI. Bentuk tabel dan metrik sudah
ditetapkan dalam `database/schemas/gold.sql`; tugas peserta adalah mengisinya
dari Silver tanpa mengubah kontrak.

| Tabel Gold | Arti satu baris (grain) |
|---|---|
| `gold.order_360` | Satu baris per order |
| `gold.customer_daily` | Satu customer per tanggal |
| `gold.product_daily` | Satu product per tanggal |
| `gold.channel_campaign_daily` | Satu tanggal, channel, dan campaign |
| `gold.executive_kpis_daily` | Satu tanggal bisnis |

### Cara menghindari angka berlipat

Jangan langsung menggabungkan semua tabel mentah sekaligus. Satu order mungkin
memiliki beberapa item, beberapa promotion, beberapa payment event, dan
beberapa refund. Jika semua digabung tanpa diringkas terlebih dahulu, satu
order dapat berubah menjadi banyak baris dan revenue ikut terhitung berkali-kali.

Pola yang lebih aman:

```text
Silver order items  -> hitung total item/revenue per order
Silver payments     -> hitung total captured per order
Silver refunds      -> hitung total refund per order
Silver promotions   -> hitung jumlah/nilai promo per order
                           |
                           v
              gabungkan hasil yang sudah diringkas
                           |
                           v
                    gold.order_360
```

Lakukan pola serupa untuk agregasi customer harian, produk harian,
channel/campaign, dan KPI eksekutif. Tentukan pula aturan untuk campaign yang
tidak memiliki atribusi dan inventory snapshot yang hilang.

Ikuti definisi metrik pada README dan kontrak Gold. Contoh:

```text
net_revenue = gross_merchandise_value
              - discount_amount
              + shipping_revenue
              - refunded_amount
```

### Hasil yang harus terlihat

- Kelima tabel Gold terisi.
- Primary key/grain setiap tabel tidak memiliki duplikasi.
- Metrik utama bisa dijelaskan dan dihitung ulang dari Silver.
- Engine/UI dapat membaca Gold sesuai kontrak.

### Jebakan

- Mengubah schema Gold agar cocok dengan query yang dibuat.
- Menghitung revenue sebelum mengatasi join satu-ke-banyak.
- Menganggap jumlah baris Gold harus sama dengan Bronze atau Silver. Grain
  masing-masing berbeda.
- Memperlakukan nilai NULL/missing inventory seolah-olah selalu nol tanpa
  aturan bisnis yang jelas.

## 10. Langkah 7 — Quality gate dan rekonsiliasi

Pemeriksaan kualitas harus menjalankan query/perhitungan nyata, bukan hanya
menulis “lulus” ke log.

### Pemeriksaan minimum yang disarankan

Sebelum Gold:

- Periksa kegagalan transformasi Silver dan rejected records.
- Periksa referensi yang wajib ada.
- Bandingkan jumlah record yang dibaca, diterima, dideduplikasi, dan ditolak.
- Pastikan input yang dibutuhkan Gold tersedia.

Sesudah Gold:

- Periksa keunikan grain setiap tabel Gold.
- Bandingkan revenue dan refund Gold dengan hasil perhitungan dari Silver.
- Periksa nilai ROAS/conversion dan metrik lain terhadap definisinya.
- Pastikan tidak terjadi penggandaan fakta akibat join.

README menempatkan quality gate sebelum Gold dan validasi Gold setelah build.
Karena itu, pemeriksaan prasyarat Silver dilakukan sebelum Gold, lalu
pemeriksaan grain dan rekonsiliasi akhir dilakukan setelah Gold.

### Hasil yang harus terlihat

- Laporan pemeriksaan menyebutkan apa yang diperiksa dan hasilnya.
- Jika pemeriksaan sebelum Gold gagal, task Gold tidak dijalankan.
- Status dan error tersimpan di `ops` atau dapat ditemukan jelas di log run.

### Jebakan

- Quality gate hanya berupa task bernama `quality_gate`, tetapi tidak memeriksa
  data.
- Kegagalan dicatat tetapi alur tetap meneruskan Gold.
- Memvalidasi hanya bahwa tabel berisi baris, tanpa menguji grain atau angka.

## 11. Langkah 8 — Hubungkan tahap-tahap dengan Airflow

DAG adalah pengatur urutan. Ia seharusnya memanggil program validasi,
inisialisasi schema, loader Bronze, transformasi Silver, quality gate, build
Gold, dan validasi akhir.

Urutan yang diminta:

```text
validasi raw files (manifest diabaikan)
        -> inisialisasi PostgreSQL schemas
        -> load Bronze
        -> build Silver
        -> quality gate
        -> build Gold
        -> validasi Gold dan catat metadata
```

### DAG yang harus dibuat

- Setiap tahap bergantung pada tahap sebelumnya yang memang harus sukses.
- DAG memberikan `pipeline_run_id` yang sama ke tahap-tahap terkait.
- Run ulang tidak menggandakan data.
- Kegagalan quality gate menghentikan tahap Gold.
- Status dan error pipeline dicatat di Ops.
- Pipeline menggunakan PostgreSQL lokal, bukan mengunggah Bronze/Silver ke
  Neon.

### Perhatian untuk DAG yang sudah ada di repository

DAG yang ada memiliki `PIPELINE_MODE=simulate` sebagai mode default. Dalam
mode simulasi, task mencatat log contoh dan **tidak** membuat tabel, mengisi
Bronze, mengolah Silver, atau membangun Gold. Mode ini berguna untuk
mendemonstrasikan urutan, tetapi bukan bukti pipeline nyata sudah bekerja.

Untuk submission, pastikan mode real memanggil modul pipeline yang benar-benar
diimplementasikan. Periksa juga bahwa nama modul, fungsi, dan parameter yang
dipanggil DAG cocok dengan kode pipeline. Kegagalan harus terlihat jelas,
bukan berubah menjadi status sukses palsu.

### Hasil yang harus terlihat

Di Airflow UI, satu DAG run menampilkan task sesuai urutan. Setelah run nyata,
periksa PostgreSQL untuk memastikan jumlah data/tabel memang berubah dan
`pipeline_run_id` tercatat.

## 12. Langkah 9 — Uji secara bertahap

Jangan menunggu sampai semua kode selesai untuk mulai menguji.

Urutan uji yang aman:

1. Jalankan pemeriksaan keberadaan dan keterbacaan file raw.
2. Jalankan inisialisasi schema; pastikan tabel muncul.
3. Muat satu file kecil ke Bronze; cocokkan payload dan lineage dengan file.
4. Jalankan loader lagi; pastikan tidak muncul duplikasi yang tidak diinginkan.
5. Jalankan transformasi Silver untuk data itu; periksa hasil dan rejected
   records.
6. Jalankan quality gate dan uji kondisi gagal; pastikan Gold berhenti.
7. Jalankan Gold dan cek grain, revenue, refund, dan jumlah order.
8. Jalankan seluruh DAG dari awal.
9. Ulangi DAG untuk menguji rerun.
10. Jalankan pertanyaan analitik lewat engine/UI.

### Contoh pertanyaan untuk memeriksa hasil

- Berapa net revenue per hari?
- Berapa refund per channel?
- Produk mana yang paling banyak terjual?
- Campaign mana yang memiliki ROAS tertinggi?

Jawaban engine hanya dapat dipercaya jika tabel Gold dan definisi metriknya
benar.

## 13. Langkah 10 — Siapkan bukti dan submission

Simpan bukti yang diminta README:

- Screenshot Airflow yang menunjukkan run pipeline.
- Contoh pertanyaan engine/UI dan hasilnya.
- Kode DAG, schema Bronze/Silver/Ops, dan loader/transformasi pipeline.

Jangan sertakan `.env`, password, API key, dataset penuh, cache, atau folder
lingkungan Python. Sebelum upload, tinjau daftar artefak submission pada
README karena itulah daftar yang menjadi acuan.

## 14. Rekomendasi urutan implementasi untuk pemula

Kerjakan dalam irisan kecil agar kesalahan mudah dicari:

1. Pastikan PostgreSQL lokal dapat dihubungi.
2. Buat schema Bronze dan tabel Bronze, lalu jalankan SQL-nya.
3. Pilih satu file sederhana, misalnya `customers.json`.
4. Buat loader untuk file itu dan pastikan payload serta lineage benar.
5. Tambahkan loader untuk semua file JSON/CSV.
6. Buat satu tabel Silver sederhana dan transformasikan data customer atau
   product.
7. Tambahkan order dan order items, lalu validasi jumlah dan nilai order.
8. Tambahkan payment/refund/return dan aturan event-nya.
9. Bangun `gold.order_360`, cek hasilnya, lalu lanjutkan ke empat Gold lain.
10. Buat quality checks, hubungkan implementasi nyata ke DAG, dan uji end-to-end.

Satu jenis data yang berjalan dengan benar dari raw ke Bronze ke Silver lebih
berguna daripada banyak file kode yang belum pernah diuji.

## 15. Checklist selesai

- [V] Semua file raw yang diwajibkan tersedia dan dapat dibaca.
- [V] PostgreSQL lokal bisa diakses pipeline.
- [V] Schema Bronze, Silver, dan Ops dibuat; Gold contract tetap kompatibel.
- [V] Bronze menyimpan payload dan lineage serta aman untuk rerun. bagaimana cara buktikan
- [ ] Silver bertipe, dinormalisasi, dideduplikasi, dan mencatat penolakan.
- [ ] Kelima tabel Gold terisi dengan grain dan metrik yang sesuai kontrak.
- [ ] Quality checks benar-benar memeriksa data dan menghentikan alur bila gagal.
- [ ] DAG menjalankan pipeline nyata dari validasi sampai validasi akhir.
- [ ] Pipeline rerun tanpa menggandakan hasil yang sama.
- [ ] Run Airflow dan pertanyaan engine/UI memiliki bukti.
- [ ] Tidak ada credential atau dataset penuh dalam submission.

## 16. Dokumen acuan

- `README.md`: skenario, aturan Bronze/Silver/Gold, urutan DAG, submission,
  dan rubrik.
- `database/schemas/gold.sql`: kontrak tabel Gold yang tidak boleh diubah.
- `database/README.md`: penggunaan database lokal dan cara inisialisasi schema.
- `docs/demo-queries.sql`: contoh query analitik yang dapat membantu
  memeriksa hasil Gold.




database diinisiasi dengan
`uv run python -m pipelines.ingestion.initialize_database`

  RUN LOADER BRONZE 
  `uv run python -m pipelines.bronze.build_bronze --input data/raw`

  belum dilakukan testing test_contract.py.