
masuk ke env lokal
.\.venv\Scripts\Activate.ps1
-supaya bisa BE fast api
pip install "fastapi>=0.115,<1" "uvicorn[standard]>=0.34,<1"

-test buat file BE
buat file sandbox

-deploy server fast api
uvicorn sandbox_app:app --reload --port 8000

-akses swaggernya 
localhost:8000/docs

-simulasi login.
hit endpoint chat ``.../api/v1/chat``
dengan login terlebih dahulu(tombol authorize di kanan atas. isi value dengan `token-alya`)

====skema database

-deploy docker di isolasi
-pindah ke folder dulu
cd PHASE2/HR-Agent/belajar-isolasi/storage-lab

-orbitkan container
docker compose up -d
*compose docker isinya postgresql dan uiPGadmin

    Setelah kedua container berstatus healthy / running:
    Buka browser: http://localhost:5050
    Login pgAdmin:
    Email: admin@local.test
    Password: admin