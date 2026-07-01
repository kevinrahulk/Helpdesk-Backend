from __future__ import annotations

import uuid
from typing import List, Optional
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field

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
    avg_resolution_hours: Optional[str] = None
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
    avg_resolution_hours: Optional[str] = None
    avg_response_hours: Optional[str] = None
    sla_compliance: SLAComplianceReport
    ticket_volume: List[TicketVolumePoint] = []
