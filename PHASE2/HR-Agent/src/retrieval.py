from __future__ import annotations

from .cache import ResilientCache
from .contracts import PolicyChunk
from .providers import ModelProvider
from .repository import Repository


class RetrievalService:
    def __init__(self, repository: Repository, provider: ModelProvider, cache: ResilientCache, cache_ttl_seconds: int) -> None:
        self.repository = repository
        self.provider = provider
        self.cache = cache
        self.cache_ttl_seconds = cache_ttl_seconds

    def search(self, query: str, top_k: int = 3) -> list[PolicyChunk]:
        """Version-aware cache -> embed -> lexical/vector candidates -> RRF -> keyword rerank."""
        cache_key = f"retrieval:{query}:{top_k}"
        if self.cache_ttl_seconds > 0:
            cached = self.cache.get(cache_key)
            if cached:
                return [PolicyChunk(**item) for item in cached]

        lex_candidates = self.repository.lexical_search(query, limit=top_k * 3)
        embeddings = self.provider.embed([query])
        vec_candidates = self.repository.vector_search(embeddings[0], limit=top_k * 3) if embeddings else []

        rrf_scores: dict[str, float] = {}
        chunks_by_id: dict[str, PolicyChunk] = {}

        k_rrf = 60
        for rank, c in enumerate(lex_candidates, start=1):
            chunks_by_id[c.chunk_id] = c
            rrf_scores[c.chunk_id] = rrf_scores.get(c.chunk_id, 0.0) + (1.0 / (k_rrf + rank))

        for rank, c in enumerate(vec_candidates, start=1):
            chunks_by_id[c.chunk_id] = c
            rrf_scores[c.chunk_id] = rrf_scores.get(c.chunk_id, 0.0) + (1.0 / (k_rrf + rank))

        # Keyword boost / reranking: prefer exact term matches
        query_words = set(query.lower().split())
        for cid, chunk in chunks_by_id.items():
            content_lower = chunk.content.lower()
            title_lower = chunk.title.lower()
            section_lower = chunk.section.lower()
            for w in query_words:
                if len(w) > 2:
                    if w in title_lower:
                        rrf_scores[cid] += 0.05
                    if w in section_lower:
                        rrf_scores[cid] += 0.03
                    if w in content_lower:
                        rrf_scores[cid] += 0.01

        sorted_chunks = sorted(chunks_by_id.values(), key=lambda c: rrf_scores.get(c.chunk_id, 0.0), reverse=True)
        results = [
            c.model_copy(update={"score": rrf_scores[c.chunk_id]})
            for c in sorted_chunks[:top_k]
        ]

        if self.cache_ttl_seconds > 0 and results:
            self.cache.set(cache_key, [c.model_dump(mode="json") for c in results], ttl_seconds=self.cache_ttl_seconds)

        return results

