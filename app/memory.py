from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime

import numpy as np

from app import embeddings


@dataclass
class MemoryHit:
    id: str
    question_summary: str
    final_reply: str
    score: float


def add_memory(
    conn,
    *,
    question_summary: str,
    final_reply: str,
    language: str,
    theme_tags: list[str],
    source: str,
    conversation_id: str | None = None,
) -> str:
    embedding = embeddings.embed_texts([question_summary])[0]
    created_at = datetime.now(UTC).isoformat()
    cursor = conn.execute(
        """
        INSERT INTO approved_memory (
            conversation_id,
            customer_question_summary,
            final_reply,
            language,
            theme_tags,
            embedding,
            source,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            conversation_id,
            question_summary,
            final_reply,
            language,
            json.dumps(theme_tags),
            embedding,
            source,
            created_at,
        ),
    )
    conn.commit()
    return str(cursor.lastrowid)


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def search_similar(
    conn,
    query: str,
    *,
    language: str | None,
    limit: int = 5,
) -> list[MemoryHit]:
    query_embedding = np.frombuffer(embeddings.embed_texts([query])[0], dtype=np.float32)

    sql = """
        SELECT id, customer_question_summary, final_reply, embedding
        FROM approved_memory
        WHERE embedding IS NOT NULL
    """
    params: list[str] = []
    if language is not None:
        sql += " AND language = ?"
        params.append(language)

    hits: list[MemoryHit] = []
    for row_id, summary, reply, embedding_blob in conn.execute(sql, params):
        memory_embedding = np.frombuffer(embedding_blob, dtype=np.float32)
        score = _cosine_similarity(query_embedding, memory_embedding)
        hits.append(
            MemoryHit(
                id=str(row_id),
                question_summary=summary,
                final_reply=reply,
                score=score,
            )
        )

    hits.sort(key=lambda hit: (-hit.score, int(hit.id)))
    return hits[:limit]
