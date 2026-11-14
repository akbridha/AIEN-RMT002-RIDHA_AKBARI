-- Inisialisasi Extension pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- 1. Tabel Employee
CREATE TABLE IF NOT EXISTS employee (
    employee_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('employee', 'monitoring_admin')),
    token_hash TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2. Tabel Leave Balance (Saldo Cuti per Tipe)
CREATE TABLE IF NOT EXISTS leave_balance (
    employee_id TEXT NOT NULL REFERENCES employee(employee_id) ON DELETE CASCADE,
    leave_type TEXT NOT NULL CHECK (leave_type IN ('annual', 'sick', 'parental')),
    available_days INT NOT NULL CHECK (available_days >= 0),
    as_of_date DATE NOT NULL DEFAULT CURRENT_DATE,
    PRIMARY KEY (employee_id, leave_type)
);

-- 3. Tabel Leave Request (Pengajuan Cuti)
CREATE TABLE IF NOT EXISTS leave_request (
    request_id TEXT PRIMARY KEY,
    employee_id TEXT NOT NULL REFERENCES employee(employee_id) ON DELETE CASCADE,
    leave_type TEXT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    business_days INT NOT NULL CHECK (business_days > 0),
    status TEXT NOT NULL, -- 'pending_manager_review', 'approved', 'cancelled', 'rejected'
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_date_order CHECK (end_date >= start_date)
);

-- 4. Tabel Action Proposal (Draft Pengajuan Cuti dengan Verifikasi 2 Langkah)
CREATE TABLE IF NOT EXISTS action_proposal (
    proposal_id TEXT PRIMARY KEY,
    employee_id TEXT NOT NULL REFERENCES employee(employee_id) ON DELETE CASCADE,
    action_type TEXT NOT NULL DEFAULT 'leave_request',
    leave_type TEXT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    business_days INT NOT NULL CHECK (business_days > 0),
    reason TEXT,
    validation_summary JSONB NOT NULL DEFAULT '[]'::jsonb,
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ,
    request_id TEXT REFERENCES leave_request(request_id),
    idempotency_key TEXT,
    audit_reference TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (proposal_id, idempotency_key)
);

-- 5. Tabel HR Ticket (Eskalasi Kasus HR)
CREATE TABLE IF NOT EXISTS hr_ticket (
    ticket_id TEXT PRIMARY KEY,
    employee_id TEXT NOT NULL REFERENCES employee(employee_id) ON DELETE CASCADE,
    category TEXT NOT NULL CHECK (category IN ('policy_question', 'leave_exception', 'technical_issue', 'privacy')),
    summary TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 6. Tabel Policy Chunk (Penyimpanan Dokumen Kebijakan & Vektor Dense + Lexical)
CREATE TABLE IF NOT EXISTS policy_chunk (
    chunk_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    title TEXT NOT NULL,
    section TEXT NOT NULL,
    version TEXT NOT NULL,
    effective_date DATE NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR(1536), -- Dimensi default 1536 (OpenAI text-embedding-3-small)
    search_tsv TSVECTOR GENERATED ALWAYS AS (to_tsvector('simple', content)) STORED,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (document_id, section, version)
);

-- Index Full Text Search & Vector (HNSW)
CREATE INDEX IF NOT EXISTS idx_policy_chunk_tsv ON policy_chunk USING GIN (search_tsv);

-- 7. Tabel Agent Trace (Observability & Audit Trail)
CREATE TABLE IF NOT EXISTS agent_trace (
    trace_id TEXT PRIMARY KEY,
    employee_id TEXT NOT NULL REFERENCES employee(employee_id) ON DELETE CASCADE,
    conversation_id TEXT,
    outcome TEXT,
    document_ids JSONB DEFAULT '[]'::jsonb,
    tool_calls JSONB DEFAULT '[]'::jsonb,
    latency_ms INT,
    input_tokens INT,
    output_tokens INT,
    estimated_cost NUMERIC,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =========================================================================
-- SEED DATA AWAL (Statis: Identitas Pegawai, Saldo, & Riwayat Permintaan)
-- =========================================================================

-- Seed Employees (Token hash dihasilkan dengan SHA-256)
INSERT INTO employee (employee_id, display_name, role, token_hash)
VALUES
    ('EMP-001', 'Alya Pratama', 'employee', 'c90e5a12e7da750f330c78f3d3845a05b10001d8f6b56c218150ae0782b2215e'),
    ('EMP-002', 'Bima Santoso', 'employee', 'fd4213def0a097a225c05baf3bd365b11809dd2171c78e478f5aad3ca02e2d79'),
    ('ADM-001', 'Monitoring Admin', 'monitoring_admin', '00f5f9625c49504b0776853a9cd04aa7a75f26b4760fc7fd555437b111b54390')
ON CONFLICT (employee_id) DO NOTHING;

-- Seed Balances (Dari data/employees.json)
INSERT INTO leave_balance (employee_id, leave_type, available_days, as_of_date)
VALUES
    ('EMP-001', 'annual', 8, '2026-09-01'),
    ('EMP-001', 'parental', 60, '2026-09-01'),
    ('EMP-001', 'sick', 10, '2026-09-01'),
    ('EMP-002', 'annual', 3, '2026-09-01'),
    ('EMP-002', 'parental', 60, '2026-09-01'),
    ('EMP-002', 'sick', 10, '2026-09-01')
ON CONFLICT (employee_id, leave_type) DO NOTHING;

-- Seed Historical Requests (Dari data/historical_requests.json)
INSERT INTO leave_request (request_id, employee_id, leave_type, start_date, end_date, business_days, status, created_at)
VALUES
    ('LR-HIST-001', 'EMP-001', 'annual', '2026-06-15', '2026-06-16', 2, 'approved', '2026-05-20T09:00:00+00:00'),
    ('LR-HIST-002', 'EMP-002', 'annual', '2026-08-10', '2026-08-10', 1, 'cancelled', '2026-07-25T04:30:00+00:00')
ON CONFLICT (request_id) DO NOTHING;
