from __future__ import annotations

from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .agent import AgentService
from .cache import NullCache, ResilientCache
from .config import Settings, get_settings
from .contracts import (
    ActionResult,
    AuthContext,
    ChatRequest,
    ChatResponse,
    ConfirmActionRequest,
    LeaveRequestView,
    ProblemDetail,
)
from .providers import DeterministicProvider, OpenAIProvider
from .repository import ConflictError, MemoryRepository, PostgresRepository, Repository
from .retrieval import RetrievalService
from .tools import ToolExecutor


security = HTTPBearer(auto_error=False)


def build_runtime(settings: Settings):
    """Wire PostgresRepository, ResilientCache, provider, retrieval, tools, and agent."""
    if settings.model_mode == "live" and settings.database_url:
        try:
            repository: Repository = PostgresRepository(settings.database_url, settings.embedding_dimensions)
        except Exception:
            repository = MemoryRepository()
    else:
        repository = MemoryRepository()

    cache = ResilientCache(settings.redis_url) if settings.redis_url and settings.model_mode == "live" else NullCache()
    provider = OpenAIProvider() if settings.model_mode == "live" else DeterministicProvider()
    retrieval = RetrievalService(repository, provider, cache, settings.retrieval_cache_ttl_seconds)
    tools = ToolExecutor(repository, retrieval, settings)
    agent = AgentService(repository, provider, tools, settings)
    return repository, cache, agent


def create_app(*, settings: Settings | None = None, repository=None, cache=None, agent=None) -> FastAPI:
    """Build the documented API without changing endpoint or response contracts."""
    resolved_settings = settings or get_settings()

    if repository is None or cache is None or agent is None:
        r_repo, r_cache, r_agent = build_runtime(resolved_settings)
        repository = repository or r_repo
        cache = cache or r_cache
        agent = agent or r_agent

    app = FastAPI(title=resolved_settings.app_name, version="0.1.0")

    def get_auth(credentials: HTTPAuthorizationCredentials | None = Depends(security)) -> AuthContext:
        if not credentials or not credentials.credentials:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authorization token")
        user = repository.authenticate(credentials.credentials)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return user

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    def readyz() -> dict[str, str]:
        db_ready = repository.health()
        if not db_ready:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database not ready")
        return {"status": "ready"}

    @app.post("/api/v1/chat", response_model=ChatResponse)
    def chat(req: ChatRequest, auth: AuthContext = Depends(get_auth)) -> ChatResponse:
        return agent.run(req, auth)

    @app.post("/api/v1/action-proposals/{proposal_id}/confirm", response_model=ActionResult)
    def confirm_action(
        proposal_id: str,
        req: ConfirmActionRequest,
        auth: AuthContext = Depends(get_auth),
    ) -> ActionResult:
        try:
            return repository.confirm_proposal(auth.employee_id, proposal_id, req.idempotency_key)
        except KeyError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        except ConflictError as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    @app.get("/api/v1/leave-requests/me", response_model=list[LeaveRequestView])
    def my_leave_requests(auth: AuthContext = Depends(get_auth)) -> list[LeaveRequestView]:
        return repository.list_leave_requests(auth.employee_id)

    @app.get("/api/v1/traces/{trace_id}")
    def get_trace(trace_id: str, auth: AuthContext = Depends(get_auth)) -> dict[str, Any]:
        trace = repository.get_trace(trace_id)
        if not trace:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trace not found")
        # Security check: only owner or monitoring_admin can read trace
        if trace["employee_id"] != auth.employee_id and auth.role != "monitoring_admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access forbidden to this trace")
        # Ensure no raw message / prompt is leaked
        trace.pop("message", None)
        return trace

    @app.get("/api/v1/monitoring/summary")
    def monitoring_summary(auth: AuthContext = Depends(get_auth)) -> dict[str, Any]:
        if auth.role != "monitoring_admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Monitoring admin only")
        return repository.monitoring_summary()

    @app.get("/api/v1/monitoring/alerts")
    def monitoring_alerts(auth: AuthContext = Depends(get_auth)) -> list[dict[str, Any]]:
        if auth.role != "monitoring_admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Monitoring admin only")
        # Return empty list or alerts if error rate exceeds threshold
        summary = repository.monitoring_summary()
        alerts = []
        if summary.get("error_rate", 0) > 0.1:
            alerts.append({
                "rule_id": "high_error_rate",
                "severity": "high",
                "message": f"Tingkat kesalahan sistem melebihi 10%: {summary['error_rate']:.1%}",
            })
        return alerts

    return app

