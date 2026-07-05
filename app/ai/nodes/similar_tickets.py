"""Node 7 — search similar historical tickets.

This is the reusable node referenced by "Feature 3 — Similar Ticket
Search" in the spec: it's used inside the creation graph, but it's a
standalone function that could equally be dropped into any other graph
(e.g. an agent-facing "find related tickets" tool) because it only
depends on (db session, query text, ticket id to exclude).

If `pgvector` is available it's used automatically (see
app.ai.tools.vector_search); otherwise an in-process cosine-similarity
fallback runs so the feature degrades gracefully instead of breaking.
"""

from __future__ import annotations

import logging
import uuid
from typing import Callable

# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session

from app.ai.config import get_ai_settings
from app.ai.schemas import SimilarTicket
from app.ai.state import TicketCreationState
from app.ai.tools.embeddings import aembed_text
from app.ai.tools.vector_search import find_similar_tickets

logger = logging.getLogger("app.ai.nodes.similar_tickets")


async def search_similar_tickets_for_text(
    db: Session,
    query_text: str,
    *,
    exclude_ticket_id: uuid.UUID | None = None,
    query_embedding: list[float] | None = None,
) -> list[SimilarTicket]:
    """Reusable entry point — callable from any graph or service, not just
    the creation graph."""
    settings = get_ai_settings()
    if not settings.AI_ENABLE_SIMILAR_TICKETS:
        return []

    try:
        if query_embedding is None:
            query_embedding = await aembed_text(query_text)
    except Exception as exc:  # noqa: BLE001
        logger.error("Embedding generation failed for similar-ticket search: %s", exc)
        return []

    matches = find_similar_tickets(db, query_embedding, exclude_ticket_id=exclude_ticket_id)
    return [
        SimilarTicket(
            ticket_id=m.ticket_id,
            ticket_no=m.ticket_no,
            title=m.title,
            similarity_score=m.similarity_score,
            resolution_summary=m.resolution_summary,
        )
        for m in matches
    ]


def build_similar_tickets_node(db: Session) -> Callable[[TicketCreationState], dict]:
    async def find_similar(state: TicketCreationState) -> dict:
        query_text = f"Title: {state['title']}\nDescription: {state['description']}"
        try:
            # 1. Generate query embedding once
            query_embedding = await aembed_text(query_text)
            # 2. Search using this embedding
            similar = await search_similar_tickets_for_text(
                db,
                query_text,
                exclude_ticket_id=state.get("ticket_id"),
                query_embedding=query_embedding,
            )
            return {"similar_tickets": similar, "embedding": query_embedding}
        except Exception as exc:  # noqa: BLE001
            logger.error("find_similar_tickets node failed: %s", exc)
            return {"similar_tickets": [], "errors": [f"find_similar_tickets: {exc}"]}

    return find_similar
