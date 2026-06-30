from __future__ import annotations
import enum


class RoleNameEnum(str, enum.Enum):
    employee = "employee"
    agent    = "agent"
    admin    = "admin"


class TicketPriorityEnum(str, enum.Enum):
    low      = "low"
    medium   = "medium"
    high     = "high"
    critical = "critical"


class TicketStatusEnum(str, enum.Enum):
    open             = "open"
    in_progress      = "in_progress"
    waiting_for_user = "waiting_for_user"
    resolved         = "resolved"
    closed           = "closed"


class SuggestionTypeEnum(str, enum.Enum):
    creation = "creation"
    summary  = "summary"
