import os
from openai import OpenAI
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
import psycopg

load_dotenv()

app = FastAPI(title="FastAPI + DB + OpenAI", version="0.3.0")
security = HTTPBearer()

DB_URL = "postgresql://hr_app:hr_app@localhost:5432/hr_assistant"
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Token sederhana → employee_id (sama seperti sandbox_app.py)
TOKEN_MAP = {
    "token-alya": {"employee_id": "EMP-001", "role": "employee"},
    "token-bima": {"employee_id": "EMP-002", "role": "employee"},
    "token-admin": {"employee_id": "ADM-001", "role": "monitoring_admin"},
}


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    answer: str
    employee_id: str


def current_user(creds: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    user = TOKEN_MAP.get(creds.credentials)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token tidak dikenal")
    return user


@app.post("/api/v1/chat", response_model=ChatResponse)
def chat(req: ChatRequest, user: dict = Depends(current_user)) -> ChatResponse:
    # Ambil nama karyawan dari DB
    with psycopg.connect(DB_URL) as conn:
        row = conn.execute(
            "SELECT display_name FROM employee WHERE employee_id = %s",
            (user["employee_id"],)
        ).fetchone()
    display_name = row[0] if row else user["employee_id"]

    # Panggil OpenAI
    completion = openai_client.chat.completions.create(
        model="gpt-6-luna",
        messages=[
            {"role": "system", "content": f"Kamu adalah asisten HR. Kamu sedang melayani {display_name}."},
            {"role": "user", "content": req.message},
        ],
         max_completion_tokens=300,
    )

    answer = completion.choices[0].message.content
    return ChatResponse(answer=answer, employee_id=user["employee_id"])
