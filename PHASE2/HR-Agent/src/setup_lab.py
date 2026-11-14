from __future__ import annotations

import re
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def chunk_policy(path: Path) -> list[dict[str, str]]:
    """Parse front matter and deterministic section chunks with stable IDs."""
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError(f"Invalid front matter in {path}")

    # Parse YAML-like front matter
    metadata: dict[str, str] = {}
    for line in parts[1].strip().splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            metadata[k.strip()] = v.strip()

    body = parts[2].strip()
    sections = re.split(r"(?m)^##\s+", body)

    chunks: list[dict[str, str]] = []
    for section_text in sections:
        section_text = section_text.strip()
        if not section_text:
            continue
        lines = section_text.splitlines()
        section_title = lines[0].strip()
        content = "\n".join(lines[1:]).strip()

        slug = re.sub(r"[^a-z0-9]+", "-", section_title.lower()).strip("-")
        chunk_id = f"{metadata.get('document_id', '')}#{slug}"

        chunks.append({
            "chunk_id": chunk_id,
            "document_id": metadata.get("document_id", ""),
            "title": metadata.get("title", ""),
            "section": section_title,
            "version": metadata.get("version", ""),
            "effective_date": metadata.get("effective_date", ""),
            "content": content,
        })

    return chunks


def reset_and_seed() -> None:
    """Create pgvector schema, seed synthetic identities/balances, batch embed, and upsert chunks."""
    from src.config import get_settings
    import psycopg

    settings = get_settings()
    init_sql_path = ROOT / "data" / "init.sql"
    init_sql = init_sql_path.read_text(encoding="utf-8")

    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(init_sql)

            # Read all policy files and chunk them
            policies_dir = ROOT / "data" / "policies"
            all_chunks = []
            for policy_file in sorted(policies_dir.glob("*.md")):
                all_chunks.extend(chunk_policy(policy_file))

            # Optional embedding if live model is ready
            embeddings: list[list[float] | None] = [None] * len(all_chunks)
            if settings.live_model_ready:
                from src.providers import OpenAIProvider
                provider = OpenAIProvider()
                texts = [c["content"] for c in all_chunks]
                embeddings = provider.embed(texts)  # type: ignore

            for chunk, emb in zip(all_chunks, embeddings):
                cur.execute(
                    """
                    INSERT INTO policy_chunk (chunk_id, document_id, title, section, version, effective_date, content, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (document_id, section, version) DO UPDATE
                    SET title = EXCLUDED.title,
                        content = EXCLUDED.content,
                        embedding = EXCLUDED.embedding;
                    """,
                    (
                        chunk["chunk_id"],
                        chunk["document_id"],
                        chunk["title"],
                        chunk["section"],
                        chunk["version"],
                        chunk["effective_date"],
                        chunk["content"],
                        str(emb) if emb else None,
                    ),
                )
        conn.commit()


if __name__ == "__main__":
    reset_and_seed()

