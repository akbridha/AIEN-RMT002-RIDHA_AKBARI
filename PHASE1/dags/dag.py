"""DAG utama milestone P1M1 — orkestrasi 7 tahap sesuai kontrak README §8.

Urutan wajib:
    validate manifest dan raw files -> initialize PostgreSQL schemas
        -> load Bronze -> build Silver -> quality gate (gagal -> berhenti)
        -> build Gold -> validate Gold dan record pipeline metadata

Mode operasi dikontrol oleh environment variable ``PIPELINE_MODE``:

* ``simulate`` (default) — setiap tahap HANYA mencatat log simulasi dan
  pemeriksaan file read-only (manifest/schema). Tidak ada koneksi database
  dan tidak ada operasi ingestion/build/transform nyata. Tujuannya agar
  dependency, rerun, dan perilaku quality gate bisa didemokan lebih dulu.
* ``real`` — setiap tahap memanggil modul pipeline yang sesuai
  (``pipelines.*``). Modul yang belum diimplementasikan menghasilkan error
  yang jelas, sehingga tahap gagal eksplisit, bukan "berhasil palsu".

``dag_run.conf`` mendukung ``{"simulate_gate_failure": true}`` untuk
mendemonstrasikan quality gate yang menghentikan tahap Gold.
"""

from __future__ import annotations

import importlib
import json
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

PIPELINE_MODE = os.getenv("PIPELINE_MODE", "simulate").strip().lower()
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
    "validate_manifest_and_raw": ("pipelines.ingestion.validate_manifest", "run"),
    "initialize_postgres_schemas": ("pipelines.ingestion.initialize_database", "run"),
    "load_bronze": ("pipelines.bronze.build_bronze", "run"),
    "build_silver": ("pipelines.silver.build_silver", "run"),
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


def _read_manifest() -> dict[str, Any] | None:
    manifest_path = RAW_DATA_DIR / "manifest.json"
    if not manifest_path.exists():
        return None
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _dispatch(stage: str, simulate_notes: list[str], context: dict[str, Any]) -> dict[str, Any]:
    if PIPELINE_MODE == "real":
        return _execute_real(stage, context)
    return _simulate(stage, simulate_notes, context)



# --- Tahap 1: validasi manifest dan raw files -------------------------------


def validate_manifest_and_raw(**context: Any) -> dict[str, Any]:
    manifest = _read_manifest()
    if manifest is not None:
        counts = manifest.get("record_counts", {})
        total_rows = sum(counts.values()) if isinstance(counts, dict) else 0
        notes = [
            f"manifest.json ditemukan: {len(manifest.get('files', {}))} file terdaftar",
            f"rentang tanggal {manifest.get('start_date')} s/d {manifest.get('end_date')}",
            f"total baris pada manifest: {total_rows}",
            "checksum SHA-256 tiap file akan diverifikasi pada mode real",
        ]
    else:
        notes = [
            f"manifest.json BELUM ada di {RAW_DATA_DIR} "
            "(unduh dataset Google Drive ke data/raw/)",
            "mode simulasi tetap lanjut; mode real akan menggagalkan tahap ini",
        ]
    return _dispatch("validate_manifest_and_raw", notes, context)


# --- Tahap 2: inisialisasi skema PostgreSQL ---------------------------------


def initialize_postgres_schemas(**context: Any) -> dict[str, Any]:
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
    manifest = _read_manifest()
    if manifest and isinstance(manifest.get("record_counts"), dict):
        counts = manifest["record_counts"]
        total = sum(counts.values())
        notes = [
            f"{len(counts)} sumber data, total ±{total} baris",
            "target: bronze.source_records (payload JSONB utuh + lineage)",
            "append-only dan idempotent via pipeline_run_id",
            "mode simulasi: tidak ada baris yang benar-benar dimuat",
        ]
    else:
        notes = [
            "manifest tidak tersedia — daftar sumber dibaca dari struktur data/raw/",
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
        "uniqueness grain per tabel Gold",
        "reconciliation net_revenue vs Silver",
        "reconciliation refunded_amount vs event payment/refund",
        "tidak ada fact multiplication pada join promotion/campaign/inventory",
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
        "Pipeline omnichannel retail: validate -> init schema -> bronze -> silver "
        "-> quality gate -> gold -> validate gold (mode simulasi secara default)"
    ),
    start_date=datetime(2025, 1, 1),
    schedule=None,  # trigger manual — cocok untuk simulasi dan demo
    catchup=False,
    max_active_runs=1,
    tags=["milestone1", "omnichannel", "simulasi" if PIPELINE_MODE == "simulate" else "real"],
    doc_md=__doc__,
    default_args={
        "owner": "data-engineer",
        "retries": 0,  # kegagalan (mis. quality gate) langsung terlihat di UI
    },
) as dag:
    t_validate = PythonOperator(
        task_id="validate_manifest_and_raw",
        python_callable=validate_manifest_and_raw,
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

