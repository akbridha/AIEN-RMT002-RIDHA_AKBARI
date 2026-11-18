# 013 — Penjelasan Reasoning Loop dan Mekanisme SQL Tool

**Target Pembaca:** Pemula / AI Engineer Newbie  
**Topik:** Bagaimana AI Agent Mengambil Data Database, Bagaimana Reasoning Loop Bekerja, dan Kapan Loop Berhenti  
**Konteks Kode:** Project HR-Agent Milestone 2  

---

## 1. Mitos vs Fakta: Siapa yang Menulis dan Mengeksekusi SQL?

Saat pertama kali belajar AI Agent, banyak orang mengira AI langsung menulis perintah SQL mentah secara bebas lalu mengeksekusinya ke database:

```
❌ Mitos (Text-to-SQL Liar):
Pengguna: "Berapa saldo cuti saya?"
AI: "SELECT * FROM leave_balance WHERE employee_id = '...'" (AI bikin SQL sendiri)
Bahaya: Rawan SQL Injection, halusinasi nama kolom/tabel, dan membocorkan data orang lain.
```

Pada sistem produksi enterprise seperti project HR-Agent ini, arsitektur yang digunakan adalah **Deterministic Tool Execution (Function Calling)**:

```
✅ Fakta (Tool Calling Terkendali):
Pengguna: "Berapa saldo cuti saya?"
    │
    ▼
1. AI/LLM hanya memutuskan NAMA TOOL:
   "Saya butuh saldo cuti, tolong panggil fungsi: get_my_leave_balance()"
    │
    ▼
2. Kode Python developer yang menangkap permintaan tersebut di `src/tools.py`
    │
    ▼
3. Kode Python developer yang menjalankan SQL yang SUDAH DITULIS sebelumnya di `src/repository.py`
```

### Bukti Langsung di Kode:
Lihat [`src/repository.py`](../HR-Agent/src/repository.py) baris 290–300:
```python
def get_balances(self, employee_id: str) -> list[LeaveBalance]:
    with self.pool.connection() as conn:
        with conn.cursor() as cur:
            # Query ini ditulis secara permanen oleh developer, BUKAN oleh AI:
            cur.execute(
                "SELECT leave_type, available_days, as_of_date FROM leave_balance WHERE employee_id = %s",
                (employee_id,),  # ID pegawai diambil dari token JWT/Bearer yang valid, bukan dari teks obrolan AI
            )
            rows = cur.fetchall()
            ...
```

**Kesimpulan Keamanan:**  
AI tidak pernah diberikan akses menulis string SQL sembarangan. AI hanya bertindak sebagai "operator saklar" yang memilih tool mana yang perlu dijalankan. Identitas user (`employee_id`) di-bind secara paksa oleh backend Python dari token login, sehingga AI tidak bisa dibohongi oleh prompt injection untuk membuka data pegawai lain.

---

## 2. Apa Itu Reasoning Loop (Agentic Loop)?

**Reasoning Loop** (sering disebut pola *ReAct: Synergizing Reasoning and Acting*) adalah siklus berulang di mana AI mengevaluasi kondisi percakapan saat ini, memutuskan tindakan apa yang perlu diambil, melihat hasil tindakan tersebut, lalu berpikir kembali sampai mendapatkan jawaban akhir.

### Analogi Dunia Nyata:
Bayangkan Anda adalah staf resepsionis HR:
1. **Putaran 1:** Karyawan bertanya: *"Berapa sisa cuti saya?"*  
   Anda sadar: Anda tidak hafal data di kepala Anda. Anda membuka laci lemari arsip (menjalankan Tool).
2. **Putaran 2:** Anda membaca lembar arsip: *"Sisa cuti Alya = 8 hari"*.  
   Sekarang Anda sudah memegang fakta tersebut. Anda tidak butuh buka laci lagi. Anda berbicara ke karyawan: *"Sisa cuti Anda 8 hari."*

---

## 3. Komponen Kode yang Terlibat dalam Reasoning Loop

Semua orkestrasi reasoning loop berada di [`src/agent.py`](../HR-Agent/src/agent.py) pada class `AgentService.run()`.

```
                    ┌─────────────────────────┐
                    │       User Prompt       │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │ messages = [user_msg]   │◄────────────────────────┐
                    └────────────┬────────────┘                         │
                                 │                                      │
                                 ▼                                      │
┌────────────────────────────────────────────────────────┐              │
│ 1. AI Berpikir (LLM Call via src/providers.py)         │              │
│    Model melihat: System Prompt + messages + Tools     │              │
└────────────────────────┬───────────────────────────────┘              │
                         │                                              │
                         ▼                                              │
               Apakah AI minta Tool?                                    │
              /                     \                                   │
       [YA]  /                       \ [TIDAK]                          │
            ▼                         ▼                                 │
┌───────────────────────────┐   ┌───────────────────────────┐           │
│ 2. Eksekusi Tool          │   │ Final Text Answer         │           │
│    (src/tools.py          │   │ (Loop selesai / BREAK)    │           │
│     & src/repository.py)  │   └─────────────┬─────────────┘           │
└───────────┬───────────────┘                 │                         │
            │                                 │                         │
            ▼                                 │                         │
┌───────────────────────────┐                 │                         │
│ 3. Simpan Hasil Tool      │                 │                         │
│    messages.append(hasil) ├─────────────────┘                         │
└───────────────────────────┘                                           │
            │                                                           │
            └───────────────────────────────────────────────────────────┘
                           Ulangi Putaran (Turn + 1)
```

### Pembagian Tugas per Modul:
| File | Tanggung Jawab |
|---|---|
| [`src/agent.py`](../HR-Agent/src/agent.py) | **Sutradara / Conductor:** Mengatur `while` loop, melacak riwayat pesan, membatasi putaran, menghitung token, mencatat audit trace. |
| [`src/providers.py`](../HR-Agent/src/providers.py) | **Jembatan LLM:** Berkomunikasi dengan OpenAI API menggunakan format Function Calling. |
| [`src/tools.py`](../HR-Agent/src/tools.py) | **Router Saklar:** Menerima nama tool dari AI, memvalidasi parameter input (via Pydantic), dan menyalurkannya ke repositori atau retrieval. |
| [`src/repository.py`](../HR-Agent/src/repository.py) | **Konektor RDBMS:** Mengeksekusi SQL riil ke PostgreSQL untuk tabel terstruktur (`leave_balance`, `leave_request`, `hr_ticket`). |
| [`src/retrieval.py`](../HR-Agent/src/retrieval.py) | **Mesin Hybrid Search:** Mengambil teks kebijakan tidak terstruktur menggunakan gabungan pgvector (semantic) dan BM25/lexical search. |

---

## 4. Bedah Kode: Bagaimana Loop Berjalan?

Mari kita lihat baris kode asli pada [`src/agent.py`](../HR-Agent/src/agent.py):

```python
turns = 0
while turns < self.settings.max_agent_turns:  # Default: max 5 putaran
    turns += 1

    # Langkah A: Minta respon dari LLM
    turn = self.provider.respond(
        input_data=messages,
        instructions=SYSTEM_INSTRUCTIONS,
        tools=TOOL_SCHEMAS,
        safety_identifier=safety_id,
        max_output_tokens=self.settings.max_output_tokens,
    )
    total_input_tokens += turn.input_tokens
    total_output_tokens += turn.output_tokens

    # Langkah B: Periksa apakah LLM meminta pemanggilan tool
    if turn.tool_calls:
        for tc in turn.tool_calls:
            # Cegah tool calls berlebihan dalam 1 turn
            if len(tool_summaries) >= self.settings.max_tool_calls:
                break

            # Eksekusi tool nyata melalui Python
            result, prop = self.tools.execute(tc.name, tc.arguments, auth)

            # Catat panggilan ke messages agar LLM tahu hasilnya
            messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": tc.call_id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                }],
            })
            messages.append({
                "role": "tool",
                "tool_call_id": tc.call_id,
                "content": json.dumps(result, default=str),
            })

        # Jika LLM menghasilkan teks sekaligus tanpa tool baru
        if turn.text and not turn.tool_calls:
            final_answer = turn.text
            break
    else:
        # Langkah C: LLM menghasilkan jawaban teks akhir (tidak meminta tool lagi)
        final_answer = turn.text
        break
```

---

## 5. Bagaimana Sistem Memutuskan Loop Lanjut atau Berhenti?

Ada **3 skenario penentu** berakhirnya loop:

### Skenario 1: Berhenti Normal (AI Merasa Informasi Sudah Lengkap)
* **Kondisi:** `if not turn.tool_calls: final_answer = turn.text; break`
* **Logika:** AI menganalisis bahwa data yang ada di `messages` (pertanyaan awal + hasil observasi tool sebelumnya) sudah cukup untuk menjawab pertanyaan pengguna. Model tidak lagi memancarkan instruksi tool call, melainkan memancarkan string kalimat jawaban. Loop langsung selesai (`break`).

### Skenario 2: Berhenti karena Batas Keamanan Putaran (Safety Cap)
* **Kondisi:** `turns >= self.settings.max_agent_turns` (default 5 putaran)
* **Tujuan:** Mencegah **Infinite Loop** dan pembengkakan biaya token. Jika model mengalami *looping kebingungan* (memanggil tool yang sama berulang-ulang tanpa henti), perulangan `while` akan otomatis selesai paksa setelah batas putaran tercapai.

### Skenario 3: Batas Jumlah Tool Call (Tool Limit)
* **Kondisi:** `if len(tool_summaries) >= self.settings.max_tool_calls:`
* **Tujuan:** Membatasi berapa banyak tool yang boleh dieksekusi dalam satu sesi permintaan pengguna, guna melindungi latency API dan rate limit database.

---

## 6. Simulasi Konkret: Pengajuan Cuti 2 Hari

Berikut adalah jejak langkah (*trace step-by-step*) yang terjadi di balik layar saat pengguna berinteraksi:

### Input Pengguna:
> *"Tolong siapkan pengajuan cuti tahunan dari tanggal 2026-12-01 sampai 2026-12-02 karena urusan keluarga."*

---

### 🔄 Putaran 1 (Turn 1):
1. **State `messages`:**
   - User: *"Tolong siapkan pengajuan cuti tahunan..."*
2. **AI Reasoning:**
   - *"Pengguna ingin mengajukan cuti tahunan. Berdasarkan aturan, saya harus memvalidasi saldo dan aturan kerja sebelum membuat proposal."*
   - *"Saya harus menjalankan tool `prepare_leave_request` dengan parameter tanggal yang diminta."*
3. **AI Action:**
   - Memanggil `prepare_leave_request(start_date="2026-12-01", end_date="2026-12-02", leave_type="annual", reason="urusan keluarga")`.
4. **Eksekusi Python (`src/tools.py` & `src/domain.py`):**
   - Ambil saldo riil pegawai dari DB: `available_days = 8`.
   - Hitung hari kerja: `2026-12-01` (Senin) s/d `2026-12-02` (Selasa) = **2 hari kerja**.
   - Cek overlap di DB: Tidak ada pengajuan lain yang bertabrakan.
   - Buat draft proposal: `AP-9A4B2C10` (status: tersimpan di memori/DB sementara dengan masa kedaluwarsa 15 menit).
5. **Feed Hasil ke Loop:**
   - Hasil tool ditambahkan ke `messages` sebagai `role: tool`.

---

### 🔄 Putaran 2 (Turn 2):
1. **State `messages`:**
   - User: *"Tolong siapkan pengajuan cuti..."*
   - Assistant: *(Tool call `prepare_leave_request`)*
   - Tool Result: `{"proposal_id": "AP-9A4B2C10", "business_days": 2, "validation_summary": ["Saldo cukup..."]}`
2. **AI Reasoning:**
   - *"Proposal sudah berhasil dibuat. Informasi sudah lengkap. Saya tidak perlu memanggil tool lain. Sekarang saya jelaskan rincian proposal kepada pengguna dan minta mereka mengonfirmasi lewat tombol."*
3. **AI Action:**
   - Tidak ada tool call.
   - Mengeluarkan teks akhir:
     > *"Pengajuan cuti tahunan Anda untuk 1–2 Desember 2026 (2 hari kerja) telah disiapkan dengan ID Proposal **AP-9A4B2C10**. Silakan periksa kembali dan tekan tombol konfirmasi di bawah untuk mengirimkannya ke manajer."*
4. **Loop Berhenti:**
   - `turn.tool_calls` kosong → `break`.
   - Response dikirim ke Streamlit UI.

---

## 7. Rangkuman Konsep Kunci bagi AI Engineer

1. **AI adalah Decision Engine, bukan Execution Engine:** AI memutuskan *kapan* dan *apa* yang perlu dilakukan; fungsi Python dan Database yang melakukan komputasi nyata.
2. **Deterministic Security:** Akses data sensitif tidak boleh bergantung pada kejujuran prompt AI. Parameter penting seperti `employee_id` harus diinjeksi langsung oleh kode backend dari sesi autentikasi.
3. **Loop Boundedness:** Setiap agentic loop wajib memiliki batas maksimal (*hard ceiling*) baik berupa `max_turns`, `max_tool_calls`, maupun `timeout`, untuk menjamin stabilitas sistem di lingkungan produksi.
