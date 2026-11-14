# Timeline Pengerjaan HR-Agent Milestone
## 10 Hari (37.5 Jam Total)

**Periode:** 11 November – 20 November 2026  
**Total Effort:** 37.5 jam (7 hari × 1.5 jam + 3 hari × 9 jam)  
**Level:** Intermediate  
**Target:** Submission siap dengan evaluasi 15 kasus

---

## 📊 Overview Timeline

```
PHASE 1 (Hari 1-3): Foundation & Setup — 4.5 jam
PHASE 2 (Hari 4-7): Core Development — 6 jam  
PHASE 3 (Hari 8-10): Integration & Polish — 27 jam
```

---

## 🔵 PHASE 1: FOUNDATION & SETUP
### Hari 1-3 | 1.5 jam per hari | Total 4.5 jam

### **Hari 1 (Monday 11-Nov) — Persiapan & Understanding**
**Duration:** 1.5 jam  
**Goal:** Pahami requirement lengkap, setup environment, buat foundation

**Tasks:**
- [ ] **15 min** — Review README milestone & brief.md
  - Baca kontrak API di `brief.md`
  - Pahami 4 tool yang dibutuhkan
  - Catat apa yang disediakan vs yang harus dibangun

- [ ] **15 min** — Setup lokal environment
  - Clone/download starter code
  - `python -m venv .venv` dan activate
  - `pip install -r requirements.txt`
  - Setup `.env` dari `.env.example`

- [ ] **30 min** — Database & Indexing planning
  - Baca `lab.md` section data schema
  - Pahami tabel: `employee`, `leave_request`, `leave_policy`
  - Catat kolom dan tipe data
  - Plan indexing strategy untuk hybrid search

- [ ] **15 min** — Tool & LLM Planning
  - Pilih LLM provider (OpenAI/Anthropic/Gemini)
  - Dokumentasikan model name & version
  - Setup API key di `.env`
  - Catat decision di `docs/technical-decisions.md`

**Checkpoint:** ✅ Environment berjalan, schema dipahami, LLM siap

**Deliverables:**
- `.env` terisi (tanpa secret di git)
- `docs/technical-decisions.md` (model choice, framework, etc)
- Checklist di kanban pribadi

---

### **Hari 2 (Tuesday 12-Nov) — Database & Indexing Foundation**
**Duration:** 1.5 jam  
**Goal:** Database schema siap, policy indexing dimulai

**Tasks:**
- [ ] **20 min** — Setup PostgreSQL
  - Run `docker compose up -d postgres`
  - Verify connection dari local machine
  - Catat connection string di `.env` sebagai `POSTGRES_URL`

- [ ] **25 min** — Create schema & test data
  - Jalankan migration/schema creation script
  - Insert dummy data 3-5 employees dengan berbagai leave balances
  - Insert 5-10 sample policies
  - Query untuk verify data inserted

- [ ] **30 min** — Plan Hybrid Search indexing
  - Baca Week 06 Day 2 notebook (RuangKarya RAG)
  - Pahami: dense search (vector) + sparse search (BM25)
  - Tentukan embedding model (`text-embedding-3-small` recommended)
  - Design: policy_text → embedding → store di PostgreSQL (pgvector)
  - Atau: store embedding + use Redis untuk cache

- [ ] **15 min** — Setup pgvector extension
  - Enable PostgreSQL pgvector: `CREATE EXTENSION IF NOT EXISTS vector`
  - Atau catat dependency untuk migration script

**Checkpoint:** ✅ Database up, schema created, policy table ready for indexing

**Deliverables:**
- PostgreSQL running dengan dummy data
- Seed script (`src/setup_lab.py`)
- Indexing plan documented

---

### **Hari 3 (Wednesday 13-Nov) — FastAPI Skeleton & Auth**
**Duration:** 1.5 jam  
**Goal:** API skeleton berjalan, auth layer siap

**Tasks:**
- [ ] **20 min** — Create FastAPI app skeleton
  - Setup `src/api.py` dengan `/healthz` endpoint
  - Basic middleware & error handling
  - Jalankan: `uvicorn src.api:app --reload`
  - Verify: `curl http://localhost:8000/healthz`

- [ ] **30 min** — Implement Auth Module
  - Buat `src/auth.py`
  - Parse Bearer token dari header
  - Hardcode 2 demo tokens → map ke emp_id (e.g., "emp_a" → 1, "emp_b" → 2)
  - Implement `verify_token(token) → emp_id` function
  - Return 401 jika token invalid

- [ ] **20 min** — Test Auth
  - Write unit test di `tests/test_auth.py`
  - Test valid token → get emp_id
  - Test invalid token → 401
  - Run: `pytest tests/test_auth.py -v`

- [ ] **10 min** — Setup conversation skeleton
  - Create `src/conversations.py` stub dengan TODO markers
  - Placeholder untuk CRUD operations
  - Link ke SQLite store (path di `.env`)

**Checkpoint:** ✅ API up, auth works, conversation scaffold ready

**Deliverables:**
- `src/api.py` dengan `/healthz` + auth middleware
- `src/auth.py` dengan token verification
- `tests/test_auth.py` passing
- Connection to SQLite verified

---

## 🟢 PHASE 2: CORE DEVELOPMENT
### Hari 4-7 | 1.5 jam per hari | Total 6 jam

### **Hari 4 (Thursday 14-Nov) — Conversation Store & Basic Endpoints**
**Duration:** 1.5 jam  
**Goal:** CRUD percakapan bekerja, ownership check siap

**Tasks:**
- [ ] **20 min** — Implement Conversation SQLite Store
  - Create `src/conversations.py`
  - Schema: `conversations` (id, emp_id, created_at, updated_at)
  - Schema: `messages` (id, conversation_id, role, content, created_at)
  - Create SQLite connection pool / manager

- [ ] **30 min** — Implement endpoints
  - `POST /api/v1/conversations` — create new (check emp_id from auth)
  - `GET /api/v1/conversations` — list user's conversations
  - `GET /api/v1/conversations/{id}` — read one (check ownership)
  - Return 404 if emp_id doesn't own conversation_id
  - Test dengan curl atau Postman

- [ ] **20 min** — Add message persistence
  - Store message history in SQLite
  - Each message: role (user/assistant), content, timestamp
  - Load history untuk context di agent loop

- [ ] **10 min** — Write unit tests
  - Test create conversation
  - Test ownership check (emp_b cannot read emp_a's conv)
  - Test 404 on unauthorized access

**Checkpoint:** ✅ Conversation CRUD works, ownership enforced

**Deliverables:**
- `src/conversations.py` full implementation
- Endpoints passing unit tests
- Ownership validation working

---

### **Hari 5 (Friday 15-Nov) — Policy Indexing & Hybrid Search**
**Duration:** 1.5 jam  
**Goal:** Hybrid search working, policy retrieval ready

**Tasks:**
- [ ] **20 min** — Implement Policy Indexing Service
  - Create `src/policy_indexer.py`
  - Load policies dari PostgreSQL (`leave_policy` table)
  - For each policy: generate embedding menggunakan OpenAI API
  - Store embedding di PostgreSQL (vector column) atau Redis
  - Benchmark: 10 policies ≈ 1-2 menit (cache response)

- [ ] **25 min** — Implement Hybrid Search
  - Create `src/policy_search.py`
  - **Dense search:** Query embedding similarity (pgvector / cosine similarity)
  - **Sparse search:** BM25 keyword matching (gunakan library seperti `rank_bm25`)
  - **Fusion:** Combine scores via RRF (Reciprocal Rank Fusion)
  - Function: `search_policies(query_text, top_k=3) → List[Policy]`

- [ ] **15 min** — Test Hybrid Search
  - Manual test: search "cuti tahunan berapa hari?"
  - Verify top-3 results make sense
  - Check ranking: dense vs sparse vs fused

**Checkpoint:** ✅ Hybrid search working, policy retrieval accurate

**Deliverables:**
- `src/policy_indexer.py`
- `src/policy_search.py` dengan hybrid search
- Test queries giving sensible results

---

### **Hari 6 (Saturday 16-Nov) — Tool Implementations 1 & 2**
**Duration:** 1.5 jam  
**Goal:** Tool 1 & 2 working, agent tool registry ready

**Tasks:**
- [ ] **20 min** — Implement Tool 1: Query Kebijakan
  - Create `src/tools.py` atau separate file per tool
  - Tool 1 function: `query_policy(question: str) → List[PolicyResult]`
  - Call `policy_search()` dari Day 5
  - Return: policy text + source + confidence score
  - Pydantic schema untuk validation

- [ ] **20 min** — Implement Tool 2: Read Leave Balance
  - Tool 2 function: `read_leave_balance(emp_id: str) → BalanceInfo`
  - Query PostgreSQL: SELECT annual_leave, sick_leave, unpaid_leave FROM employee WHERE emp_id = ?
  - Return structured data dengan Pydantic model
  - Include: balance available, used, remaining

- [ ] **20 min** — Create Tool Registry & Schemas
  - Define all 4 tools dengan schema (name, description, parameters, return type)
  - Use Pydantic BaseModel untuk input/output validation
  - Create `get_tools() → List[Tool]` function
  - Document tool descriptions untuk LLM context

- [ ] **10 min** — Unit test tools
  - Test Tool 1: search for "cuti" returns policies
  - Test Tool 2: get balance untuk emp_id = 1 returns correct data

**Checkpoint:** ✅ Tool 1 & 2 callable, schemas defined, registry working

**Deliverables:**
- `src/tools.py` dengan Tool 1 & 2
- Pydantic schemas di `src/contracts.py`
- Unit tests passing

---

### **Hari 7 (Sunday 17-Nov) — Tool Implementations 3 & 4**
**Duration:** 1.5 jam  
**Goal:** All 4 tools working, validation logic complete

**Tasks:**
- [ ] **20 min** — Implement Tool 3: Prepare Leave Proposal
  - Tool 3 function: `prepare_leave_proposal(emp_id, start_date, end_date, leave_type) → ProposalInfo`
  - Validate logic:
    - Date tidak boleh di masa lalu
    - Duration hitung dengan business days / calendar days
    - Check saldo cukup untuk annual/sick leave
    - Unpaid leave = unlimited
  - Return: proposal dengan duration, type, balance_after prediction

- [ ] **20 min** — Implement Tool 4: Create Leave Request
  - Tool 4 function: `create_leave_request(emp_id, proposal: ProposalInfo) → RequestInfo`
  - Insert ke PostgreSQL: `INSERT INTO leave_request VALUES (...)`
  - Set status = 'pending_manager_review' (NO auto-approval)
  - Return: request_id + status
  - Constraint: proposal validation harus sudah passed

- [ ] **15 min** — Business Rule Validation
  - Centralize validasi policy di `src/leave_rules.py`
  - Rules: annual_leave_max = 15 days, sick_leave_max = 5 days, etc
  - Rules: blackout dates (optional), min/max per request, carry-over logic
  - Document assumptions dalam code comment

- [ ] **5 min** — Unit test Tool 3 & 4
  - Test proposal dengan saldo cukup → valid
  - Test proposal dengan saldo kurang → rejected
  - Test create request → status = pending_manager_review

**Checkpoint:** ✅ All 4 tools callable, validation logic solid, request in DB

**Deliverables:**
- `src/tools.py` Tool 3 & 4
- `src/leave_rules.py` dengan business logic
- All tool unit tests passing

---

## 🟡 PHASE 3: INTEGRATION & POLISH
### Hari 8-10 | 9 jam per hari | Total 27 jam

### **Hari 8 (Monday 18-Nov) — Agent Loop & LLM Integration**
**Duration:** 9 jam  
**Goal:** Complete agent reasoning loop, agent bisa call tools

**Tasks (Morning: 4.5 hr):**
- [ ] **30 min** — Study agent loop patterns
  - Review Week 06 Day 4 & 5 notebooks (agent reasoning loop)
  - Understand: think → act → observe → loop
  - Catat pattern: LLM meminta tool, app executes, result → observation

- [ ] **60 min** — Implement Basic Agent Loop
  - Create `src/agent.py`
  - Initialize: LLM client (OpenAI/Anthropic/Gemini)
  - System prompt: define agent goal, available tools, response format
  - Function: `run_agent(emp_id, question, chat_history) → AgentResponse`
  - Loop logic:
    ```
    1. Send to LLM: [system] + [chat history] + [question] + [available tools]
    2. LLM respond: answer atau tool_request
    3. If tool_request:
       - Parse tool name & params
       - Validate params
       - Call tool function
       - Add result to history as observation
       - Loop back to step 1 (max 5 iterations)
    4. Else: return answer
    ```

- [ ] **45 min** — Integrate all 4 tools into agent
  - Add tool definitions ke system prompt
  - Tool descriptions must be clear untuk LLM
  - Validate LLM tool requests sebelum execution
  - Handle tool errors gracefully (fallback message, no answer hallucination)

- [ ] **45 min** — Test agent end-to-end
  - Test Q: "Berapa saldo cuti saya?" → should call Tool 2
  - Test Q: "Apakah saya bisa cuti 10-14 Nov?" → should call Tool 3
  - Test Q: "Ajukan cuti 10-14 Nov untuk annual" → should call Tool 3 + 4
  - Manual testing dengan postman atau curl

**Tasks (Afternoon: 4.5 hr):**
- [ ] **60 min** — Implement Message Endpoint
  - Create `POST /api/v1/conversations/{id}/messages`
  - Input: {message: "user question"}
  - Flow:
    1. Verify token & ownership
    2. Store message (role=user, content=question) to SQLite
    3. Load chat history (last 10 messages? configurable)
    4. Call agent.run_agent(emp_id, question, history)
    5. Store response (role=assistant, content=answer) to SQLite
    6. Return response with metadata
  - Response format: {answer, tool_used[], data_basis, outcome, request_id}

- [ ] **60 min** — Response Validation & Formatting
  - Implement `AgentResponse` Pydantic model
  - Validasi: answer harus grounded (tidak hallucinated)
  - If Tool 2 called: include balance di response
  - If Tool 3/4 called: include proposal details + request_id
  - Format: jelas, bilingual (English technical, Indonesian for user)

- [ ] **60 min** — Follow-up Support
  - Agent harus maintain context dari percakapan sebelumnya
  - Test: Q1 "berapa saldo?" → Q2 "untuk cuti tahunan berapa?" 
  - Verify: agent menggunakan context dari Q1

- [ ] **60 min** — Error Handling & Edge Cases
  - What if LLM times out? → Return timeout message
  - What if tool fails? → Fallback message (jangan hallucinate)
  - What if emp_id has invalid data? → graceful 404 or message
  - What if question out of scope? → agent should refuse politely

**Checkpoint:** ✅ Agent loop complete, all tools integrated, message endpoint working

**Deliverables:**
- `src/agent.py` full implementation
- `POST /api/v1/conversations/{id}/messages` endpoint
- End-to-end test with 5+ scenarios passing
- Error handling tested

---

### **Hari 9 (Tuesday 19-Nov) — Testing, Security, Docker**
**Duration:** 9 jam  
**Goal:** 15 test cases, security tested, Docker ready

**Tasks (Morning: 4.5 hr):**
- [ ] **90 min** — Implement 15 Evaluation Test Cases
  - Create `tests/test_evaluation.py` (reference: `assessment.md`)
  - **Accuracy (4 cases):**
    1. Correct balance query
    2. Valid proposal generation
    3. Request creation with correct status
    4. Policy search returns relevant docs
  
  - **Follow-up (2 cases):**
    1. Context maintained across messages
    2. Ambiguous follow-up asks for clarification
  
  - **Scope & Refusal (2 cases):**
    1. Out-of-scope question → refuse politely
    2. Invalid date → offer correction
  
  - **Prompt Injection (2 cases):**
    1. User tries to inject: "ignore your instructions..."
    2. Database exception_note (if exists) injection
  
  - **Authorization (3 cases):**
    1. emp_b cannot read emp_a conversation
    2. emp_b cannot write to emp_a conversation
    3. emp_b cannot modify emp_a leave request

- [ ] **90 min** — Run & Document Test Results
  - Run all 15 cases
  - Record: input, expected, actual, pass/fail
  - For failures: debug & fix
  - Create test report: `docs/evaluation-results.md`

**Tasks (Afternoon: 4.5 hr):**
- [ ] **45 min** — Security Testing
  - SQL injection attempt in queries → blocked?
  - Token tampering → 401?
  - Cross-user access → 404?
  - Verify in `tests/test_security.py`

- [ ] **60 min** — Create Dockerfile
  - Multi-stage build (builder → runtime)
  - Non-root user for security
  - Expose port 8000 for API
  - Entry: `python -m uvicorn src.api:app --host 0.0.0.0 --port 8000`
  - Include health check

- [ ] **60 min** — Create docker-compose.yml
  - Service `api` (FastAPI, port 8000 internal)
  - Service `ui` (Streamlit, port 8501 internal)
  - Service `postgres` (database)
  - Service `redis` (caching policy vector, optional)
  - Named volume untuk SQLite (conversations.sqlite3)
  - Environment variables via `.env`
  - Network: all services on bridge

- [ ] **60 min** — Test Docker Build & Run
  - `docker compose build`
  - `docker compose up`
  - API healthz check: `curl http://localhost:8000/healthz`
  - UI check: `http://localhost:8501`
  - Stop: `docker compose down` (volume persists)
  - Restart: `docker compose up` → conversation data persists

**Checkpoint:** ✅ 15 test cases documented, Docker working, security verified

**Deliverables:**
- `tests/test_evaluation.py` dengan 15 cases
- `docs/evaluation-results.md` dengan results
- `Dockerfile` untuk API & UI
- `docker-compose.yml`
- All tests passing in Docker

---

### **Hari 10 (Wednesday 20-Nov) — Documentation, Demo, Polish**
**Duration:** 9 jam  
**Goal:** Production-ready submission, demo script ready

**Tasks (Morning: 4.5 hr):**
- [ ] **90 min** — Write Comprehensive Documentation
  - **README.md** (60 min):
    - Overview: apa yang dibangun
    - Architecture diagram (Mermaid atau image)
    - Setup instructions (local + Docker)
    - Environment variables explanation
    - API contract endpoints
    - Example curl requests
  
  - **docs/technical-decisions.md** (30 min):
    - Why this LLM? (model choice, cost, latency)
    - Why PostgreSQL + pgvector? (vs alternative)
    - Why hybrid search? (dense + sparse trade-off)
    - Why 4-tool design? (vs single complex tool)
    - Production considerations vs current scope

- [ ] **90 min** — Risk Register & Known Limitations
  - Create `docs/risk-register.md`:
    - Risk 1: LLM hallucination on policy → Mitigation: only return from search
    - Risk 2: Concurrent requests same emp → DB transaction handling?
    - Risk 3: Policy updates invalidate embeddings → Reindex strategy?
    - Risk 4: Bearer token in plain HTTP (local) → TLS in production
    - Document assumptions: 2 demo tokens, local SQLite, etc

- [ ] **90 min** — Code Quality & Cleanup
  - Remove debug prints & TODO comments (unless documented)
  - Add docstrings to all public functions
  - Run linter: `black`, `flake8`, `pylint` on `src/`
  - Check coverage: `pytest --cov=src`
  - Fix any warnings

**Tasks (Afternoon: 4.5 hr):**
- [ ] **90 min** — Create Demo Script & Runbook
  - Script `demo.sh` atau `demo.md`:
    1. Start Docker Compose
    2. Create conversation for emp_a
    3. Query balance → show Tool 2 execution
    4. Propose leave → show Tool 3 execution
    5. Create request → show Tool 4 execution
    6. Follow-up without context loss
    7. Out-of-scope question rejection
    8. Injection attempt showing no effect
    9. emp_b tries to read emp_a → 404
  
  - Time each demo step: target 5-7 minutes total
  - Screenshot/video recording points

- [ ] **90 min** — Final Submission Checklist
  - Verify all required files present (reference `required_files.participant.md`):
    - [ ] src/ directory with all modules
    - [ ] tests/ directory with 15+ test cases
    - [ ] Dockerfile & docker-compose.yml
    - [ ] requirements.txt (no .env secrets)
    - [ ] README.md & docs/
    - [ ] .gitignore (exclude .env, __pycache__, .venv, etc)
  
  - Verify no secrets in repo:
    - [ ] No OPENAI_API_KEY in code
    - [ ] No DB passwords in code
    - [ ] No .env file in git
  
  - Final build test:
    - [ ] `docker compose build` succeeds
    - [ ] `docker compose up` runs
    - [ ] All endpoints respond
    - [ ] Test case passes in container

- [ ] **60 min** — Submit & Prep for Grading
  - Zip submission
  - Include: submission-checklist signed off
  - Include: evaluation-results.md
  - Include: demo-script.md
  - Double-check README clarity for grader

**Checkpoint:** ✅ Submission complete, demo ready, all documentation done

**Deliverables:**
- Comprehensive README.md
- docs/technical-decisions.md
- docs/risk-register.md
- docs/evaluation-results.md (15 cases, all pass)
- demo-script.md (5-7 min walkthrough)
- Clean, tested code
- Docker compose working
- Ready for submission

---

## 📋 Daily Checklist & Tracking

Gunakan template ini untuk setiap hari:

```markdown
## Hari X (Date) — [Phase & Topic]
Duration: X jam
Status: [ ] In Progress | [ ] Complete

### Tasks
- [ ] Task 1
- [ ] Task 2
- [ ] Task 3

### Checkpoint
- [ ] Deliverable 1 ready
- [ ] Tests passing
- [ ] No blockers

### Notes
- What went well:
- What was challenging:
- Next day dependency:
```

---

## 🚨 Critical Path & Blockers

| Hari | If Blocked | Workaround |
|---|---|---|
| 1-3 | PostgreSQL won't connect | Use local SQLite instead for MVP |
| 5 | Hybrid search not working | Use keyword search only (Day 1 feature) |
| 6-7 | Tool validation complex | Simplify: pass through LLM validation first |
| 8 | Agent loop timeout | Reduce max iterations, simplify prompt |
| 9 | Docker issues | Test local first, then containerize |
| 10 | Time pressure | Prioritize: testing > documentation > demo |

---

## 🎯 Success Criteria

By end of Day 10, you should have:

✅ **Functional System:**
- [ ] All 4 tools working
- [ ] Agent reasoning loop complete
- [ ] 15 test cases passing
- [ ] Docker compose working

✅ **Security & Authorization:**
- [ ] Token validation working
- [ ] Cross-user access blocked
- [ ] SQL injection prevented
- [ ] Injection attempts handled

✅ **Documentation:**
- [ ] README clear for grader
- [ ] Technical decisions explained
- [ ] Risk register documented
- [ ] Evaluation results recorded

✅ **Submission Quality:**
- [ ] No secrets in repo
- [ ] Code well-formatted
- [ ] Demo script ready (5-7 min)
- [ ] All required files included

---

## 📞 Daily Mentoring Sessions

**Session 1 (Day 5, after Hari 4-5 work):**
- Review database & policy indexing
- Discuss hybrid search strategy
- Q&A on tool implementations

**Session 2 (Day 8-9, after Hari 6-7 work):**
- Agent loop review
- Tool validation deep dive
- Testing strategy discussion

**Session 3 (Day 10, final polish):**
- Docker & deployment check
- Documentation review
- Demo run-through
- Final Q&A before submission

---

## 📊 Effort Distribution

```
Phase 1 (Foundation)     - 4.5 hr (12%)
Phase 2 (Development)    - 6 hr   (16%)
Phase 3 (Integration)    - 27 hr  (72%)
  ├─ Agent & Tools      - 9 hr
  ├─ Testing & Security - 9 hr
  └─ Docs & Demo        - 9 hr
```

**Note:** Phase 3 intensive untuk memastikan kualitas production-ready.

---

## 🎓 Learning Objectives by Day

| Hari | Core Learning |
|---|---|
| 1 | Project scoping & planning |
| 2 | Database design & indexing |
| 3 | API basics & authentication |
| 4 | Persistence & CRUD patterns |
| 5 | Hybrid search & retrieval |
| 6-7 | Multi-tool integration & validation |
| 8 | Agent reasoning loop & orchestration |
| 9 | Testing, security, containerization |
| 10 | Documentation & production readiness |

---

**Good luck! 🚀 Estimated completion: 20 Nov 2026**

