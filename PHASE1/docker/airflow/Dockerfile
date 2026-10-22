# Airflow runs the same PostgreSQL pipeline modules as the application image.
FROM apache/airflow:2.10.4-python3.12

ARG AIRFLOW_VERSION=2.10.4
ARG PYTHON_VERSION=3.12
RUN pip install --no-cache-dir \
    --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt" \
    "pg8000>=1.31,<2" \
    "python-dotenv>=1,<2"
