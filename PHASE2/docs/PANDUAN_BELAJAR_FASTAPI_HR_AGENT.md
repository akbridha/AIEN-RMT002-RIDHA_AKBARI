# Panduan Belajar & Implementasi FastAPI di Project HR-Agent

Dokumen ini dirancang khusus untuk Anda yang **belum pernah menggunakan FastAPI** sama sekali. Panduan ini mencakup materi esensial dari nol, analogi sederhana, pemetaan langsung ke arsitektur project `HR-Agent`, serta langkah-langkah implementasinya.

---

## 1. Apa Itu FastAPI dan Mengapa Digunakan?

### Analogi Sederhana: Restoran & Pelayan
Bayangkan aplikasi HR-Agent Anda adalah sebuah **dapur restoran**:
- **Logika Agent/LLM/Database** adalah para koki yang memasak makanan.
- **Frontend / Klien (Web/UI/cURL/Postman)** adalah pelanggan di meja makan.
- **FastAPI** adalah **pelayan (waiter)**:
  1. Menerima pesanan dari pelanggan (`HTTP Request`).
  2. Mengecek apakah format pesanan valid (misal: "tidak boleh kosong", "menu harus ada"). Jika salah, langsung ditolak sebelum masuk dapur (`Validation`).
  3. Memeriksa identitas pelanggan apakah punya hak pesan menu VIP (`Authentication & Authorization`).
  4. Mengantarkan pesanan ke koki (`Agent / Database`).
  5. Mengembalikan masakan yang sudah jadi ke pelanggan dengan format rapi (`HTTP Response JSON`).

FastAPI dibangun di atas dua komponen utama Python:
1. **Starlette**: Framework web asynchronous super cepat.
2. **Pydantic**: Validasi data otomatis berbasis Python type hints.

---

## 2. 5 Konsep Esensial FastAPI yang Wajib Dipahami

### Konsep 1: Endpoint & HTTP Methods (Routing)
Setiap fungsi dihubungkan dengan URL dan metode HTTP menggunakan *decorator*:
```python
from fastapi import FastAPI

app = FastAPI()

# GET: Mengambil data
@app.get("/healthz")
def check_health():
    return {"status": "ok"}

# POST: Mengirim data baru
@app.post("/api/v1/chat")
def chat(payload: dict):
    return {"reply": "Halo!"}
```

### Konsep 2: Request & Response Model (Pydantic)
FastAPI membaca type hint class Pydantic Anda untuk memvalidasi input otomatis:
```python
from pydantic import BaseModel

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    answer: str

@app.post("/api/v1/chat", response_model=ChatResponse)
def handle_chat(req: ChatRequest):
    # req.message sudah otomatis divalidasi sebagai string
    return ChatResponse(answer=f"Anda berkata: {req.message}")
```
*Di project ini, semua schema sudah siap di file `PHASE2/HR-Agent/src/contracts.py`!*

### Konsep 3: Dependency Injection (`Depends`)
Ini adalah fitur andalan FastAPI untuk modularitas kode, terutama untuk:
- Auth (memeriksa Bearer Token)
- Mengambil koneksi Database / Cache / Service Agent

```python
from fastapi import Depends, Header, HTTPException, status

def get_current_user(authorization: str = Header(...)):
    # Format: "Bearer token-alya"
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid auth header")
    token = authorization.split(" ")[1]
    if token == "token-alya":
        return {"id": "EMP-001", "role": "employee"}
    raise HTTPException(status_code=401, detail="Unauthorized")

@app.get("/api/v1/profile")
def my_profile(user: dict = Depends(get_current_user)):
    return user
```

### Konsep 4: Status Code & HTTP Exceptions
Mengembalikan error secara formal:
```python
from fastapi import HTTPException, status

# 401 Unauthorized (Belum login/token salah)
# 403 Forbidden (Sudah login, tapi bukan hak aksesnya, misal: non-admin)
# 404 Not Found (Data tidak ditemukan)
# 422 Unprocessable Entity (Format JSON salah/field kurang - ditangani otomatis)
if user["role"] != "monitoring_admin":
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Only monitoring_admin can access this resource"
    )
```

### Konsep 5: Interactive Docs (Swagger UI)
FastAPI otomatis membuat dokumentasi interaktif tanpa coding tambahan.
Ketika server berjalan, buka browser di:
`http://localhost:8000/docs`
Anda bisa mencoba semua endpoint langsung dari browser!

---

## 3. Peta Kebutuhan Endpoint di Project HR-Agent

Berdasarkan `tests/test_api.py`, `src/contracts.py`, dan `src/api.py`, aplikasi butuh:

| Endpoint | Method | Auth | Role Akses | Fungsi |
|---|---|---|---|---|
| `/healthz` | GET | Tidak | Public | Healthcheck server (`{"status": "ok"}`) |
| `/api/v1/chat` | POST | Ya | Employee / Admin | Kirim pesan percakapan ke Agent |
| `/api/v1/proposals/{proposal_id}/confirm` | POST | Ya | Pemilik proposal | Konfirmasi pengajuan cuti (idempotent) |
| `/api/v1/leave-requests` | GET | Ya | Employee (data sendiri) | Riwayat cuti karyawan yang login |
| `/api/v1/leave-balances` | GET | Ya | Employee (data sendiri) | Cek sisa saldo cuti |
| `/api/v1/traces/{trace_id}` | GET | Ya | Pemilik trace / Admin | Melihat audit trace proses agent |
| `/api/v1/monitoring/summary` | GET | Ya | `monitoring_admin` saja | Dashboard metrik performa & biaya |
| `/api/v1/monitoring/alerts` | GET | Ya | `monitoring_admin` saja | Daftar alert anomali / eskalasi |

---

## 4. Rencana Langkah Belajar & Implementasi (Step-by-Step)

### Tahap 1: Pengenalan Mandiri (Waktu: 15–30 Menit)
1. **Eksperimen File Mini:**
   Buat file percobaan sementara (misal `playground.py`):
   ```python
   from fastapi import FastAPI
   import uvicorn

   app = FastAPI()

   @app.get("/")
   def hello():
       return {"pesan": "FastAPI berhasil jalan!"}

   if __name__ == "__main__":
       uvicorn.run(app, host="127.0.0.1", port=8000)
   ```
2. Jalankan di terminal: `python playground.py`
3. Buka browser: `http://localhost:8000/docs` untuk melihat Swagger UI.

### Tahap 2: Memahami Dependency Auth di Project (Security & Context)
Di project ini, user diidentifikasi melalui header `Authorization: Bearer <token>`.
- Token `token-alya` $\rightarrow$ Employee Alya
- Token `token-bima` $\rightarrow$ Employee Bima
- Token `token-admin` $\rightarrow$ Role `monitoring_admin`
Buat dependency function di `api.py`:
```python
def get_current_user(authorization: str = Header(...)) -> AuthContext:
    ...
```

### Tahap 3: Implementasi Factory Pattern (`create_app`)
File `src/api.py` menggunakan fungsi pabrik `create_app(...)`:
```python
def create_app(*, settings=None, repository=None, cache=None, agent=None) -> FastAPI:
    app = FastAPI(title="HR Agent API", version="1.0.0")

    # 1. Mount endpoint /healthz
    # 2. Injeksi dependencies (agent, repository, cache) ke state aplikasi atau Depends
    # 3. Mount endpoint chat, traces, proposals, leave, monitoring
    return app
```

### Tahap 4: Menjalankan Testing API
Jalankan unit test yang sudah disediakan untuk menguji API Anda secara bertahap:
```powershell
pytest PHASE2\HR-Agent\tests\test_api.py -v
```

---

## 5. Cara Menjalankan Server Lokal (Development)

Setelah implementasi dibuat di `src/api.py` dan `app.py`:
```powershell
cd PHASE2\HR-Agent
uvicorn src.api:create_app --factory --reload --port 8000
```
- `--factory`: Memberitahu uvicorn bahwa `create_app` adalah fungsi yang mengembalikan instance `FastAPI`.
- `--reload`: Server otomatis restart saat Anda menyimpan perubahan file `.py`.

---

## 6. Checklist Kesiapan Anda
- [ ] Paham beda method GET (baca) dan POST (kirim data).
- [ ] Paham peran Pydantic Model untuk request body (`contracts.ChatRequest`).
- [ ] Paham cara kerja Header `Authorization: Bearer <token>` menggunakan `Header()` atau `Security()`.
- [ ] Siap mengedit `PHASE2/HR-Agent/src/api.py` langkah demi langkah bersama AI assistant.
