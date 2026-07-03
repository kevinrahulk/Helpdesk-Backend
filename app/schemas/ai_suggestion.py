
# from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, List, Optional

# pyrefly: ignore [missing-import]
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from app.schemas.enums import SuggestionTypeEnum, TicketPriorityEnum


class SimilarTicketRef(BaseModel):
    ticket_no: str
    title: str


class TicketAISuggestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ticket_id: uuid.UUID
    suggestion_type: SuggestionTypeEnum
    suggested_category: Optional[str] = None
    suggested_priority: Optional[str] = None
    summary: Optional[str] = None
    root_cause: Optional[str] = None
    suggested_reply: Optional[str] = None
    first_fix: Optional[List[str]] = None
    similar_tickets: Optional[List[SimilarTicketRef]] = None
    confidence_score: Optional[Decimal] = None
    created_at: datetime
    updated_at: datetime

    @field_validator("confidence_score", mode="before")
    @classmethod
    def coerce_decimal(cls, v: Any) -> Optional[Decimal]:
        if v is None:
            return None
        return Decimal(str(v))


class AITicketSuggestionRequest(BaseModel):
    title: str = Field(..., min_length=5, max_length=255)
    description: str = Field(..., min_length=20, max_length=5000)


class AITicketSuggestionResponse(BaseModel):
    suggestion_id: uuid.UUID
    suggested_category: Optional[str] = None
    suggested_priority: Optional[TicketPriorityEnum] = None
    summary: Optional[str] = None
    first_fix: Optional[List[str]] = None
    similar_tickets: Optional[List[SimilarTicketRef]] = None
    confidence_score: Optional[Decimal] = Field(None, ge=Decimal("0.00"), le=Decimal("1.00"))
    low_confidence: bool = False
    category_confidence: Optional[Decimal] = None
    priority_confidence: Optional[Decimal] = None
    confidence_reason: Optional[str] = None
    needs_human_review: bool = False
    degraded: bool = Field(
        False, description="True if one or more AI steps fell back to a default (e.g. provider outage)."
    )

    @model_validator(mode="after")
    def set_low_confidence_flag(self) -> "AITicketSuggestionResponse":
        if self.confidence_score is not None:
            self.low_confidence = self.confidence_score < Decimal("0.50")
        return self


class AITicketSummaryResponse(BaseModel):
    suggestion_id: uuid.UUID
    summary: Optional[str] = None
    root_cause: Optional[str] = None
    suggested_reply: Optional[str] = None
    similar_tickets: Optional[List[SimilarTicketRef]] = None
    confidence_score: Optional[Decimal] = Field(None, ge=Decimal("0.00"), le=Decimal("1.00"))
    low_confidence: bool = False

    # Feature 2 — AI Ticket Detail Summary fields
    current_issue: Optional[str] = None
    important_customer_info: Optional[List[str]] = None
    actions_already_attempted: Optional[List[str]] = None
    recommended_next_action: Optional[str] = None
    pending_items: Optional[List[str]] = None
    risk_level: Optional[str] = None
    degraded: bool = Field(
        False, description="True if one or more AI steps fell back to a default (e.g. provider outage)."
    )

    @model_validator(mode="after")
    def set_low_confidence_flag(self) -> "AITicketSummaryResponse":
        if self.confidence_score is not None:
            self.low_confidence = self.confidence_score < Decimal("0.50")
        return self
