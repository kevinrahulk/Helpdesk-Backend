"""
AI Helpdesk Ticket Assistant — Pydantic V2 Schemas
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Generic, List, Optional, TypeVar
import math

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)
from enum import Enum


# ---------------------------------------------------------------------------
# 1. Enums
# ---------------------------------------------------------------------------

class RoleNameEnum(str, Enum):
    employee = "employee"
    agent    = "agent"
    admin    = "admin"


class TicketPriorityEnum(str, Enum):
    low      = "low"
    medium   = "medium"
    high     = "high"
    critical = "critical"


class TicketStatusEnum(str, Enum):
    open             = "open"
    in_progress      = "in_progress"
    waiting_for_user = "waiting_for_user"
    resolved         = "resolved"
    closed           = "closed"


class SuggestionTypeEnum(str, Enum):
    creation = "creation"
    summary  = "summary"


# ---------------------------------------------------------------------------
# 2. Role
# ---------------------------------------------------------------------------

class RoleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: RoleNameEnum
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# 3. User / Auth
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# 4. TicketCategory
# ---------------------------------------------------------------------------

class TicketCategoryBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = None
    is_active: bool = True


class TicketCategoryCreate(TicketCategoryBase):
    pass


class TicketCategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class TicketCategoryResponse(TicketCategoryBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# 5. Ticket
# ---------------------------------------------------------------------------

class TicketBase(BaseModel):
    title: str = Field(..., min_length=5, max_length=255)
    description: str = Field(..., min_length=20, max_length=5000)


class TicketCreate(TicketBase):
    category_id: Optional[uuid.UUID] = None
    priority: TicketPriorityEnum = TicketPriorityEnum.medium
    ai_suggestion_id: Optional[uuid.UUID] = None


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

    ai_suggestions: List[TicketAISuggestionResponse] = []
    comments: List[TicketCommentResponse] = []
    status_logs: List[TicketStatusLogResponse] = []
    attachments: List[TicketAttachmentResponse] = []


class TicketListResponse(BaseModel):
    items: List[TicketSummary]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# 6. TicketComment
# ---------------------------------------------------------------------------

class TicketCommentCreate(BaseModel):
    body: str = Field(..., min_length=1, max_length=10000)
    is_internal: bool = Field(False)


class TicketCommentUpdate(BaseModel):
    body: Optional[str] = Field(None, min_length=1, max_length=10000)
    is_internal: Optional[bool] = None


# ---------------------------------------------------------------------------
# 7. TicketAttachment
# ---------------------------------------------------------------------------

class TicketAttachmentCreate(BaseModel):
    ticket_id: uuid.UUID
    uploaded_by: uuid.UUID
    file_name: str = Field(..., max_length=255)
    file_url: str = Field(..., max_length=2048)
    content_type: str = Field(..., max_length=100)
    file_size_bytes: int = Field(..., gt=0, le=10 * 1024 * 1024)


# ---------------------------------------------------------------------------
# 8. Dashboard
# ---------------------------------------------------------------------------

class EmployeeDashboard(BaseModel):
    open_tickets: int = 0
    closed_tickets: int = 0
    recent_tickets: List[TicketSummary] = []


class AgentDashboard(BaseModel):
    assigned_open: int = 0
    assigned_in_progress: int = 0
    assigned_waiting: int = 0
    sla_breached: int = 0
    recently_assigned: List[TicketSummary] = []


class AdminDashboard(BaseModel):
    total_tickets: int = 0
    open_tickets: int = 0
    in_progress_tickets: int = 0
    resolved_tickets: int = 0
    closed_tickets: int = 0
    overdue_tickets: int = 0
    unassigned_tickets: int = 0
    high_priority_tickets: int = 0
    pending_assignments: int = 0
    todays_tickets: int = 0
    agent_workload: List[AgentWorkload] = []
    recent_tickets: List[TicketSummary] = []


# ---------------------------------------------------------------------------
# 9. Reports
# ---------------------------------------------------------------------------

class TicketVolumePoint(BaseModel):
    period: str
    count: int


class AgentPerformanceRow(BaseModel):
    agent_id: uuid.UUID
    agent_name: str
    agent_email: Optional[str] = None
    assigned_tickets: int = 0
    resolved_tickets: int = 0
    open_tickets: int = 0
    tickets_handled: int = 0
    avg_resolution_hours: Optional[float] = None
    sla_compliance_pct: Optional[float] = None


class SLAComplianceReport(BaseModel):
    resolved_within_sla: int
    resolved_breached_sla: int
    compliance_rate_pct: float = Field(..., ge=0.0, le=100.0)


class CategoryDistribution(BaseModel):
    category_name: str
    count: int


class PriorityDistribution(BaseModel):
    priority: str
    count: int


class EmployeeActivityRow(BaseModel):
    employee_id: uuid.UUID
    employee_name: str
    employee_email: Optional[str] = None
    tickets_created: int = 0


class EmployeeActivityReport(BaseModel):
    total_tickets_created: int = 0
    active_employees: int = 0
    most_active: List[EmployeeActivityRow] = []


class ReportSummary(BaseModel):
    total_tickets: int = 0
    open_tickets: int = 0
    in_progress_tickets: int = 0
    resolved_tickets: int = 0
    closed_tickets: int = 0
    overdue_tickets: int = 0
    avg_resolution_hours: Optional[float] = None
    avg_response_hours: Optional[float] = None
    sla_compliance: SLAComplianceReport
    ticket_volume: List[TicketVolumePoint] = []


# ---------------------------------------------------------------------------
# 10. AI placeholder schemas (for later integration)
# ---------------------------------------------------------------------------

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

    @model_validator(mode="after")
    def set_low_confidence_flag(self) -> "AITicketSummaryResponse":
        if self.confidence_score is not None:
            self.low_confidence = self.confidence_score < Decimal("0.50")
        return self


# ---------------------------------------------------------------------------
# 11. Notifications
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# 12. System Settings
# ---------------------------------------------------------------------------

class SystemSettingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    value: str


class SystemSettingUpdate(BaseModel):
    value: str = Field(..., max_length=500)


class CommentPermissionResponse(BaseModel):
    employee_comments_enabled: bool = True


# ---------------------------------------------------------------------------
# 13. Generic API envelope
# ---------------------------------------------------------------------------

DataT = TypeVar("DataT")


class APIResponse(BaseModel, Generic[DataT]):
    success: bool = True
    message: str = "OK"
    data: Optional[DataT] = None


class ErrorResponse(BaseModel):
    success: bool = False
    message: str
    detail: Optional[Any] = None


class PaginatedResponse(BaseModel, Generic[DataT]):
    items: List[DataT]
    total: int
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
    total_pages: int = 0

    @model_validator(mode="after")
    def compute_total_pages(self) -> "PaginatedResponse[DataT]":
        if self.page_size > 0:
            self.total_pages = math.ceil(self.total / self.page_size)
        return self


# Rebuild forward refs
TicketResponse.model_rebuild()
LoginResponse.model_rebuild()
AuthData.model_rebuild()
TicketSummary.model_rebuild()
