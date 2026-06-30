from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.user import UserSummary


class TicketCommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ticket_id: uuid.UUID
    author_id: uuid.UUID
    author: Optional[UserSummary] = None
    body: str
    is_internal: bool
    created_at: datetime
    updated_at: datetime


class TicketCommentCreate(BaseModel):
    body: str = Field(..., min_length=1, max_length=10000)
    is_internal: bool = Field(False)


class TicketCommentUpdate(BaseModel):
    body: Optional[str] = Field(None, min_length=1, max_length=10000)
    is_internal: Optional[bool] = None
