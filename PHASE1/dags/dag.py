"""DAG utama milestone P1M1 — orkestrasi 7 tahap sesuai kontrak README §8.

Urutan wajib:
    validate raw files -> initialize PostgreSQL schemas
        -> load Bronze -> build Silver -> quality gate (gagal -> berhenti)
        -> build Gold -> validate Gold dan record pipeline metadata

Mode operasi dikontrol oleh environment variable ``PIPELINE_MODE``:

* ``real`` (default) — setiap tahap memanggil modul pipeline yang sesuai
  (``pipelines.*``) dan terhubung ke PostgreSQL.
* ``simulate`` — setiap tahap HANYA mencatat log simulasi dan pemeriksaan file
  read-only (raw/schema), tanpa koneksi database atau operasi ingestion nyata.
  Gunakan untuk mendemokan dependency, rerun, dan quality gate.

``dag_run.conf`` mendukung ``{"simulate_gate_failure": true}`` untuk
mendemonstrasikan quality gate yang menghentikan tahap Gold.
"""

from __future__ import annotations

import importlib
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from airflow import DAG
from airflow.exceptions import AirflowException
from airflow.operators.python import PythonOperator

log = logging.getLogger(__name__)

PIPELINE_MODE = os.getenv("PIPELINE_MODE", "real").strip().lower()
RAW_DATA_DIR = Path(os.getenv("RAW_DATA_DIR", "data/raw"))
SCHEMAS_DIR = Path(os.getenv("SCHEMAS_DIR", "database/schemas"))

GOLD_TABLES = (
    "gold.order_360 (1 baris per order)",
    "gold.customer_daily (1 customer per tanggal)",
    "gold.product_daily (1 product per tanggal)",
    "gold.channel_campaign_daily (1 tanggal x channel x campaign)",
    "gold.executive_kpis_daily (1 tanggal bisnis)",
)

SCHEMA_FILES = ("bronze.sql", "silver.sql", "gold.sql", "ops.sql")

# Peta tahap -> modul pipeline yang dipanggil pada PIPELINE_MODE=real.
REAL_STAGE_TARGETS = {
    "validate_raw_files": ("pipelines.ingestion.validate_raw_files", "run"),
    "initialize_postgres_schemas": ("pipelines.ingestion.initialize_database", "run"),
    "load_bronze": ("pipelines.bronze.build_bronze", "run"),
    "build_silver": ("pipelines.silver.build_silver", "run"),
    "quality_gate": ("pipelines.quality.quality_gate", "run"),
    "build_gold": ("pipelines.gold.build_gold", "run"),
    "validate_gold_and_record_metadata": ("pipelines.quality.validate_gold", "run"),
}


def _run_id(context: dict[str, Any]) -> str:
    """pipeline_run_id yang diteruskan ke setiap layer (kontrak DAG)."""
    return str(context["dag_run"].run_id)


def _conf_flag(context: dict[str, Any], key: str) -> bool:
    value = context["dag_run"].conf.get(key, False)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return bool(value)


def _execute_real(stage: str, context: dict[str, Any]) -> Any:
    """Panggil modul pipeline sesuai peta tahap (mode real)."""
    if stage not in REAL_STAGE_TARGETS:
        raise AirflowException(f"Tahap '{stage}' tidak memiliki pemetaan modul pipeline.")
    module_name, func_name = REAL_STAGE_TARGETS[stage]
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        raise AirflowException(
            f"PIPELINE_MODE=real tetapi modul '{module_name}' belum tersedia. "
            f"Implementasikan pipeline untuk tahap '{stage}' terlebih dahulu, "
            f"atau jalankan DAG dengan PIPELINE_MODE=simulate."
        ) from exc
    func = getattr(module, func_name, None)
    if func is None:
        raise AirflowException(f"Modul '{module_name}' tidak memiliki fungsi '{func_name}()'.")
    log.info("[REAL] Menjalankan tahap %s via %s.%s()", stage, module_name, func_name)
    return func(pipeline_run_id=_run_id(context), context=context)


def _simulate(stage: str, notes: list[str], context: dict[str, Any], pause: float = 1.5) -> dict[str, Any]:
    """Catat log simulasi satu tahap (tanpa database, tanpa transformasi nyata)."""
    run_id = _run_id(context)
    log.info("[SIMULASI] Tahap '%s' | pipeline_run_id=%s", stage, run_id)
    for note in notes:
        log.info("    - %s", note)
    time.sleep(pause)  # memberi waktu agar transisi tahap terlihat di UI
    return {
        "stage": stage,
        "mode": "simulate",
        "pipeline_run_id": run_id,
        "notes": notes,
    }


def _dispatch(stage: str, simulate_notes: list[str], context: dict[str, Any]) -> Any:
    if PIPELINE_MODE == "real":
        return _execute_real(stage, context)
    return _simulate(stage, simulate_notes, context)



# --- Tahap 1: validasi raw files --------------------------------------------


def validate_raw_files(**context: Any) -> dict[str, Any]:
    source_files = [
        path
        for path in RAW_DATA_DIR.rglob("*")
        if path.is_file()
        and path.name != "manifest.json"
        and path.suffix.lower() in {".json", ".csv"}
    ] if RAW_DATA_DIR.is_dir() else []
    notes = [
        f"folder raw: {RAW_DATA_DIR}",
        f"file JSON/CSV ditemukan: {len(source_files)}",
        "manifest.json diabaikan; mode real memeriksa struktur dan kemampuan parsing file",
        "mode simulasi hanya memeriksa daftar file, tanpa parsing atau koneksi database",
    ]
    if PIPELINE_MODE == "simulate" and not source_files:
        notes.append("belum ada file sumber yang ditemukan")
    return _dispatch("validate_raw_files", notes, context)


# --- Tahap 2: inisialisasi skema PostgreSQL ---------------------------------


def initialize_postgres_schemas(**context: Any) -> Any:
    found = [name for name in SCHEMA_FILES if (SCHEMAS_DIR / name).exists()]
    missing = [name for name in SCHEMA_FILES if name not in found]
    notes = [
        f"skema tersedia: {', '.join(found) if found else '(tidak ada)'}",
        (
            f"skema belum dibuat: {', '.join(missing)}"
            if missing
            else "seluruh file skema (bronze, silver, gold, ops) siap di-apply"
        ),
        "pada mode simulasi TIDAK ada koneksi PostgreSQL",
    ]
    return _dispatch("initialize_postgres_schemas", notes, context)


# --- Tahap 3: load Bronze ---------------------------------------------------


def load_bronze(**context: Any) -> dict[str, Any]:
    source_files = [
        path
        for path in RAW_DATA_DIR.rglob("*")
        if path.is_file()
        and path.name != "manifest.json"
        and path.suffix.lower() in {".json", ".csv"}
    ] if RAW_DATA_DIR.is_dir() else []
    notes = [
        f"{len(source_files)} file JSON/CSV ditemukan di {RAW_DATA_DIR}",
        "target: bronze.source_records (payload JSONB utuh + lineage)",
        "rerun aman melalui UNIQUE (source_file, source_row_number)",
        "manifest.json diabaikan",
        "mode simulasi: tidak ada baris yang benar-benar dimuat",
    ]
    return _dispatch("load_bronze", notes, context)


# --- Tahap 4: build Silver --------------------------------------------------


def build_silver(**context: Any) -> dict[str, Any]:
    notes = [
        "normalisasi timestamp ke UTC",
        "deduplikasi dengan deterministic key",
        "validasi foreign reference + penolakan record invalid "
        "(negative quantity, missing reference) ke silver.rejected_records",
        "temporal version selection untuk perubahan profil/kategori",
        "event identity resolution + penanganan late-arriving records",
        "mode simulasi: tidak ada tabel Silver yang ditulis",
    ]
    return _dispatch("build_silver", notes, context)


# --- Tahap 5: quality gate --------------------------------------------------


def quality_gate(**context: Any) -> dict[str, Any]:
    run_id = _run_id(context)
    checks = [
        "ketersediaan tabel Silver yang dibutuhkan Gold",
        "orders dan order_items dihasilkan pada run saat ini",
        "referensi customer/channel/order/product/promotion/inventory valid",
        "jumlah rejected records tercatat dan dirinci",
    ]
    if PIPELINE_MODE == "real":
        return _execute_real("quality_gate", context)
    if _conf_flag(context, "simulate_gate_failure"):
        for check in checks:
            log.info("    - %s: GAGAL (dipaksa via dag_run.conf)", check)
        raise AirflowException(
            "Quality gate GAGAL (simulate_gate_failure=true) — "
            "tahap build_gold dan validate_gold tidak dijalankan."
        )
    log.info("[SIMULASI] Tahap 'quality_gate' | pipeline_run_id=%s", run_id)
    for check in checks:
        log.info("    - %s: LULUS", check)
    return {
        "stage": "quality_gate",
        "mode": "simulate",
        "pipeline_run_id": run_id,
        "notes": [f"{len(checks)} pemeriksaan LULUS", "tahap Gold dibuka"],
    }


# --- Tahap 6: build Gold -----------------------------------------------------


def build_gold(**context: Any) -> dict[str, Any]:
    notes = [
        "membaca Silver (bukan file mentah)",
        "fact dibangun dulu, baru digabung promotion/campaign/inventory",
        *[f"mengisi {table}" for table in GOLD_TABLES],
        "mode simulasi: tidak ada tabel Gold yang ditulis",
    ]
    return _dispatch("build_gold", notes, context)


# --- Tahap 7: validasi Gold + metadata pipeline ------------------------------


def validate_gold_and_record_metadata(**context: Any) -> dict[str, Any]:
    if PIPELINE_MODE == "real":
        return _execute_real("validate_gold_and_record_metadata", context)
    notes = [
        "verifikasi grain dan metric 5 tabel Gold terhadap kontrak gold.sql",
        "rekonsiliasi akhir Gold vs Silver (order, revenue, refund, return)",
        "mencatat status dan error pipeline ke schema ops",
        f"metadata simulasi tercatat: pipeline_run_id={_run_id(context)}",
    ]
    return _simulate("validate_gold_and_record_metadata", notes, context)


# --- Definisi DAG -------------------------------------------------------------


with DAG(
    dag_id="milestone1_omnichannel_pipeline",
    description=(
        "Pipeline omnichannel retail: validate raw -> init schema -> bronze -> silver "
        "-> quality gate -> gold -> validate gold "
        f"(mode {PIPELINE_MODE})"
    ),
    start_date=datetime(2025, 1, 1),
    schedule=None,  # trigger manual — cocok untuk simulasi dan demo
    catchup=False,
    max_active_runs=1,
    tags=["milestone1", "omnichannel", "simulasi" if PIPELINE_MODE == "simulate" else "real"],
    doc_md=__doc__,
    default_args={
        "owner": "aXbar",
        "retries": 0,  # kegagalan (mis. quality gate) langsung terlihat di UI
    },
) as dag:
    t_validate = PythonOperator(
        task_id="validate_raw_files",
        python_callable=validate_raw_files,
    )
    t_init_schemas = PythonOperator(
        task_id="initialize_postgres_schemas",
        python_callable=initialize_postgres_schemas,
    )
    t_bronze = PythonOperator(
        task_id="load_bronze",
        python_callable=load_bronze,
    )
    t_silver = PythonOperator(
        task_id="build_silver",
        python_callable=build_silver,
    )
    t_quality_gate = PythonOperator(
        task_id="quality_gate",
        python_callable=quality_gate,
    )
    t_gold = PythonOperator(
        task_id="build_gold",
        python_callable=build_gold,
    )
    t_validate_gold = PythonOperator(
        task_id="validate_gold_and_record_metadata",
        python_callable=validate_gold_and_record_metadata,
    )

    # Dependency persis kontrak README §8.
    (
        t_validate
        >> t_init_schemas
        >> t_bronze
        >> t_silver
        >> t_quality_gate
        >> t_gold
        >> t_validate_gold
    )
