"""
AI orchestration service.

This is the seam between FastAPI (routes/services) and LangGraph. Per
the architecture requirement "Avoid putting LangGraph logic inside
route handlers", routers call these functions; these functions build
and invoke the appropriate graph. Nothing in `app/routers` or
`app/services` should import from `app.ai.graphs` or `app.ai.nodes`
directly — only from here.
"""

from __future__ import annotations

import logging
import time
import uuid

# pyrefly: ignore [missing-import]
from fastapi import HTTPException
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session

from app.ai.graphs.creation_graph import build_creation_graph
from app.ai.schemas import ConfidenceResult, TicketSuggestion
from app.ai.state import TicketCreationState
from app.ai.tools.rate_limiter import get_rate_limiter

logger = logging.getLogger("app.ai.orchestration")


class InvalidTicketInputError(ValueError):
    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


async def generate_ticket_creation_suggestion(
    db: Session,
    *,
    title: str,
    description: str,
    requester_id: uuid.UUID | None = None,
) -> TicketSuggestion:
    """Feature 1 entry point — run the creation-assistant graph."""
    get_rate_limiter().acquire()

    trace_id = str(uuid.uuid4())
    started_at = time.monotonic()
    logger.info("ai.creation.start trace_id=%s title=%r", trace_id, title[:80])

    graph = build_creation_graph(db)
    initial_state: TicketCreationState = {
        "title": title,
        "description": description,
        "requester_id": requester_id,
        "errors": [],
        "trace_id": trace_id,
    }

    final_state: TicketCreationState = await graph.ainvoke(initial_state)

    duration_ms = round((time.monotonic() - started_at) * 1000, 1)

    if not final_state.get("is_valid", True):
        logger.info("ai.creation.invalid trace_id=%s errors=%s", trace_id, final_state.get("validation_errors"))
        raise InvalidTicketInputError(final_state.get("validation_errors") or ["Invalid ticket input."])

    category = final_state.get("category")
    priority = final_state.get("priority")
    summary = final_state.get("summary")
    first_fix = final_state.get("first_fix")
    similar_tickets = final_state.get("similar_tickets") or []
    confidence = final_state.get("confidence") or ConfidenceResult(
        confidence=0.0, reason="Confidence step did not run.", needs_human_review=True
    )
    errors = final_state.get("errors") or []

    logger.info(
        "ai.creation.done trace_id=%s duration_ms=%s confidence=%s needs_review=%s errors=%s",
        trace_id, duration_ms, confidence.confidence, confidence.needs_human_review, len(errors),
    )

    return TicketSuggestion(
        suggested_category=category.category_name if category else None,
        category_confidence=category.confidence if category else None,
        suggested_priority=priority.priority if priority else None,
        priority_confidence=priority.confidence if priority else None,
        summary=summary.summary if summary else None,
        first_fix=first_fix or {"steps": [], "estimated_resolution_minutes": None, "requires_agent": True},
        similar_tickets=similar_tickets,
        confidence=confidence,
        errors=errors,
    )



async def trigger_initial_ai_generation_if_missing(ticket_id: uuid.UUID) -> None:
    """Generate and store initial summary and first fix if they are missing at creation time."""
    from app.database import SessionLocal
    from app.models import Ticket
    
    db = SessionLocal()
    try:
        ticket = db.get(Ticket, ticket_id)
        if ticket and (not ticket.ai_summary or not ticket.ai_first_fix):
            graph = build_creation_graph(db)
            initial_state: TicketCreationState = {
                "ticket_id": ticket_id,
                "title": ticket.title,
                "description": ticket.description,
                "requester_id": ticket.created_by,
                "errors": [],
                "trace_id": str(uuid.uuid4()),
            }
            await graph.ainvoke(initial_state)
            logger.info("ai.creation.initial_generation_backfilled ticket_id=%s", ticket_id)
    except Exception as e:
        logger.error("Background initial AI generation failed: %s", e)
    finally:
        db.close()


async def trigger_ai_assignment_update(ticket_id: uuid.UUID) -> None:
    """Run the assignment-summary update graph in the background."""
    from app.database import SessionLocal
    from app.ai.graphs.assignment_graph import build_assignment_graph
    
    db = SessionLocal()
    try:
        graph = build_assignment_graph(db)
        initial_state = {
            "ticket_id": ticket_id,
            "errors": [],
            "trace_id": str(uuid.uuid4()),
        }
        await graph.ainvoke(initial_state)
        logger.info("ai.assignment.summary_updated ticket_id=%s", ticket_id)
    except Exception as e:
        logger.error("Background AI assignment summary update failed: %s", e)
    finally:
        db.close()


async def trigger_ai_resolution_update(ticket_id: uuid.UUID) -> None:
    """Run the resolution-summary generation graph in the background."""
    from app.database import SessionLocal
    from app.ai.graphs.resolution_graph import build_resolution_graph
    
    db = SessionLocal()
    try:
        graph = build_resolution_graph(db)
        initial_state = {
            "ticket_id": ticket_id,
            "errors": [],
            "trace_id": str(uuid.uuid4()),
        }
        await graph.ainvoke(initial_state)
        logger.info("ai.resolution.summary_updated ticket_id=%s", ticket_id)
    except Exception as e:
        logger.error("Background AI resolution summary update failed: %s", e)
    finally:
        db.close()


