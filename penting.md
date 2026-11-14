.\.venv\Scripts\Activate.ps1


pip install "fastapi>=0.115,<1" "uvicorn[standard]>=0.34,<1"


buat file sandbox
uvicorn sandbox_app:app --reload --port 8000