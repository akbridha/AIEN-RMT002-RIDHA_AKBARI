# Starter: lengkapi image aplikasi untuk FastAPI DAN Streamlit pada Compose.
# Build tidak boleh membutuhkan OPENAI_API_KEY; konfigurasi model diberikan saat runtime.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY data/ ./data/
COPY tests/ ./tests/
COPY assets/ ./assets/
COPY app.py ui_contract.py demo_personas.json ./

RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "src.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]

