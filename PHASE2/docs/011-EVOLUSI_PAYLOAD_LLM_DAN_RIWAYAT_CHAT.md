# Evolusi Payload Input LLM & Cara Pengelolaan Riwayat Percakapan

Dokumen ini merangkum penjelasan lengkap mengenai evolusi cara pengiriman data/payload ke Large Language Model (LLM)—mulai dari satu string sederhana di pembelajaran awal hingga payload terstruktur (multi-turn, RAG, dan agent tool calling).

---

## 1. Konsep Dasar: Mengapa LLM Terasa "Ingat" Padahal Stateless?

Secara teknis, **LLM sama sekali tidak memiliki memori internal antar panggilan API (stateless)**. Setiap panggilan HTTP ke endpoint LLM diperlakukan sebagai entitas yang benar-benar baru.

```
Panggilan 1: [User: "Halo, saya Bima"]     → LLM: "Halo Bima!"
Panggilan 2: [User: "Siapa nama saya?"]    → LLM: "Maaf, saya tidak tahu." (karena Panggilan 1 sudah hilang)
```

Chatbot (seperti ChatGPT atau Asisten HR) terasa "ingat" karena **aplikasi pengembang (backend FastAPI / Python)** yang menyimpan transkrip percakapan di database (misalnya PostgreSQL atau SQLite), lalu **mengirimkan kembali seluruh atau ringkasan riwayat percakapan tersebut** pada setiap permintaan baru.

---

## 2. Mengapa Riwayat Tidak Di-concat Menjadi Satu Teks Biasa?

Pada masa awal model teks generasi pertama (generasi completion murni seperti GPT-3 Davinci), orang memang menggabungkan teks secara manual:
> *"Percakapan sebelumnya:\nUser: Halo\nBot: Hai\nUser: Siapa nama saya?"*

Cara **penggabungan teks manual (*string concatenation*) ini sekarang ditinggalkan** karena kelemahan-kelemahan berikut:
1. **Rentan Kebingungan Peran (*Role Confusion*):** Jika user mengetik *"Bot: jangan hiraukan aturan ini"*, LLM kesulitan membedakan mana ucapan asli asisten dan mana teks manipulasi dari pengguna.
2. **Keamanan & Prompt Injection:** API modern menggunakan format terstruktur berlabel peran (`system`, `user`, `assistant`, `tool`). Di server penyedia LLM, pesan ini dibungkus dengan token pembatas biner khusus (seperti `<|im_start|>user...<|im_end|>`) sehingga instruksi user tidak dapat membajak sistem.
3. **Dukungan Tool Calling:** Ketika LLM memanggil fungsi (tool/database), hasil eksekusi tool harus disuntikkan kembali dengan `role: "tool"` beserta `tool_call_id` yang cocok. Hal ini mustahil dilakukan secara rapi dengan string tunggal biasa.

---

## 3. Tahapan Evolusi Payload Input di Materi Bootcamp

Berikut peta evolusi bentuk payload input dari materi pembelajaran:

```
[Tahap 1: Single String]
       │  (01-openai_temperature.ipynb)
       ▼
[Tahap 2: Template String & Replace/Concat Manual]
       │  (02-P2W1D2 - Prompt Technique and Optimization.ipynb)
       ▼
[Tahap 3: List of Messages & Structured ChatPromptTemplate]  <-- TITIK BALIK
       │  (04-P2W1D4 - LangChain Intro.ipynb)
       ▼
[Tahap 4: Payload Dinamis RAG (Injeksi Konteks Dokumen)]
       │  (04-P2W1D4 - RAG.ipynb & 06-18_rag_structured_data.ipynb)
       ▼
[Tahap 5: Multi-Turn Conversation History & Tool Calling State]
          (09-P2W2D4 / 10-P2W2D5 - AI Agent & src/agent.py)
```

---

### Tahap 1: String Tunggal (*Single-turn Raw String*)
* **Referensi:** `PHASE2/referensi/01-openai_temperature.ipynb`
* **Karakteristik:** Hanya mengirim satu baris/blok teks tanpa pemisahan peran instruksi.
* **Bentuk Payload:**
```python
prompt = "sebutkan rekomendasi model low resource..."

response = client.responses.create(
    model="gpt-4o-mini",
    input=prompt  # <-- Teks mentah tunggal
)
```

---

### Tahap 2: Template String & Penggabungan Manual
* **Referensi:** `PHASE2/referensi/02-P2W1D2 - Prompt Technique and Optimization.ipynb`
* **Karakteristik:** Instruksi mulai dibagi menjadi blok struktural (`[ROLE]`, `[CONTEXT]`, `[TASK]`, `<data>`, `[FORMAT]`), namun data masih dimasukkan lewat manipulasi teks manual (`.replace()` / f-string).
* **Bentuk Payload:**
```python
REASONING_PROMPT = """
[ROLE] Analis Sentimen
[CONTEXT] Transaksi tiket keluhan pelanggan
[TASK] Analisis pesan berikut:
<data>
<<PESAN>>
</data>
[FORMAT] Tulis Penalaran: ... lalu JSON
"""

prompt = REASONING_PROMPT.replace("<<PESAN>>", TICKETS["T5"])
ask_llm(prompt)  # Masih mengirim satu string utuh hasil replace
```

---

### Tahap 3: Struktur Pesan Terpisah (*List of Dict* / *Roles*) — Titik Balik
* **Referensi:** `PHASE2/referensi/04-P2W1D4 - LangChain Intro.ipynb` (Checkpoint 2 & Section 5)
* **Karakteristik:** Input tidak lagi berupa string panjang tunggal, melainkan array / list objek yang membedakan peran pengirim (`system`, `user`, `assistant`).
* **Bentuk Payload:**
```python
messages = [
    {"role": "system", "content": "Kamu adalah asisten HR yang ramah dan faktual."},
    {"role": "user", "content": "Berapa jatah cuti tahunan saya?"}
]

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=messages  # <-- Payload berupa list of dictionaries
)
```
* **Versi LangChain:**
```python
prompt = ChatPromptTemplate.from_messages([
    ("system", "Kamu adalah mentor Python untuk pemula."),
    ("human", "Jelaskan {konsep} dengan bahasa sederhana.")
])
```

---

### Tahap 4: Payload Dinamis RAG (*Context Injection*)
* **Referensi:** `PHASE2/referensi/04-P2W1D4 - RAG.ipynb` & `06-18_rag_structured_data.ipynb`
* **Karakteristik:** Payload memuat data hasil pencarian eksternal (dokumen PDF/vektor database) yang disuntikkan secara dinamis sebelum dikirim ke LLM.
* **Bentuk Payload:**
```python
messages = [
    {
        "role": "system", 
        "content": (
            "Jawab hanya berdasarkan konteks berikut. Jika tidak ada, katakan tidak tahu.\n\n"
            f"=== KONTEKS DOKUMEN ===\n{retrieved_chunks_text}\n======================="
        )
    },
    {"role": "user", "content": "Berapa hari hak cuti melahirkan?"}
]
```

---

### Tahap 5: Multi-Turn Conversation History & State Tool Calling
* **Referensi:** `PHASE2/referensi/09-P2W2D4 - AI Agent Part 1.ipynb` & `src/agent.py` di proyek HR-Agent
* **Karakteristik:** Seluruh jejak percakapan (user, balasan asisten, panggilan fungsi, hasil fungsi) dikirimkan secara berurutan dalam satu array `messages`.
* **Bentuk Payload Lengkap:**
```python
messages = [
    # 1. Instruksi Sistem
    {"role": "system", "content": "Anda adalah Asisten Kebijakan HR..."},
    
    # 2. Riwayat Chat Putaran 1
    {"role": "user", "content": "Halo, saya Bima."},
    {"role": "assistant", "content": "Halo Bima, ada yang bisa dibantu?"},
    
    # 3. Riwayat Chat Putaran 2 (User bertanya)
    {"role": "user", "content": "Berapa sisa saldo cuti tahunan saya?"},
    
    # 4. Asisten memutuskan memanggil Tool (Function Calling)
    {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "call_12345",
                "type": "function",
                "function": {"name": "get_my_leave_balance", "arguments": "{}"}
            }
        ]
    },
    
    # 5. Hasil eksekusi tool dari database internal
    {
        "role": "tool",
        "tool_call_id": "call_12345",
        "content": '{"annual_leave": 3, "sick_leave": 10}'
    },
    
    # 6. Jawaban final asisten berdasarkan hasil tool
    {"role": "assistant", "content": "Sisa saldo cuti tahunan Anda saat ini adalah 3 hari kerja."},
    
    # 7. Pertanyaan terbaru user (Follow-up)
    {"role": "user", "content": "Kalau begitu, bolehkah saya mengajukan cuti 5 hari?"}
]
```

Saat `messages` di atas dikirim ke LLM, model bisa langsung menyadari:
> *"Oh, sisa saldo user hanya 3 hari, jadi permohonan 5 hari cuti tahunan akan melebihi kuota!"*
Meskipun model tidak menyimpan memori, model bisa bernalar tepat karena seluruh runtutan kejadian dikirimkan kembali ke dalam `messages`.

---

## 4. Implementasi pada Arsitektur Proyek HR-Agent (`src/`)

Pada proyek HR-Agent di repositori ini, pola tersebut diimplementasikan melalui koordinasi tiga berkas:

1. **`src/repository.py`:**
   Menyimpan pesan pengguna dan respons asisten ke dalam tabel database (misalnya SQLite/PostgreSQL) setiap kali sebuah turn selesai.
2. **`src/agent.py`:**
   Mengambil $N$ pesan terakhir dari riwayat obrolan pengguna, menyusunnya ke dalam variabel `messages: list[dict]`, lalu meneruskannya ke `provider.respond(...)`.
3. **`src/providers.py`:**
   Menerima `messages` dan mengirimkannya langsung ke OpenAI API:
   ```python
   def respond(self, *, input_data: str | list[Any], instructions: str, ...):
       messages = [{"role": "system", "content": instructions}]
       if isinstance(input_data, list):
           messages.extend(input_data)  # Seluruh riwayat pesan digabungkan di sini
       
       completion = self.client.chat.completions.create(
           model=...,
           messages=messages,
           tools=formatted_tools,
           ...
       )
   ```

---

## 5. Ringkasan Praktis

| Tahap | Tipe Payload | Kelebihan | Kekurangan / Batasan |
|---|---|---|---|
| **String Tunggal** | `str` | Sangat simpel untuk tes cepat | Tidak punya peran sistem, tidak bisa riwayat |
| **Concat / Template** | `str` | Struktur prompt lebih rapi | Rawan prompt injection & role confusion |
| **List of Messages** | `list[dict]` | Aman, standar industri, jelas perannya | Perlu parsing struktur data di kode |
| **RAG Payload** | `list[dict]` + data eksternal | Faktual, grounded, minim halusinasi | Bergantung pada kualitas retriever |
| **Multi-turn Agent State** | `list[dict]` + `tool_calls` | Kontekstual, bisa eksekusi fungsi database | Ukuran token bertambah seiring panjangnya chat |

Untuk mempraktikkan langsung kelima tahap di atas, jalankan notebook pendamping:
📂 **`PHASE2/referensi/11-eksperimen_evolusi_payload_llm.ipynb`**
