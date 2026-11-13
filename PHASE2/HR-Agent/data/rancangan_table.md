 DDL Literal yang Benar-Benar Ada
Hanya ini, di ANALISIS_DUA_PILIHAN_MILESTONE.md:409-436:
```
CREATE TABLE employee (
  emp_id SERIAL PRIMARY KEY,
  name VARCHAR,
  department VARCHAR,
  annual_leave_balance INT,
  sick_leave_balance INT,
  -- ... other fields
);

CREATE TABLE leave_request (
  request_id SERIAL PRIMARY KEY,
  emp_id INT,
  start_date DATE,
  end_date DATE,
  leave_type VARCHAR,
  status VARCHAR, -- pending_manager_review, approved, rejected
  created_at TIMESTAMP,
  -- ... other fields
);

CREATE TABLE leave_policy (
  policy_id SERIAL PRIMARY KEY,
  content TEXT,
  embedding VECTOR(1536), -- pgvector untuk dense search
  category VARCHAR,
  updated_at TIMESTAMP
);


```


Jangan dipakai langsung. Skema ini bertentangan dengan kontrak project di 5 titik:

Masalah	Bukti
emp_id SERIAL vs "EMP-001"	data/employees.json memakai string ID, bukan integer
employee.name vs display_name	AuthContext.display_name di contracts.py
Saldo per-tipe di kolom annual_leave_balance, sick_leave_balance — hardcoded per tipe	LeaveBalance model fleksibel: leave_type, available_days, as_of_date
leave_policy hanya content + category, tanpa document_id/version/section	PolicyChunk butuh 8 field; test test_policy_chunk_ids_and_metadata_are_stable mengecek document_id, version, effective_date
Tidak ada kolom token_hash	brief.md:23 — "Simpan hash token pada database"; security.token_hash() mengimplikasikan tabel employee punya kolom hash
Tidak ada tabel proposal, trace, ticket/idempotency	Diperlukan oleh confirm_proposal, save_trace, create_ticket
2. Tabel yang WAJIB Ada (dari lab.md + Protocol)
Urutan ini dari src/repository.py — setiap method memaksa tabel tertentu:

Method Repository	Butuh tabel
authenticate(token)	employee (dengan token_hash)
get_balances(employee_id)	leave_balance
list_leave_requests(employee_id)	leave_request
has_overlap(employee_id, start, end)	leave_request (query rentang)
save_proposal / get_proposal / confirm_proposal	action_proposal + leave_request
create_ticket(...)	hr_ticket
lexical_search + vector_search	policy_chunk
save_trace / get_trace / monitoring_summary	agent_trace
health()	apa pun (SELECT 1)
3. Rekonstruksi Skema (Usulan, Diturunkan dari Kontrak)
Kolom di bawah bukan yang sudah ditulis di repo — ini hasil penurunan dari contracts.py, repository.py, dan fixture JSON. Gunakan sebagai rancangan setup_lab.py.

employee
Dari data/employees.json + AuthContext + security.token_hash()


```

```



leave_balance
Dari LeaveBalance + employees.json.balances (satu baris per tipe)


```
employee_id    TEXT FK -> employee
leave_type     TEXT            -- 'annual','sick','parental'
available_days INT CHECK (available_days >= 0)
as_of_date     DATE NOT NULL
PRIMARY KEY (employee_id, leave_type)

```



leave_request
Dari LeaveRequestView + data/historical_requests.json

```
request_id    TEXT PK          -- 'LR-HIST-001'
employee_id   TEXT FK NOT NULL
leave_type    TEXT NOT NULL
start_date    DATE NOT NULL
end_date      DATE NOT NULL
business_days INT  NOT NULL CHECK (business_days > 0)
status        TEXT NOT NULL
created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
```



⚠️ Perangkap: historical_requests.json berisi status: "approved" dan "cancelled". Constraint tidak boleh hanya CHECK (status = 'pending_manager_review') — seed akan gagal. Yang benar: izinkan nilai historis, tapi kode tidak pernah menghasilkan approved. Rubric (rubric.md:19-20) menjadikannya hard gate.

action_proposal
Dari ActionProposal + confirm_proposal(employee_id, proposal_id, idempotency_key)



```
proposal_id         TEXT PK       -- 'AP-...'
employee_id         TEXT FK NOT NULL
action_type         TEXT NOT NULL DEFAULT 'leave_request'
leave_type          TEXT NOT NULL
start_date          DATE NOT NULL
end_date            DATE NOT NULL
business_days        INT  NOT NULL CHECK (business_days > 0)
reason              TEXT
validation_summary  JSONB NOT NULL        -- list[str] di contract
expires_at          TIMESTAMPTZ NOT NULL  -- proposal_ttl_minutes = 15
consumed_at         TIMESTAMPTZ           -- null = belum dikonfirmasi
request_id          TEXT FK -> leave_request  -- hasil konfirmasi
idempotency_key     TEXT
audit_reference     TEXT
UNIQUE (proposal_id, idempotency_key)   -- replay → request_id sama
```



Test test_actions.py menuntut tiga perilaku yang harus dipenuhi skema ini:

Key sama dua kali → request_id sama, idempotent_replay=True → butuh UNIQUE(proposal_id, idempotency_key).
Employee berbeda → KeyError (jadi 404, bukan 403 — lihat brief.md:44).
Key berbeda setelah sukses → ConflictError.
expires_at lewat → ConflictError("expired") → butuh SELECT ... FOR UPDATE di dalam transaksi.
hr_ticket
Dari create_ticket(employee_id, category, summary) + TicketArgs



```
ticket_id   TEXT PK
employee_id TEXT FK NOT NULL
category    TEXT NOT NULL CHECK (category IN
              ('policy_question','leave_exception','technical_issue','privacy'))
summary     TEXT NOT NULL
created_at  TIMESTAMPTZ NOT NULL DEFAULT now()

```



policy_chunk
Dari PolicyChunk + front matter data/policies/*.md (7 dokumen, masing-masing 2 section)
```chunk_id        TEXT PK        -- stabil: '<document_id>#<section-slug>' atau hash
document_id     TEXT NOT NULL  -- 'HR-LEAVE-001'
title           TEXT NOT NULL
section         TEXT NOT NULL  -- 'Hak dan saldo'
version         TEXT NOT NULL  -- '2.1'
effective_date  DATE NOT NULL
content         TEXT NOT NULL
embedding       VECTOR(1536)   -- dimensi = Settings.embedding_dimensions, 64..4096
search_tsv      TSVECTOR GENERATED ALWAYS AS
                  (to_tsvector('simple', content)) STORED   -- untuk lexical_search
UNIQUE (document_id, section, version)

```



Catatan: embedding VECTOR(n) tidak bisa di-parameterize lewat %s psycopg. Harus f-string dengan int yang sudah divalidasi Field(ge=64, le=4096) dari Settings.

agent_trace
Dari save_trace(dict) / get_trace() / monitoring_summary() + lab.md:163

```
trace_id        TEXT PK
employee_id     TEXT FK NOT NULL      -- untuk cek owner vs admin
conversation_id TEXT
outcome         TEXT                  -- answered/action_proposed/escalated/abstained
document_ids    JSONB                 -- retrieved doc IDs
tool_calls      JSONB                 -- [{name,status,duration_ms}]
latency_ms      INT
input_tokens    INT
output_tokens   INT
estimated_cost  NUMERIC
error           TEXT                  -- SUDAH tersamarkan, tanpa stack trace
created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
```



⚠️ Test test_provider_failure_is_side_effect_free_and_redacted memeriksa "ABCDEF123" not in trace["error"], dan test_api.py memastikan response trace tidak memuat key "message" (raw prompt). Ini constraint aplikasi, bukan DB — tapi relevan saat memilih kolom: jangan buat kolom raw_prompt.