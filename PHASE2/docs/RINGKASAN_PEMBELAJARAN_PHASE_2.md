# Ringkasan Pembelajaran Phase 2 - Applied AI Engineer Bootcamp

**Periode:** Week 05 - Week 06 (10 hari pembelajaran)  
**Tanggal:** November 2026

---

## 📋 Daftar Isi

1. [Week 05 Day 01 - Principles of AI & AI Gateway](#week-05-day-01)
2. [Week 05 Day 02 - Prompt Technique and Optimization](#week-05-day-02)
3. [Week 05 Day 03 - Data Infrastructure for AI](#week-05-day-03)
4. [Week 05 Day 04 - RAG dengan LangChain](#week-05-day-04)
5. [Week 05 Day 05 - Reliability Layer & Function Calling](#week-05-day-05)
6. [Week 06 Day 01 - RAG untuk Data Terstruktur](#week-06-day-01)
7. [Week 06 Day 02 - Lab RAG RuangKarya](#week-06-day-02)
8. [Week 06 Day 03 - Consuming and Presenting AI Output](#week-06-day-03)
9. [Week 06 Day 04 - AI Agent Part 1](#week-06-day-04)
10. [Week 06 Day 05 - AI Agent Part 2](#week-06-day-05)

---

## <a name="week-05-day-01"></a>Week 05 Day 01: Principles of AI, LLM & Local AI Gateway Setup

### 🎯 Tujuan Pembelajaran
- Memahami peran AI Gateway dalam arsitektur enterprise
- Menginstal dan menjalankan OmniRoute server lokal
- Mengonfigurasi provider OpenAI dan batas kuota
- Menyiapkan provider fallback untuk high availability
- Membuat local API key dengan hard limit pricing

### 📚 Materi Utama

**Konsep Kunci:**
- **AI Gateway (Smart Proxy Router)** sebagai solusi enterprise untuk sentralisasi kredensial, standardisasi endpoint, fallback routing, dan observabilitas
- Menghindari hardcoding API key langsung ke aplikasi klien
- Risk mitigation: keamanan, rate limiting, kontrol biaya, dan kuota pemakaian

**Teknologi yang Digunakan:**
- OmniRoute: Local AI Gateway berbasis Node.js/npm atau Docker
- OpenAI API: Provider utama dengan hard limit budget 5 USD per siswa
- OpenRouter Free Tier & OpenCode Zen Free Tier: Provider fallback tanpa biaya
- Python 3.8+ untuk skrip verifikasi

**Arsitektur:**
```
Aplikasi Lokal → OmniRoute (Port 20128) → OpenAI (Primary)
                      ↓
                  Fallback: OpenRouter/OpenCode Zen
```

**Fitur Lanjutan (Opsional):**
- RTK (Rust Token Killer): kompresi token input
- Caveman: pemangkas token output untuk penghematan biaya

### 🔑 Pembelajaran Praktis
- Setup environment dengan Node.js dan npm
- Konfigurasi endpoint OpenAI-compatible (`/v1`)
- Membuat local API key dengan batasan penggunaan
- Verifikasi konektivitas menggunakan `/v1/models` dan `/v1/chat/completions`
- Monitoring alert threshold di 80% kuota

---

## <a name="week-05-day-02"></a>Week 05 Day 02: Prompt Technique and Optimization

### 🎯 Tujuan Pembelajaran
- Menerapkan structured prompting untuk hasil yang terarah
- Menggunakan chain-of-thought reasoning untuk tugas multi-langkah
- Menerapkan few-shot prompting dengan contoh konsisten
- Mengevaluasi dan mengoptimasi prompt secara sistematis

### 📚 Materi Utama

**Masalah yang Diatasi:**
- Halusinasi: model mengarang jawaban yang terdengar meyakinkan padahal tidak akurat
- Inisiatif terbuang: model menebak-nebak karena instruksi tidak terstruktur
- Token waste: instruksi bertele-tele memboroskan token tanpa hasil lebih baik

**Teknik Prompting:**
1. **Structured Prompting:** Memisahkan role/context, instruction/task, data input, dan output format secara eksplisit
2. **Chain-of-Thought Reasoning:** Mendorong model bernalar secara bertahap
3. **Few-shot Prompting:** Menyertakan contoh input-output yang relevan dan konsisten

**Siklus Optimasi:**
Draft → Test → Evaluate (5 dimensi) → Refine → Final

**5 Dimensi Evaluasi:**
- Akurasi/Correctness
- Konsistensi
- Relevansi
- Clarity
- Efficiency (token usage)

### 🔑 Pembelajaran Praktis
- Menulis dan menguji prompt secara terprogram via Claude API atau OpenAI API
- Menggunakan `ask_llm()` function untuk konsistensi testing
- Iterasi berulang sampai hasil stabil dan konsisten
- API cost rendah (< USD 1 untuk notebook lengkap)

---

## <a name="week-05-day-03"></a>Week 05 Day 03: Data Infrastructure for AI

### 🎯 Tujuan Pembelajaran
- Menjelaskan kebutuhan vector database vs pencarian tradisional
- Setup dan indexing dengan Pinecone
- Melakukan insert dan query data vektor
- Mengintegrasikan vector database ke aplikasi

### 📚 Materi Utama

**Masalah yang Diatasi:**
- LLM tidak mengingat data privat atau data lebih baru dari waktu training
- Perlu transformasi teks menjadi vector untuk pencarian berdasarkan kemiripan makna

**Alur Sistem:**

**INDEXING (menyiapkan katalog vector):**
- Input: Katalog produk/dokumen
- Proses: Embedding dengan `text-embedding-3-small`
- Output: Disimpan ke Pinecone Index dengan namespace khusus

**RETRIEVAL (mencari produk relevan):**
- Input: Pertanyaan pengguna
- Proses: Query embedding → Similarity search dengan top-k filtering
- Output: Produk paling relevan dengan metadata

**Teknologi yang Digunakan:**
- OpenAI API: `text-embedding-3-small` untuk embedding
- Pinecone: managed vector database dengan free tier Starter (2GB storage)
- Python 3.10+ dan Jupyter Notebook

**Konsep Kunci:**
- Vector embedding: representasi numerik dari teks
- Similarity search: pencarian berdasarkan kemiripan vektor
- Metadata filtering: penyaringan berdasarkan atribut tambahan
- Namespace isolation: pemisahan data antar proyek

### 🔑 Pembelajaran Praktis
- Setup Pinecone index dengan konfigurasi yang sesuai
- Membuat embedding untuk katalog dan query
- Melakukan similarity search dengan confidence threshold
- Cost: biaya OpenAI < USD 1 untuk seluruh notebook

---

## <a name="week-05-day-04"></a>Week 05 Day 04: RAG dengan LangChain

### 🎯 Tujuan Pembelajaran
- Menjelaskan perbedaan tahap indexing dan query pada RAG
- Memuat dokumen PDF dan mempertahankan metadata
- Membagi dokumen menjadi chunk yang optimal
- Membuat embedding dan menyimpan ke Pinecone
- Menyusun RAG chain LangChain untuk menghasilkan jawaban grounded

### 📚 Materi Utama

**Retrieval-Augmented Generation (RAG) Pipeline:**

**INDEXING Phase:**
```
PDF Dokumen
    ↓
PyPDFLoader (per halaman)
    ↓
RecursiveCharacterTextSplitter (chunk 1000 char, overlap 200)
    ↓
OpenAI Embeddings (text-embedding-3-small)
    ↓
Pinecone Index (namespace: rag-handson)
```

**QUERY Phase:**
```
Pertanyaan Pengguna
    ↓
Embedding Query (vector)
    ↓
Similarity Retriever (top-k = 4)
    ↓
Grounded Prompt (context + question)
    ↓
OpenAI LLM (gpt-5.6-luna)
    ↓
Decision: Bukti cukup?
    ├── Ya → Jawaban grounded dengan sitasi
    └── Tidak → Fallback: "Informasi tidak ditemukan"
```

**Teknologi yang Digunakan:**
- LangChain: orkestrasi loader, splitter, retriever, prompt, dan chain
- OpenAI API: embedding dan LLM generation
- Pinecone: vector database
- PyPDF: membaca dokumen PDF
- Python 3.13 (3.10+ supported)
- Jupyter Notebook

**Konsep Kunci:**
- Document loading dengan metadata preservation
- Chunking strategy: RecursiveCharacterTextSplitter optimal untuk kebanyakan teks
- Retrieval quality: bergantung pada chunk size, overlap, dan similarity threshold
- Grounded generation: menjawab hanya berdasarkan konteks yang diambil

### 🔑 Pembelajaran Praktis
- Workflow lengkap dari PDF hingga jawaban grounded
- Testing retrieval sebelum LLM integration
- Handling fallback saat bukti tidak tersedia
- Sitasi otomatis: [1], [2], dst dari source dokumen

---

## <a name="week-05-day-05"></a>Week 05 Day 05: Reliability Layer - Function Calling & Validation

### 🎯 Tujuan Pembelajaran
- Menjelaskan peran function calling pada RAG, agent, dan automation
- Mendefinisikan strict tool schema untuk membatasi argumen model
- Memvalidasi input dan output dengan Pydantic v2
- Menegakkan allowlist, business rule, dan ownership
- Menerapkan retry terbatas hanya untuk transient error
- Menghasilkan fallback aman

### 📚 Materi Utama

**Reliability Boundary (dalam aplikasi, bukan model):**

```
Pertanyaan Pengguna + Context RAG
    ↓
OpenAI LLM (function request)
    ↓
RELIABILITY CHECKS:
├── Tool ada di allowlist? (Ya/Tidak)
├── Contract valid? (Pydantic validation)
├── Business rule & ownership valid? (Authorization)
├── Execute handler (authenticated user)
├── Transient error? (Retry max 3x)
└── Output valid? (Pydantic validation)
    ↓
Safe Fallback (tanpa detail internal) atau Jawaban Grounded
```

**Validasi Multi-Layer:**
1. **Allowlist:** Hanya tool terdaftar yang dapat dipanggil
2. **Contract Validation:** Input harus sesuai schema Pydantic
3. **Business Rule:** Ownership, permission, quota checks
4. **Authorization:** User authentication dan authorization
5. **Output Validation:** Hasil tool harus sesuai contract

**Retry Strategy:**
- Transient error (timeout, temporary unavailable): retry max 3x dengan exponential backoff
- Permanent error (forbidden, invalid input): langsung fallback

**Fallback Pattern:**
- Tidak mengekspos detail internal ke user
- Pesan yang aman dan dapat ditindaklanjuti
- Logging untuk debugging internal

**Teknologi yang Digunakan:**
- OpenAI Responses API: function calling dengan `gpt-5.6-luna`
- Pydantic v2: validasi contract input/output
- Tenacity: retry logic dengan exponential backoff dan jitter
- LangChain: reusable retriever dari RAG Day 04
- Pinecone: context dari namespace `rag-handson`
- Python 3.13

### 🔑 Pembelajaran Praktis
- Mendefinisikan tool schema yang ketat
- Implementasi validation gate sebelum execution
- Retry logic yang bijak untuk error transient
- Safe fallback pattern untuk error permanen
- Integration dengan RAG context dari session sebelumnya

---

## <a name="week-06-day-01"></a>Week 06 Day 01: RAG untuk Data Terstruktur

### 🎯 Tujuan Pembelajaran
- Menjalankan RAG pipeline untuk query database
- Menggunakan OpenAI untuk text-to-SQL
- Kombinasi LLM dengan database schema
- Keamanan data dan access control

### 📚 Materi Utama

**Perbedaan dengan RAG Unstruktur:**
- Input: Bukan dokumen, tapi database schema dan data terstruktur
- Query: Text-to-SQL dengan validasi
- Response: Data hasil SQL query + context dari LLM

**Setup:**
- Python 3.11+
- PostgreSQL read-only database
- OpenAI API key
- Virtual environment dengan venv atau pipenv

**Workflow:**
```
User Question
    ↓
OpenAI reads Schema
    ↓
Generate SQL Query
    ↓
Execute (parameterized) against Database
    ↓
Format Results
    ↓
Grounded Answer
```

**Security Practices:**
- Read-only database role
- Parameterized queries (prevent SQL injection)
- Limited column exposure (e.g., hide salary)
- Query result sanitization

### 🔑 Pembelajaran Praktis
- Setup PostgreSQL dengan schema untuk lab
- Membuat reader role dengan limited permissions
- Integration OpenAI API untuk SQL generation
- Testing query hasil untuk keamanan dan akurasi

---

## <a name="week-06-day-02"></a>Week 06 Day 02: Lab RAG RuangKarya

### 🎯 Tujuan Pembelajaran
- Praktik RAG dengan corpus Markdown dokumen nyata
- Similarity search dan metadata filtering
- Hybrid search (dense + BM25)
- Troubleshoot kasus retrieval yang kompleks

### 📚 Materi Utama

**Setup Lab:**
- Corpus: 10+ dokumen Markdown (panduan FAQ RuangKarya)
- Archive: dokumen lama untuk edge case testing
- Cache: local embedding storage untuk efficiency
- Pinecone namespace: unique per peserta

**4 Kasus yang Dipelajari:**

1. **Aturan Lama Muncul**
   - Masalah: Dokumen lama dalam hasil
   - Solusi: Filter metadata `status` sebelum retrieval

2. **Baris Tabel Terpotong**
   - Masalah: Data terstruktur dalam passage kehilangan konteks
   - Solusi: Passage design yang menjaga baris tetap utuh

3. **Ranking Tertukar**
   - Masalah: Dense search saja kurang tepat untuk kasus tertentu
   - Solusi: Hybrid search dengan BM25 + RRF (Reciprocal Rank Fusion)

4. **Data Tidak Ada**
   - Masalah: Menebak jawaban saat data tidak ditemukan
   - Solusi: Check passage support, jangan hallucinate

**Teknologi:**
- OpenAI Embeddings: `text-embedding-3-small`
- Pinecone: dense vector search + BM25 hybrid + metadata filtering
- Python-dotenv: environment variable management
- Caching: local `.cache/` untuk efficiency

### 🔑 Pembelajaran Praktis
- End-to-end lab dari setup hingga hasil
- Troubleshooting kasus RAG yang kompleks
- Hybrid search evaluation
- Documenting changes dan improvements per kasus

---

## <a name="week-06-day-03"></a>Week 06 Day 03: Consuming and Presenting AI Output

### 🎯 Tujuan Pembelajaran
- Membedakan output visual, naratif, dan dapat ditindaklanjuti
- Menunjukkan evidence dihitung sebelum dikirim ke model
- Mengonsumsi structured output dari OpenAI Responses API
- Membatasi output dengan JSON Schema dan Pydantic
- Menjelaskan mengapa output valid belum boleh otomatis execute action

### 📚 Materi Utama

**Tiga Bentuk Output:**

1. **Visual:** Grafik profit per kategori dan wilayah (Plotly)
2. **Naratif:** Laporan Markdown berbahasa Indonesia (grounded dari evidence)
3. **Actionable:** Rekomendasi JSON tervalidasi (NOT auto-execute)

**Pipeline Architecture:**
```
CSV Transaksi Sintetis
    ↓
Validasi Kolom, Tipe, Range
    ↓
Agregasi Pandas (deterministic)
    ↓
Evidence Summary JSON ← [Bukti Data Dihitung Lebih Dulu]
    ↓
Visualisasi Plotly
    ↓
Satu Panggilan OpenAI Responses API
    ↓
Structured Outputs (JSON Schema)
    ↓
Validasi Ulang (Pydantic)
    ↓
Laporan Markdown + Rekomendasi JSON + Status Approval
```

**Konsep Kunci:**
- **Evidence First:** Semua angka dihitung di kode sebelum dikirim ke LLM
- **Structured Output:** JSON Schema membatasi bentuk output
- **Double Validation:** Pydantic v2 untuk extra safety
- **Human Approval:** Rekomendasi JSON tidak auto-execute, tunggu approval
- **Guardrail:** Demo menolak output yang tidak sesuai format

**Teknologi yang Digunakan:**
- Python 3.11+
- Pandas: agregasi data deterministic
- Plotly: visualisasi interaktif
- OpenAI Responses API: structured outputs dengan `gpt-5.6-luna`
- Pydantic v2: contract validation
- Jupyter Notebook

**Struktur Project:**
```
data/
  └── retail_transactions.csv

src/
  ├── __init__.py
  ├── main.py          # entry point
  ├── pipeline.py      # orchestration
  ├── schemas.py       # Pydantic schemas
  └── validation_demo.py

tests/
  ├── test_pipeline.py
  └── test_schemas.py
```

### 🔑 Pembelajaran Praktis
- Evidence calculation sebelum LLM call
- JSON Schema definition untuk structured outputs
- Pydantic validation di input dan output
- Guardrail demo: rejection of invalid formats
- Testing pipeline end-to-end

---

## <a name="week-06-day-04"></a>Week 06 Day 04: AI Agent Part 1

### 🎯 Tujuan Pembelajaran
- Membedakan chatbot biasa dengan AI agent berbasis tool
- Menjelaskan siklus pikir → bertindak → amati pada reasoning loop
- Membaca dan menelusuri histori pemanggilan tool
- Menghubungkan satu loop agent ke berbagai sumber tool
- Membandingkan tool database buatan sendiri vs MCP

### 📚 Materi Utama

**Reasoning Loop (Think-Act-Observe):**
```
Pertanyaan Pengguna
    ↓
LLM Melihat Histori + Daftar Tool
    ├── Informasi cukup? → Jawaban Final
    └── Perlu tool? → Permintaan Tool + Argumen
            ↓
        Kode Eksekusi Tool (Bukan LLM!)
            ↓
        Hasil Menjadi Observasi
            ↓
        [Loop kembali ke LLM]
```

**Prinsip Penting:**
- LLM TIDAK menjalankan fungsi, API, SQL, atau MCP langsung
- LLM HANYA meminta pemanggilan tool
- Fungsi aplikasi menentukan kode apa yang benar-benar dijalankan
- Guardrail diterapkan oleh aplikasi, bukan model

**4 Sumber Tool yang Diintegrasikan:**

1. **Tool 1 — Python Function (Local)**
   - Contoh: Perhitungan margin deterministik
   - Kelebihan: Cepat, tidak ada network latency

2. **Tool 2 — Web API (Tavily)**
   - Contoh: Pencarian web untuk informasi terkini
   - Kelebihan: Real-time data
   - Memerlukan: `TAVILY_API_KEY`

3. **Tool 3 — PostgreSQL (Custom)**
   - Contoh: Query ke tabel `public.sales_datamart`
   - Keamanan: Parameterized queries
   - Memerlukan: `DATABASE_URI` (read-only recommended)

4. **Tool 4 — MCP (Model Context Protocol)**
   - Contoh: Tool dari `postgres-mcp`
   - Kelebihan: Standar terbuka untuk tool integration
   - Discovery otomatis tool yang tersedia

**Teknologi yang Digunakan:**
- Python 3.11+
- OpenAI API / Anthropic Claude / Google Gemini (pilih salah satu)
- Tavily API: web search
- PostgreSQL: structured data
- MCP: Model Context Protocol
- Jupyter Notebook

### 🔑 Pembelajaran Praktis
- Implementasi reasoning loop dari OpenAI atau Claude API
- Tool registry dan schema definition
- Error handling dan guardrail application
- Testing happy path dan failure path
- Membandingkan custom tool vs MCP integration

---

## <a name="week-06-day-05"></a>Week 06 Day 05: AI Agent Part 2

### 🎯 Tujuan Pembelajaran
- Menjelaskan perbedaan multi-tools dan multi-agent
- Mendefinisikan Agent, Task, Crew, dan tool di CrewAI
- Merancang urutan tool berdasarkan state dan hasil
- Membungkus fungsi Python menjadi CrewAI tool
- Menerapkan audit trail pada workflow yang mengubah data

### 📚 Materi Utama

**CrewAI Framework:**

**Konsep Dasar:**
- **Agent:** Entitas dengan LLM, tools, dan goal spesifik
- **Task:** Pekerjaan yang diberikan ke agent
- **Crew:** Kumpulan agent yang bekerja dalam koordinasi
- **Tool:** Fungsi yang dapat dijalankan agent

**Part 1 — Multi-Tools (Satu Agent, Empat Tool):**

**Workflow Update Nomor Telepon Pelanggan:**
```
Permintaan Pelanggan
    ↓
Agent CS Mengklasifikasi
    ├── Bukan update telepon → Teruskan ke CS berikutnya
    └── Update telepon → Lanjut ke pipeline

Pipeline 4 Tool Sequential:
1. Format Permintaan      → Normalkan email & phone
2. Verifikasi Akuan (DB)  → Query database, return VERIFIED/NOT_FOUND
3. Kirim OTP              → Generate OTP, simpan ke DB
4. Konfirmasi OTP         → Validasi OTP, update DB + Audit Log

Result: SUCCESS / FAILED / NOT_FOUND
```

**Database Schema:**
- `profiles` table: customer data
- `audit_log` table: trail of changes

**Part 2 — Multi-Agent (Beberapa Agent, Sequential Pipeline):**

**Workflow Research-Write-Review Newsletter:**
```
Topik Input
    ↓
[Agent 1: Researcher]
├─ Tool: Tavily Web Search
└─ Output: Research findings

    ↓
[Agent 2: Writer]
├─ Input: Research findings
├─ Task: Tulis newsletter
└─ Output: Draft newsletter

    ↓
[Agent 3: Reviewer] (bonus)
├─ Input: Draft newsletter
├─ Task: Review & refine
└─ Output: Final version
```

**Teknologi yang Digunakan:**
- CrewAI framework
- Python 3.11+
- PostgreSQL: customer database + audit log
- OpenAI / Anthropic / Gemini: LLM provider
- Tavily API: web search tool
- Jupyter Notebook

**Konsep Kunci:**
- **Multi-tools:** Urutan tool execution bergantung pada state dan hasil sebelumnya
- **Multi-agent:** Setiap agent memiliki goal dan expertise unik
- **Sequential Processing:** Output task satu menjadi input task berikutnya
- **Audit Trail:** Setiap perubahan data dicatat dengan timestamp dan user info
- **Parameterized SQL:** Prevent SQL injection pada tool database
- **Error Handling:** Graceful fallback jika tool gagal

### 🔑 Pembelajaran Praktis
- Definisi agent dengan specific goal dan tools
- Membungkus fungsi Python dengan `@tool` decorator
- Task sequencing dengan `context=[...]` parameter
- Database integration dengan parameterized queries
- Audit trail implementation
- Testing happy path, failure path, dan out-of-scope requests
- Identifikasi perbedaan edukasional vs production system

---

## 🎓 Kesimpulan Pembelajaran

### Progresif dari Dasar ke Kompleks

**Week 05 — Foundation:**
- Day 1: Infrastructure (AI Gateway)
- Day 2: Prompting (Optimization)
- Day 3: Data Layer (Vector Database)
- Day 4: RAG Pipeline (Document + LLM)
- Day 5: Reliability (Validation + Fallback)

**Week 06 — Advanced Applications:**
- Day 1: RAG untuk Data Terstruktur (Database)
- Day 2: Real-world RAG Lab (Troubleshooting)
- Day 3: Production Output Patterns (Visual + Narrative + Actionable)
- Day 4: AI Agent with Tools (Reasoning Loop)
- Day 5: Multi-Agent Workflows (CrewAI)

### Kemampuan Akhir yang Dimiliki

✅ Setup local AI gateway dengan fallback routing  
✅ Teknik prompting yang terstruktur dan optimized  
✅ Vector database setup untuk semantic search  
✅ End-to-end RAG pipeline (unstructured + structured data)  
✅ Output validation dengan JSON Schema dan Pydantic  
✅ Function calling dan tool execution dengan guardrail  
✅ Multi-agent orchestration dengan CrewAI  
✅ Audit trail dan database integration  
✅ Error handling, retry, dan fallback patterns  
✅ Production-ready design patterns  

### Teknologi Stack yang Dikuasai

**Infrastructure:**
- OmniRoute AI Gateway
- Node.js 18+, Python 3.10+

**Vector & Search:**
- Pinecone (Vector Database)
- OpenAI Embeddings

**LLM & APIs:**
- OpenAI API (gpt-5.6-luna, text-embedding-3-small)
- Anthropic Claude API
- Tavily Web Search API

**Frameworks & Libraries:**
- LangChain (RAG orchestration)
- CrewAI (Multi-agent framework)
- Pydantic v2 (Data validation)
- Tenacity (Retry logic)
- Plotly (Visualization)
- Pandas (Data processing)

**Database & Data:**
- Pinecone (Vector DB)
- PostgreSQL (Structured data)
- Jupyter Notebook (Development)

**Development Practices:**
- Parameterized queries (SQL injection prevention)
- Structured prompting
- Chain-of-thought reasoning
- Error handling & retry logic
- Audit trail implementation
- Output validation & guardrails
- Environment variable management

---

## 📌 Catatan Penting

1. **Cost Management:** Semua lab dirancang dengan budget kecil (< USD 1 per day umumnya)
2. **Security First:** Menggunakan read-only database, parameterized queries, allowlist
3. **Validation Layers:** Multi-layer validation (schema, business rule, output format)
4. **Production Considerations:** Setiap lab menyebutkan aspek yang berbeda untuk production
5. **Hands-on Approach:** 100% praktik dengan guided notebooks, bukan teori saja

---

**Generasi:** November 2026  
**Status:** Completed Phase 2, Ready for Phase 3
