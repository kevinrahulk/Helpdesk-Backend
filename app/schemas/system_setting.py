from __future__ import annotations
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, ConfigDict, Field

class SystemSettingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    key: str
    value: str


class SystemSettingUpdate(BaseModel):
    value: str = Field(..., max_length=500)


class CommentPermissionResponse(BaseModel):
    employee_comments_enabled: bool = True
