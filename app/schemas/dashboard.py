from __future__ import annotations
from typing import List

# pyrefly: ignore [missing-import]
from pydantic import BaseModel

from app.schemas.user import AgentWorkload
from app.schemas.ticket import TicketSummary


class StatusCounts(BaseModel):
    open: int = 0
    in_progress: int = 0
    waiting_for_user: int = 0
    resolved: int = 0
    closed: int = 0


class EmployeeDashboard(BaseModel):
    open_tickets: int = 0
    resolved_tickets: int = 0
    in_progress_tickets: int = 0
    waiting_for_user_tickets: int = 0
    status_counts: StatusCounts = StatusCounts()
    recent_tickets: List[TicketSummary] = []


class AgentDashboard(BaseModel):
    assigned_open: int = 0
    assigned_in_progress: int = 0
    assigned_waiting: int = 0
    assigned_resolved: int = 0
    waiting_for_user_tickets: int = 0
    sla_breached: int = 0
    status_counts: StatusCounts = StatusCounts()
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
    status_counts: StatusCounts = StatusCounts()
    agent_workload: List[AgentWorkload] = []
    recent_tickets: List[TicketSummary] = []
