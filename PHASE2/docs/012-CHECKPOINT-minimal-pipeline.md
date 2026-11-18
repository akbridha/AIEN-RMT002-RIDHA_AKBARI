# 012 — Checkpoint: Minimal Pipeline Verified

**Tanggal checkpoint:** 18 November 2026  
**Status sistem:** Streamlit (container) → FastAPI → PostgreSQL RDBMS + pgvector — **BERJALAN**

---

## Ringkasan Eksekutif

Sistem minimal telah berhasil dijalankan secara end-to-end:
- Chat dari Streamlit yang di-deploy dalam container
- Menekan endpoint FastAPI `/api/v1/chat`
- Terhubung ke RDBMS PostgreSQL (saldo, leave request) dan pgvector (kebijakan HR)

Hasil scan menyeluruh terhadap [`submission-checklist.md`](../HR-Agent/submission-checklist.md) menunjukkan **~65% butir terpenuhi** (11 dari 17). Sisa pekerjaan bukan lagi implementasi kode baru, melainkan artefak dokumentasi dan bukti pengujian.

---

## Status per Butir Submission Checklist

### ✅ Terpenuhi (11 dari 17)

| # | Butir Checklist | Bukti / File |
|---|---|---|
| 1 | `Dockerfile` lengkap; build tanpa API key; berjalan sebagai non-root | [`Dockerfile`](../HR-Agent/Dockerfile) — `appuser` UID 1000, CMD uvicorn factory |
| 2 | `.dockerignore` memblokir `.env`, venv, cache | [`HR-Agent/.dockerignore`](../HR-Agent/.dockerignore) |
| 3 | Grader dapat jalankan urutan `docker compose` tanpa Python di host | [`docker-compose.yml`](../HR-Agent/docker-compose.yml) — 4 service self-contained |
| 4 | FastAPI terhubung ke Streamlit yang disediakan | [`src/api.py`](../HR-Agent/src/api.py) ↔ [`app.py`](../HR-Agent/app.py); `API_URL=http://api:8000` |
| 5 | Policy indexing menghasilkan chunk versioned dan vector dimensi sesuai | [`src/setup_lab.py`](../HR-Agent/src/setup_lab.py) — `version`, `effective_date`, embedding 1536-dim (`text-embedding-3-small`) |
| 6 | Pertanyaan kebijakan menampilkan sitasi valid | [`src/agent.py`](../HR-Agent/src/agent.py) — validasi `[HR-XXX-YYY]` vs `retrieved_docs`; sitasi palsu → `abstained` |
| 7 | Akses lintas pegawai diblokir | `get_my_leave_balance` di-bind ke `auth.employee_id`; trace cross-read → HTTP 403 (`test_trace_cannot_be_read_by_another_employee`) |
| 8 | Proposal tidak menulis `leave_request` sebelum konfirmasi | `prepare_leave_request` → `save_proposal()` saja; write ke DB hanya di `confirm_proposal()` |
| 9 | Konfirmasi ulang dengan key sama tidak membuat duplicate | [`src/repository.py`](../HR-Agent/src/repository.py) — `idempotency_key` check; `idempotent_replay=True` jika key sama |
| 10 | Semua request berstatus `pending_manager_review` | Status hardcoded di `repository.py` baris 134, 147, 420, 432 — tidak ada path menuju `approved` via chat |
| 11 | `/healthz` dan `/readyz` merespons | [`src/api.py`](../HR-Agent/src/api.py) — `/healthz` → `{"status":"ok"}`; `/readyz` cek koneksi DB |

---

### ❌ Belum Terpenuhi (6 dari 17) — Prioritas Sisa Pekerjaan

| Prioritas | Butir Checklist | Kekurangan | Langkah |
|---|:---|---|---|
| 🔴 **Kritis** | `pytest -m "not live"` lulus | Test suite sudah ada di [`tests/`](../HR-Agent/tests/) tapi belum ada bukti dijalankan & lulus | Jalankan `pytest -m "not live"` di container atau env lokal, dokumentasikan hasilnya |
| 🔴 **Kritis** | Diagram arsitektur (trust boundary, cache, telemetry, confirmation flow) | [`architecture.md`](../HR-Agent/architecture.md) masih berisi 1 kalimat template, belum ada diagram | Isi [`templates/architecture.md`](../HR-Agent/templates/architecture.md) dengan diagram ASCII/Mermaid minimal |
| 🔴 **Kritis** | Live evaluation report ≥ 15 kasus | Kasus ada di [`data/evaluation_cases.json`](../HR-Agent/data/evaluation_cases.json), runner ada di [`src/run_evaluation.py`](../HR-Agent/src/run_evaluation.py), tetapi folder `outputs/` belum ada | Jalankan `python -m src.run_evaluation <url> <token>` dan commit hasilnya |
| 🟡 **Penting** | README diuji dari environment bersih | [`README.md`](../HR-Agent/README.md) masih berisi konten template starter, bukan keputusan teknis proyek ini | Update dengan: model yang dipakai, langkah setup aktual, hasil uji bersih |
| 🟡 **Penting** | Risk register (owner, mitigation, evidence) | Tidak ada file risk register di project | Buat `PHASE2/docs/risk-register.md` menggunakan template risiko |
| 🟡 **Penting** | Screenshot UI, monitoring, dan hasil test | Folder `assets/` kosong/tidak ada | Simpan screenshot Streamlit aktif + hasil test ke `HR-Agent/assets/` |

---

### 🟡 Sebagian Terpenuhi

| Butir | Status |
|---|---|
| Seed & OpenAPI dalam container berhasil | Seed (`setup_lab`) ✅. OpenAPI otomatis dari FastAPI ✅. Test **dalam** container belum dibuktikan secara tertulis. |
| Demo 5–7 menit dengan backup output | Template tersedia di [`templates/demo-script.md`](../HR-Agent/templates/demo-script.md) — belum diisi dan dilatih |

---

## Komponen Teknis yang Sudah Terimplementasi

```
Streamlit (port 8501)
    │  Bearer token (SHA-256 hash di DB)
    ▼
FastAPI  /api/v1/chat          → AgentService (agentic loop, max 5 turns)
         /api/v1/action-proposals/{id}/confirm  → confirm_proposal (idempotent)
         /api/v1/leave-requests/me
         /api/v1/traces/{id}  (redacted, owner-only)
         /api/v1/monitoring/* (admin-only)
         /healthz  /readyz
    │
    ├── ToolExecutor
    │     ├── search_hr_policy      → RetrievalService (Lexical + pgvector RRF + keyword rerank)
    │     ├── get_my_leave_balance  → PostgresRepository (identity-bound)
    │     ├── prepare_leave_request → domain.validate_leave_request() → save_proposal()
    │     └── create_hr_ticket      → repository.create_ticket()
    │
    ├── PostgreSQL (pgvector:pg16)
    │     ├── RDBMS: employee, leave_balance, leave_request, hr_ticket, agent_trace
    │     └── Vector: policy_chunk (dim=1536, cosine)
    │
    └── Redis (rate-limit cache, retrieval TTL cache — NullCache jika tidak tersedia)
```

---

## Pemetaan Kode → Checklist

| Modul | Fungsi Checklist yang Dicakup |
|---|---|
| [`src/domain.py`](../HR-Agent/src/domain.py) | Hari kerja, validasi tanggal terbalik, weekend 0 hari, saldo tidak cukup |
| [`src/security.py`](../HR-Agent/src/security.py) | Redaksi PII (email, telp, token, diagnosis medis), stable safety ID |
| [`src/agent.py`](../HR-Agent/src/agent.py) | Validasi sitasi, outcome abstained jika bukti tidak ada, trace tanpa raw message |
| [`src/repository.py`](../HR-Agent/src/repository.py) | Idempotency, `pending_manager_review`, akses identity-bound, overlap check |
| [`src/retrieval.py`](../HR-Agent/src/retrieval.py) | Hybrid retrieval (lexical + vector RRF), keyword rerank, cache TTL |
| [`tests/test_domain.py`](../HR-Agent/tests/test_domain.py) | 4 test domain rules deterministik |
| [`tests/test_actions.py`](../HR-Agent/tests/test_actions.py) | Idempotency, cross-identity, expired proposal |
| [`tests/test_retrieval_security.py`](../HR-Agent/tests/test_retrieval_security.py) | Retrieval lexical preference, redaksi PII, cross-employee tool bound |
| [`tests/test_api.py`](../HR-Agent/tests/test_api.py) | Contract health, auth, monitoring admin-only, trace isolation |
| [`tests/test_agent_reliability.py`](../HR-Agent/tests/test_agent_reliability.py) | Provider failure → abstained, sitasi palsu → abstained, chunk stability |

---

## Estimasi Persentase Completion

| Dimensi | Persen |
|---|---|
| Implementasi kode (backend logic) | ~90% |
| Infrastruktur Docker | ~95% |
| Test suite (kode sudah ada) | ~70% — butuh dijalankan & dibuktikan lulus |
| Dokumentasi & artefak deliverable | ~30% — diagram, risk register, screenshot belum ada |
| **Total submission-checklist** | **~65% (11/17 butir)** |

---

## Langkah Selanjutnya (Urutan Prioritas)

```
1. pytest -m "not live"              → verifikasi & dokumentasikan output
2. python -m src.run_evaluation      → hasilkan outputs/evaluation_report.json
3. Isi architecture.md               → diagram Mermaid/ASCII + ADR
4. Buat docs/risk-register.md        → owner, mitigation, evidence
5. Update README.md                  → langkah setup aktual + model yang dipakai
6. Ambil screenshot UI & test        → simpan ke assets/
7. Latih demo 5–7 menit             → isi templates/demo-script.md
```
