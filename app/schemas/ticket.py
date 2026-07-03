from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.enums import TicketPriorityEnum, TicketStatusEnum
from app.schemas.user import UserSummary
from app.schemas.ticket_category import TicketCategoryResponse
from app.schemas.ticket_comment import TicketCommentResponse
from app.schemas.ticket_status_log import TicketStatusLogResponse
from app.schemas.ticket_attachment import TicketAttachmentResponse
from app.schemas.ai_suggestion import TicketAISuggestionResponse, SimilarTicketRef


class TicketBase(BaseModel):
    title: str = Field(..., min_length=5, max_length=255)
    description: str = Field(..., min_length=20, max_length=5000)


class TicketCreate(TicketBase):
    category_id: Optional[uuid.UUID] = None
    priority: TicketPriorityEnum = TicketPriorityEnum.medium
    ai_suggestion_id: Optional[uuid.UUID] = None
    ai_summary: Optional[str] = None
    ai_first_fix: Optional[dict] = None
    ai_similar_tickets: Optional[list] = None


class TicketUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=5, max_length=255)
    description: Optional[str] = Field(None, min_length=20, max_length=5000)
    category_id: Optional[uuid.UUID] = None
    priority: Optional[TicketPriorityEnum] = None
    sla_due_at: Optional[datetime] = None


class TicketStatusUpdate(BaseModel):
    status: TicketStatusEnum
    reason: Optional[str] = Field(None, max_length=1000)


class TicketAssignRequest(BaseModel):
    agent_id: uuid.UUID = Field(..., description="UUID of the agent to assign.")


class TicketSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ticket_no: str
    title: str
    priority: TicketPriorityEnum
    status: TicketStatusEnum
    created_at: datetime
    sla_due_at: Optional[datetime] = None
    assigned_to: Optional[uuid.UUID] = None
    category_id: Optional[uuid.UUID] = None
    creator: Optional[UserSummary] = None
    assignee: Optional[UserSummary] = None


class TicketResponse(TicketBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ticket_no: str
    category_id: Optional[uuid.UUID] = None
    category: Optional[TicketCategoryResponse] = None
    priority: TicketPriorityEnum
    status: TicketStatusEnum
    created_by: uuid.UUID
    creator: Optional[UserSummary] = None
    assigned_to: Optional[uuid.UUID] = None
    assignee: Optional[UserSummary] = None
    sla_due_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    ai_summary: Optional[str] = None
    ai_first_fix: Optional[dict] = None
    ai_similar_tickets: Optional[List[SimilarTicketRef]] = None
    last_ai_updated_at: Optional[datetime] = None

    ai_suggestions: List[TicketAISuggestionResponse] = []
    comments: List[TicketCommentResponse] = []
    status_logs: List[TicketStatusLogResponse] = []
    attachments: List[TicketAttachmentResponse] = []


class TicketListResponse(BaseModel):
    items: List[TicketSummary]
    total: int
    page: int
    page_size: int
