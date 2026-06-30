from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, List, Optional
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from app.schemas.role import RoleResponse


class LoginRequest(BaseModel):
    email: EmailStr = Field(..., description="Registered email address")
    password: str = Field(..., min_length=8, max_length=100)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Token lifetime in seconds")


class UserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    email: EmailStr
    role: str

    @field_validator("role", mode="before")
    @classmethod
    def coerce_role(cls, v: Any) -> str:
        # When coming from ORM, v is a Role object
        if hasattr(v, "name"):
            name = v.name
            # name is a RoleNameEnum, get its string value
            return name.value if hasattr(name, "value") else str(name)
        return str(v) if v is not None else "employee"

    @classmethod
    def from_orm_user(cls, user: Any) -> "UserSummary":
        return cls(
            id=user.id,
            full_name=user.full_name,
            email=user.email,
            role=user.role.name.value if user.role else "employee",
        )


class AuthData(BaseModel):
    access_token: str
    user: UserSummary


class LoginResponse(BaseModel):
    success: bool = True
    message: str = "Login Successful"
    data: AuthData


class UserBase(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    is_active: bool = True


class UserCreate(UserBase):
    role_id: uuid.UUID
    password: str = Field(
        ...,
        min_length=8,
        max_length=100,
        description="Must contain at least one letter and one number.",
    )

    @field_validator("password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        has_letter = any(c.isalpha() for c in v)
        has_digit  = any(c.isdigit() for c in v)
        if not (has_letter and has_digit):
            raise ValueError("Password must contain at least one letter and one number.")
        return v


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    email: Optional[EmailStr] = None
    role_id: Optional[uuid.UUID] = None


class UserStatusUpdate(BaseModel):
    is_active: bool


class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role_id: uuid.UUID
    role: Optional[RoleResponse] = None
    created_at: datetime
    updated_at: datetime


class UserListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: List[UserResponse]
    total: int
    page: int
    page_size: int


class AgentWorkload(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    email: EmailStr
    open_ticket_count: int = 0
