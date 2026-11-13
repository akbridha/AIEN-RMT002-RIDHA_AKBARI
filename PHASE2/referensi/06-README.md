# RAG untuk Data Terstruktur

Folder ini berisi notebook, dependensi, dataset sintetis, dan konfigurasi contoh untuk menjalankan lab secara mandiri.

## Mulai cepat

Butuh Python 3.11+, URL PostgreSQL read-only, dan API key OpenAI.

Windows PowerShell, jalankan perintah dari folder ini:

    python -m venv .venv
    .venv\Scripts\Activate.ps1
    python -m pip install -r requirements.txt
    Copy-Item .env.example .env
    jupyter lab 18_rag_structured_data.ipynb

macOS/Linux, jalankan perintah dari folder ini:

    python3 -m venv .venv
    source .venv/bin/activate
    python -m pip install -r requirements.txt
    cp .env.example .env
    jupyter lab 18_rag_structured_data.ipynb

Isi .env lokal dengan RAG_DATABASE_URL dan OPENAI_API_KEY. AGENT_MODEL opsional; default-nya gpt-4o-mini. Jangan membagikan .env.

## Database

Instruktur dapat memberi URL read-only ke database lab yang sudah disiapkan. Untuk database lab baru:

1. Jalankan setup.sql sebagai pemilik database. Skrip membuat ulang hanya objek dalam schema m18_rag_structured_data.
2. Salin setup_reader_role.sql.example menjadi setup_reader_role.local.sql di folder ini.
3. Ganti password placeholder dengan password unik, lalu jalankan file lokal itu sekali sebagai pemilik database.
4. Simpan URL role m18_rag_reader ke RAG_DATABASE_URL dalam .env.

setup_reader_role.sql.example mengasumsikan nama database playground. Jika nama database berbeda, ubah baris GRANT CONNECT sebelum menjalankan. setup.sql memberi ulang akses schema jika role m18_rag_reader sudah ada.

Semua baris dataset bersifat fiktif. View employee_directory tidak mengekspos kolom salary. Notebook mengirim skema ke OpenAI saat menyusun SQL, kemudian mengirim hasil query yang dibatasi saat merangkai jawaban.
