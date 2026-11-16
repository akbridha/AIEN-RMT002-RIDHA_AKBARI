def search_vector(query: str, top_k: int = 2, category: str = None):
    # Ubah query menjadi vektor
    query_vector = embed_text(query)
    
    # Filter opsional berdasarkan metadata
    filter_dict = {"category": {"$eq": category}} if category else None
    
    # Query ke Pinecone
    response = index.query(
        namespace="hr-policies",
        vector=query_vector,
        top_k=top_k,
        include_metadata=True,
        filter=filter_dict
    )
    
    print(f"\nHasil pencarian untuk: '{query}'")
    for match in response.matches:
        score = match.score
        doc_id = match.id
        text = match.metadata.get("text", "")
        print(f"[{doc_id}] (Skor: {score:.3f}): {text}")

# Uji pencarian (walaupun kata-katanya berbeda: 'libur' vs 'cuti')
search_vector("Berapa lama libur tahunan pegawai?")