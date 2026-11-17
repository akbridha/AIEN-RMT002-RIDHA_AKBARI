# 009 — Checklist Minimum Viable Pipeline (MVP) HR-Agent

Dokumen ini adalah panduan praktis dan daftar periksa (*checklist*) langkah demi langkah untuk mengaktifkan alur minimal:
> **Streamlit UI ➡️ FastAPI (/api/v1/chat) ➡️ AI Agent (OpenAI) ➡️ Database (PostgreSQL RDBMS & Vector Unstructured)**

---

## 🔗 Jembatan: Hubungan Apa yang Sudah Dipelajari vs Implementasi

Berikut perbandingan langsung antara materi yang Anda eksplorasi di `belajar-isolasi/` dengan file sistem utama yang mengimplementasikannya:

```
[EKSPERIMEN LOKAL]                                  [SISTEM UTAMA (src/)]
belajar-isolasi/storage-lab/init.sql       ──► data/init.sql & src/repository.py (Postgres)
belajar-isolasi/vector_db/search_example.py ──► src/retrieval.py (Vector & Hybrid Search)
belajar-isolasi/sandbox_app.py             ──► src/api.py & src/security.py (FastAPI Auth)
belajar-isolasi/storage-lab/app_dengan_api_db.py ──► src/agent.py & src/providers.py (OpenAI Tools)
belajar-isolasi/storage-lab/app_fe_streamlit.py  ──► app.py (Streamlit UI resmi)
```

| Konsep yang Sudah Dipelajari | Praktik di `belajar-isolasi` | Implementasi Nyata di Sistem | Catatan Perubahan & Manfaat |
|---|---|---|---|
| **RDBMS (Data Terstruktur)** | `app_dengan_db.py` query langsung `SELECT employee_id...` via psycopg. | `src/repository.py` (`PostgresRepository`) | Menggunakan *Connection Pool*, query aman dari SQL Injection, dan mengisolasi akses database. |
| **Vector DB (Unstructured)** | `vector_db/save_data.py` & `search_example.py` (Pinecone). | `src/setup_lab.py` & `src/retrieval.py` | Di sistem utama menggunakan **pgvector** (di dalam PostgreSQL yang sama), dicampur dengan pencarian teks (BM25) menjadi **Hybrid Search**. Konsep embedding & cosine similarity-nya sama persis. |
| **Otorisasi & Login** | `TOKEN_MAP = {"token-alya": ...}` di-hardcode dalam file Python. | `src/security.py` | Token di-hash dengan SHA-256 dan dicocokkan ke tabel `employee.token_hash` di database. |
| **Panggilan LLM / AI** | `openai_client.chat.completions.create()` langsung di endpoint chat. | `src/providers.py` & `src/agent.py` | Menggunakan **OpenAI Function/Tool Calling**: LLM yang otomatis memilih apakah butuh cek saldo (RDBMS) atau cari pasal kebijakan (Vector). |
| **Frontend Web** | `app_fe_streamlit.py` sederhana dengan input chat dan sidebar persona. | `app.py` | Sudah terintegrasi dengan tab riwayat cuti, monitoring admin, dan penampil kotak sitasi dokumen (*citations*). |

---

## 📋 Checklist Eksekusi MVP (Langkah demi Langkah)

Tandai `[x]` saat menyelesaikan tiap tahap:

### FASE 1: Konfigurasi Environment & Database Service
- [ ] **1.1. Konfigurasi file `.env` di `PHASE2/HR-Agent/`**
  - Pastikan variabel berikut terisi:
    ```ini
    OPENAI_API_KEY=sk-...
    AGENT_MODEL=gpt-4o-mini
    EMBEDDING_MODEL=text-embedding-3-small
    EMBEDDING_DIMENSIONS=1536
    DATABASE_URL=postgresql://hr_app:hr_app@localhost:5432/hr_assistant
    MODEL_MODE=live
    ```
- [ ] **1.2. Pastikan Docker PostgreSQL (pgvector) aktif**
  - Jalankan container database (port 5432):
    ```powershell
    cd PHASE2/HR-Agent/belajar-isolasi/storage-lab
    docker compose up -d
    ```
  - Verifikasi container `hr_postgres_lab` (atau service postgres) berstatus `Up/Healthy`.

---

### FASE 2: Seeding Data (RDBMS & Unstructured Knowledge Base)
- [ ] **2.1. Jalankan Script Seeding Otomatis**
  - Di terminal (pastikan virtual environment aktif):
    ```powershell
    cd PHASE2/HR-Agent
    python src/setup_lab.py
    ```
- [ ] **2.2. Verifikasi Data Masuk ke Database**
  - Buka pgAdmin (`localhost:5050`) atau jalankan query:
    - **Cek Data RDBMS:** `SELECT employee_id, display_name FROM employee;` (harus ada Alya, Bima, Admin).
    - **Cek Data Unstructured:** `SELECT count(*), document_id FROM policy_chunk GROUP BY document_id;` (pastikan kolom `embedding` terisi vektor float).

---

### FASE 3: Pengujian Backend API (FastAPI)
- [ ] **3.1. Jalankan Server FastAPI Resmi**
  ```powershell
  cd PHASE2/HR-Agent
  uvicorn src.api:app --reload --port 8000
  ```
- [ ] **3.2. Cek Kesiapan Endpoint**
  - Akses `http://localhost:8000/docs` di browser.
  - Test endpoint `GET /healthz` ➡️ respon harus `{"status": "ok"}`.
  - Test endpoint `GET /readyz` ➡️ respon harus mengonfirmasi database & model `ready`.
- [ ] **3.3. Uji Coba Chat via Swagger / cURL (Simulasi Login)**
  - Masukkan Bearer token: `token-alya`.
  - Hit `POST /api/v1/chat` dengan payload:
    ```json
    {"message": "Berapa sisa saldo cuti tahunan saya?"}
    ```
    *(Verifikasi: AI memanggil tool RDBMS dan menjawab saldo Alya).*
  - Hit `POST /api/v1/chat` dengan payload:
    ```json
    {"message": "Berapa hari hak cuti melahirkan?"}
    ```
    *(Verifikasi: AI memanggil tool Vector retrieval dan memunculkan citations).*

---

### FASE 4: Pengujian Frontend Terhubung (Streamlit)
- [ ] **4.1. Jalankan Aplikasi Streamlit Utama**
  - Buka terminal baru:
    ```powershell
    cd PHASE2/HR-Agent
    streamlit run app.py
    ```
  - Buka browser di `http://localhost:8501`.
- [ ] **4.2. Uji Alur End-to-End Chat UI**
  - Pilih persona di sidebar: **Alya Pratama**.
  - **Uji Skenario 1 (Akses RDBMS):** Ketik *"Berapa saldo cuti saya?"*
    - Jawaban harus menampilkan saldo cuti Alya dari tabel database PostgreSQL.
  - **Uji Skenario 2 (Akses Unstructured DB):** Ketik *"Bagaimana kebijakan kerja remote?"*
    - Jawaban merujuk aturan dan muncul expander **Sumber kebijakan (Citations)**.
  - **Uji Skenario 3 (Privasi Antar Karyawan):** Ganti persona ke **Bima Santoso** lalu tanyakan saldo cuti.
    - Jawaban harus menampilkan saldo Bima, bukan saldo Alya.

---

## 🎯 Target Minimum Terpenuhi Jika:
1. Pengguna mengetik di UI Streamlit ➡️ Request masuk ke FastAPI dengan token autentikasi.
2. Pertanyaan tentang orang/saldo ➡️ Terjawab akurat dari **PostgreSQL (RDBMS)**.
3. Pertanyaan tentang pasal/aturan ➡️ Terjawab akurat dari **Policy Chunks (Vector Search)** lengkap dengan sitasi dokumen aslinya.
