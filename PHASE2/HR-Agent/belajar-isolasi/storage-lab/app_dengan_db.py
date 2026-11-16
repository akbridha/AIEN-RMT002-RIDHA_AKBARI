import psycopg
from fastapi import FastAPI, HTTPException

app = FastAPI(title="FastAPI + DB[punya-akbar]", version="0.2.0")

DB_URL = "postgresql://hr_app:hr_app@localhost:5432/hr_assistant"


def get_conn():
    """Buka koneksi baru, lalu tutup setelah selesai."""
    return psycopg.connect(DB_URL)


@app.get("/healthz")
def healthz():
    try:
        with get_conn() as conn:
            conn.execute("SELECT 1")
        return {"status": "ok", "db": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"DB error: {e}")


@app.get("/karyawan")
def list_karyawan():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT employee_id, display_name, role FROM employee"
        ).fetchall()
    return [
        {"employee_id": r[0], "display_name": r[1], "role": r[2]}
        for r in rows
    ]
