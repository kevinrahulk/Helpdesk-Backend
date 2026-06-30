from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.user import UserSummary


class TicketAttachmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ticket_id: uuid.UUID
    uploaded_by: uuid.UUID
    uploader: Optional[UserSummary] = None
    file_name: str
    file_url: str
    content_type: str
    file_size_bytes: int
    created_at: datetime
    updated_at: datetime


class TicketAttachmentCreate(BaseModel):
    ticket_id: uuid.UUID
    uploaded_by: uuid.UUID
    file_name: str = Field(..., max_length=255)
    file_url: str = Field(..., max_length=2048)
    content_type: str = Field(..., max_length=100)
    file_size_bytes: int = Field(..., gt=0, le=10 * 1024 * 1024)
