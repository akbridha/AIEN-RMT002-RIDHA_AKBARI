import os
import time
from dotenv import load_dotenv, find_dotenv
from pinecone import Pinecone, ServerlessSpec

# 1. Otomatis cari file .env di folder parent/root
load_dotenv(find_dotenv())

pinecone_api_key = os.getenv("VECTOR_DB_KEY", "").strip()
if not pinecone_api_key:
    raise ValueError("PINECONE_API_KEY belum terpasang di file .env!")

# 2. Inisialisasi Pinecone Client
pc = Pinecone(api_key=pinecone_api_key)

# 3. Parameter Index
INDEX_NAME = "knowledge-base-vector"
DIMENSION = 1536       # Wajib 1536 jika memakai OpenAI text-embedding-3-small
METRIC = "cosine"      # Pengukuran kemiripan sudut vektor

# 4. Buat Index jika belum ada
if not pc.has_index(INDEX_NAME):
    print(f"Mengirim perintah pembuatan index '{INDEX_NAME}' ke Pinecone...")
    pc.create_index(
        name=INDEX_NAME,
        dimension=DIMENSION,
        metric=METRIC,
        spec=ServerlessSpec(cloud="aws", region="us-east-1")
    )
    
    # Tunggu beberapa detik sampai status index menjadi 'Ready'
    print("Menunggu index siap di cloud Pinecone...")
    while not pc.describe_index(INDEX_NAME).status["ready"]:
        time.sleep(2)
        print("  ...masih inisialisasi...")
    print(f"Selamat! Index '{INDEX_NAME}' berhasil dibuat dan siap digunakan.")
else:
    print(f"Index '{INDEX_NAME}' sudah ada sebelumnya di Pinecone.")

# 5. Hubungkan dan cek statistik index
index = pc.Index(INDEX_NAME)
stats = index.describe_index_stats()
print("\nStatistik Index saat ini:")
print(stats)