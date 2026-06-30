"""
Module 10 — AI Assistant (Placeholder)
========================================
These endpoints are scaffolded and ready for AI integration.
Currently they return empty/stub responses so the rest of the system
can be tested end-to-end without an AI provider.

POST /ai/ticket-suggestion     → creation-time suggestions (employee)
GET  /ai/tickets/{id}/summary  → agent-facing ticket insight panel
"""

import uuid
from decimal import Decimal
from uuid import UUID

# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, HTTPException
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_agent_or_admin
from app.database import get_db
from app.models import RoleNameEnum, Ticket, TicketAISuggestion, SuggestionTypeEnum, User
from app.schemas import (
    AITicketSuggestionRequest,
    AITicketSuggestionResponse,
    AITicketSummaryResponse,
    APIResponse,
)

router = APIRouter(prefix="/ai", tags=["AI Assistant"])


@router.post("/ticket-suggestion", response_model=APIResponse[AITicketSuggestionResponse])
def get_ticket_suggestion(
    payload: AITicketSuggestionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    [PLACEHOLDER — AI not yet integrated]

    Employee submits title + description before creating a ticket.
    Returns suggested category, priority, first-fix steps, and similar tickets.

    Current behaviour: persists a stub TicketAISuggestion row and returns it.
    Replace the body of this function with real AI provider calls in Phase 2.

    FR-AI-001: AI calls are backend-only — frontend never calls AI directly.
    FR-AI-005: Graceful degradation when AI provider is unavailable.
    """
    # Stub — no AI call yet; create a placeholder suggestion record
    # (ticket_id will be NULL at this stage — linked when ticket is submitted)
    stub_suggestion = TicketAISuggestion(
        ticket_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),  # placeholder
        suggestion_type=SuggestionTypeEnum.creation,
        suggested_category=None,
        suggested_priority=None,
        first_fix=None,
        similar_tickets=None,
        confidence_score=None,
        summary=f"AI suggestions for: {payload.title[:60]}",
    )

    # NOTE: We do NOT persist to DB here since ticket_id is a required FK.
    # When AI is integrated, persist after generating real suggestions,
    # then return the suggestion_id for the employee to include in TicketCreate.

    # For now, return a stub response with a generated UUID
    suggestion_id = uuid.uuid4()

    return APIResponse(
        success=True,
        message="AI suggestion generated (stub — AI not yet integrated)",
        data=AITicketSuggestionResponse(
            suggestion_id=suggestion_id,
            suggested_category=None,
            suggested_priority=None,
            summary=None,
            first_fix=None,
            similar_tickets=None,
            confidence_score=None,
            low_confidence=False,
        ),
    )


@router.get("/tickets/{ticket_id}/summary", response_model=APIResponse[AITicketSummaryResponse])
def get_ticket_summary(
    ticket_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_agent_or_admin),
):
    """
    [PLACEHOLDER — AI not yet integrated]

    Agent/Admin opens a ticket detail page — AI generates:
      - Summary of the ticket
      - Probable root cause
      - Suggested reply to employee
      - Similar resolved ticket references

    Current behaviour: checks ticket exists and returns a stub.
    Replace the body with real AI provider calls in Phase 2.

    FR-AI-006: UI must label all AI outputs as AI-generated.
    """
    ticket = db.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")

    # Check for existing summary suggestion (avoid regenerating)
    existing = (
        db.query(TicketAISuggestion)
        .filter(
            TicketAISuggestion.ticket_id == ticket_id,
            TicketAISuggestion.suggestion_type == SuggestionTypeEnum.summary,
        )
        .order_by(TicketAISuggestion.created_at.desc())
        .first()
    )
    if existing:
        return APIResponse(
            success=True,
            message="Existing AI summary returned",
            data=AITicketSummaryResponse(
                suggestion_id=existing.id,
                summary=existing.summary,
                root_cause=existing.root_cause,
                suggested_reply=existing.suggested_reply,
                similar_tickets=None,
                confidence_score=Decimal(str(existing.confidence_score)) if existing.confidence_score else None,
                low_confidence=False,
            ),
        )

    # Stub — persist a placeholder record
    new_suggestion = TicketAISuggestion(
        ticket_id=ticket_id,
        suggestion_type=SuggestionTypeEnum.summary,
        summary=f"[AI stub] Summary for ticket {ticket.ticket_no}: {ticket.title[:80]}",
        root_cause=None,
        suggested_reply=None,
        confidence_score=None,
    )
    db.add(new_suggestion)
    db.commit()
    db.refresh(new_suggestion)

    return APIResponse(
        success=True,
        message="AI summary generated (stub — AI not yet integrated)",
        data=AITicketSummaryResponse(
            suggestion_id=new_suggestion.id,
            summary=new_suggestion.summary,
            root_cause=None,
            suggested_reply=None,
            similar_tickets=None,
            confidence_score=None,
            low_confidence=False,
        ),
    )
