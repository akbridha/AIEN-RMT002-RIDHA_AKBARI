# Week 05 - Day 01: Principles of AI, LLM &amp; Local AI Gateway Setup (OmniRoute)

![Phase](https://img.shields.io/badge/phase-2_applied_ai-orange.svg)
![Week](https://img.shields.io/badge/week-5_ai_foundations-blue.svg)
![Day](https://img.shields.io/badge/day-1_principles_of_ai_llm-green.svg)
![Gateway](https://img.shields.io/badge/ai_gateway-OmniRoute-7B2CBF.svg)
![Runtime](https://img.shields.io/badge/runtime-Node.js_18+-339933.svg?logo=node.js&logoColor=white)

Selamat datang di **Phase 2 Week 5 Day 1** dari **Applied AI Engineer Bootcamp**. Hari ini menandai langkah pertama kita memasuki dunia rekayasa kecerdasan artifisial terapan (*Applied AI Engineering*).

Sebagai AI Engineer yang bekerja pada skala enterprise, kita **tidak disarankan meng-hardcode pemanggilan API vendor (OpenAI, Anthropic, Google Cloud) secara langsung ke dalam setiap aplikasi klien atau skrip kode**. Pola tersebut menimbulkan risiko keamanan (kebocoran API key), kerentanan *single-point-of-failure* saat terkena *rate limit* (`HTTP 429`), pembengkakan biaya yang tidak terkontrol, serta ketiadaan kontrol sentral atas kuota pemakaian tim.

Solusi standar industri modern adalah menggunakan **AI Gateway (Smart Proxy Router)**. Pada praktikum hari ini, kita akan membangun *local AI development environment* mandiri menggunakan **OmniRoute** sebagai gerbang tunggal untuk mengatur akses model AI, menerapkan batas kuota pengeluaran (*hard limit budget*), dan mengonfigurasi jalur pengalihan otomatis (*fallback router*).

---

## Tujuan Pembelajaran

Setelah menyelesaikan sesi praktikum terbimbing ini, kita akan mampu:

1. **Memahami Peran AI Gateway dalam Arsitektur Enterprise:** Menjelaskan mengapa gateway dibutuhkan untuk sentralisasi kredensial, standardisasi endpoint OpenAI-compatible (`/v1`), *fallback routing*, serta observabilitas biaya dan token.
2. **Menginstal &amp; Menjalankan OmniRoute Server:** Memasang server gateway lokal berbasis Node.js/npm atau Docker yang berjalan pada port `20128`.
3. **Mengonfigurasi Provider OpenAI &amp; Batas Kuota:** Memasang **Shared OpenAI API Key** (dengan alokasi batas budget kuota 5 USD satu kali per siswa) ke dalam OmniRoute.
4. **Mengonfigurasi Provider Fallback (OpenCode Zen Free Tier &amp; OpenRouter Free Tier):** Menyiapkan penyedia cadangan tanpa biaya untuk menjamin ketersediaan layanan (*high availability*) saat kuota utama habis atau terjadi *rate limiting*.
5. **Membuat Local API Key dengan Hard Limit Pricing (1.25 USD Weekly) &amp; Budget Alert (80%):** Mengatur *hard limit usage limit* 1.25 USD Weekly pada kunci akses lokal OmniRoute serta memantau ambang peringatan (*warning alert*) di 4.00 USD (80% kuota).
6. **Memverifikasi Konektivitas Gateway secara End-to-End:** Menguji kesiapan server lokal melalui endpoint `/v1/models` dan `/v1/chat/completions` menggunakan perintah `curl` serta skrip Python `verify_gateway.py`.
7. **Mengeksplorasi Fitur Kompresi Token Lanjutan (Opsional &amp; Eksplorasi):** Memahami cara kerja **RTK (Rust Token Killer)** untuk mereduksi token input dan **Caveman** untuk memangkas token output guna penghematan biaya pada pengerjaan project mandiri mendatang (dengan instruksi wajib di-disable setelah praktikum).

---

## Arsitektur Sistem Praktikum

Berikut adalah gambaran arsitektur antara aplikasi pengembang lokal, AI Gateway lokal (OmniRoute), dan penyedia model AI di cloud:

```mermaid
flowchart TD
    subgraph DeveloperEnvironment["Lingkungan Pengembang (Local Machine)"]
        ClientApp["Aplikasi Klien / Skrip Python / curl\n(Header: Bearer sk-omniroute-local-xxxx)"]
        VerifyScript["Skrip Verifikasi\n(verify_gateway.py)"]
    end

    subgraph LocalGateway["Local AI Gateway: OmniRoute (Port 20128)"]
        OmniRoute["OmniRoute Server Core\n(http://localhost:20128)"]
        AuthCost["Local API Key & Cost Governance\n• Usage Limit: 5.00 USD Cap\n• Warning Alert: 4.00 USD (80%)\n• Cost Telemetry & Analytics"]
        RouterEngine["Smart Routing & Failover Policy\n• Primary: OpenAI (5 USD Key)\n• Auto-Failover: Free Tier Providers"]
        OptionalEngine["Fitur Kompresi Opsional (Project Mandiri)\n• RTK (Input Filter) - [DISABLE saat Belajar]\n• Caveman (Output Stripper) - [DISABLE saat Belajar]"]
    end

    subgraph ExternalProviders["Penyedia Model AI (Cloud)"]
        OpenAI["Primary Provider:\nOpenAI API (Shared Key 5 USD Budget)"]
        FreeTier["Fallback Providers:\n• OpenRouter Free Tier\n• OpenCode Zen Free Tier"]
    end

    ClientApp -->|"HTTP /v1/chat/completions"| OmniRoute
    VerifyScript -->|"Healthcheck /v1/models"| OmniRoute

    OmniRoute <--> AuthCost
    OmniRoute <--> RouterEngine
    OmniRoute -.-> OptionalEngine

    RouterEngine -->|"Permintaan Utama (Selama Kuota Bulanan < 5.00 USD)"| OpenAI
    RouterEngine -.->|"Auto-Failover (Bila Kuota >= 5.00 USD / Error 429)"| FreeTier
```

---

## Struktur Direktori Praktikum

```text
phase-2-ai/week_5_day_1_principles_of_ai_llm/
├── readme.md                       # Panduan praktikum lengkap (berkas ini)
└── handsonlab/
    ├── .env.example                # Template konfigurasi environment (Port & API Keys)
    └── verify_gateway.py           # Skrip pengujian kesehatan konektivitas OmniRoute
```

> **Catatan Format Praktikum:**
>
> - Sesi hari ini difokuskan sepenuhnya sebagai **Guided Hands-on Lab &amp; Interactive Demo** untuk membangun dan mengonfigurasi **OmniRoute** sebagai pondasi gateway lokal kita.
> - Tidak ada tugas *challenge* yang dinilai pada modul ini. Fokus utama kita adalah memastikan gateway lokal berjalan stabil, kredensial terlindungi oleh *hard limit budget*, dan jalur *fallback* berfungsi sempurna.

---

## Pengaturan Environment &amp; Prasyarat

Sebelum memulai, pastikan komputer kita telah memenuhi prasyarat berikut:

1. **Node.js &amp; npm:** Versi 18.x atau lebih baru.
   ```bash
     node --version    # Minimal v18.0.0
     npm --version
   ```

     *(Jika belum terpasang, unduh dari [nodejs.org](https://nodejs.org/)).*
2. **Python 3:** Versi 3.8+ untuk menjalankan skrip pengujian `verify_gateway.py`.
   ```bash
     python3 --version
   ```
3. **Shared OpenAI API Key:** Instruktur telah membagikan API key bersama dengan batas saldo budget **5 USD per siswa (diberikan 1 kali untuk kebutuhan praktikum awal)**. Siapkan kunci tersebut.

---

## Alur Kerja Praktikum Hands-On

Praktikum dibagi menjadi **5 tahapan utama yang wajib dikerjakan** serta **1 tahap eksplorasi opsional**:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ TAHAP 1: INSTALASI & MENJALANKAN OMNIROUTE SERVER (WAJIB)                   │
│ Memasang gateway via npm/Docker, menjalankan service pada port 20128        │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ TAHAP 2: KONFIGURASI PROVIDER OPENAI (WAJIB)                                │
│ Memasukkan Shared Key (alokasi 5 USD) & mengatur spending limit di provider │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ TAHAP 3: KONFIGURASI PROVIDER FALLBACK (WAJIB)                              │
│ Menambahkan OpenRouter Free Tier & OpenCode Zen Free Tier sebagai failover  │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ TAHAP 4: KONFIGURASI LOCAL API KEY, HARD LIMIT & BUDGET WARNING (WAJIB)     │
│ Buat Local Key: Usage Limit 5 USD, Pantau Warning Alert 4.00 USD (80%)     │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ TAHAP 5: VERIFIKASI & UJI COBA ENDPOINT GATEWAY (WAJIB)                     │
│ Jalankan verify_gateway.py dan kirim prompt via curl ke localhost:20128     │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ TAHAP 6: EKSPLORASI FITUR KOMPRESI TOKEN (OPSIONAL & INFORMATIF)            │
│ Eksplorasi RTK & Caveman untuk project mandiri [WAJIB DISABLE SETELAH COBA] │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Tahap 1: Instalasi &amp; Menjalankan OmniRoute Server

**OmniRoute** adalah AI Gateway open-source berkinerja tinggi yang menyediakan antarmuka standar OpenAI (`/v1`) untuk ratusan model AI sekaligus secara lokal di komputer kita.

### Opsi A: Instalasi Global via npm (Disarankan)

Buka terminal kita dan jalankan perintah instalasi global:

```bash
npm install -g omniroute
```

Setelah instalasi selesai, jalankan server OmniRoute:

```bash
omniroute
```

Terminal akan menampilkan log inisialisasi:

```text
[OmniRoute] Starting server on port 20128...
[OmniRoute] Dashboard available at: http://localhost:20128
[OmniRoute] OpenAI-compatible endpoint: http://localhost:20128/v1
```

> 💡 **Tip:** Biarkan tab terminal ini tetap terbuka dan berjalan di latar belakang selama sesi praktikum berlangsung.

### Opsi B: Menggunakan Docker (Alternatif)

Jika kita lebih terbiasa menggunakan container Docker:

```bash
docker run -d --name omniroute --restart unless-stopped \
  -p 127.0.0.1:20128:20128 \
  -v omniroute-data:/app/data \
  diegosouzapw/omniroute:latest
```

### Verifikasi Akses Dashboard

Buka browser kita dan akses:
[**http://localhost:20128**](http://localhost:20128)

Kita akan melihat antarmuka web dashboard OmniRoute yang menampilkan status server, metrik pemakaian token, daftar provider, dan log permintaan.

---

## Tahap 2: Konfigurasi Provider OpenAI

Pada tahap ini, kita akan memasukkan kredensial **Shared OpenAI API Key** yang diberikan oleh instruktur ke dalam OmniRoute.

```mermaid
flowchart LR
    A["Dashboard http://localhost:20128"] --> B["Menu: Providers"]
    B --> C["Klik 'Add Provider' → Pilih OpenAI"]
    C --> D["Masukkan Provider Name & Shared API Key"]
    D --> E["Set Spending Limit: 5 USD"]
    E --> F["Klik Save & Test Connection (Status: Green)"]
```

### Langkah Konfigurasi:

1. Pada Dashboard OmniRoute (`http://localhost:20128`), klik menu **Providers** pada sidebar navigasi sebelah kiri.
2. Klik tombol **Add Provider** → pilih **OpenAI**.
3. Lengkapi formulir konfigurasi berikut:
   - **Provider Name:** `OpenAI-Shared`
   - **API Key:** Masukkan Shared OpenAI API Key yang dibagikan oleh instruktur (`sk-proj-xxxxxxxx...`).
   - **Spending Limit / Budget:** Masukkan `5` USD *(Batas alokasi saldo awal per siswa)*.
4. Klik tombol **Save &amp; Test Connection**.
5. Pastikan indikator status berubah menjadi **Connected (Green)** yang menandakan koneksi ke server OpenAI berhasil diverifikasi.

---

## Tahap 3: Konfigurasi Provider Fallback (OpenCode Zen Free / OpenRouter)

Sebagai AI Engineer profesional, kita wajib menerapkan prinsip keandalan sistem (*system resilience*). Jika alokasi kuota utama OpenAI (5 USD) habis di tengah jalan atau terkena pembatasan frekuensi (*rate limit* `HTTP 429`), gateway harus secara otomatis mengalihkan permintaan ke penyedia cadangan tanpa memutus jalannya aplikasi.

### Langkah 1: Menambahkan Fallback Providers

1. **Menambahkan OpenRouter Free Tier:**
   - Di menu **Providers**, klik **Add Provider** → pilih **OpenRouter**.
   - Masukkan API Key dari [openrouter.ai/keys](https://openrouter.ai/keys) (gratis tanpa kartu kredit), atau aktifkan router model gratis bawaan (`openrouter/free`).
   - Simpan konfigurasi provider.
2. **Menambahkan OpenCode Zen Free Tier:**
   - Di menu **Providers**, klik **Add Provider** → pilih **OpenCode Zen** (atau penyedia bertipe OpenAI-Compatible dengan endpoint Zen).
   - Simpan konfigurasi provider.

### Langkah 2: Mengatur Routing &amp; Fallback Rule di Dashboard

1. Masuk ke menu **Routing Rules** (atau **Fallback Policies**) di dashboard OmniRoute.
2. Klik **Create Rule / New Rule** dan sesuaikan parameter berikut:
   - **Rule Name:** `openai-to-free-fallback`
   - **Primary Model / Provider:** `gpt-4o-mini` (OpenAI Provider).
   - **Fallback Triggers (Kondisi Pengalihan):** Centang kondisi berikut:
     - `On Hard Limit Exceeded` (Saat pemakaian mencapai batas kuota)
     - `On Rate Limit (HTTP 429)` (Saat terkena limit frekuensi)
     - `On Server Error (HTTP 5xx)` (Saat server upstream mengalami kendala)
   - **Backup Targets (Multi-Tier Fallback):**
   1. Prioritas 1: **OpenRouter Free Tier** (`openrouter/free` atau `openrouter/auto:free`).
   2. Prioritas 2: **OpenCode Zen Free Tier** (`opencode/zen`).
3. Klik **Save Rule**.

```mermaid
flowchart TD
    Req["Request Masuk ke OmniRoute Gateway"] --> CheckQuota{"Akumulasi Biaya < 5.00 USD\n& Status Provider Normal?"}
    
    CheckQuota -- "Ya (Normal)\nHTTP 200 OK" --> OpenAI["Primary Provider:\nOpenAI API (GPT-4o / GPT-4o-mini)"]
    CheckQuota -- "Mencapai 4.00 USD (80%)" --> Warn["Munculkan Warning Alert di Dashboard\n(Sisa Kuota 1.00 USD)"]
    Warn --> OpenAI
    
    CheckQuota -- "Habis >= 5.00 USD (Hard Limit)\natau Error HTTP 429 / 5xx" --> FallbackEngine["Auto-Failover Routing Engine"]
    
    FallbackEngine --> Free1["Fallback 1: OpenRouter Free Tier\n(openrouter/free)"]
    FallbackEngine --> Free2["Fallback 2: OpenCode Zen Free Tier\n(opencode/zen)"]
```

---

## Tahap 4: Konfigurasi Local API Key, Hard Limit &amp; Budget Warning

Aplikasi kita **tidak boleh memegang API key OpenAI langsung**. Sebaliknya, aplikasi akan mengakses OmniRoute menggunakan **Local API Key** yang kita terbitkan sendiri di gateway. 

Pada tahap ini, kita menerapkan tata kelola biaya (*cost governance*) berbasis API Key dengan aturan:

- **Hard Limit Budget:** Batasi pemakaian API Key melalui fitur **Usage Limit** sebesar **5.00 USD** (Daily / Weekly limit).
- **Budget Monitoring &amp; Warning Alert:** Pantau konsumsi biaya pada menu **Costs / Analytics** hingga ambang **80% (4.00 USD)** sebelum limit 5.00 USD tercapai.

```mermaid
flowchart LR
    A["Menu: API Manager / Endpoints"] --> B["Klik 'Create API Key'"]
    B --> C["Beri Nama: 'local-dev-key'"]
    C --> D["Aktifkan: 'Enable Usage Limit'"]
    D --> E["Atur Limit: 5.00 USD\n(Daily / Weekly Usage Limit)"]
    E --> F["Klik Save & Salin Kunci\n(sk-xxxxxxxx...)"]
```

### Langkah Konfigurasi \~ Membuat API Key:

1. Di dashboard OmniRoute (`http://localhost:20128`), Pada Sidebar, pada section **OmniProxy**, buka menu **API Keys**.
2. Pada kanan atas, Klik tombol **Create API Key**.
3. Lengkapi parameter konfigurasi kunci:
   - **Key Name:** `local-dev-key` (atau nama kita).
   - **Own Cost and Token Usage**: Centang atau pastikan **Enabled**.
4. Klik **Create** / **Save**.
5. **Salin dan simpan kunci lokal yang ditampilkan** (format: `sk-xxxxxxxx...`). Kunci ini hanya ditampilkan satu kali demi alasan keamanan.

### Langkah Konfigurasi \~ Membuat USD Quota Limit:

Pada bagian ini, kita akan mencoba untuk meng-konfigurasi *Hard Limit* dari API Key yang bisa kita gunakan, dengan harapan supaya setelah melebihi quota yang ada, maka akan Fallback menggunakan Free Tier Model yang sudah dikonfigurasi sebelumnya.

1. Masih pada menu **API Keys**, lihat bagian **Registered Keys**.
2. Pada API Key yang tadi baru dibuat, lihat pada sebelah kanan, bagian **Actions**, ada tombol settings dengan nama actionnya adalah **Edit Permissions**. Klik tombol tersebut
3. Scroll ke bawah sampai pada section **Self-Service Visibility**:
   - Lihat pada bagian **USD usage Quota**, pastikan ini tercentang **Enabled**.
   - Setting pada bagian ini, untuk **Weekly Quota** menjadi **1.25 USD**.
   - Scroll ke bawah, tekan tombol **Save Permissions**.
4. Pastikan sekarang pada API Key yang tadi baru dibuat, ada tulisan **USD Quota**, pada row **PERMISSIONS**-nya.
5. Pada bagian ini, kita sudah meng-set *Hard Limit* mingguan pada API Key yang kita buat.

### Langkah Konfigurasi \~ Monitoring Budget Bulanan:

Pada bagian ini, kita akan mencoba untuk meng-konfigurasi *Budget Monitoring* bulanan kita (**5 USD**) dan OmniRoute akan memberikan notifikasi (warning), ketika budget sudah melebihi **80%** (**4 USD**)

1. Lihat kembali pada SideBar, pada section **Costs**, buka menu **Budget**.
2. Pada menu **Budget** ini, perhatikan ada API Key yang tadi sudah kita namakan `local-dev-key` atau apapun nama API Key yang tadi dibuat, lalu klik API Key tersebut untuk memunculkan Drop Down Menu penjelasan dari API Key yang tadi sudah dibuat.
3. Pada Drop Down Menu ini, akan diberikan opsi limits *Daily*, *Weekly*, *Monthly*, dan *Warn At %*:
   - Set **Monthly** menjadi **5** \~ menandakan bahwa kita akan monitoring budget sebanyak **5 USD** yang akan di-refresh per bulan
   - Set **Warn At** menjadi **80** \~ menandakan bahwa OmniRoute harus memberikan notifikasi ketika budget sudah melebihi **80 %**.
4. Setelah itu jangan lupa tekan tombol **Save Limits**.

### Pemantauan Biaya &amp; Perilaku Proteksi:

- 🛑 **Perilaku Hard Limit (Usage Limit 1.25 USD Weekly):** Jika total akumulasi pemanggilan model menggunakan kunci ini mencapai **1.25 USD** (weekly), OmniRoute secara otomatis memblokir (*hard stop*) request berbayar berikutnya dengan respon error `HTTP 429: Usage limit exceeded`. Permintaan kemudian otomatis dialihkan ke Provider Fallback gratis (OpenRouter / OpenCode Zen) sesuai aturan routing yang telah dibuat.
- ⚠️ **Pemantauan Budget &amp; Warning Alert (80% / 4.00 USD):** Melalui menu **Costs** di dashboard web, kita dapat memantau pergerakan saldo secara langsung (*real-time cost telemetry*). Saat pengeluaran menyentuh *threshold* 80% (4.00 USD), grafik pemakaian akan memberikan indikasi visual bahwa alokasi kuota utama tersisa 1.00 USD (20%).

---

## Tahap 5: Verifikasi &amp; Uji Coba Endpoint Gateway

Untuk memastikan seluruh konfigurasi telah aktif dan siap melayani permintaan, kita akan melakukan verifikasi menggunakan dua cara: skrip otomatis Python dan perintah `curl`.

### Langkah 1: Menjalankan Skrip Verifikasi Otomatis

Arahkan terminal ke folder proyek praktikum dan jalankan skrip `verify_gateway.py`:

```bash
python3 handsonlab/verify_gateway.py
```

Skrip ini akan memeriksa dua hal:

1. Status hidup (*liveness*) dari server web dashboard OmniRoute pada port `20128`.
2. Kesiapan endpoint OpenAI-compatible `/v1/models` serta daftar model yang berhasil didaftarkan oleh gateway.

Output yang diharapkan:

```text
======================================================================
🔍 MEMERIKSA STATUS KONEKSI LOCAL AI GATEWAY (OMNIROUTE)
======================================================================
Target URL: http://localhost:20128
✅ Web Dashboard aktif! (HTTP 200)
✅ OpenAI-compatible Endpoint '/v1/models' aktif!
   Terdeteksi 4 model terdaftar di OmniRoute.
   Sample Model IDs: gpt-4o-mini, gpt-4o, openrouter/free, opencode/zen
======================================================================
🎉 OmniRoute siap digunakan untuk melayani pemanggilan model AI!
======================================================================
```

### Langkah 2: Mengirimkan Prompt via Perintah `curl`

Buka terminal kita dan kirimkan permintaan chat completion secara langsung ke gateway lokal menggunakan Local API Key yang telah kita buat pada Tahap 4:

```bash
curl -X POST http://localhost:20128/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-omniroute-local-xxxx" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [
      {"role": "user", "content": "Hai OmniRoute! Jelaskan dalam 2 kalimat apa fungsi utama AI Gateway!"}
    ]
  }'
```

*(Ganti `sk-omniroute-local-xxxx` dengan Local API Key asli kita).*

Perhatikan respons JSON standar OpenAI yang dikembalikan:

```json
{
  "id": "chatcmpl-xxxx",
  "object": "chat.completion",
  "created": 1727260000,
  "model": "gpt-4o-mini",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "AI Gateway berfungsi sebagai gerbang proksi terpusat yang mengatur autentikasi, pembatasan kuota biaya, dan perutean permintaan ke berbagai penyedia model AI. Gateway ini juga menjamin ketersediaan layanan melalui fitur pengalihan otomatis (fallback) saat penyedia utama mengalami gangguan."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 22,
    "completion_tokens": 58,
    "total_tokens": 80
  }
}
```

### Langkah 3: Menginspeksi Dashboard Analytics &amp; Logs

Buka kembali dashboard OmniRoute di browser pada [**http://localhost:20128**](http://localhost:20128), lalu amati:

1. **Menu Requests / Logs:** Permintaan `curl` yang baru saja kita kirimkan tercatat lengkap beserta waktu eksekusi, provider tujuan, kode status HTTP, dan model yang digunakan.
2. **Menu Analytics / Costs:** Muncul grafik konsumsi token (input vs output) dan estimasi biaya pemakaian yang memotong alokasi kuota bulanan 5.00 USD kita.

---

## Tahap 6: Eksplorasi Fitur Kompresi Token (Materi Opsional &amp; Informatif)

> \[!WARNING\]
>
> ### ⚠️ DISCLAIMER PENTING — BACA DENGAN SEKSAMA SEBELUM MENCOBA
>
> 1. **BELUM BOLEH DIGUNAKAN UNTUK MATERI PEMBELAJARAN KE DEPAN:** Seluruh modul materi, latihan hands-on, dan pengujian coding pada sesi-sesi berikutnya di bootcamp ini membutuhkan format prompt yang utuh, penalaran mendalam (*step-by-step reasoning*), instruksi terstruktur, serta keluaran jawaban model yang lengkap dan rapi. Mengaktifkan fitur kompresi secara permanen dapat merusak evaluasi tugas dan memotong instruksi penting yang dibutuhkan saat belajar.
> 2. **WAJIB DI-NONAKTIFKAN (DISABLE) KEMBALI SETELAH PRAKTIKUM INI:** Setelah kita selesai mencoba dan memahami cara kerjanya pada sesi eksplorasi ini, pastikan kedua fitur ini (**RTK dan Caveman**) **SEGERA DI-NONAKTIFKAN (STATUS: DISABLED / TOGGLE OFF)** kembali di dashboard OmniRoute!
> 3. **BOLEH DAN SANGAT DISARANKAN DIGUNAKAN UNTUK PROJECT MANDIRI:** Fitur RTK dan Caveman **sangat dianjurkan untuk digunakan kelak saat pengerjaan Project Mandiri / Final Project** guna menekan konsumsi token (*token usage*) hingga 60% - 90% dan menghemat pengeluaran biaya API secara signifikan saat kita membangun aplikasi mandiri.

OmniRoute dilengkapi dengan dua mesin kompresi token canggih: **RTK** (untuk memangkas token input) dan **Caveman** (untuk memangkas token output).

### Eksplorasi A: Token Compression Menggunakan "Caveman" (Output Stripping)

```mermaid
flowchart LR
    Prompt["User Prompt: 'Review kode ini'"] --> LLM["LLM Processing"]
    LLM --> Verbose["Normal Output (250 tokens):\n'Tentu! Berikut analisis mendalam saya... Sebagai asisten AI yang ramah, saya merekomendasikan kita untuk...'"]
    LLM --> Caveman["Caveman Mode (60 tokens):\n'Baris 14 rentan SQL injection. Ganti query pakai parameterized statement. Tambah index kolom email.'"]
    
    Verbose -.-> Cost1["Biaya Output: Standar\nKecepatan: Normal"]
    Caveman -.-> Cost2["Biaya Output: Hemat 65%+\nKecepatan: Sangat Cepat"]
```

#### Apa itu Caveman?

**Caveman** adalah fitur kompresi output pada OmniRoute yang menginstruksikan model AI untuk membuang segala bentuk basa-basi (*pleasantries*, kalimat pembuka sopan, *disclaimer* panjang, dan pengulangan pertanyaan pengguna).

- **Hasil:** Model langsung memberikan inti solusi teknis secara padat (*dense &amp; concise*).
- **Keuntungan:** Memangkas konsumsi token output sebesar **60% s.d. 75%** tanpa menurunkan ketepatan logika teknis.
- **Cara Mencoba di Dashboard:**
  1. Masuk ke menu **Settings** atau **Compression** di dashboard `http://localhost:20128`.
  2. Aktifkan toggle **Caveman Engine**.
  3. Kirimkan kembali permintaan chat completion via `curl` di terminal.
  4. Amati bahwa respons yang dikembalikan menjadi sangat singkat, langsung pada pokok pembahasan (*straight to the point*).
- **Langkah Wajib:**
  - 🛑 **Matikan kembali toggle Caveman Engine (Status: Disabled)** di menu Settings sebelum mengakhiri sesi.

---

### Eksplorasi B: Context Filtering Menggunakan "RTK (Rust Token Killer)" (Input Filtering)

#### Apa itu RTK?

Ketika sebuah aplikasi klien mengirimkan konteks data berukuran raksasa (seperti ribuan baris log terminal, hasil eksekusi unit test, atau riwayat commit git), token input akan membengkak secara drastis (*context bloat*). Hal ini membuat context window cepat penuh dan biaya API terkuras dengan cepat.

**RTK (Rust Token Killer)** adalah filter proksi berkinerja tinggi yang ditulis dalam bahasa pemrograman Rust:

- Menganalisis dan membuang baris-baris log yang berulang (*redundant noise*) sebelum diteruskan ke model AI.
- Melakukan kompresi struktur kode secara cerdas (*syntax-aware folding*).
- **Hasil:** Mereduksi token input sebesar **60% s.d. 90%**, menjaga context window tetap bersih, serta menghemat saldo kuota secara dramatis.
- **Cara Mencoba di Dashboard:**
  1. Pada menu **Settings** atau **Compression** di OmniRoute, aktifkan toggle **RTK Engine**.
  2. Kirimkan prompt yang memuat teks panjang atau log berulang via `curl`.
  3. Buka menu **Analytics** di dashboard OmniRoute dan perhatikan metrik pada kolom **Tokens Saved by RTK**.
- **Langkah Wajib:**
  - 🛑 **Matikan kembali toggle RTK Engine (Status: Disabled)** di menu Settings sebelum mengakhiri sesi.

---

## Panduan Pemecahan Masalah (Troubleshooting)


| Gejala Masalah                                                   | Kemungkinan Penyebab                                                                           | Tindakan Solusi                                                                                                                                                                                              |
| :---------------------------------------------------------------- | :---------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `Error: listen EADDRINUSE :::20128` saat menjalankan `omniroute` | Port 20128 sedang digunakan oleh proses OmniRoute lain atau container Docker yang masih aktif. | Cari PID proses lama dengan `lsof -i :20128` lalu hentikan dengan `kill -9 [[ORCA_RICH_MD:a0a20bb6df38fc9d17c8d065dad07831:inline-html:%3CPID%3E]]`, atau jalankan pada port lain: `omniroute --port 20129`. |
| Perintah `curl` atau browser menampilkan `Connection refused`    | Server OmniRoute belum dijalankan di terminal.                                                 | Buka tab terminal terpisah dan jalankan perintah `omniroute`. Pastikan dashboard dapat diakses pada `http://localhost:20128`.                                                                                |
| Muncul *Warning Banner* Kuning di Dashboard OmniRoute            | Total pemakaian telah mencapai 4.00 USD (80% dari batas budget 5.00 USD).                      | Ini adalah notifikasi pengingat normal. Saldo kuota OpenAI kita tersisa 1.00 USD. Pastikan Provider Fallback (OpenRouter &amp; OpenCode Zen) sudah terpasang.                                                |
| Error `HTTP 429: Usage limit exceeded` dari Gateway Lokal        | Pemakaian Local API Key telah mencapai 5.00 USD (Hard Limit tercapai).                         | OmniRoute secara otomatis memutus akses berbayar dan mengaktifkan rute fallback gratis. Pastikan aturan fallback pada Tahap 3 sudah aktif.                                                                   |
| Error `HTTP 401: Unauthorized` saat menjalankan perintah `curl`  | Header Authorization salah atau Local API Key belum disertakan.                                | Pastikan format header adalah `-H "Authorization: Bearer sk-omniroute-local-xxxx"` dengan kunci lokal yang dibuat pada Tahap 4.                                                                              |
| Endpoint `/v1/models` kosong atau tidak menampilkan model        | Belum ada Provider yang tersambung dengan sukses di dashboard.                                 | Buka menu **Providers** di dashboard dan pastikan Provider OpenAI berstatus **Connected (Green)**.                                                                                                           |


---

## Checklist Verifikasi Praktikum Siswa

Pastikan kita mencentang seluruh daftar berikut sebelum mengakhiri sesi praktikum hari ini:

- [ ] Server OmniRoute berhasil terpasang dan berjalan lancar pada port `20128` (`http://localhost:20128`).
- [ ] Shared OpenAI API Key (alokasi batas budget 5 USD) berhasil dikonfigurasi pada menu Providers dan berstatus **Connected**.
- [ ] Fallback Providers (**OpenRouter Free Tier** dan **OpenCode Zen Free Tier**) berhasil ditambahkan ke OmniRoute.
- [ ] Routing &amp; Fallback Rule (`openai-to-free-fallback`) berhasil dibuat untuk pengalihan otomatis saat hard limit tercapai atau terkena `HTTP 429`.
- [ ] Local API Key OmniRoute berhasil dibuat dengan **Usage Limit 5.00 USD**, serta memahami pemantauan **Warning Alert 4.00 USD (80%)** pada dashboard Costs.
- [ ] Skrip pengujian `python3 handsonlab/verify_gateway.py` berhasil dijalankan dengan status seluruh komponen centang hijau.
- [ ] Berhasil melakukan pemanggilan chat completion via `curl` ke endpoint `/v1/chat/completions` menggunakan Local API Key.
- [ ] Memahami konsep fitur kompresi token (**Caveman** dan **RTK**) sebagai teknik penghematan biaya untuk project mandiri mendatang.
- [ ] **MEMASTIKAN FITUR RTK DAN CAVEMAN DALAM KONDISI NONAKTIF (DISABLED)** agar tidak mengganggu sesi materi modul berikutnya.

