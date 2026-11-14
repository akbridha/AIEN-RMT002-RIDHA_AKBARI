"""Strict tool schemas and identity-bound execution."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from .config import Settings
from .contracts import (
    ActionProposal,
    AuthContext,
    PrepareLeaveArgs,
    SearchPolicyArgs,
    TicketArgs,
)
from .domain import validate_leave_request
from .repository import Repository
from .retrieval import RetrievalService


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "search_hr_policy",
        "description": "Cari dokumen kebijakan HR resmi dengan pencarian hibrida.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Pertanyaan atau kata kunci pencarian kebijakan",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Jumlah dokumen teratas yang diambil (1-5)",
                },
            },
            "required": ["query", "top_k"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_my_leave_balance",
        "description": "Ambil saldo cuti resmi milik pegawai yang sedang login. Tidak menerima parameter identitas.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
    },
    {
        "name": "prepare_leave_request",
        "description": "Siapkan draft proposal pengajuan cuti baru yang harus dikonfirmasi manual oleh pegawai.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "start_date": {
                    "type": "string",
                    "description": "Tanggal mulai cuti (YYYY-MM-DD)",
                },
                "end_date": {
                    "type": "string",
                    "description": "Tanggal akhir cuti (YYYY-MM-DD)",
                },
                "leave_type": {
                    "type": "string",
                    "enum": ["annual", "sick", "parental"],
                    "description": "Tipe cuti",
                },
                "reason": {
                    "type": ["string", "null"],
                    "description": "Alasan cuti opsional",
                },
            },
            "required": ["start_date", "end_date", "leave_type", "reason"],
            "additionalProperties": False,
        },
    },
    {
        "name": "create_hr_ticket",
        "description": "Buat tiket eskalasi kasus atau pengecualian ke tim HR.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["policy_question", "leave_exception", "technical_issue", "privacy"],
                    "description": "Kategori tiket",
                },
                "summary": {
                    "type": "string",
                    "description": "Ringkasan persoalan tanpa informasi medis/rahasia",
                },
            },
            "required": ["category", "summary"],
            "additionalProperties": False,
        },
    },
]


class ToolExecutor:
    def __init__(self, repository: Repository, retrieval: RetrievalService, settings: Settings, today_factory=None) -> None:
        self.repository = repository
        self.retrieval = retrieval
        self.settings = settings
        self.today_factory = today_factory

    def execute(self, name: str, arguments: dict[str, Any], auth: AuthContext) -> tuple[Any, ActionProposal | None]:
        """Validate arguments with Pydantic and bind all private-data tools to auth.employee_id."""
        if name == "search_hr_policy":
            args = SearchPolicyArgs(**arguments)
            chunks = self.retrieval.search(args.query, top_k=args.top_k)
            return ([c.model_dump(mode="json") for c in chunks], None)

        elif name == "get_my_leave_balance":
            balances = self.repository.get_balances(auth.employee_id)
            return ([b.model_dump(mode="json") for b in balances], None)

        elif name == "prepare_leave_request":
            args = PrepareLeaveArgs(**arguments)
            today = self.today_factory() if self.today_factory else date.today()
            balances = self.repository.get_balances(auth.employee_id)
            overlaps = self.repository.has_overlap(auth.employee_id, args.start_date, args.end_date)
            days, validation_summary = validate_leave_request(args, balances, overlaps, today)

            proposal_id = f"AP-{uuid.uuid4().hex[:8].upper()}"
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=self.settings.proposal_ttl_minutes)
            proposal = ActionProposal(
                proposal_id=proposal_id,
                action_type="leave_request",
                leave_type=args.leave_type,
                start_date=args.start_date,
                end_date=args.end_date,
                business_days=days,
                reason=args.reason,
                validation_summary=validation_summary,
                expires_at=expires_at,
                requires_confirmation=True,
            )
            self.repository.save_proposal(auth.employee_id, proposal)
            return (proposal.model_dump(mode="json"), proposal)

        elif name == "create_hr_ticket":
            args = TicketArgs(**arguments)
            ticket_id = self.repository.create_ticket(auth.employee_id, args.category, args.summary)
            return ({"ticket_id": ticket_id, "status": "created"}, None)

        else:
            raise ValueError(f"Unknown tool: {name}")

