# Week 06 - Day 05: AI Agent Part 2

[![Phase](https://img.shields.io/badge/phase-2_applied_ai-blue.svg)](#)
[![Week](https://img.shields.io/badge/week-6_advanced_rag_and_ai_systems-orange.svg)](#)
[![Day](https://img.shields.io/badge/day-5_ai_agent_part_2-green.svg)](#)
[![Python](https://img.shields.io/badge/python-3.11+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)

## Multi-Tools dan Multi-Agent dengan CrewAI

Pada hands-on ini, kamu akan melanjutkan konsep agent dari Sesi 9 dengan membangun dua workflow menggunakan **CrewAI**:

1. **Multi-Tools — Agent Customer Service:** satu agent menggunakan empat tool secara berurutan untuk memproses perubahan nomor telepon pelanggan.
2. **Multi-Agent — Researcher, Writer, dan Reviewer:** beberapa agent dengan peran tetap bekerja secara sequential untuk menghasilkan newsletter berbasis riset web.

Notebook utama: [`P2W2D5 - AI Agent Part 2.ipynb`](P2W2D5 - AI Agent Part 2.ipynb)

Contoh konfigurasi kredensial: [`.env.example`](.env.example)

> **Tujuan utama:** Setelah menyelesaikan lab, kamu dapat memutuskan kapan sebuah workflow membutuhkan satu agent dengan banyak tool dan kapan pekerjaan lebih tepat dibagi kepada beberapa agent dengan tanggung jawab yang berbeda.

## Hasil Belajar

Setelah menyelesaikan hands-on ini, kamu diharapkan mampu:

- menjelaskan perbedaan multi-tools dan multi-agent;
- mendefinisikan `Agent`, `Task`, `Crew`, tool, dan proses sequential di CrewAI;
- membatasi agent ke satu ruang lingkup tugas yang jelas;
- merancang urutan tool berdasarkan state dan hasil langkah sebelumnya;
- membungkus fungsi Python menjadi CrewAI tool menggunakan `@tool`;
- melakukan verifikasi dan pembaruan database dengan parameterized SQL;
- menerapkan audit trail pada workflow yang mengubah data;
- meneruskan output satu task ke task lain menggunakan `context=[...]`;
- menguji happy path, failure path, dan permintaan di luar scope; serta
- mengidentifikasi perbedaan antara implementasi edukasional dan sistem production.

## Gambaran Sistem

### Part 1 — Satu agent, empat tool

```mermaid
flowchart TD
    A["Permintaan pelanggan"] --> B["Agent CS mengklasifikasi permintaan"]
    B -- "Bukan update telepon" --> C["Teruskan ke CS berikutnya"]
    B -- "Update telepon" --> D["Format Permintaan"]
    D --> E["Verifikasi Akun (DB)"]
    E -- "Gagal" --> F["Berhenti (NOT_FOUND)"]
    E -- "VERIFIED" --> G["Kirim OTP"]
    G --> H["Konfirmasi OTP"]
    H -- "Gagal" --> I["Berhenti (FAILED)"]
    H -- "Cocok" --> J["Update DB + Audit (SUCCESS)"]
```

### Part 2 — Beberapa agent, satu pipeline

```mermaid
flowchart TD
    A["Topik"] --> B["Researcher (Tool: Tavily)"]
    B -- "Hasil riset" --> C["Writer"]
    C -- "Draft newsletter" --> D["Reviewer (Bonus)"]
    D --> E["Versi final"]
```

## Yang Akan Kamu Kerjakan

| Bagian | Aktivitas | Kebutuhan tambahan |
|---|---|---|
| Setup CrewAI | Memilih provider dan membuat satu objek LLM | API key provider LLM |
| Database setup | Membuat tabel profil pelanggan dan audit log, lalu memasukkan data dummy bila tabel kosong | `DATABASE_URI` dengan izin membuat dan mengubah tabel latihan |
| Tool formatting | Menormalkan email dan nomor telepon | Tidak ada |
| Tool verification | Memeriksa identitas pelanggan dan membuat audit record | PostgreSQL |
| Tool OTP | Membuat dan menyimpan OTP simulasi | PostgreSQL |
| Tool update | Memvalidasi OTP dan mengubah nomor telepon | PostgreSQL |
| Agent CS | Menjalankan happy path dan mengalihkan permintaan refund | Provider LLM dan PostgreSQL |
| Researcher → Writer | Mencari informasi dan menyusun newsletter | Provider LLM, `TAVILY_API_KEY`, dan internet |
| Reviewer | Meninjau draft melalui task ketiga | Provider LLM dan Tavily |

> **Catatan:** Kedua part menggunakan konfigurasi LLM yang sama, tetapi dependensi tool-nya berbeda. Part 1 membutuhkan PostgreSQL; Part 2 membutuhkan Tavily. Jika salah satu layanan belum tersedia, selesaikan part yang dapat dijalankan dan dokumentasikan dependensi yang terlewat.

## Prasyarat

### Pengetahuan

Sebelum mulai, pastikan kamu sudah memahami:

- fungsi, decorator, dictionary, list, dan async/await dasar di Python;
- environment variable dan file `.env`;
- SQL dasar: `SELECT`, `INSERT`, dan `UPDATE`;
- parameterized query dan transaksi database;
- konsep tool calling serta reasoning loop dari Sesi 9; dan
- dasar penggunaan Jupyter Notebook.

### Software

- Python 3.11 atau lebih baru;
- JupyterLab, Jupyter Notebook, atau VS Code dengan ekstensi Jupyter;
- koneksi internet untuk instalasi package dan pemanggilan API; dan
- PostgreSQL latihan yang dapat diakses dari environment notebook.

### Kredensial

Kamu membutuhkan:

- satu API key provider LLM: OpenAI-compatible, Anthropic, atau Gemini;
- Tavily API key untuk workflow Researcher; dan
- PostgreSQL connection string untuk workflow Agent CS.

> **Security Note:** Gunakan database khusus latihan. Notebook membuat tabel, menyimpan OTP simulasi, menambahkan audit log, dan menjalankan `UPDATE`, sehingga akun database read-only tidak cukup untuk Part 1.

## Persiapan Environment

Jalankan perintah dari folder `modules/10-ai-agent-part-2` agar notebook dapat menemukan `.env` di folder yang sama.

### Windows PowerShell

```powershell
cd modules\10-ai-agent-part-2
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install jupyterlab
python -m jupyter lab
```

### macOS atau Linux

```bash
cd modules/10-ai-agent-part-2
python3 -m venv .venv
source .venv/bin/activate
python -m pip install jupyterlab
python -m jupyter lab
```

Buka `sesi10_AI_Agent_Part_2_Hands_on.ipynb`, pilih kernel dari `.venv`, lalu jalankan cell instalasi package di awal notebook.

Package utama yang dipasang notebook meliputi:

- `crewai` dan `crewai-tools`;
- `google-genai`, `openai`, dan `anthropic`;
- `tavily-python`;
- `python-dotenv`;
- `psycopg[binary]`; dan
- `nest_asyncio`.

> **Checkpoint:** Cell instalasi selesai tanpa error, kernel menggunakan `.venv`, dan import `Agent`, `Task`, `Crew`, `Process`, serta `LLM` berhasil.

## Menyiapkan File `.env`

Salin `.env.example` menjadi `.env`.

### Windows PowerShell

```powershell
Copy-Item .env.example .env
```

### macOS atau Linux

```bash
cp .env.example .env
```

Isi variabel yang akan kamu gunakan:

```dotenv
# Isi salah satu sesuai provider pilihan
OPENAI_API_KEY=isi_key_kamu
ANTHROPIC_API_KEY=isi_key_kamu
GEMINI_API_KEY=isi_key_kamu

# Part 2 — Researcher
TAVILY_API_KEY=isi_key_kamu

# Part 1 — Agent Customer Service
DATABASE_URI=postgresql://user:password@host:5432/nama_db
```

Kemudian ubah `PROVIDER` di notebook:

```python
PROVIDER = "openai"  # "openai" | "claude" | "gemini"
```

Setelah menjalankan cell konfigurasi, periksa output berikut:

```text
Provider aktif: ... | model: ...
TAVILY_API_KEY terisi: True
DATABASE_URI terisi : True
LLM siap untuk CrewAI: ...
```

Nilai `False` boleh muncul jika kamu akan melewati part yang memakai kredensial tersebut.

> **Security Note:** Jangan menulis secret langsung di notebook, menampilkan nilai lengkapnya di output, atau melakukan commit file `.env`. Periksa kembali output notebook sebelum dikumpulkan.

## Panduan Pengerjaan

Jalankan notebook dari atas ke bawah. Karena Part 1 mengubah state database, baca tujuan dan expected result setiap cell sebelum menjalankannya kembali.

## Part 1 — Multi-Tools: Agent Customer Service

### 1. Siapkan database latihan

Cell setup membuat dua tabel jika belum tersedia:

| Tabel | Tanggung jawab |
|---|---|
| `customer_profile_datamart` | Menyimpan profil dan nomor telepon pelanggan |
| `phone_change_request_log` | Menyimpan state permintaan, OTP simulasi, status, timestamp, dan catatan audit |

Jika tabel profil masih kosong, notebook menambahkan tiga pelanggan dummy. Setup bersifat idempoten terhadap pembuatan tabel dan seed: menjalankan ulang cell tidak membuat tabel duplikat dan seed dilewati ketika tabel sudah berisi data.

> **Common Mistake:** Idempoten bukan berarti tidak ada perubahan sama sekali. Menjalankan ulang workflow agent tetap dapat menambahkan baris audit baru ke `phone_change_request_log`.

> **Security Note:** Kolom password pada data dummy hanya untuk demo. Sistem production wajib menyimpan password menggunakan password hashing yang sesuai, bukan teks biasa atau hash contoh statis.

> **Checkpoint:** Query akhir cell setup menampilkan minimal satu pelanggan dengan `customer_id`, `email`, `last_name`, dan `phone_number`.

### 2. Pelajari empat tool

#### Tool 1 — Format Permintaan

`format_permintaan(...)`:

- menghapus whitespace pada email dan nama belakang;
- mengubah email menjadi lowercase;
- membersihkan karakter selain digit dan `+` dari nomor telepon; dan
- mengembalikan JSON dengan struktur konsisten.

Output contoh:

```json
{
  "email": "budi.santoso@example.com",
  "last_name": "Santoso",
  "current_phone_number": "081200000001",
  "new_phone_number": "089912345678"
}
```

#### Tool 2 — Verifikasi Akun

`verifikasi_akun(...)` mencocokkan kombinasi:

- `email`;
- `last_name`; dan
- `current_phone_number`.

Jika cocok, tool membuat audit record berstatus `VERIFIED`. Jika tidak cocok, tool mengembalikan `NOT_FOUND` dan workflow harus berhenti.

#### Tool 3 dalam alur — Kirim OTP

Fungsi `kirim_otp(...)` membuat OTP enam digit, mencetak simulasi pengiriman, lalu mengubah audit record menjadi `OTP_SENT`.

> **Security Note:** Notebook sengaja mengembalikan `otp_demo` agar workflow dapat selesai otomatis dalam satu kali kickoff. Sistem nyata tidak boleh mengembalikan OTP kepada agent atau menaruh OTP plaintext dalam log. OTP harus dikirim melalui channel terpisah, memiliki masa berlaku, jumlah percobaan terbatas, dan disimpan secara aman.

#### Tool 4 dalam alur — Konfirmasi OTP dan Update Nomor

`konfirmasi_dan_update(...)`:

- mengambil permintaan `OTP_SENT` terbaru;
- membandingkan `otp_input` dengan OTP pada audit record;
- menandai log `FAILED` jika OTP tidak cocok; atau
- memperbarui `phone_number` dan menandai log `SUCCESS` jika OTP cocok.

> **Checkpoint:** Kamu dapat menjelaskan mengapa nomor tool di notebook tidak sama dengan urutan eksekusinya, serta mengurutkan workflow sebagai format → verifikasi → kirim OTP → konfirmasi dan update.

### 3. Periksa guardrail database

Sebelum menjalankan agent, identifikasi guardrail berikut di kode:

- SQL ditentukan oleh aplikasi, bukan dibuat bebas oleh LLM;
- seluruh input query menggunakan parameter `%s`;
- verifikasi memakai beberapa atribut akun;
- pembaruan dibatasi ke nomor telepon dan timestamp;
- setiap langkah penting memiliki status audit; dan
- workflow berhenti ketika verifikasi atau OTP gagal.

Catat juga batasannya: belum ada authorization session, OTP expiry, rate limit, retry limit, row locking eksplisit, atau human approval.

### 4. Bungkus fungsi menjadi CrewAI tool

Amati decorator `@tool` pada empat wrapper. Wrapper memberi CrewAI:

- nama tool;
- deskripsi kapan tool digunakan;
- nama dan tipe parameter; serta
- fungsi Python yang benar-benar dieksekusi.

Pastikan kamu dapat membedakan fungsi domain, seperti `verifikasi_akun(...)`, dengan adapter CrewAI, seperti `verifikasi_akun_tool(...)`.

### 5. Definisikan Agent, Task, dan Crew

`cs_agent` memiliki satu scope: perubahan nomor telepon. Permintaan refund, perubahan email, dan keluhan tidak boleh menjalankan tool database.

`cs_task` memasukkan pesan serta identitas pelanggan melalui placeholder `inputs`. `cs_crew` kemudian menjalankan task dengan proses sequential.

> **Checkpoint:** Empat tool terdaftar pada `cs_agent`, tetapi agent tetap memiliki aturan untuk tidak memanggil tool apa pun pada permintaan di luar scope.

### 6. Jalankan Demo A — happy path

Notebook mengambil satu pelanggan yang benar-benar ada, menentukan nomor baru, lalu menjalankan:

```python
hasil_a = await cs_crew.kickoff_async(inputs=inputs_a)
```

Saat membaca verbose trace, cari urutan berikut:

1. permintaan dikenali sebagai update nomor telepon;
2. input diformat;
3. akun terverifikasi;
4. OTP simulasi dibuat;
5. OTP dikonfirmasi;
6. nomor telepon diperbarui; dan
7. agent memberi ringkasan akhir.

Cell verifikasi berikutnya membaca ulang tabel dan audit log. Expected result:

- nomor sebelum dan sesudah berbeda;
- log terakhir berstatus `SUCCESS`; dan
- nomor pelanggan dikembalikan ke nilai awal pada akhir demo agar dapat diulang.

> **Checkpoint:** Kamu memiliki bukti dari query database, bukan hanya pernyataan agent, bahwa perubahan benar-benar terjadi.

### 7. Jalankan Demo B — permintaan di luar scope

Demo kedua meminta refund. Expected behavior:

- agent tidak memanggil tool formatting, database, atau OTP;
- agent menyatakan permintaan akan diteruskan ke CS berikutnya; dan
- tidak ada audit record perubahan nomor baru untuk permintaan tersebut.

> **Common Mistake:** Notebook mencetak jumlah total log untuk satu email dan mengharapkan `0` pada database yang masih bersih. Jika kamu sudah pernah memakai email tersebut pada eksperimen lain, bandingkan jumlah log sebelum dan sesudah demo untuk membuktikan bahwa tidak ada baris baru.

## Part 2 — Multi-Agent: Researcher → Writer → Reviewer

### 8. Buat tool pencarian

`search_topic(...)` memakai Tavily untuk mengambil maksimal tiga hasil. Wrapper `search_topic_tool(...)` menjadikannya tool CrewAI.

Hanya Researcher yang menerima tool ini. Writer dan Reviewer bekerja dari context hasil task sebelumnya.

> **Checkpoint:** Kamu dapat menjelaskan prinsip least privilege pada desain ini: agent hanya mendapat tool yang dibutuhkan oleh perannya.

### 9. Definisikan Researcher dan Writer

Setiap agent memiliki:

- `role`: identitas tanggung jawab;
- `goal`: hasil yang harus dicapai;
- `backstory`: konteks perilaku;
- `tools`: kemampuan eksternal jika diperlukan; dan
- `llm`: model yang digunakan.

Researcher mencari informasi terkini. Writer mengubah hasil riset menjadi newsletter maksimal 150 kata.

### 10. Hubungkan task dengan context

`research_task` menghasilkan poin-poin riset. `writing_task` menggunakan:

```python
context=[research_task]
```

Artinya, output task riset diteruskan sebagai bahan task penulisan. `Process.sequential` memastikan task dijalankan sesuai urutan.

Jalankan crew dengan topik bawaan, lalu periksa:

- query pencarian yang dibuat Researcher;
- ringkasan sumber yang diteruskan;
- apakah Writer mengikuti batas 150 kata; dan
- apakah draft tetap setia pada hasil riset.

Karena informasi web dan respons model berubah, hasilmu tidak harus identik dengan output yang tersimpan di notebook.

### 11. Tambahkan Reviewer

Bonus workflow menambahkan:

- agent `reviewer`;
- `review_task` dengan `context=[writing_task]`; dan
- crew baru berisi tiga agent dan tiga task.

Bandingkan draft Writer dengan versi final Reviewer. Catat perubahan pada kejelasan, akurasi, struktur, dan tone.

> **Checkpoint:** Kamu dapat menggambar urutan `research_task → writing_task → review_task` dan menjelaskan data apa yang berpindah pada setiap handoff.

## Eksperimen Mandiri

Lakukan minimal empat eksperimen berikut.

### Wajib

1. Jalankan fungsi `format_permintaan(...)` dengan email berhuruf kapital dan nomor yang memakai spasi atau tanda hubung. Verifikasi hasil normalisasinya.
2. Uji verifikasi akun dengan satu atribut yang salah. Pastikan status `NOT_FOUND` dan nomor telepon tidak berubah.
3. Uji permintaan di luar scope selain refund, misalnya perubahan email. Buktikan bahwa tidak ada audit record baru.
4. Ganti topik Researcher–Writer, lalu nilai apakah output Writer benar-benar memakai hasil riset.

### Pilihan

- Uji OTP yang salah dan periksa perubahan status menjadi `FAILED`.
- Tambahkan validasi format nomor telepon dan larangan nomor baru sama dengan nomor lama.
- Tambahkan expiry OTP dan batas percobaan konfirmasi.
- Tambahkan task Fact Checker di antara Writer dan Reviewer.
- Minta Writer menghasilkan output terstruktur dengan bagian judul, ringkasan, dan sumber.
- Catat jumlah tool call, latency per task, token usage, dan failure reason.
- Bandingkan hasil crew dua agent dengan crew tiga agent dari sisi kualitas, latency, dan biaya.

## Troubleshooting

| Masalah | Kemungkinan penyebab | Solusi |
|---|---|---|
| `ModuleNotFoundError` | Kernel bukan dari `.venv` atau cell instalasi belum selesai | Pilih kernel yang benar, jalankan ulang instalasi, lalu restart kernel |
| `.env` tidak terbaca | Jupyter dijalankan dari folder lain atau file masih bernama `.env.example` | Jalankan Jupyter dari folder module 10 dan pastikan file bernama `.env` |
| `401`, `403`, atau authentication error | API key salah, provider tidak sesuai, atau endpoint menolak key | Periksa `PROVIDER`, variabel key, model, dan endpoint yang dikonfigurasi tanpa mencetak secret |
| `model not found` | Model tidak tersedia untuk akun atau nama model telah berubah | Gunakan model yang tersedia untuk akunmu dan didukung CrewAI; konfirmasi dengan instruktur |
| `429` atau quota exceeded | Terlalu banyak request dalam waktu singkat atau kuota provider habis | Tunggu sesuai petunjuk provider, kurangi pengulangan kickoff, atau gunakan provider lain yang tersedia |
| `RuntimeError` terkait event loop | `nest_asyncio.apply()` belum dijalankan | Jalankan cell setup LLM sebelum memanggil `kickoff_async` |
| `DATABASE_URI` kosong | `.env` belum lengkap atau kernel masih menyimpan environment lama | Perbaiki `.env`, restart kernel, lalu jalankan ulang dari cell konfigurasi |
| PostgreSQL connection failed | URI, host, port, SSL, firewall, atau kredensial tidak benar | Uji koneksi dengan client PostgreSQL dan gunakan database latihan yang dapat dijangkau |
| `permission denied` saat setup | User database tidak punya izin DDL/DML | Gunakan akun latihan yang boleh membuat tabel serta menjalankan `SELECT`, `INSERT`, dan `UPDATE` |
| Demo happy path berhenti di verifikasi | Data input tidak cocok dengan profil terkini | Jalankan ulang cell yang mengambil target langsung dari database dan periksa state dari run sebelumnya |
| Tidak ada permintaan `VERIFIED` atau `OTP_SENT` | Tool dipanggil tidak berurutan atau state audit sebelumnya berubah | Baca verbose trace dan jalankan workflow dari langkah format serta verifikasi |
| Jumlah log Demo B bukan `0` | Email sudah memiliki log dari run atau eksperimen sebelumnya | Bandingkan count sebelum dan sesudah Demo B, bukan hanya nilai absolut |
| Tavily gagal | Key kosong, kuota habis, atau jaringan diblokir | Periksa `TAVILY_API_KEY` dan koneksi; dokumentasikan jika Part 2 harus dilewati |
| Writer tidak memakai hasil riset | `context=[research_task]` hilang atau task dijalankan di crew berbeda | Periksa context dan urutan task pada `Crew` |
| Output berubah pada run ulang | Respons LLM dan hasil web bersifat non-deterministik | Evaluasi struktur dan bukti, bukan kesamaan kata per kata |

## Batasan Implementasi

Notebook ini dirancang agar arsitektur multi-tools dan multi-agent mudah diamati. Sistem production memerlukan kontrol tambahan, antara lain:

- autentikasi pengguna sebelum workflow dimulai;
- otorisasi eksplisit untuk perubahan profil;
- OTP delivery melalui channel terpisah, expiry, retry limit, dan penyimpanan aman;
- transaksi dan locking yang menangani permintaan bersamaan;
- idempotency key untuk mencegah update ganda;
- validasi email serta format nomor telepon yang lebih ketat;
- least-privilege database role dan pemisahan environment;
- redaksi PII dan secret pada prompt, trace, log, serta observability platform;
- timeout, retry terbatas, circuit breaker, rate limit, dan pembatasan biaya;
- evaluasi routing untuk permintaan di luar scope;
- pengujian kualitas handoff dan factual consistency antar-agent;
- pertahanan terhadap prompt injection dari pengguna dan hasil pencarian web; serta
- human approval atau escalation untuk operasi berisiko tinggi.

> **Production Note:** Lebih banyak agent tidak otomatis membuat sistem lebih baik. Setiap agent menambah call, latency, biaya, state, dan failure mode. Tambahkan agent hanya jika pemisahan peran memberi manfaat yang dapat diuji.

## Ringkasan

Multi-tools dan multi-agent menyelesaikan masalah yang berbeda. Multi-tools memberi satu agent beberapa kemampuan untuk menyelesaikan satu workflow yang terikat. Multi-agent membagi pekerjaan ke beberapa peran ketika spesialisasi dan handoff memang membantu kualitas hasil.

Fokus hands-on ini bukan sekadar membuat CrewAI berjalan. Kamu perlu memahami **scope setiap agent, urutan dan izin tool, state yang disimpan, bukti perubahan, aturan handoff, stopping condition, serta failure mode dari setiap komponen**.
