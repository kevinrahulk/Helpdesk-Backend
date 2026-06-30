from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, ConfigDict
from app.schemas.enums import RoleNameEnum


class RoleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: RoleNameEnum
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
