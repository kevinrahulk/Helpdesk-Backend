"""
Similar-ticket vector search.

Primary path: Postgres + `pgvector` extension, using the `<=>` cosine
distance operator for an index-accelerated nearest-neighbor query.

Fallback path (used automatically when `pgvector` is not installed):
load candidate embeddings and rank them with an in-process cosine
similarity calculation. This is O(n) and intended for small/medium
ticket volumes or local development — for large deployments, install
`pgvector` (`pip install pgvector` + `CREATE EXTENSION vector;`).
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass

# pyrefly: ignore [missing-import]
from sqlalchemy import text
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session

from app.ai.config import get_ai_settings
from app.models.ticket import Ticket
from app.models.ticket_embedding import HAS_PGVECTOR, TicketEmbedding


@dataclass
class SimilarTicketMatch:
    ticket_id: uuid.UUID
    ticket_no: str
    title: str
    similarity_score: float


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def find_similar_tickets(
    db: Session,
    query_embedding: list[float],
    *,
    exclude_ticket_id: uuid.UUID | None = None,
    top_k: int | None = None,
    min_score: float | None = None,
) -> list[SimilarTicketMatch]:
    settings = get_ai_settings()
    top_k = top_k or settings.AI_SIMILAR_TICKETS_TOP_K
    min_score = min_score if min_score is not None else settings.AI_SIMILAR_TICKETS_MIN_SCORE

    if HAS_PGVECTOR:
        return _search_pgvector(db, query_embedding, exclude_ticket_id, top_k, min_score)
    return _search_fallback(db, query_embedding, exclude_ticket_id, top_k, min_score)


def _search_pgvector(
    db: Session,
    query_embedding: list[float],
    exclude_ticket_id: uuid.UUID | None,
    top_k: int,
    min_score: float,
) -> list[SimilarTicketMatch]:
    # cosine distance = 1 - cosine similarity, so similarity = 1 - distance
    sql = text(
        """
        SELECT
            te.ticket_id,
            t.ticket_no,
            t.title,
            1 - (te.embedding <=> CAST(:query_embedding AS vector)) AS similarity
        FROM ticket_embeddings te
        JOIN tickets t ON t.id = te.ticket_id
        WHERE (:exclude_id IS NULL OR te.ticket_id != :exclude_id)
        ORDER BY te.embedding <=> CAST(:query_embedding AS vector)
        LIMIT :top_k
        """
    )
    rows = db.execute(
        sql,
        {
            "query_embedding": query_embedding,
            "exclude_id": str(exclude_ticket_id) if exclude_ticket_id else None,
            "top_k": top_k,
        },
    ).fetchall()

    return [
        SimilarTicketMatch(
            ticket_id=row.ticket_id,
            ticket_no=row.ticket_no,
            title=row.title,
            similarity_score=round(float(row.similarity), 4),
        )
        for row in rows
        if row.similarity >= min_score
    ]


def _search_fallback(
    db: Session,
    query_embedding: list[float],
    exclude_ticket_id: uuid.UUID | None,
    top_k: int,
    min_score: float,
) -> list[SimilarTicketMatch]:
    query = db.query(TicketEmbedding, Ticket).join(Ticket, Ticket.id == TicketEmbedding.ticket_id)
    if exclude_ticket_id:
        query = query.filter(TicketEmbedding.ticket_id != exclude_ticket_id)

    scored: list[SimilarTicketMatch] = []
    for embedding_row, ticket in query.all():
        candidate_vector = embedding_row.embedding
        if not isinstance(candidate_vector, list):
            # JSON fallback column may deserialize as list already; guard just in case
            candidate_vector = list(candidate_vector)
        score = _cosine_similarity(query_embedding, candidate_vector)
        if score >= min_score:
            scored.append(
                SimilarTicketMatch(
                    ticket_id=ticket.id,
                    ticket_no=ticket.ticket_no,
                    title=ticket.title,
                    similarity_score=round(score, 4),
                )
            )

    scored.sort(key=lambda m: m.similarity_score, reverse=True)
    return scored[:top_k]


def upsert_ticket_embedding(
    db: Session,
    ticket_id: uuid.UUID,
    source_text: str,
    embedding: list[float],
) -> TicketEmbedding:
    """Create or update the embedding row for a ticket (call after create/resolve)."""
    existing = (
        db.query(TicketEmbedding).filter(TicketEmbedding.ticket_id == ticket_id).one_or_none()
    )
    if existing:
        existing.source_text = source_text
        existing.embedding = embedding
        db.commit()
        db.refresh(existing)
        return existing

    row = TicketEmbedding(
        ticket_id=ticket_id,
        source_text=source_text,
        embedding=embedding,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
