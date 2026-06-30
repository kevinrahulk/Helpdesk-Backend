from __future__ import annotations
from enum import Enum

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
