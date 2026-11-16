def embed_text(text: str) -> list[float]:
    """Mengubah teks menjadi vektor 1536 dimensi."""
    res = openai_client.embeddings.create(model=EMBEDDING_MODEL, input=text)
    return res.data[0].embedding

# Contoh data tidak terstruktur (kebijakan / artikel)
documents = [
    {
        "id": "doc-cuti-01",
        "text": "Karyawan berhak atas cuti tahunan sebanyak 12 hari kerja setelah masa kerja 1 tahun.",
        "category": "kebijakan_cuti"
    },
    {
        "id": "doc-cuti-02",
        "text": "Pengajuan cuti melahirkan diberikan hingga 3 bulan dengan persetujuan HR.",
        "category": "kebijakan_khusus"
    }
]

# Siapkan data upsert (id, vector, metadata)
vectors_to_upsert = []
for doc in documents:
    vector = embed_text(doc["text"])
    vectors_to_upsert.append({
        "id": doc["id"],
        "values": vector,
        "metadata": {
            "text": doc["text"],
            "category": doc["category"]
        }
    })

# Simpan ke Pinecone (bisa tentukan namespace)
index.upsert(vectors=vectors_to_upsert, namespace="hr-policies")
print("Data berhasil di-upsert ke Pinecone!")