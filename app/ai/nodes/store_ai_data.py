import json
import uuid
from datetime import datetime, timezone
from typing import Any
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.ai.tools.embeddings import embed_text

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
