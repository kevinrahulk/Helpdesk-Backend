from __future__ import annotations
import uuid
from datetime import datetime
from typing import List, Optional
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, ConfigDict

class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    message: str
    ticket_id: Optional[uuid.UUID] = None
    is_read: bool
    created_at: datetime


class NotificationListResponse(BaseModel):
    items: List[NotificationResponse]
    total: int
    unread_count: int
