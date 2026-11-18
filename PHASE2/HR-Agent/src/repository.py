"""Repository implementations: MemoryRepository for tests and PostgresRepository for production."""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone
from typing import Any, Protocol

from .contracts import ActionProposal, ActionResult, AuthContext, LeaveBalance, LeaveRequestView, PolicyChunk
from .security import token_hash


class Repository(Protocol):
    def health(self) -> bool: ...
    def authenticate(self, token: str) -> AuthContext | None: ...
    def lexical_search(self, query: str, limit: int) -> list[PolicyChunk]: ...
    def vector_search(self, embedding: list[float], limit: int) -> list[PolicyChunk]: ...
    def get_balances(self, employee_id: str) -> list[LeaveBalance]: ...
    def has_overlap(self, employee_id: str, start: date, end: date) -> bool: ...
    def save_proposal(self, employee_id: str, proposal: ActionProposal) -> None: ...
    def get_proposal(self, proposal_id: str) -> tuple[str, ActionProposal] | None: ...
    def confirm_proposal(self, employee_id: str, proposal_id: str, idempotency_key: str) -> ActionResult: ...
    def list_leave_requests(self, employee_id: str) -> list[LeaveRequestView]: ...
    def create_ticket(self, employee_id: str, category: str, summary: str) -> str: ...
    def save_trace(self, trace: dict[str, Any]) -> None: ...
    def get_trace(self, trace_id: str) -> dict[str, Any] | None: ...
    def monitoring_summary(self) -> dict[str, Any]: ...
    def get_all_employees_with_balances(self) -> list[dict[str, Any]]: ...
    def get_all_leave_requests(self) -> list[dict[str, Any]]: ...
    def get_all_tickets(self) -> list[dict[str, Any]]: ...
    def get_recent_traces(self, limit: int) -> list[dict[str, Any]]: ...


class ConflictError(RuntimeError):
    pass


class MemoryRepository:
    def __init__(self) -> None:
        self.chunks: list[PolicyChunk] = []
        self.users: dict[str, dict[str, Any]] = {
            "token-alya": {"employee_id": "EMP-001", "display_name": "Alya Pratama", "role": "employee"},
            "token-bima": {"employee_id": "EMP-002", "display_name": "Bima Santoso", "role": "employee"},
            "token-admin": {"employee_id": "ADM-001", "display_name": "Monitoring Admin", "role": "monitoring_admin"},
        }
        self.balances: dict[str, dict[str, int]] = {
            "EMP-001": {"annual": 8, "parental": 60, "sick": 10},
            "EMP-002": {"annual": 3, "parental": 60, "sick": 10},
        }
        self.proposals: dict[str, tuple[str, ActionProposal]] = {}
        self.confirmed: dict[str, tuple[str, str, str]] = {}  # proposal_id -> (idempotency_key, request_id, audit_ref)
        self.leave_requests: dict[str, list[LeaveRequestView]] = {}
        self.tickets: list[dict[str, Any]] = []
        self.traces: dict[str, dict[str, Any]] = {}

    def health(self) -> bool:
        return True

    def authenticate(self, token: str) -> AuthContext | None:
        user = self.users.get(token)
        if not user:
            # Also check by token_hash
            th = token_hash(token)
            for raw_tok, u in self.users.items():
                if token_hash(raw_tok) == th:
                    user = u
                    break
        if not user:
            return None
        return AuthContext(
            employee_id=user["employee_id"],
            display_name=user["display_name"],
            role=user["role"],
        )

    def lexical_search(self, query: str, limit: int) -> list[PolicyChunk]:
        terms = [t.lower() for t in query.split() if len(t) > 1]
        scored: list[tuple[float, PolicyChunk]] = []
        for chunk in self.chunks:
            content_lower = chunk.content.lower()
            title_lower = chunk.title.lower()
            section_lower = chunk.section.lower()
            score = 0.0
            for term in terms:
                if term in content_lower:
                    score += 1.0 + content_lower.count(term) * 0.1
                if term in title_lower:
                    score += 2.0
                if term in section_lower:
                    score += 1.5
            if score > 0:
                scored.append((score, chunk.model_copy(update={"score": score})))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [chunk for _, chunk in scored[:limit]]

    def vector_search(self, embedding: list[float], limit: int) -> list[PolicyChunk]:
        # Return chunks up to limit for memory mode
        return self.chunks[:limit]

    def get_balances(self, employee_id: str) -> list[LeaveBalance]:
        user_balances = self.balances.get(employee_id, {})
        return [
            LeaveBalance(leave_type=lt, available_days=days, as_of_date=date(2026, 9, 1))
            for lt, days in user_balances.items()
        ]

    def has_overlap(self, employee_id: str, start: date, end: date) -> bool:
        requests = self.leave_requests.get(employee_id, [])
        for req in requests:
            if req.status in ("pending_manager_review", "approved"):
                if not (req.end_date < start or req.start_date > end):
                    return True
        return False

    def save_proposal(self, employee_id: str, proposal: ActionProposal) -> None:
        self.proposals[proposal.proposal_id] = (employee_id, proposal)

    def get_proposal(self, proposal_id: str) -> tuple[str, ActionProposal] | None:
        return self.proposals.get(proposal_id)

    def confirm_proposal(self, employee_id: str, proposal_id: str, idempotency_key: str) -> ActionResult:
        if proposal_id not in self.proposals:
            raise KeyError(f"Proposal {proposal_id} not found")
        owner_id, prop = self.proposals[proposal_id]
        if owner_id != employee_id:
            raise KeyError(f"Proposal {proposal_id} not owned by {employee_id}")

        now = datetime.now(timezone.utc)
        if prop.expires_at < now:
            raise ConflictError("Proposal has expired")

        if proposal_id in self.confirmed:
            stored_key, req_id, audit_ref = self.confirmed[proposal_id]
            if stored_key != idempotency_key:
                raise ConflictError("Idempotency key mismatch for confirmed proposal")
            return ActionResult(
                request_id=req_id,
                status="pending_manager_review",
                idempotent_replay=True,
                audit_reference=audit_ref,
            )

        req_id = f"LR-{uuid.uuid4().hex[:8].upper()}"
        audit_ref = f"AUD-{uuid.uuid4().hex[:8].upper()}"
        new_req = LeaveRequestView(
            request_id=req_id,
            leave_type=prop.leave_type,
            start_date=prop.start_date,
            end_date=prop.end_date,
            business_days=prop.business_days,
            status="pending_manager_review",
            created_at=now,
        )
        self.leave_requests.setdefault(employee_id, []).append(new_req)
        self.confirmed[proposal_id] = (idempotency_key, req_id, audit_ref)
        return ActionResult(
            request_id=req_id,
            status="pending_manager_review",
            idempotent_replay=False,
            audit_reference=audit_ref,
        )

    def list_leave_requests(self, employee_id: str) -> list[LeaveRequestView]:
        return self.leave_requests.get(employee_id, [])

    def create_ticket(self, employee_id: str, category: str, summary: str) -> str:
        ticket_id = f"TICK-{uuid.uuid4().hex[:8].upper()}"
        self.tickets.append({
            "ticket_id": ticket_id,
            "employee_id": employee_id,
            "category": category,
            "summary": summary,
            "created_at": datetime.now(timezone.utc),
        })
        return ticket_id

    def save_trace(self, trace: dict[str, Any]) -> None:
        self.traces[trace["trace_id"]] = trace

    def get_trace(self, trace_id: str) -> dict[str, Any] | None:
        return self.traces.get(trace_id)

    def monitoring_summary(self) -> dict[str, Any]:
        total = len(self.traces)
        errors = sum(1 for t in self.traces.values() if t.get("error"))
        latencies = [t.get("latency_ms", 0) for t in self.traces.values()]
        latencies.sort()
        p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0
        tool_calls_count = sum(len(t.get("tool_calls", [])) for t in self.traces.values())
        return {
            "run_count": total,
            "error_rate": float(errors / total) if total > 0 else 0.0,
            "p95_latency_ms": p95,
            "tool_calls": tool_calls_count,
        }

    def get_all_employees_with_balances(self) -> list[dict[str, Any]]:
        result = []
        seen = set()
        for token, user in self.users.items():
            emp_id = user["employee_id"]
            if emp_id in seen:
                continue
            seen.add(emp_id)
            balances = self.balances.get(emp_id, {})
            result.append({
                "employee_id": emp_id,
                "display_name": user["display_name"],
                "role": user["role"],
                "balances": [
                    {"leave_type": lt, "available_days": days}
                    for lt, days in balances.items()
                ],
            })
        return result

    def get_all_leave_requests(self) -> list[dict[str, Any]]:
        result = []
        emp_names = {u["employee_id"]: u["display_name"] for u in self.users.values()}
        for emp_id, requests in self.leave_requests.items():
            for req in requests:
                result.append({
                    "request_id": req.request_id,
                    "employee_id": emp_id,
                    "display_name": emp_names.get(emp_id, emp_id),
                    "leave_type": req.leave_type,
                    "start_date": req.start_date.isoformat() if hasattr(req.start_date, "isoformat") else str(req.start_date),
                    "end_date": req.end_date.isoformat() if hasattr(req.end_date, "isoformat") else str(req.end_date),
                    "business_days": req.business_days,
                    "status": req.status,
                    "created_at": req.created_at.isoformat() if hasattr(req.created_at, "isoformat") else str(req.created_at),
                })
        return result

    def get_all_tickets(self) -> list[dict[str, Any]]:
        emp_names = {u["employee_id"]: u["display_name"] for u in self.users.values()}
        return [
            {
                "ticket_id": t["ticket_id"],
                "employee_id": t["employee_id"],
                "display_name": emp_names.get(t["employee_id"], t["employee_id"]),
                "category": t["category"],
                "summary": t["summary"],
                "created_at": t["created_at"].isoformat() if hasattr(t["created_at"], "isoformat") else str(t["created_at"]),
            }
            for t in self.tickets
        ]

    def get_recent_traces(self, limit: int = 50) -> list[dict[str, Any]]:
        traces = list(self.traces.values())
        traces.sort(key=lambda t: t.get("created_at", ""), reverse=True)
        return [
            {
                "trace_id": t["trace_id"],
                "employee_id": t["employee_id"],
                "conversation_id": t.get("conversation_id"),
                "outcome": t.get("outcome"),
                "latency_ms": t.get("latency_ms"),
                "input_tokens": t.get("input_tokens"),
                "output_tokens": t.get("output_tokens"),
                "estimated_cost": t.get("estimated_cost"),
                "error": t.get("error"),
                "created_at": t.get("created_at").isoformat() if hasattr(t.get("created_at"), "isoformat") else str(t.get("created_at") or ""),
            }
            for t in traces[:limit]
        ]


class PostgresRepository:
    def __init__(self, database_url: str, embedding_dimensions: int) -> None:
        import psycopg_pool
        self.pool = psycopg_pool.ConnectionPool(database_url, min_size=1, max_size=10)
        self.dimensions = embedding_dimensions

    def health(self) -> bool:
        try:
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
            return True
        except Exception:
            return False

    def authenticate(self, token: str) -> AuthContext | None:
        th = token_hash(token)
        try:
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT employee_id, display_name, role FROM employee WHERE token_hash = %s",
                        (th,),
                    )
                    row = cur.fetchone()
                    if row:
                        return AuthContext(employee_id=row[0], display_name=row[1], role=row[2])
        except Exception:
            pass
        return None

    def lexical_search(self, query: str, limit: int) -> list[PolicyChunk]:
        try:
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT chunk_id, document_id, title, section, version, effective_date, content,
                               ts_rank(search_tsv, plainto_tsquery('simple', %s)) as rank
                        FROM policy_chunk
                        WHERE search_tsv @@ plainto_tsquery('simple', %s)
                        ORDER BY rank DESC
                        LIMIT %s;
                        """,
                        (query, query, limit),
                    )
                    rows = cur.fetchall()
                    return [
                        PolicyChunk(
                            chunk_id=r[0],
                            document_id=r[1],
                            title=r[2],
                            section=r[3],
                            version=r[4],
                            effective_date=r[5],
                            content=r[6],
                            score=float(r[7]),
                        )
                        for r in rows
                    ]
        except Exception:
            return []

    def vector_search(self, embedding: list[float], limit: int) -> list[PolicyChunk]:
        try:
            emb_str = str(embedding)
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT chunk_id, document_id, title, section, version, effective_date, content,
                               1 - (embedding <=> %s::vector) as similarity
                        FROM policy_chunk
                        WHERE embedding IS NOT NULL
                        ORDER BY embedding <=> %s::vector
                        LIMIT %s;
                        """,
                        (emb_str, emb_str, limit),
                    )
                    rows = cur.fetchall()
                    return [
                        PolicyChunk(
                            chunk_id=r[0],
                            document_id=r[1],
                            title=r[2],
                            section=r[3],
                            version=r[4],
                            effective_date=r[5],
                            content=r[6],
                            score=float(r[7]),
                        )
                        for r in rows
                    ]
        except Exception:
            return []

    def get_balances(self, employee_id: str) -> list[LeaveBalance]:
        try:
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT leave_type, available_days, as_of_date FROM leave_balance WHERE employee_id = %s",
                        (employee_id,),
                    )
                    rows = cur.fetchall()
                    return [
                        LeaveBalance(leave_type=r[0], available_days=r[1], as_of_date=r[2])
                        for r in rows
                    ]
        except Exception:
            return []

    def has_overlap(self, employee_id: str, start: date, end: date) -> bool:
        try:
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT 1 FROM leave_request
                        WHERE employee_id = %s
                          AND status IN ('pending_manager_review', 'approved')
                          AND NOT (end_date < %s OR start_date > %s)
                        LIMIT 1;
                        """,
                        (employee_id, start, end),
                    )
                    return cur.fetchone() is not None
        except Exception:
            return False

    def save_proposal(self, employee_id: str, proposal: ActionProposal) -> None:
        try:
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO action_proposal (
                            proposal_id, employee_id, action_type, leave_type,
                            start_date, end_date, business_days, reason,
                            validation_summary, expires_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                        ON CONFLICT (proposal_id, idempotency_key) DO NOTHING;
                        """,
                        (
                            proposal.proposal_id,
                            employee_id,
                            proposal.action_type,
                            proposal.leave_type,
                            proposal.start_date,
                            proposal.end_date,
                            proposal.business_days,
                            proposal.reason,
                            json.dumps(proposal.validation_summary),
                            proposal.expires_at,
                        ),
                    )
                conn.commit()
        except Exception:
            pass

    def get_proposal(self, proposal_id: str) -> tuple[str, ActionProposal] | None:
        try:
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT employee_id, proposal_id, action_type, leave_type,
                               start_date, end_date, business_days, reason,
                               validation_summary, expires_at
                        FROM action_proposal WHERE proposal_id = %s;
                        """,
                        (proposal_id,),
                    )
                    row = cur.fetchone()
                    if row:
                        prop = ActionProposal(
                            proposal_id=row[1],
                            action_type=row[2],
                            leave_type=row[3],
                            start_date=row[4],
                            end_date=row[5],
                            business_days=row[6],
                            reason=row[7],
                            validation_summary=row[8] if isinstance(row[8], list) else json.loads(row[8]),
                            expires_at=row[9],
                        )
                        return (row[0], prop)
        except Exception:
            pass
        return None

    def confirm_proposal(self, employee_id: str, proposal_id: str, idempotency_key: str) -> ActionResult:
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT employee_id, leave_type, start_date, end_date, business_days,
                           expires_at, consumed_at, request_id, idempotency_key, audit_reference
                    FROM action_proposal
                    WHERE proposal_id = %s
                    FOR UPDATE;
                    """,
                    (proposal_id,),
                )
                row = cur.fetchone()
                if not row:
                    raise KeyError(f"Proposal {proposal_id} not found")
                if row[0] != employee_id:
                    raise KeyError(f"Proposal {proposal_id} not owned by {employee_id}")

                expires_at = row[5]
                consumed_at = row[6]
                existing_req_id = row[7]
                existing_idem_key = row[8]
                existing_audit_ref = row[9]

                now = datetime.now(timezone.utc)
                if expires_at < now:
                    raise ConflictError("Proposal has expired")

                if consumed_at is not None:
                    if existing_idem_key != idempotency_key:
                        raise ConflictError("Idempotency key mismatch")
                    return ActionResult(
                        request_id=existing_req_id,
                        status="pending_manager_review",
                        idempotent_replay=True,
                        audit_reference=existing_audit_ref,
                    )

                req_id = f"LR-{uuid.uuid4().hex[:8].upper()}"
                audit_ref = f"AUD-{uuid.uuid4().hex[:8].upper()}"

                # Insert leave_request
                cur.execute(
                    """
                    INSERT INTO leave_request (request_id, employee_id, leave_type, start_date, end_date, business_days, status)
                    VALUES (%s, %s, %s, %s, %s, %s, 'pending_manager_review');
                    """,
                    (req_id, employee_id, row[1], row[2], row[3], row[4]),
                )

                # Update action_proposal
                cur.execute(
                    """
                    UPDATE action_proposal
                    SET consumed_at = %s, request_id = %s, idempotency_key = %s, audit_reference = %s
                    WHERE proposal_id = %s;
                    """,
                    (now, req_id, idempotency_key, audit_ref, proposal_id),
                )
            conn.commit()

        return ActionResult(
            request_id=req_id,
            status="pending_manager_review",
            idempotent_replay=False,
            audit_reference=audit_ref,
        )

    def list_leave_requests(self, employee_id: str) -> list[LeaveRequestView]:
        try:
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT request_id, leave_type, start_date, end_date, business_days, status, created_at
                        FROM leave_request WHERE employee_id = %s
                        ORDER BY created_at DESC;
                        """,
                        (employee_id,),
                    )
                    rows = cur.fetchall()
                    return [
                        LeaveRequestView(
                            request_id=r[0],
                            leave_type=r[1],
                            start_date=r[2],
                            end_date=r[3],
                            business_days=r[4],
                            status=r[5],
                            created_at=r[6],
                        )
                        for r in rows
                    ]
        except Exception:
            return []

    def create_ticket(self, employee_id: str, category: str, summary: str) -> str:
        ticket_id = f"TICK-{uuid.uuid4().hex[:8].upper()}"
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO hr_ticket (ticket_id, employee_id, category, summary) VALUES (%s, %s, %s, %s);",
                    (ticket_id, employee_id, category, summary),
                )
            conn.commit()
        return ticket_id

    def save_trace(self, trace: dict[str, Any]) -> None:
        try:
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO agent_trace (
                            trace_id, employee_id, conversation_id, outcome,
                            document_ids, tool_calls, latency_ms,
                            input_tokens, output_tokens, estimated_cost, error
                        )
                        VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s, %s, %s)
                        ON CONFLICT (trace_id) DO NOTHING;
                        """,
                        (
                            trace["trace_id"],
                            trace["employee_id"],
                            trace.get("conversation_id"),
                            trace.get("outcome"),
                            json.dumps(trace.get("document_ids", [])),
                            json.dumps(trace.get("tool_calls", [])),
                            trace.get("latency_ms"),
                            trace.get("input_tokens"),
                            trace.get("output_tokens"),
                            trace.get("estimated_cost"),
                            trace.get("error"),
                        ),
                    )
                conn.commit()
        except Exception:
            pass

    def get_trace(self, trace_id: str) -> dict[str, Any] | None:
        try:
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT trace_id, employee_id, conversation_id, outcome,
                               document_ids, tool_calls, latency_ms,
                               input_tokens, output_tokens, estimated_cost, error
                        FROM agent_trace WHERE trace_id = %s;
                        """,
                        (trace_id,),
                    )
                    row = cur.fetchone()
                    if row:
                        return {
                            "trace_id": row[0],
                            "employee_id": row[1],
                            "conversation_id": row[2],
                            "outcome": row[3],
                            "document_ids": row[4] if isinstance(row[4], list) else json.loads(row[4] or "[]"),
                            "tool_calls": row[5] if isinstance(row[5], list) else json.loads(row[5] or "[]"),
                            "latency_ms": row[6],
                            "input_tokens": row[7],
                            "output_tokens": row[8],
                            "estimated_cost": float(row[9]) if row[9] is not None else None,
                            "error": row[10],
                        }
        except Exception:
            pass
        return None

    def monitoring_summary(self) -> dict[str, Any]:
        try:
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT count(*),
                               count(*) FILTER (WHERE error IS NOT NULL),
                               COALESCE(percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms), 0)
                        FROM agent_trace;
                        """
                    )
                    row = cur.fetchone()
                    total = row[0] if row else 0
                    errors = row[1] if row else 0
                    p95 = int(row[2]) if row and row[2] is not None else 0

                    cur.execute("SELECT sum(jsonb_array_length(tool_calls)) FROM agent_trace;")
                    tc_row = cur.fetchone()
                    tool_calls = tc_row[0] if tc_row and tc_row[0] is not None else 0

                    return {
                        "run_count": total,
                        "error_rate": float(errors / total) if total > 0 else 0.0,
                        "p95_latency_ms": p95,
                        "tool_calls": tool_calls,
                    }
        except Exception:
            return {"run_count": 0, "error_rate": 0.0, "p95_latency_ms": 0, "tool_calls": 0}

    def get_all_employees_with_balances(self) -> list[dict[str, Any]]:
        try:
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT employee_id, display_name, role FROM employee ORDER BY employee_id;"
                    )
                    employees = cur.fetchall()
                    result = []
                    for emp in employees:
                        emp_id, display_name, role = emp
                        cur.execute(
                            "SELECT leave_type, available_days FROM leave_balance WHERE employee_id = %s;",
                            (emp_id,),
                        )
                        balances = cur.fetchall()
                        result.append({
                            "employee_id": emp_id,
                            "display_name": display_name,
                            "role": role,
                            "balances": [
                                {"leave_type": b[0], "available_days": b[1]}
                                for b in balances
                            ],
                        })
                    return result
        except Exception:
            return []

    def get_all_leave_requests(self) -> list[dict[str, Any]]:
        try:
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT lr.request_id, lr.employee_id, e.display_name,
                               lr.leave_type, lr.start_date, lr.end_date,
                               lr.business_days, lr.status, lr.created_at
                        FROM leave_request lr
                        JOIN employee e ON lr.employee_id = e.employee_id
                        ORDER BY lr.created_at DESC;
                        """
                    )
                    rows = cur.fetchall()
                    return [
                        {
                            "request_id": r[0],
                            "employee_id": r[1],
                            "display_name": r[2],
                            "leave_type": r[3],
                            "start_date": r[4].isoformat() if r[4] else None,
                            "end_date": r[5].isoformat() if r[5] else None,
                            "business_days": r[6],
                            "status": r[7],
                            "created_at": r[8].isoformat() if r[8] else None,
                        }
                        for r in rows
                    ]
        except Exception:
            return []

    def get_all_tickets(self) -> list[dict[str, Any]]:
        try:
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT ht.ticket_id, ht.employee_id, e.display_name,
                               ht.category, ht.summary, ht.created_at
                        FROM hr_ticket ht
                        JOIN employee e ON ht.employee_id = e.employee_id
                        ORDER BY ht.created_at DESC;
                        """
                    )
                    rows = cur.fetchall()
                    return [
                        {
                            "ticket_id": r[0],
                            "employee_id": r[1],
                            "display_name": r[2],
                            "category": r[3],
                            "summary": r[4],
                            "created_at": r[5].isoformat() if r[5] else None,
                        }
                        for r in rows
                    ]
        except Exception:
            return []

    def get_recent_traces(self, limit: int = 50) -> list[dict[str, Any]]:
        try:
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT trace_id, employee_id, conversation_id, outcome,
                               latency_ms, input_tokens, output_tokens, estimated_cost, error, created_at
                        FROM agent_trace
                        ORDER BY created_at DESC
                        LIMIT %s;
                        """,
                        (limit,),
                    )
                    rows = cur.fetchall()
                    return [
                        {
                            "trace_id": r[0],
                            "employee_id": r[1],
                            "conversation_id": r[2],
                            "outcome": r[3],
                            "latency_ms": r[4],
                            "input_tokens": r[5],
                            "output_tokens": r[6],
                            "estimated_cost": float(r[7]) if r[7] is not None else None,
                            "error": r[8],
                            "created_at": r[9].isoformat() if r[9] else None,
                        }
                        for r in rows
                    ]
        except Exception:
            return []

