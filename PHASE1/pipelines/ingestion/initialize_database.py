
    # ###### ======== Q & A ======== #####
    # Q = apakah perlu buat directory baru lagi?
    # A = __Tidak perlu directory baru, tidak perlu generate project baru.__ Repo yang sekarang sudah ADALAH "dasar" milestone ini — ini paket participant yang sudah disiapkan instructor (berbasis __uv__, Python ≥3.11, FastAPI engine + Streamlit UI + `gold.sql` contract + test harness). Yang harus Anda lakukan adalah __mengisi bagian yang hilang di dalam repo ini__, bukan scaffold proyek baru.


    #     Q = Bagaimana menghubungkan file-file python di repo ini agar bisa      berinteraksi dengan database postgre?
    #     Bagaimana membuat file koneksi agar file file python ini bisa berhubungan dengan database apakah harus buat connection.py? dan bagiamana nanti jika saya eksekusi 'loader_bronze.py' apakah saya harus run file connection dan bagaimana jika saya melakukan via DAG nantinya bagaimana membuat koneksi tetap valid?
    #     A = MEnggunakan file shared/db.py. aman digunakan jika secara file terpisah atau secara beruntun/pipepline dengan airflow.
    #     Tidak perlu membuat atau menjalankan `connection.py` terpisah. Gunakan helper `shared/db.py` melalui `pipelines.ingestion.db`. Loader meminta koneksi saat fungsi loader berjalan, misalnya dengan `connect("local")`, lalu koneksi ditutup setelah pekerjaan selesai. Untuk eksekusi manual, konfigurasi database harus tersedia di `.env` atau environment. Untuk Airflow, konfigurasi yang sama harus tersedia di lingkungan worker/container Airflow juga; `localhost` di dalam container menunjuk ke container itu sendiri, bukan otomatis ke komputer host. Pipeline milestone harus memakai PostgreSQL lokal, bukan Neon. Jangan menulis password ke kode atau log.

    # Q = Untuk schema bronze pakai desain 'shred & load' atau pakai JSONB ?
    # A = pADA file readmie ada anjuran JSONB. README memperbolehkan payload Bronze disimpan sebagai JS   raw tetap disimpan tanpa perubahan di `data/raw/`.

    # Q = Bagaimana cara membuat script untuk menjalankan schema agar tabel benar-benar dibuat di     database?
    # A = PostgreSQL dan database tujuan harus sudah hidup/tersedia terlebih dahulu. File SQL adalah resep pembentukan schema/tabel; untuk menerapkannya gunakan `uv run python -m pipelines.ingestion.initialize_database` dari folder `PHASE1`. Script tersebut memakai `shared/db.py`, memilih koneksi `local`, lalu menjalankan `bronze.sql`, `silver.sql`, `gold.sql`, dan `ops.sql` dalam satu koneksi/transaksi. Script dapat dijalankan manual untuk pengembangan, dan fungsi `run()` yang sama dapat dipanggil sebagai task inisialisasi dari DAG. Jika salah satu file

    # cara reset DB = DROP SCHEMA IF EXISTS bronze, silver, gold, ops CASCADE;


    # Q = Apa perbedaan `pipelines/__init__.py` dan `pipelines/ingestion/__init__.py`?
    # A = Keduanya adalah penanda/pengaturan package Python, bukan script koneksi atau inisialisasi database. File pertama menandai folder `pipelines` sebagai package utama. File kedua menandai subpackage `pipelines.ingestion`. Keduanya membantu import seperti `from pipelines.ingestion.db import connect`. Untuk membuat tabel, gunakan modul terpisah `pipelines.ingestion.initialize_database`.

    # Q = Apakah tabel `bronze.ingestion_files` memang diperlukan?
    # A = Tidak wajib secara teori, tetapi berguna dan sesuai schema Bronze saat ini. `bronze.source_records` mencatat lineage per record; `bronze.ingestion_files` mencatat metadata per file dan per run, seperti SHA-256 hasil hitung loader, ukuran, jumlah record, dan `pipeline_run_id`. Tabel ini tidak menyimpan checksum manifest karena manifest diabaikan.






"""Create the milestone schemas in the local PostgreSQL database."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any

from pipelines.ingestion.db import apply_sql_file, connect

log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCHEMA_DIR = PROJECT_ROOT / "database" / "schemas"
REQUIRED_SCHEMA_FILES = ("bronze.sql", "silver.sql", "gold.sql", "ops.sql")


def run(
    pipeline_run_id: str | None = None,
    context: dict[str, Any] | None = None,
    schema_dir: Path | str = DEFAULT_SCHEMA_DIR,
) -> list[str]:
    """Apply all schema files to the local database in one transaction.

    ``pipeline_run_id`` and ``context`` are accepted so Airflow can call this
    function through the same interface as the other pipeline stages.
    """
    del pipeline_run_id, context
    schema_path = Path(schema_dir).resolve()
    missing = [name for name in REQUIRED_SCHEMA_FILES if not (schema_path / name).is_file()]
    if missing:
        missing_list = ", ".join(missing)
        raise FileNotFoundError(f"Schema file(s) missing in {schema_path}: {missing_list}")

    applied: list[str] = []
    with connect("local") as connection:
        for filename in REQUIRED_SCHEMA_FILES:
            path = schema_path / filename
            log.info("Applying schema file %s", path)
            apply_sql_file(connection, path)
            applied.append(filename)

    log.info("Initialized local PostgreSQL schemas: %s", ", ".join(applied))
    return applied


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create Bronze, Silver, Gold, and Ops schemas in local PostgreSQL."
    )
    parser.add_argument(
        "--schema-dir",
        type=Path,
        default=DEFAULT_SCHEMA_DIR,
        help=f"Directory containing schema SQL files (default: {DEFAULT_SCHEMA_DIR})",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    run(schema_dir=args.schema_dir)


if __name__ == "__main__":
    main()
