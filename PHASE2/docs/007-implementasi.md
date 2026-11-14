# 007 — Panduan Implementasi: Menggabungkan Yang Sudah Dipelajari

Dokumen ini menjembatani apa yang sudah Anda pelajari di `belajar-isolasi` dengan langkah berikutnya menuju HR-Agent yang sesungguhnya.

---

## Apa Yang Sudah Anda Kuasai

| # | Komponen | Bukti |
|---|---|---|
| 1 | **PostgreSQL + pgvector** | `belajar-isolasi/storage-lab/` — schema 7 tabel, seed data, docker compose |
| 2 | **FastAPI dasar** | `belajar-isolasi/sandbox_app.py` — endpoint, Pydantic, auth Bearer, Depends |
| 3 | **Hit OpenAI API** | Anda sudah bisa panggil API key dan terima response |

---

## Peta Jalan: Dari Belajar ke Produksi

```
Yang sudah ada:                    Langkah berikutnya:
─────────────────────              ──────────────────────────────────
storage-lab/init.sql  ──────────►  Gunakan langsung (sudah benar)
sandbox_app.py        ──────────►  Pindahkan logika ke src/api.py
Hit OpenAI API        ──────────►  Hubungkan ke src/providers.py
                                             │
                                             ▼
                                   Langkah 1: DB → FastAPI
                                   Langkah 2: FastAPI → OpenAI
                                   Langkah 3: Semua terhubung
```

---

## Langkah 1: Hubungkan FastAPI ke Database

**Tujuan:** Endpoint `/healthz` bisa konfirmasi bahwa Postgres berjalan.

### 1a. Pastikan Docker Postgres masih jalan

```bash
cd PHASE2/HR-Agent/belajar-isolasi/storage-lab
docker compose up -d
```

Verifikasi:
```bash
docker ps   # harus ada hr_postgres_lab
```

### 1b. Pasang library koneksi

Library yang dibutuhkan sudah ada di `requirements.txt` proyek utama:
```
psycopg[binary]   # driver PostgreSQL untuk Python
```

Install (dari direktori HR-Agent):
```bash
cd PHASE2/HR-Agent
pip install -r requirements.txt
```

### 1c. Coba koneksi manual (di Python shell atau Jupyter)

```python
import psycopg

conn_string = "postgresql://hr_app:hr_app@localhost:5432/hr_assistant"

with psycopg.connect(conn_string) as conn:
    result = conn.execute("SELECT employee_id, display_name FROM employee").fetchall()
    print(result)
# Output: [('EMP-001', 'Alya Pratama'), ('EMP-002', 'Bima Santoso'), ('ADM-001', 'Monitoring Admin')]
```

> **Mengapa ini penting?** Sebelum membuat endpoint, pastikan koneksi berhasil dulu. Kalau gagal di sini, perbaiki dulu sebelum melangkah ke FastAPI.

### 1d. Tambahkan koneksi ke FastAPI

Buat file baru `belajar-isolasi/app_dengan_db.py`:

```python
import psycopg
from fastapi import FastAPI, HTTPException

app = FastAPI(title="FastAPI + DB", version="0.2.0")

DB_URL = "postgresql://hr_app:hr_app@localhost:5432/hr_assistant"


def get_conn():
    """Buka koneksi baru, lalu tutup setelah selesai."""
    return psycopg.connect(DB_URL)


@app.get("/healthz")
def healthz():
    try:
        with get_conn() as conn:
            conn.execute("SELECT 1")
        return {"status": "ok", "db": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"DB error: {e}")


@app.get("/karyawan")
def list_karyawan():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT employee_id, display_name, role FROM employee"
        ).fetchall()
    return [
        {"employee_id": r[0], "display_name": r[1], "role": r[2]}
        for r in rows
    ]
```

Jalankan:
```bash
cd PHASE2/HR-Agent/belajar-isolasi
uvicorn app_dengan_db:app --reload --port 8001
```

Test:
```bash
curl http://localhost:8001/healthz
# → {"status":"ok","db":"connected"}

curl http://localhost:8001/karyawan
# → [{"employee_id":"EMP-001",...}, ...]
```

---

## Langkah 2: Hubungkan FastAPI ke OpenAI

**Tujuan:** Endpoint chat yang memanggil OpenAI dan mengembalikan jawaban nyata.

### 2a. Simpan API key di file .env

Di `belajar-isolasi/`, buat file `.env`:
```
OPENAI_API_KEY=sk-...isi_key_anda...
```

> **Jangan commit file ini ke Git!** Pastikan `.env` sudah ada di `.gitignore`.

### 2b. Baca .env dari Python

```python
# Di bagian atas file Python
import os
from dotenv import load_dotenv

load_dotenv()   # baca file .env secara otomatis

api_key = os.getenv("OPENAI_API_KEY")
```

Library `python-dotenv` sudah ada di `requirements.txt`.

### 2c. Buat endpoint chat yang nyata

Tambahkan ke `app_dengan_db.py` (atau buat file baru `app_lengkap.py`):

```python
import os
from openai import OpenAI
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
import psycopg

load_dotenv()

app = FastAPI(title="FastAPI + DB + OpenAI", version="0.3.0")
security = HTTPBearer()

DB_URL = "postgresql://hr_app:hr_app@localhost:5432/hr_assistant"
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Token sederhana → employee_id (sama seperti sandbox_app.py)
TOKEN_MAP = {
    "token-alya": {"employee_id": "EMP-001", "role": "employee"},
    "token-bima": {"employee_id": "EMP-002", "role": "employee"},
    "token-admin": {"employee_id": "ADM-001", "role": "monitoring_admin"},
}


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    answer: str
    employee_id: str


def current_user(creds: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    user = TOKEN_MAP.get(creds.credentials)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token tidak dikenal")
    return user


@app.post("/api/v1/chat", response_model=ChatResponse)
def chat(req: ChatRequest, user: dict = Depends(current_user)) -> ChatResponse:
    # Ambil nama karyawan dari DB
    with psycopg.connect(DB_URL) as conn:
        row = conn.execute(
            "SELECT display_name FROM employee WHERE employee_id = %s",
            (user["employee_id"],)
        ).fetchone()
    display_name = row[0] if row else user["employee_id"]

    # Panggil OpenAI
    completion = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": f"Kamu adalah asisten HR. Kamu sedang melayani {display_name}."},
            {"role": "user", "content": req.message},
        ],
        max_tokens=300,
    )

    answer = completion.choices[0].message.content
    return ChatResponse(answer=answer, employee_id=user["employee_id"])
```

Jalankan:
```bash
uvicorn app_lengkap:app --reload --port 8002
```

Test dengan curl:
```bash
curl -X POST http://localhost:8002/api/v1/chat \
  -H "Authorization: Bearer token-alya" \
  -H "Content-Type: application/json" \
  -d '{"message": "Berapa sisa cuti tahunan saya?"}'
```

---

## Langkah 3: Memahami Arsitektur Project Asli

Setelah Langkah 1 dan 2 berjalan di `belajar-isolasi`, Anda siap memahami struktur di `src/` proyek utama.

### Peta File `src/` → Apa fungsinya

```
src/
├── config.py        # Baca semua variabel dari .env (pakai pydantic-settings)
├── security.py      # Verifikasi token dari DB (bukan hardcode seperti sandbox)
├── repository.py    # Semua operasi DB (SELECT, INSERT) terpusat di sini
├── retrieval.py     # Hybrid search: vector + full-text search policy
├── providers.py     # Panggil OpenAI / LLM (wrapper dari openai_client)
├── tools.py         # 4 tool yang bisa dipanggil agent (search, balance, propose, confirm)
├── agent.py         # Loop: terima pesan → pilih tool → panggil → balas
├── api.py           # Endpoint FastAPI (chat, confirm, history, monitoring)
└── contracts.py     # Semua Pydantic model (request/response shapes)
```

### Alur satu request chat (dari kanan ke kiri = dari luar ke dalam)

```
User kirim POST /api/v1/chat
        │
        ▼
   [api.py]  — parse request, cek auth
        │
        ▼
   [agent.py] — terima pesan, mulai loop
        │
        ├──► [tools.py: search_policy] ──► [retrieval.py] ──► PostgreSQL (policy_chunk)
        │
        ├──► [tools.py: get_balance]   ──► [repository.py] ──► PostgreSQL (leave_balance)
        │
        ├──► [tools.py: prepare_leave] ──► [repository.py] ──► PostgreSQL (action_proposal)
        │
        └──► [providers.py]            ──► OpenAI API
        │
        ▼
   [api.py]  — format ChatResponse, kembalikan ke user
```

### Perbandingan: sandbox vs proyek asli

| Aspek | sandbox_app.py (belajar) | src/api.py (proyek asli) |
|---|---|---|
| Auth | Hardcode TOKEN_MAP | Ambil dari DB, cek token_hash |
| DB | Koneksi langsung di endpoint | Pooling via `repository.py` |
| OpenAI | Panggil langsung di endpoint | Abstraksi di `providers.py` |
| Response | `{"answer": "..."}` sederhana | `ChatResponse` lengkap dengan trace_id, citations, usage |
| Loop | Satu tembakan | Agentic loop (bisa beberapa putaran) |

---

## Langkah 4: Tahapan Selanjutnya Menuju Proyek Utama

Urutan ini mengikuti timeline di `004-TIMELINE_HR_AGENT_10_HARI.md`:

### Hari 4 — Jalankan `src/setup_lab.py`

Script ini mengisi `policy_chunk` dengan embedding dari file `.md` di `data/policies/`.

```bash
cd PHASE2/HR-Agent
python src/setup_lab.py
```

> **Prasyarat:** Docker Postgres harus jalan, `OPENAI_API_KEY` harus terisi di `.env`.

### Hari 5 — Pahami `src/retrieval.py`

Buka file tersebut dan baca fungsi `search_policies()`. Ia menggabungkan dua cara cari:
1. **Vector search** — cocok secara makna (pakai embedding OpenAI + pgvector)
2. **Full-text search** — cocok secara kata kunci (pakai `tsvector` PostgreSQL)

### Hari 6-7 — Baca `src/tools.py` dan `src/repository.py`

Setiap tool di `tools.py` memanggil method di `repository.py`. Baca keduanya bersamaan.

### Hari 8+ — Baca `src/agent.py`

Ini yang paling kompleks. Baca setelah semua komponen di atas dipahami.

---

## Checklist Sebelum Melanjutkan

Pastikan semua ini sudah berjalan sebelum lanjut ke `src/`:

- [ ] `docker compose up -d` di `storage-lab/` → container postgres hidup
- [ ] Script Python koneksi DB berhasil (Langkah 1c)
- [ ] `curl localhost:8001/healthz` → `{"status":"ok","db":"connected"}`
- [ ] `curl localhost:8002/api/v1/chat` dengan Bearer token → dapat balasan OpenAI
- [ ] File `.env` di `belajar-isolasi/` sudah berisi `OPENAI_API_KEY` (dan **tidak** di-commit)

---

## Referensi Silang

| Dokumen | Isi |
|---|---|
| [`004-TIMELINE_HR_AGENT_10_HARI.md`](./004-TIMELINE_HR_AGENT_10_HARI.md) | Jadwal dan task harian |
| [`005-PANDUAN_BELAJAR_FASTAPI_HR_AGENT.md`](./005-PANDUAN_BELAJAR_FASTAPI_HR_AGENT.md) | Konsep FastAPI lebih dalam |
| [`006-rancangan_table.md`](./006-rancangan_table.md) | Penjelasan setiap kolom tabel |
| [`belajar-isolasi/sandbox_app.py`](../HR-Agent/belajar-isolasi/sandbox_app.py) | Latihan FastAPI yang sudah ada |
| [`belajar-isolasi/storage-lab/`](../HR-Agent/belajar-isolasi/storage-lab/) | Postgres + schema yang sudah ada |
