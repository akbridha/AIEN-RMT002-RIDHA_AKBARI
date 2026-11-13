from fastapi import FastAPI, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

app = FastAPI(title="Latihan FastAPI", version="0.1.0")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    answer: str
    trace_id: str


def current_user(authorization: str = Header(...)) -> dict:
    # Contoh header: "Authorization: Bearer token-alya"
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Header auth tidak valid")
    users = {
        "token-alya": {"employee_id": "EMP-001", "role": "employee"},
        "token-bima": {"employee_id": "EMP-002", "role": "employee"},
        "token-admin": {"employee_id": "EMP-999", "role": "monitoring_admin"},
    }
    if token not in users:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token tidak dikenal")
    return users[token]


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.post("/api/v1/chat", response_model=ChatResponse)
def chat(req: ChatRequest, user: dict = Depends(current_user)) -> ChatResponse:
    return ChatResponse(answer=f"Halo {user['employee_id']}, Anda bilang: {req.message}", trace_id="tr-001")


@app.get("/api/v1/monitoring/summary")
def monitoring(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "monitoring_admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Khusus monitoring_admin")
    return {"traces": 0, "alerts": []}