from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, ConfigDict
from app.schemas.user import UserSummary


class TicketStatusLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ticket_id: uuid.UUID
    changed_by: uuid.UUID
    changed_by_user: Optional[UserSummary] = None
    from_status: Optional[str] = None
    to_status: str
    reason: Optional[str] = None
    changed_at: datetime
