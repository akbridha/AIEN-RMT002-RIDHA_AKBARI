# Storage Lab: PostgreSQL (pgvector)

Lab terisolasi ini dirancang khusus untuk menguji inisialisasi penyimpanan (DDL schema & static seed) tanpa menjalankan backend API, agent, maupun proses chunk embedding.

Container ini mengekspos port `5432:5432` ke host mesin Anda, sehingga dapat langsung diakses dari **pgAdmin yang terpasang di host/laptop**.

## File di Lab Ini
- `init.sql`: Berisi DDL untuk 7 tabel utama + seed data awal pegawai, saldo, dan riwayat cuti.
- `docker-compose.yml`: Menjalankan service `postgres` (pgvector).

## Cara Menjalankan

1. Masuk ke direktori lab:
   ```bash
   cd PHASE2/HR-Agent/belajar-isolasi/storage-lab
   ```

2. Jalankan container:
   ```bash
   docker compose up -d
   ```

3. Hubungkan dari **pgAdmin Host (Desktop)**:
   - Buka pgAdmin di komputer Anda.
   - Klik kanan **Servers** -> **Register** -> **Server...**
   - Di tab **General**:
     - **Name**: `HR Assistant DB (Docker)`
   - Di tab **Connection**:
     - **Host name/address**: `localhost` (atau `127.0.0.1`)
     - **Port**: `5432`
     - **Maintenance database**: `hr_assistant`
     - **Username**: `hr_app`
     - **Password**: `hr_app` (centang *Save password*)
   - Klik **Save**.

4. Navigasi ke:
   `Databases` -> `hr_assistant` -> `Schemas` -> `public` -> `Tables`.

5. Tabel yang Langsung Tersedia:
   - `employee` (3 baris seed)
   - `leave_balance` (6 baris seed)
   - `leave_request` (2 baris seed historis)
   - `action_proposal`
   - `hr_ticket`
   - `policy_chunk`
   - `agent_trace`

## Menghentikan Lab
```bash
docker compose down
# atau jika ingin membersihkan volume data untuk reset ulang:
docker compose down -v
```
