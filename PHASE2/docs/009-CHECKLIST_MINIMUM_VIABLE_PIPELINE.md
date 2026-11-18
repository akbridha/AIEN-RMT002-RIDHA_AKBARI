# 009 — Checklist Minimum Viable Pipeline (MVP) HR-Agent

Dokumen ini adalah panduan praktis dan daftar periksa (*checklist*) langkah demi langkah untuk mengaktifkan alur minimal:
> **Streamlit UI ➡️ FastAPI (/api/v1/chat) ➡️ AI Agent (OpenAI) ➡️ Database (PostgreSQL RDBMS & Vector Unstructured)**

Seluruh eksekusi infrastruktur menggunakan file resmi proyek milestone: [`PHASE2/HR-Agent/docker-compose.yml`](../HR-Agent/docker-compose.yml) dan [`PHASE2/HR-Agent/Dockerfile`](../HR-Agent/Dockerfile).

---

## 🔗 Jembatan: Hubungan Apa yang Sudah Dipelajari vs Implementasi

Berikut perbandingan langsung antara materi yang Anda eksplorasi di `belajar-isolasi/` dengan file sistem utama yang mengimplementasikannya:

```
[EKSPERIMEN LOKAL]                                  [SISTEM UTAMA RESMI (PHASE2/HR-Agent/)]
belajar-isolasi/storage-lab/init.sql       ──► data/init.sql & src/repository.py (Postgres)
belajar-isolasi/storage-lab/docker-compose ──► docker-compose.yml (Resmi 4 service: pg, redis, api, ui)
belajar-isolasi/vector_db/search_example.py ──► src/retrieval.py (Vector & Hybrid Search)
belajar-isolasi/sandbox_app.py             ──► src/api.py & src/security.py (FastAPI Auth)
belajar-isolasi/storage-lab/app_dengan_api_db.py ──► src/agent.py & src/providers.py (OpenAI Tools)
belajar-isolasi/storage-lab/app_fe_streamlit.py  ──► app.py (Streamlit UI resmi)
```

| Konsep yang Sudah Dipelajari | Praktik di `belajar-isolasi` | Implementasi Nyata di Sistem | Catatan Perubahan & Manfaat |
|---|---|---|---|
| **Docker Orchestration** | `docker-compose.yml` di `storage-lab` hanya untuk postgres manual. | `PHASE2/HR-Agent/docker-compose.yml` | Mengelola 4 service terintegrasi: PostgreSQL (pgvector), Redis (cache), API (FastAPI), dan Streamlit (UI). |
| **RDBMS (Data Terstruktur)** | `app_dengan_db.py` query langsung `SELECT employee_id...` via psycopg. | `src/repository.py` (`PostgresRepository`) | Menggunakan *Connection Pool*, query aman dari SQL Injection, dan mengisolasi akses database. |
| **Vector DB (Unstructured)** | `vector_db/save_data.py` & `search_example.py` (Pinecone). | `src/setup_lab.py` & `src/retrieval.py` | Menggunakan **pgvector** terpadu di PostgreSQL, digabung pencarian teks (BM25) menjadi **Hybrid Search**. |
| **Otorisasi & Login** | `TOKEN_MAP = {"token-alya": ...}` di-hardcode dalam file Python. | `src/security.py` | Token di-hash dengan SHA-256 dan dicocokkan ke tabel `employee.token_hash` di database. |
| **Panggilan LLM / AI** | `openai_client.chat.completions.create()` langsung di endpoint chat. | `src/providers.py` & `src/agent.py` | Menggunakan **OpenAI Function/Tool Calling**: LLM yang otomatis memilih apakah butuh cek saldo (RDBMS) atau cari pasal kebijakan (Vector). |
| **Frontend Web** | `app_fe_streamlit.py` sederhana dengan input chat dan sidebar persona. | `app.py` | Sudah terintegrasi dengan tab riwayat cuti, monitoring admin, dan penampil kotak sitasi dokumen (*citations*). |

---

## 🛠️ Pilihan Jalur Eksekusi

Anda dapat memilih salah satu dari dua jalur eksekusi di bawah ini:
- **Jalur A (Full Docker — Sesuai Standar Milestone & Grader):** Seluruh service (Postgres, Redis, API, Streamlit) berjalan di dalam Docker Container. Sangat bersih tanpa perlu dependensi Python di host.
- **Jalur B (Hybrid Development — Cepat untuk Debugging):** Postgres & Redis berjalan via Docker Compose, sedangkan API & Streamlit dijalankan lokal dengan fitur `--reload`.

---

## 📋 Checklist Eksekusi MVP: Jalur A (Full Docker — Direkomendasikan)

Tandai `[x]` saat menyelesaikan tiap tahap:

### FASE 1: Konfigurasi Environment
- [x] **1.1. Konfigurasi file `.env` di `PHASE2/HR-Agent/`**
  - Pastikan variabel berikut terisi di `PHASE2/HR-Agent/.env`:
    ```ini
    OPENAI_API_KEY=sk-...
    AGENT_MODEL=gpt-4o-mini
    EMBEDDING_MODEL=text-embedding-3-small
    EMBEDDING_DIMENSIONS=1536
    DATABASE_URL=postgresql://hr_app:hr_app@postgres:5432/hr_assistant
    REDIS_URL=redis://redis:6379/0
    MODEL_MODE=live
    ```

### FASE 2: Build & Jalankan Service Infrastruktur
- [x] **2.1. Build Image Aplikasi (API & Streamlit)**
  - Masuk ke folder proyek utama dan build image:
    ```powershell
    cd PHASE2/HR-Agent
    docker compose build api streamlit
    ```
- [x] **2.2. Jalankan Database (pgvector) dan Redis**
  - Jalankan container database dan cache:
    ```powershell
    docker compose up -d postgres redis
    ```
  - Verifikasi kedua service berstatus `healthy`:
    ```powershell
    docker compose ps
    ```

### FASE 3: Seeding Database & Knowledge Base Vektor
- [x] **3.1. Eksekusi Seeding via Container API**
  - Jalankan script `src.setup_lab` untuk membuat tabel, memasukkan data karyawan (RDBMS), dan meng-embed markdown kebijakan ke pgvector (Unstructured):
    ```powershell
    docker compose run --rm api python -m src.setup_lab
    ```
  - Tunggu hingga proses embedding dan upsert policy chunk selesai tanpa error.

### FASE 4: Jalankan Aplikasi & Uji Coba End-to-End
- [x] **4.1. Nyalakan Service API dan Streamlit**
  - Jalankan:
    ```powershell
    docker compose up -d api streamlit
    ```
  - Cek log jika diperlukan: `docker compose logs -f api`
- [x] **4.2. Cek Kesiapan Endpoint API (Port 8000)**
  - Buka browser ke `http://localhost:8000/healthz` ➡️ respon: `{"status": "ok"}`
  - Buka `http://localhost:8000/readyz` ➡️ respon: `{"status": "ready"}`
- [x] **4.3. Uji Chat UI Streamlit (Port 8501)**
  - Buka browser ke `http://localhost:8501`.
  - Pilih persona: **Alya Pratama**.
  - **Uji Skenario 1 (Query RDBMS):**
    - Ketik: *"Berapa saldo cuti saya?"*
    - Jawaban harus menampilkan saldo cuti Alya langsung dari database PostgreSQL.
  - **Uji Skenario 2 (Query Unstructured / Vector DB):**
    - Ketik: *"Bagaimana aturan cuti tahunan dan pengajuannya?"*
    - Jawaban harus merujuk aturan dan menampilkan expander **Sumber kebijakan (Citations)** dengan cuplikan dokumen aslinya.
  - **Uji Skenario 3 (Isolasi Hak Akses):**
    - Ganti persona ke **Bima Santoso** lalu tanyakan saldo. AI hanya menampilkan data Bima.

---

## 📋 Checklist Eksekusi MVP: Jalur B (Hybrid Development)

Gunakan jalur ini jika ingin mengedit kode Python secara langsung dengan instant hot-reload:

1. **Jalankan Database & Redis di Docker:**
   ```powershell
   cd PHASE2/HR-Agent
   docker compose up -d postgres redis
   ```
2. **Setup .env untuk Lokal (Host):**
   Ubah host URL di `.env` lokal:
   ```ini
   DATABASE_URL=postgresql://hr_app:hr_app@localhost:5432/hr_assistant
   REDIS_URL=redis://localhost:6379/0
   ```
3. **Seeding dari Terminal Lokal:**
   ```powershell
   python src/setup_lab.py
   ```
4. **Jalankan FastAPI di Terminal 1:**
   ```powershell
   uvicorn src.api:app --reload --port 8000
   ```
5. **Jalankan Streamlit di Terminal 2:**
   ```powershell
   streamlit run app.py
   ```

---

## 🎯 Kriteria Selesai (Definition of Done)
1. Seluruh proses menggunakan `PHASE2/HR-Agent/docker-compose.yml` resmi.
2. Pengguna mengetik di UI Streamlit ➡️ Request diteruskan ke FastAPI dengan header Bearer Token.
3. Pertanyaan saldo/karyawan ➡️ Terjawab akurat dari **PostgreSQL (RDBMS)**.
4. Pertanyaan kebijakan/aturan ➡️ Terjawab akurat dari **Policy Chunk (Vector DB pgvector)** disertai sitasi dokumen.
