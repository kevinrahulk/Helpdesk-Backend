from app.models.base import Base, TimestampMixin

from app.models.enums import (
    RoleNameEnum,
    TicketPriorityEnum,
    TicketStatusEnum,
    SuggestionTypeEnum,
)

from app.models.role import Role
from app.models.user import User
from app.models.ticket_category import TicketCategory
from app.models.ticket import Ticket
from app.models.ticket_ai_suggestion import TicketAISuggestion
from app.models.ticket_comment import TicketComment
from app.models.ticket_status_log import TicketStatusLog
from app.models.ticket_attachment import TicketAttachment
from app.models.notification import Notification
from app.models.system_setting import SystemSetting

__all__ = [
    "Base",
    "TimestampMixin",
    # enums
    "RoleNameEnum",
    "TicketPriorityEnum",
    "TicketStatusEnum",
    "SuggestionTypeEnum",
    # models
    "Role",
    "User",
    "TicketCategory",
    "Ticket",
    "TicketAISuggestion",
    "TicketComment",
    "TicketStatusLog",
    "TicketAttachment",
    "Notification",
    "SystemSetting",
]
