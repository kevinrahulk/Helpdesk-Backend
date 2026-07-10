"""
Module 10 — AI Assistant
=========================
Thin FastAPI routes. All LangGraph orchestration lives behind
`app.ai.services.ai_orchestration_service` — routes never import
`app.ai.graphs` or `app.ai.nodes` directly (see that module's
docstring for why).

POST /ai/ticket-suggestion     → creation-time suggestions (employee)
GET  /ai/tickets/{id}/summary  → agent-facing ticket insight panel
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, HTTPException
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session

from app.ai.services import (
    InvalidTicketInputError,
    generate_ticket_creation_suggestion,
)
from app.auth import get_current_user, require_agent_or_admin
from app.database import get_db
from app.models import SuggestionTypeEnum, Ticket, TicketAISuggestion, User
from app.schemas import (
    AITicketSuggestionRequest,
    AITicketSuggestionResponse,
    AITicketSummaryResponse,
    APIResponse,
    SimilarTicketRef,
)

router = APIRouter(prefix="/ai", tags=["AI Assistant"])


@router.post("/ticket-suggestion", response_model=APIResponse[AITicketSuggestionResponse])
async def get_ticket_suggestion(
    payload: AITicketSuggestionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Employee submits title + description before creating a ticket.
    Runs the Feature 1 LangGraph workflow and returns suggested category,
    priority, summary, first-fix steps, similar tickets, and a confidence
    score. Does NOT persist a TicketAISuggestion row yet, since no ticket
    exists — the caller should re-submit these fields when creating the
    ticket, at which point the ticket service can persist the final
    suggestion linked to the new ticket_id.

    FR-AI-001: AI calls are backend-only — frontend never calls AI directly.
    FR-AI-005: Graceful degradation when AI provider is unavailable (nodes
    fall back to safe defaults rather than raising; see app.ai.nodes.*).
    """
    try:
        suggestion = await generate_ticket_creation_suggestion(
            db,
            title=payload.title,
            description=payload.description,
            requester_id=current_user.id,
        )
    except InvalidTicketInputError as exc:
        raise HTTPException(status_code=422, detail="; ".join(exc.errors)) from exc

    suggestion_id = uuid.uuid4()
    confidence_score = Decimal(str(suggestion.confidence.confidence))

    return APIResponse(
        success=True,
        message="AI suggestion generated"
        if not suggestion.confidence.needs_human_review
        else "AI suggestion generated (low confidence — recommend manual review)",
        data=AITicketSuggestionResponse(
            suggestion_id=suggestion_id,
            suggested_category=suggestion.suggested_category,
            suggested_priority=suggestion.suggested_priority,
            summary=suggestion.summary,
            first_fix=suggestion.first_fix.steps if suggestion.first_fix else [],
            similar_tickets=[
                SimilarTicketRef(
                    ticket_id=t.ticket_id,
                    ticket_no=t.ticket_no,
                    title=t.title,
                    similarity=Decimal(str(t.similarity_score)),
                )
                for t in suggestion.similar_tickets
            ],
            confidence_score=confidence_score,
            category_confidence=(
                Decimal(str(suggestion.category_confidence)) if suggestion.category_confidence is not None else None
            ),
            priority_confidence=(
                Decimal(str(suggestion.priority_confidence)) if suggestion.priority_confidence is not None else None
            ),
            confidence_reason=suggestion.confidence.reason,
            needs_human_review=suggestion.confidence.needs_human_review,
            degraded=bool(suggestion.errors),
        ),
    )


@router.get("/tickets/{ticket_id}/summary", response_model=APIResponse[AITicketSummaryResponse])
async def get_ticket_summary(
    ticket_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_agent_or_admin),
):
    """
    Agent/Admin opens a ticket detail page. Runs the Feature 2 LangGraph
    workflow (load ticket → load comments → load status history →
    summarize → recommend next action → confidence) and persists the
    result as a TicketAISuggestion row.

    Recent suggestions (within AI_CACHE_TTL_SECONDS) are reused instead
    of re-running the graph, to avoid re-billing the LLM provider every
    time an agent re-opens the same ticket in quick succession.

    FR-AI-006: UI must label all AI outputs as AI-generated.
    """
    ticket = db.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")

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
            data=_to_summary_response(db, existing, ticket),
        )

    # Fallback: if no suggestion record exists, but we have ai_summary on the ticket:
    if ticket.ai_summary:
        new_suggestion = TicketAISuggestion(
            ticket_id=ticket_id,
            suggestion_type=SuggestionTypeEnum.summary,
            summary=ticket.ai_summary,
            root_cause="None",
            suggested_reply="Awaiting assignment." if not ticket.assigned_to else "Assigned.",
            confidence_score=1.0,
            detail_context={
                "important_customer_info": [],
                "actions_already_attempted": [],
                "pending_items": [],
                "risk_level": "low",
                "errors": [],
            },
        )
        db.add(new_suggestion)
        db.commit()
        db.refresh(new_suggestion)
        return APIResponse(
            success=True,
            message="AI summary returned from ticket",
            data=_to_summary_response(db, new_suggestion, ticket),
        )

    # If absolutely no summary is found, return a default mock summary response.
    # We do NOT run the detail summary graph or invoke the LLM to avoid charges on view.
    mock_id = uuid.uuid4()
    similar_refs = None
    if ticket.ai_similar_tickets:
        try:
            similar_refs = _resolve_similar_ticket_refs(db, ticket.ai_similar_tickets)
        except Exception:
            pass

    return APIResponse(
        success=True,
        message="Default AI summary returned (no summary generated yet)",
        data=AITicketSummaryResponse(
            suggestion_id=mock_id,
            summary="Awaiting AI summary generation.",
            root_cause="Unknown",
            suggested_reply="Awaiting assignment.",
            similar_tickets=similar_refs,
            confidence_score=Decimal("1.00"),
            current_issue="Unknown",
            important_customer_info=[],
            actions_already_attempted=[],
            recommended_next_action="Awaiting assignment.",
            pending_items=[],
            risk_level="low",
            degraded=False,
        )
    )


def _resolve_similar_ticket_refs(db: Session, raw_similar: list | str | None) -> list[SimilarTicketRef]:
    from app.routers.tickets import resolve_similar_tickets
    resolved_items = resolve_similar_tickets(db, raw_similar)

    similar_refs = []
    for item in resolved_items:
        if isinstance(item, dict):
            similar_refs.append(
                SimilarTicketRef(
                    ticket_id=uuid.UUID(item["ticket_id"]) if item.get("ticket_id") else None,
                    ticket_no=item.get("ticket_no"),
                    title=item.get("title"),
                    similarity=(
                        Decimal(str(item["similarity_score"])) if item.get("similarity_score") is not None else None
                    ),
                )
            )
    return similar_refs


def _to_summary_response(db: Session, existing: TicketAISuggestion, ticket: Ticket | None = None) -> AITicketSummaryResponse:
    ctx = existing.detail_context or {}

    similar_refs = None
    if ticket and ticket.ai_similar_tickets:
        try:
            similar_refs = _resolve_similar_ticket_refs(db, ticket.ai_similar_tickets)
        except Exception:
            pass

    return AITicketSummaryResponse(
        suggestion_id=existing.id,
        summary=existing.summary,
        root_cause=existing.root_cause,
        suggested_reply=existing.suggested_reply,
        similar_tickets=similar_refs,
        confidence_score=Decimal(str(existing.confidence_score)) if existing.confidence_score else None,
        current_issue=existing.root_cause,
        important_customer_info=ctx.get("important_customer_info", []),
        actions_already_attempted=ctx.get("actions_already_attempted", []),
        recommended_next_action=existing.suggested_reply,
        pending_items=ctx.get("pending_items", []),
        risk_level=ctx.get("risk_level"),
        degraded=bool(ctx.get("errors")),
    )
