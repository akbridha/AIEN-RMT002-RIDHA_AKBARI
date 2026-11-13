# Week 06 - Day 04: AI Agent Part 1

[![Phase](https://img.shields.io/badge/phase-2_applied_ai-blue.svg)](#)
[![Week](https://img.shields.io/badge/week-6_advanced_rag_and_ai_systems-orange.svg)](#)
[![Day](https://img.shields.io/badge/day-4_ai_agent_part_1-green.svg)](#)
[![Python](https://img.shields.io/badge/python-3.11+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)

## Empat Sumber Tool, Satu Reasoning Loop

Pada hands-on ini, kamu akan membangun dan mengamati sebuah **AI agent sederhana yang dapat memilih serta menggunakan tool**. Kamu hanya menulis satu reasoning loop, lalu menghubungkannya ke empat sumber tool yang berbeda:

1. fungsi Python lokal;
2. API pencarian web;
3. database PostgreSQL melalui tool buatan sendiri; dan
4. server MCP yang terhubung ke database yang sama.

Notebook utama: [`P3W2D4 - AI Agent Part 1.ipynb`](P3W2D4 - AI Agent Part 1.ipynb)

> **Tujuan utama:** Setelah menyelesaikan lab, kamu dapat menjelaskan bahwa LLM memilih tindakan dan argumen, sedangkan kode aplikasi tetap bertanggung jawab mengeksekusi tool, mengembalikan hasil, menerapkan batasan, dan menghentikan loop.

## Hasil Belajar

Setelah menyelesaikan hands-on ini, kamu diharapkan mampu:

- membedakan chatbot biasa dengan AI agent berbasis tool;
- menjelaskan siklus **pikir → bertindak → amati** pada reasoning loop;
- membaca dan menelusuri histori pemanggilan tool;
- mendefinisikan nama, deskripsi, dan parameter tool menggunakan skema netral;
- menghubungkan satu loop agent ke fungsi Python, API, PostgreSQL, dan MCP;
- membandingkan tool database buatan sendiri dengan tool yang ditemukan melalui MCP; dan
- menjelaskan guardrail dasar untuk eksekusi SQL oleh agent.

## Gambaran Sistem

```mermaid
flowchart TD
    A["Pertanyaan pengguna"] --> B["LLM melihat histori + daftar tool"]
    B -- "Informasi cukup" --> C["Jawaban final"]
    B -- "Perlu tool" --> D["Permintaan tool + argumen"]
    D --> E["Kode mengeksekusi tool"]
    E --> F["Hasil menjadi observasi"]
    F --> B
```

LLM tidak menjalankan fungsi, API, SQL, atau MCP secara langsung. LLM hanya meminta pemanggilan tool. Fungsi `run_agent(...)` dan registry tool di dalam notebook menentukan kode apa yang benar-benar dijalankan.

## Yang Akan Kamu Kerjakan

| Bagian | Aktivitas | Kebutuhan tambahan |
|---|---|---|
| Baseline | Menguji chatbot tanpa tool | API key provider LLM |
| Reasoning loop | Membaca implementasi agent untuk OpenAI-compatible API dan Claude | API key provider LLM |
| Tool 1 — Python | Menghitung margin dengan fungsi deterministik | Tidak ada |
| Tool 2 — API | Mengambil informasi terkini melalui Tavily | `TAVILY_API_KEY` dan internet |
| Tool 3 — PostgreSQL | Membandingkan query parameterized dengan text-to-SQL | `DATABASE_URI` dan tabel `public.sales_datamart` |
| Tool 4 — MCP | Menemukan dan memanggil tool dari `postgres-mcp` | Database yang sama dan executable `postgres-mcp` |

> **Catatan:** Jika kamu belum memiliki akses Tavily atau PostgreSQL, kamu tetap dapat menyelesaikan bagian baseline, reasoning loop, dan tool Python. Tandai bagian yang dilewati dan jelaskan dependensi yang belum tersedia.

## Estimasi Waktu

| Aktivitas | Durasi |
|---|---:|
| Persiapan environment dan kredensial | 20–30 menit |
| Baseline dan reasoning loop | 25 menit |
| Tool fungsi Python dan API | 30–40 menit |
| Tool PostgreSQL | 35–45 menit |
| Tool MCP dan perbandingan | 30–40 menit |
| Eksperimen, refleksi, dan dokumentasi | 20–30 menit |
| **Total** | **sekitar 2,5–3 jam** |

## Prasyarat

### Pengetahuan

Sebelum mulai, pastikan kamu sudah memahami:

- dasar Python: fungsi, dictionary, list, loop, dan exception;
- dasar penggunaan Jupyter Notebook;
- konsep dasar API dan environment variable; serta
- SQL dasar, terutama `SELECT`, `WHERE`, `GROUP BY`, dan `ORDER BY`.

### Software

- Python 3.11 atau lebih baru;
- JupyterLab, Jupyter Notebook, atau VS Code dengan ekstensi Jupyter;
- koneksi internet untuk instalasi package dan pemanggilan API; dan
- PostgreSQL yang dapat diakses untuk bagian database dan MCP.

### Kredensial dan data

Kamu membutuhkan:

- satu API key provider LLM: OpenAI, Anthropic, atau Gemini;
- Tavily API key untuk bagian pencarian web; dan
- PostgreSQL connection string yang memiliki akses baca ke tabel `public.sales_datamart`.

Tabel `sales_datamart` setidaknya perlu menyediakan kolom yang digunakan notebook, termasuk `region`, `category`, `sub_category`, `segment`, `sales`, `quantity`, `discount`, `profit`, `customer_name`, dan `order_date`.

> **Security Note:** Gunakan database latihan dengan akun read-only. Jangan menghubungkan notebook ini ke database produksi atau database yang berisi data sensitif.

## Persiapan Environment

Jalankan perintah dari folder `modules/09-ai-agent-part-1` agar notebook dapat menemukan file `.env` di folder yang sama.

### Windows PowerShell

```powershell
cd modules\09-ai-agent-part-1
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install jupyterlab
python -m jupyter lab
```

### macOS atau Linux

```bash
cd modules/09-ai-agent-part-1
python3 -m venv .venv
source .venv/bin/activate
python -m pip install jupyterlab
python -m jupyter lab
```

Buka `sesi9_AI_Agent_Part_1_Hands_on.ipynb`, pilih kernel dari environment `.venv`, lalu jalankan cell instalasi package di awal notebook.

> **Checkpoint:** Kernel yang aktif harus berasal dari `.venv`, dan cell `pip install` harus selesai tanpa error sebelum kamu melanjutkan.

## Menyiapkan File `.env`

Buat file bernama `.env` di folder yang sama dengan notebook. Isi hanya variabel yang akan kamu gunakan:

```dotenv
# Pilih satu provider LLM
OPENAI_API_KEY=isi_key_kamu
ANTHROPIC_API_KEY=isi_key_kamu
GEMINI_API_KEY=isi_key_kamu

# Dibutuhkan untuk bagian pencarian web
TAVILY_API_KEY=isi_key_kamu

# Dibutuhkan untuk bagian PostgreSQL dan MCP
DATABASE_URI=postgresql://user:password@host:5432/dbname
```

Kemudian ubah variabel `PROVIDER` di notebook:

```python
PROVIDER = "gemini"  # "openai" | "claude" | "gemini"
```

Kamu hanya memerlukan API key yang sesuai dengan provider pilihanmu. Setelah menjalankan cell konfigurasi, periksa output berikut:

```text
Provider aktif: ... | model: ...
TAVILY_API_KEY terisi: True
DATABASE_URI terisi: True
```

Nilai `False` boleh muncul jika kamu memang akan melewati bagian yang memakai kredensial tersebut.

> **Security Note:** Jangan menulis API key langsung di notebook, menampilkan nilainya di output, atau melakukan commit file `.env` ke Git.

## Panduan Pengerjaan

Jalankan notebook dari atas ke bawah. Baca penjelasan sebelum menjalankan setiap cell dan jangan hanya berfokus pada jawaban final. Trace yang dicetak oleh agent adalah bagian utama dari latihan.

### 1. Uji baseline chatbot

Jalankan `ask_chatbot(question)` tanpa memberikan tool.

Sebelum melihat output, prediksi:

- apakah model dapat memberi jawaban yang meyakinkan tetapi tidak terverifikasi;
- apakah model memiliki akses ke informasi terbaru; dan
- bukti apa yang tersedia untuk mengaudit prosesnya.

### 2. Pelajari reasoning loop

Telusuri fungsi berikut:

- `to_openai_schema(...)`;
- `to_claude_schema(...)`;
- `execute_tool(...)`;
- `run_agent_openai(...)`;
- `run_agent_claude(...)`; dan
- `run_agent(...)`.

Untuk setiap putaran, identifikasi:

1. pertanyaan atau goal pengguna;
2. daftar tool yang tersedia;
3. tool dan argumen yang dipilih LLM;
4. kode yang mengeksekusi tool;
5. observasi yang dikirim kembali ke LLM; dan
6. kondisi berhenti.

> **Checkpoint:** Kamu dapat menunjuk baris tempat LLM meminta tool dan baris berbeda tempat kode benar-benar mengeksekusinya.

### 3. Jalankan tool fungsi Python

Agent menggunakan `hitung_margin(sales, cost)` untuk menjawab pertanyaan berikut:

```text
Kalau harga jual 2500 dan biaya 1800, berapa margin-nya?
```

Hasil fungsi yang diharapkan:

```text
Margin = 28.00% (profit 700.00 dari sales 2500.00)
```

Bandingkan jawaban chatbot dengan agent. Jelaskan mengapa fungsi deterministik lebih mudah diuji dan diaudit untuk perhitungan bisnis.

### 4. Jalankan tool API Tavily

Agent menggunakan `search_topic(query)` untuk mencari informasi terkini. Perhatikan bahwa:

- LLM memilih kapan pencarian diperlukan;
- LLM menyusun nilai `query`;
- kode Python memanggil Tavily; dan
- hasil pencarian dikirim kembali sebagai observasi.

Karena hasil web berubah, jawabanmu tidak harus sama persis dengan contoh output yang tersimpan di notebook.

> **Checkpoint:** Trace menampilkan pemanggilan `search_topic` dan agent menghasilkan jawaban berdasarkan hasil pencarian, bukan hanya pengetahuan bawaan model.

### 5. Bandingkan dua tool PostgreSQL

#### C1 — Query parameterized

`ringkasan_penjualan(region)` menggunakan SQL yang sudah ditentukan. LLM hanya mengisi nilai `region`.

Amati keuntungan desain ini:

- ruang tindakan LLM sempit;
- parameter dipisahkan dari query; dan
- perilaku lebih mudah diprediksi dan diuji.

#### C2 — Text-to-SQL

`run_sql(query)` memberi LLM fleksibilitas untuk menulis `SELECT`, tetapi menambahkan tiga guardrail:

1. hanya query yang diawali `SELECT` yang diterima;
2. koneksi database dibuka dalam mode read-only; dan
3. hasil dibatasi maksimal 20 baris.

> **Common Mistake:** `fetchmany(20)` membatasi jumlah baris yang dikembalikan ke agent, tetapi tidak selalu mengurangi beban query di database. Di production, tetap gunakan `LIMIT`, statement timeout, allowlist tabel/kolom, dan pembatasan resource pada database.

> **Checkpoint:** Pertanyaan tentang sub-category dengan total profit tertinggi menghasilkan trace SQL, hasil query, dan jawaban final. Nilai akhirnya bergantung pada database latihanmu.

### 6. Gunakan MCP pada database yang sama

Notebook menjalankan `postgres-mcp` sebagai subprocess dalam mode `restricted`, lalu:

1. membuka sesi MCP melalui `stdio`;
2. meminta daftar tool dari server;
3. mengambil skema `execute_sql` langsung dari server;
4. memasukkan skema tersebut ke reasoning loop yang sama; dan
5. memanggil tool discovery seperti `list_objects` dan `get_object_details`.

Bandingkan hasil pertanyaan C2 dengan D-utama. Keduanya membaca tabel yang sama; yang berbeda hanya sumber tool dan cara skemanya diperoleh.

> **Checkpoint:** `mcp_list_tools()` menampilkan tool dari server, `execute_sql` dapat menjawab pertanyaan yang sama dengan C2, dan discovery menemukan `public.sales_datamart`.

## Eksperimen Mandiri

Setelah seluruh bagian utama berjalan, lakukan minimal tiga modifikasi berikut.

### Wajib

1. Ganti pertanyaan margin dengan nilai `sales` dan `cost` milikmu sendiri. Prediksi hasilnya sebelum menjalankan cell.
2. Buat satu pertanyaan database baru yang membutuhkan `GROUP BY`, filter, atau pengurutan.
3. Uji guardrail `run_sql(...)` secara langsung menggunakan query non-`SELECT`, misalnya query perubahan data fiktif. Pastikan tool menolak query tersebut. Jangan jalankan pengujian ini melalui database produksi.

### Pilihan

- Tambahkan validasi agar `cost` tidak boleh negatif.
- Batasi nilai `region` ke daftar region yang dikenal.
- Tambahkan pencatatan durasi setiap tool call.
- Tambahkan field trace untuk `turn`, `tool_name`, `arguments`, `status`, dan `latency_ms`.
- Buat tool Python kedua, lalu biarkan LLM memilih tool yang sesuai.
- Bandingkan jawaban dari dua provider LLM tanpa mengubah implementasi tool.

## Troubleshooting

| Masalah | Kemungkinan penyebab | Solusi |
|---|---|---|
| `ModuleNotFoundError` | Kernel bukan dari `.venv` atau cell instalasi belum dijalankan | Pilih kernel yang benar, jalankan ulang cell instalasi, lalu restart kernel |
| API key dianggap kosong | `.env` tidak berada di working directory notebook | Jalankan Jupyter dari folder module 9 dan periksa nama file benar-benar `.env` |
| `401`, `403`, atau authentication error | Key salah, kedaluwarsa, tidak memiliki akses, atau provider tidak sesuai | Periksa `PROVIDER`, nama environment variable, dan akses akun tanpa mencetak key |
| `model not found` | Nama model tidak tersedia untuk akun atau telah berubah | Gunakan model yang tersedia untuk akunmu dan mendukung tool/function calling; konfirmasi dengan instruktur |
| Tavily gagal | `TAVILY_API_KEY` kosong, kuota habis, atau jaringan diblokir | Periksa key dan koneksi, lalu dokumentasikan jika bagian harus dilewati |
| `DATABASE_URI` kosong | Variabel belum ditambahkan atau `.env` belum dimuat | Tambahkan URI, restart kernel, dan jalankan ulang cell konfigurasi |
| Gagal terhubung ke PostgreSQL | Host/port salah, database tidak dapat dijangkau, SSL/firewall, atau kredensial salah | Uji URI dengan client PostgreSQL dan pastikan akses jaringan diizinkan |
| `relation public.sales_datamart does not exist` | Tabel belum tersedia atau berada di schema lain | Gunakan database latihan yang disediakan dan konfirmasi nama schema/tabel |
| `postgres-mcp` tidak ditemukan | Package terpasang di environment berbeda atau executable tidak ada di `PATH` kernel | Pastikan kernel memakai `.venv`, jalankan ulang instalasi, lalu restart kernel |
| `asyncio.run() cannot be called...` | Event loop notebook bentrok | Pastikan `nest_asyncio.apply()` sudah dijalankan sebelum fungsi MCP |
| Agent berhenti setelah `max_turns` | Tool gagal, hasil tidak cukup jelas, atau model terus memanggil tool | Baca trace tiap putaran, periksa hasil tool, deskripsi schema, dan argumen yang dikirim |
| SQL ditolak meskipun aman | Guardrail sederhana hanya menerima query yang diawali `SELECT` | Gunakan format `SELECT ...` untuk lab; bahas parser SQL yang lebih kuat sebagai peningkatan production |

## Batasan Implementasi

Notebook ini adalah implementasi edukasional agar reasoning loop mudah dilihat. Sistem production membutuhkan kontrol tambahan, antara lain:

- validasi argumen tool menggunakan schema dan kode aplikasi;
- timeout, retry terbatas, circuit breaker, dan idempotency jika relevan;
- autentikasi dan otorisasi per pengguna dan per tool;
- allowlist tool, tabel, kolom, serta operasi;
- pembatasan biaya, token, jumlah putaran, dan concurrency;
- observability untuk prompt, keputusan, tool call, latency, error, dan stopping reason;
- redaksi data sensitif pada log;
- pertahanan terhadap prompt injection dan output tool yang tidak tepercaya; serta
- human approval untuk tindakan berisiko tinggi.

> **Production Note:** Jangan menganggap mode read-only sebagai satu-satunya pengamanan. Query baca tetap dapat mengekspos data sensitif atau menghabiskan resource database. Terapkan prinsip least privilege dan beberapa lapis guardrail.

## Ringkasan

Satu reasoning loop dapat menggunakan banyak sumber tool karena semuanya dipresentasikan kepada LLM sebagai nama, deskripsi, dan skema input. Perbedaan sumber tool tetap penting bagi kode aplikasi: fungsi lokal, API, database, dan MCP memiliki kegagalan, izin, biaya, latency, dan kebutuhan observability yang berbeda.

Fokus hands-on ini bukan sekadar mendapatkan jawaban final, tetapi memahami **siapa yang memilih tindakan, siapa yang menjalankan tindakan, data apa yang berpindah, guardrail apa yang berlaku, dan mengapa loop berhenti**.
