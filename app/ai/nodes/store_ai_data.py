import json
import uuid
from datetime import datetime, timezone
from typing import Any
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.ai.tools.embeddings import embed_text


def _serialize_similar_tickets(similar_tickets: list) -> str:
    """Turn a list of `SimilarTicket` pydantic models into the plain
    JSON shape the frontend/`SimilarTicketRef` parsing expects:
    [{"ticket_no": ..., "title": ..., "similarity_score": ..., "resolution_summary": ...}, ...]
    """
    return json.dumps([
        {
            "ticket_id": str(t.ticket_id),
            "ticket_no": t.ticket_no,
            "title": t.title,
            "similarity_score": t.similarity_score,
            "resolution_summary": t.resolution_summary,
        }
        for t in similar_tickets
    ])

def build_generate_embedding_node():
    def generate_embedding(state: Any) -> dict:
        return {}
    return generate_embedding

def build_store_summary_node(db: Session):
    def store_summary(state: Any) -> dict:
        ticket_id = state.get("ticket_id")
        
        # Summary can come from TicketCreationState ("summary") or TicketDetailState ("conversation_summary")
        summary_obj = state.get("summary") or state.get("conversation_summary")
        if ticket_id and summary_obj:
            summary_str = getattr(summary_obj, "summary", None) or getattr(summary_obj, "conversation_summary", None)
            if summary_str:
                db.execute(text("UPDATE tickets SET ai_summary = :summary, last_ai_updated_at = :now WHERE id = :id"), 
                           {"summary": summary_str, "now": datetime.now(timezone.utc), "id": ticket_id})
                db.commit()
        return {}
    return store_summary

def build_store_first_fix_node(db: Session):
    def store_first_fix(state: Any) -> dict:
        ticket_id = state.get("ticket_id")
        first_fix = state.get("first_fix")
        if ticket_id and first_fix:
            db.execute(text("UPDATE tickets SET ai_first_fix = :first_fix, last_ai_updated_at = :now WHERE id = :id"), 
                       {"first_fix": json.dumps(first_fix.model_dump()), "now": datetime.now(timezone.utc), "id": ticket_id})
            db.commit()
        return {}
    return store_first_fix

def build_store_similar_tickets_node(db: Session):
    """Persist the similar tickets found by `find_similar_tickets` onto
    `tickets.ai_similar_tickets`, once, right after they're generated.

    This is the missing half of "generate once, read from DB after
    that": without this node the similar-ticket search result only ever
    lived in the in-memory graph state and was discarded, so every
    consumer (the ticket detail page, the summary endpoint) had nothing
    to read. Writing it here means it is computed exactly once (right
    after ticket submission) and every later view just reads the stored
    column instead of re-querying the LLM/embedding search.
    """
    def store_similar_tickets(state: Any) -> dict:
        ticket_id = state.get("ticket_id")
        similar_tickets = state.get("similar_tickets")
        # Only write when we actually got a result — an empty/None result
        # (e.g. AI_ENABLE_SIMILAR_TICKETS is off, or the node errored) should
        # not overwrite anything, and should not be treated as "already
        # generated" so a later attempt can still try again.
        if ticket_id and similar_tickets is not None:
            db.execute(
                text("UPDATE tickets SET ai_similar_tickets = :similar_tickets, last_ai_updated_at = :now WHERE id = :id"),
                {
                    "similar_tickets": _serialize_similar_tickets(similar_tickets),
                    "now": datetime.now(timezone.utc),
                    "id": ticket_id,
                },
            )
            db.commit()
        return {}
    return store_similar_tickets


def build_store_embedding_node(db: Session):
    def store_embedding(state: Any) -> dict:
        ticket_id = state.get("ticket_id")
        
        # In Creation State, it's title/description
        title = state.get("title")
        description = state.get("description")
        
        # In Detail State, we use the ticket dict
        if not title and "ticket" in state:
            title = state["ticket"].get("title", "")
            description = state["ticket"].get("description", "")
            
        if ticket_id and title:
            # Generate the embedding
            source_text = f"Title: {title}\nDescription: {description}"
            embedding = embed_text(source_text)
            
            stmt = text("""
                INSERT INTO ticket_embeddings (id, ticket_id, source_text, embedding, created_at, updated_at)
                VALUES (:id, :ticket_id, :source_text, :embedding, :now, :now)
                ON CONFLICT (ticket_id) DO UPDATE 
                SET source_text = EXCLUDED.source_text,
                    embedding = EXCLUDED.embedding,
                    updated_at = EXCLUDED.updated_at
            """)
            db.execute(stmt, {
                "id": uuid.uuid4(),
                "ticket_id": ticket_id,
                "source_text": source_text,
                "embedding": str(embedding),
                "now": datetime.now(timezone.utc)
            })
            db.commit()
        return {}
    return store_embedding
