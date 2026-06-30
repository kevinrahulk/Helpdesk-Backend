# ── Enums ───────────────────────────────────────────────────────────────────
from app.schemas.enums import (
    RoleNameEnum,
    TicketPriorityEnum,
    TicketStatusEnum,
    SuggestionTypeEnum,
)

# ── Generic API envelope ────────────────────────────────────────────────────
from app.schemas.common import (
    DataT,
    APIResponse,
    ErrorResponse,
    PaginatedResponse,
)

# ── Role ─────────────────────────────────────────────────────────────────────
from app.schemas.role import RoleResponse

# ── User / Auth ──────────────────────────────────────────────────────────────
from app.schemas.user import (
    LoginRequest,
    TokenResponse,
    UserSummary,
    AuthData,
    LoginResponse,
    UserBase,
    UserCreate,
    UserUpdate,
    UserStatusUpdate,
    UserResponse,
    UserListResponse,
    AgentWorkload,
)

# ── TicketCategory ───────────────────────────────────────────────────────────
from app.schemas.ticket_category import (
    TicketCategoryBase,
    TicketCategoryCreate,
    TicketCategoryUpdate,
    TicketCategoryResponse,
)

# ── TicketComment ────────────────────────────────────────────────────────────
from app.schemas.ticket_comment import (
    TicketCommentResponse,
    TicketCommentCreate,
    TicketCommentUpdate,
)

# ── TicketStatusLog ──────────────────────────────────────────────────────────
from app.schemas.ticket_status_log import TicketStatusLogResponse

# ── TicketAttachment ─────────────────────────────────────────────────────────
from app.schemas.ticket_attachment import (
    TicketAttachmentResponse,
    TicketAttachmentCreate,
)

# ── AI suggestion (ticket-embedded + standalone placeholder schemas) ────────
from app.schemas.ai_suggestion import (
    SimilarTicketRef,
    TicketAISuggestionResponse,
    AITicketSuggestionRequest,
    AITicketSuggestionResponse,
    AITicketSummaryResponse,
)

# ── Ticket ───────────────────────────────────────────────────────────────────
from app.schemas.ticket import (
    TicketBase,
    TicketCreate,
    TicketUpdate,
    TicketStatusUpdate,
    TicketAssignRequest,
    TicketSummary,
    TicketResponse,
    TicketListResponse,
)

# ── Dashboard ────────────────────────────────────────────────────────────────
from app.schemas.dashboard import (
    EmployeeDashboard,
    AgentDashboard,
    AdminDashboard,
)

# ── Reports ──────────────────────────────────────────────────────────────────
from app.schemas.reports import (
    TicketVolumePoint,
    AgentPerformanceRow,
    SLAComplianceReport,
    CategoryDistribution,
    PriorityDistribution,
    EmployeeActivityRow,
    EmployeeActivityReport,
    ReportSummary,
)

# ── Notifications ────────────────────────────────────────────────────────────
from app.schemas.notification import (
    NotificationResponse,
    NotificationListResponse,
)

# ── System Settings ──────────────────────────────────────────────────────────
from app.schemas.system_setting import (
    SystemSettingResponse,
    SystemSettingUpdate,
    CommentPermissionResponse,
)


__all__ = [
    # enums
    "RoleNameEnum",
    "TicketPriorityEnum",
    "TicketStatusEnum",
    "SuggestionTypeEnum",
    # common
    "DataT",
    "APIResponse",
    "ErrorResponse",
    "PaginatedResponse",
    # role
    "RoleResponse",
    # user / auth
    "LoginRequest",
    "TokenResponse",
    "UserSummary",
    "AuthData",
    "LoginResponse",
    "UserBase",
    "UserCreate",
    "UserUpdate",
    "UserStatusUpdate",
    "UserResponse",
    "UserListResponse",
    "AgentWorkload",
    # ticket category
    "TicketCategoryBase",
    "TicketCategoryCreate",
    "TicketCategoryUpdate",
    "TicketCategoryResponse",
    # ticket comment
    "TicketCommentResponse",
    "TicketCommentCreate",
    "TicketCommentUpdate",
    # ticket status log
    "TicketStatusLogResponse",
    # ticket attachment
    "TicketAttachmentResponse",
    "TicketAttachmentCreate",
    # ai suggestion
    "SimilarTicketRef",
    "TicketAISuggestionResponse",
    "AITicketSuggestionRequest",
    "AITicketSuggestionResponse",
    "AITicketSummaryResponse",
    # ticket
    "TicketBase",
    "TicketCreate",
    "TicketUpdate",
    "TicketStatusUpdate",
    "TicketAssignRequest",
    "TicketSummary",
    "TicketResponse",
    "TicketListResponse",
    # dashboard
    "EmployeeDashboard",
    "AgentDashboard",
    "AdminDashboard",
    # reports
    "TicketVolumePoint",
    "AgentPerformanceRow",
    "SLAComplianceReport",
    "CategoryDistribution",
    "PriorityDistribution",
    "EmployeeActivityRow",
    "EmployeeActivityReport",
    "ReportSummary",
    # notifications
    "NotificationResponse",
    "NotificationListResponse",
    # system settings
    "SystemSettingResponse",
    "SystemSettingUpdate",
    "CommentPermissionResponse",
]


# ── Rebuild forward refs ──────────────────────────────────────────────────
# Mirrors the original single-file module: with `from __future__ import
# annotations`, nested model references are deferred, so we force a rebuild
# once every schema class has been imported and is resolvable.
TicketResponse.model_rebuild()
LoginResponse.model_rebuild()
AuthData.model_rebuild()
TicketSummary.model_rebuild()
