"""
Structured output models for the AI orchestration layer.

Every node that talks to an LLM parses its response into one of these
models (via LangChain's `with_structured_output`, see app.ai.llm.base).
Keeping these separate from `app.schemas` avoids coupling the AI
internals to the public API contracts — routers/services translate
between the two at the boundary.
"""

from __future__ import annotations

import uuid
from typing import Literal, Optional

# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Feature 1 — Ticket Creation Assistant
# ---------------------------------------------------------------------------

class IntentAnalysis(BaseModel):
    """Output of the intent-analysis node."""

    primary_intent: str = Field(..., description="Short label for what the user is trying to accomplish")
    key_symptoms: list[str] = Field(default_factory=list)
    affected_system: Optional[str] = Field(None, description="Product/system/module the issue relates to")
    urgency_signal: Literal["none", "low", "medium", "high"] = "none"
    is_actionable: bool = Field(True, description="False if the ticket text is too vague to analyze")
    is_it_related: bool = Field(
        True,
        description="False if the ticket describes a real, coherent problem that is nonetheless not an IT/helpdesk issue (e.g. medical, legal, personal, physical). Independent of is_actionable.",
    )


class CategoryPrediction(BaseModel):
    category_name: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    alternative_categories: list[str] = Field(default_factory=list)
    rationale: str = ""


class PriorityPrediction(BaseModel):
    priority: Literal["low", "medium", "high", "critical"]
    confidence: float = Field(..., ge=0.0, le=1.0)
    rationale: str = ""


class TicketSummary(BaseModel):
    """Concise summary generated at creation time."""

    summary: str


class FirstFixSuggestion(BaseModel):
    steps: list[str] = Field(default_factory=list)
    estimated_resolution_minutes: Optional[int] = None
    requires_agent: bool = Field(
        False, description="True if this cannot realistically be self-served by the employee"
    )


class SimilarTicket(BaseModel):
    ticket_id: uuid.UUID
    ticket_no: str
    title: str
    similarity_score: float = Field(..., ge=0.0, le=1.0)
    resolution_summary: Optional[str] = None


class ConfidenceResult(BaseModel):
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason: str
    needs_human_review: bool = False
    component_scores: dict[str, float] = Field(default_factory=dict)


class TicketSuggestion(BaseModel):
    """Final structured payload for Feature 1 (creation-time assistant)."""

    suggested_category: Optional[str] = None
    category_confidence: Optional[float] = None
    suggested_priority: Optional[str] = None
    priority_confidence: Optional[float] = None
    summary: Optional[str] = None
    first_fix: FirstFixSuggestion = Field(default_factory=FirstFixSuggestion)
    similar_tickets: list[SimilarTicket] = Field(default_factory=list)
    confidence: ConfidenceResult
    errors: list[str] = Field(default_factory=list, description="Non-fatal node errors, for observability")



