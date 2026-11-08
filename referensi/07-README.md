# Lab RAG RuangKarya — V3

**Durasi:** sekitar 65 menit setelah setup. **Siapkan:** Python 3.11+, OpenAI API key, Pinecone API key, internet, dan dasar Python/RAG.

RuangKarya adalah penyedia ruang kerja **fiktif**. Folder ini berdiri sendiri; tidak perlu materi v1/v2 atau database lokal. OpenAI membuat embedding, Pinecone menyimpan dan mencari passage, lalu notebook membandingkan hasilnya. Ini lab yang dipandu, bukan ujian tertutup.

## Isi folder

```text
v3/
├── .env.example             # template konfigurasi tanpa key asli
├── .gitignore               # melindungi key dan cache saat folder dipindah
├── README.md
├── requirements.txt
├── rag_helpers.py
├── lab-kasus-rag.ipynb
└── corpus/
    ├── 10 dokumen aktif .md
    └── arsip/
        └── 1 aturan lama .md
```

## Setup di Windows PowerShell

Buka PowerShell **di folder `v3`**, lalu jalankan:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

Di Notepad, isi `OPENAI_API_KEY` dan `PINECONE_API_KEY`. Ganti `PINECONE_NAMESPACE` menjadi nama unik untukmu, misalnya `ruangkarya-v3-ani`. Simpan file, lalu lanjutkan:

```powershell
python -m ipykernel install --user --name ruangkarya-v3 --display-name "RuangKarya V3"
jupyter lab
```

Pilih kernel **RuangKarya V3**. Notebook akan membaca `.env` otomatis dengan `python-dotenv`; kamu tidak perlu membuat environment variable di PowerShell. Jika PowerShell menolak aktivasi, gunakan `.venv\Scripts\python.exe -m pip install -r requirements.txt` dan `.venv\Scripts\python.exe -m jupyter lab`.

Di macOS/Linux, gunakan `python3 -m venv .venv`, aktifkan dengan `source .venv/bin/activate`, instal requirements, salin dengan `cp .env.example .env`, lalu edit `.env` sebelum membuka Jupyter.

> **Jaga key:** `.env` diabaikan oleh Git. Jangan menaruh key di notebook atau membagikan `.env`. Sebelum mengirim salinan folder, keluarkan juga `.venv/` dan `.cache/`.

## Apa yang dilakukan notebook?

Notebook membuat embedding dengan `text-embedding-3-small` untuk dokumen dan pertanyaan. Embedding disimpan di `.cache/` berdasarkan model dan isi teks. Pada run berikutnya, cache menghindari panggilan embedding yang sama. Pinecone tetap memerlukan internet untuk menyimpan passage dan menjalankan query.

Notebook membuat satu **index Pinecone** secara otomatis jika belum ada. `PINECONE_INDEX` boleh sama untuk peserta yang memakai satu proyek Pinecone, tetapi setiap peserta harus punya **namespace unik** agar data eksperimen tidak bercampur. Jika index lama dengan nama yang sama memakai schema berbeda, pilih nama index lain di `.env`. Pembuatan index pertama kali bisa memerlukan beberapa menit. Periksa batas dan biaya akun Pinecone serta OpenAI sebelum kelas.

Empat kasusnya:

1. Aturan pembatalan lama muncul → saring metadata `status` sebelum retrieval.
2. Baris tabel `R17` terpotong → buat passage yang menjaga satu baris tetap utuh.
3. `R17` KD-410 tertukar dengan KD-420 → bandingkan dense search dan BM25 di Pinecone, gabungkan dengan RRF, lalu filter model.
4. Angka biaya kartu hilang tidak ada → periksa dukungan passage dan jangan menebak.

**SIMULASI TERKENDALI** adalah contoh yang sengaja diatur. **HASIL RUN** adalah hasil dari embedding, index, dan query yang dijalankan peserta. Jangan melaporkan ranking simulasi sebagai pengukuran.

| Bagian | Waktu |
| --- | ---: |
| Peta data dan indexing | 10 menit |
| Empat kasus | 40 menit |
| Tugas mandiri dan diskusi | 15 menit |

**Yang dikumpulkan:** notebook yang sudah dijalankan dan tabel ringkasan di bagian akhir. Untuk tiap kasus, tulis masalahnya, perubahan yang dicoba, dan apakah hasilnya membaik. Bagian menulis jawaban dengan LLM bersifat opsional.

> **Catatan untuk pengajar:** sel wajib sudah diuji dari salinan folder dengan respons OpenAI dan Pinecone tiruan. Ranking dan waktu dari layanan asli **belum diuji langsung** karena tidak ada API key di lingkungan pengembangan. Jalankan notebook sekali sebelum kelas dan catat hasilnya. Hybrid tidak selalu menaikkan peringkat.

> **Batas latihan:** ini prototipe kelas. Aplikasi produksi masih perlu pengelolaan akses, pembaruan index, retry, biaya, dan monitoring.

## Jika ada kendala

| Gejala | Cek ini |
| --- | --- |
| `.env` tidak ditemukan | Salin `.env.example` menjadi `.env` di folder `v3`. |
| Key tidak terbaca | Pastikan dua key terisi di `.env`, simpan file, lalu jalankan ulang sel pertama. |
| Index Pinecone bentrok schema | Ubah `PINECONE_INDEX` di `.env` ke nama baru. |
| Hasil Pinecone belum muncul | Tunggu sebentar, lalu ulangi sel indexing. Upsert memerlukan waktu sebelum data terlihat. |
| `corpus/` tidak ditemukan | Buka Jupyter dari folder `v3`. |

## Bacaan lanjutan

- [Embedding OpenAI](https://developers.openai.com/api/docs/guides/embeddings)
- [Pinecone: membuat index](https://docs.pinecone.io/guides/index-data/create-an-index)
- [Pinecone: filter metadata](https://docs.pinecone.io/guides/search/filter-by-metadata)
