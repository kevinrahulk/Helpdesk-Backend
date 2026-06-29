"""
Module 9 — Reports (Admin only)
GET /reports/summary            high-level metrics
GET /reports/agent-performance  per-agent performance
GET /reports/sla                SLA compliance
GET /reports/ticket-volume      volume by period
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, case, cast, Float
from sqlalchemy.orm import Session

from app.auth import require_admin
from app.database import get_db
from app.models import (
    RoleNameEnum,
    Ticket,
    TicketStatusEnum,
    User,
    Role,
)
from app.schemas import (
    AgentPerformanceRow,
    APIResponse,
    ReportSummary,
    SLAComplianceReport,
    TicketVolumePoint,
)

router = APIRouter(prefix="/reports", tags=["Reports"])


def _base_query(db: Session, date_from: Optional[datetime], date_to: Optional[datetime]):
    q = db.query(Ticket)
    if date_from:
        q = q.filter(Ticket.created_at >= date_from)
    if date_to:
        q = q.filter(Ticket.created_at <= date_to)
    return q


@router.get("/summary", response_model=APIResponse[ReportSummary])
def report_summary(
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    priority: Optional[str] = Query(None),
    category_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """High-level metrics: totals, resolution time, SLA compliance. Admin only."""
    now = datetime.now(timezone.utc)
    q = _base_query(db, date_from, date_to)

    if priority:
        q = q.filter(Ticket.priority == priority)
    if category_id:
        q = q.filter(Ticket.category_id == category_id)

    total = q.count()
    closed = q.filter(Ticket.status == TicketStatusEnum.closed).count()
    overdue = q.filter(
        Ticket.sla_due_at < now,
        Ticket.status.notin_([TicketStatusEnum.resolved, TicketStatusEnum.closed]),
    ).count()

    # Average resolution hours (resolved_at - created_at for resolved/closed)
    resolved_tickets = q.filter(Ticket.resolved_at.isnot(None)).all()
    avg_hours: Optional[float] = None
    if resolved_tickets:
        total_secs = sum(
            (t.resolved_at - t.created_at).total_seconds()
            for t in resolved_tickets
            if t.resolved_at and t.created_at
        )
        avg_hours = round(total_secs / len(resolved_tickets) / 3600, 2)

    # SLA compliance
    closed_or_resolved = q.filter(
        Ticket.status.in_([TicketStatusEnum.resolved, TicketStatusEnum.closed]),
        Ticket.resolved_at.isnot(None),
        Ticket.sla_due_at.isnot(None),
    ).all()

    within_sla = sum(1 for t in closed_or_resolved if t.resolved_at <= t.sla_due_at)
    breached = len(closed_or_resolved) - within_sla
    rate = round((within_sla / len(closed_or_resolved) * 100), 2) if closed_or_resolved else 0.0

    sla_report = SLAComplianceReport(
        resolved_within_sla=within_sla,
        resolved_breached_sla=breached,
        compliance_rate_pct=rate,
    )

    # Ticket volume (last 12 months by month)
    volume_rows = (
        db.query(
            func.to_char(Ticket.created_at, "YYYY-MM").label("period"),
            func.count(Ticket.id).label("count"),
        )
        .group_by("period")
        .order_by("period")
        .limit(12)
        .all()
    )
    volume = [TicketVolumePoint(period=r.period, count=r.count) for r in volume_rows]

    return APIResponse(
        success=True,
        message="Report summary fetched",
        data=ReportSummary(
            total_tickets=total,
            closed_tickets=closed,
            overdue_tickets=overdue,
            avg_resolution_hours=avg_hours,
            sla_compliance=sla_report,
            ticket_volume=volume,
        ),
    )


@router.get("/agent-performance", response_model=APIResponse[list[AgentPerformanceRow]])
def agent_performance(
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Per-agent: ticket count + average resolution hours. Admin only."""
    agent_role = db.query(Role).filter(Role.name == RoleNameEnum.agent).first()
    if not agent_role:
        return APIResponse(success=True, message="No agents found", data=[])

    agents = (
        db.query(User)
        .filter(User.role_id == agent_role.id, User.is_active == True)
        .all()
    )

    rows = []
    for agent in agents:
        q = db.query(Ticket).filter(Ticket.assigned_to == agent.id)
        if date_from:
            q = q.filter(Ticket.created_at >= date_from)
        if date_to:
            q = q.filter(Ticket.created_at <= date_to)

        handled = q.filter(
            Ticket.status.in_([TicketStatusEnum.resolved, TicketStatusEnum.closed])
        ).count()

        resolved = q.filter(Ticket.resolved_at.isnot(None)).all()
        avg_h: Optional[float] = None
        if resolved:
            total_secs = sum(
                (t.resolved_at - t.created_at).total_seconds()
                for t in resolved
                if t.resolved_at and t.created_at
            )
            avg_h = round(total_secs / len(resolved) / 3600, 2)

        rows.append(
            AgentPerformanceRow(
                agent_id=agent.id,
                agent_name=agent.full_name,
                tickets_handled=handled,
                avg_resolution_hours=avg_h,
            )
        )

    return APIResponse(success=True, message="Agent performance fetched", data=rows)


@router.get("/sla", response_model=APIResponse[SLAComplianceReport])
def sla_compliance(
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """SLA compliance stats. Admin only."""
    q = db.query(Ticket).filter(
        Ticket.status.in_([TicketStatusEnum.resolved, TicketStatusEnum.closed]),
        Ticket.resolved_at.isnot(None),
        Ticket.sla_due_at.isnot(None),
    )
    if date_from:
        q = q.filter(Ticket.created_at >= date_from)
    if date_to:
        q = q.filter(Ticket.created_at <= date_to)

    tickets = q.all()
    within = sum(1 for t in tickets if t.resolved_at <= t.sla_due_at)
    breached = len(tickets) - within
    rate = round((within / len(tickets) * 100), 2) if tickets else 0.0

    return APIResponse(
        success=True,
        message="SLA compliance fetched",
        data=SLAComplianceReport(
            resolved_within_sla=within,
            resolved_breached_sla=breached,
            compliance_rate_pct=rate,
        ),
    )


@router.get("/ticket-volume", response_model=APIResponse[list[TicketVolumePoint]])
def ticket_volume(
    groupby: str = Query("month", pattern="^(day|week|month)$"),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Ticket volume grouped by day, week, or month. Admin only."""
    fmt_map = {
        "day":   "YYYY-MM-DD",
        "week":  "IYYY-IW",
        "month": "YYYY-MM",
    }
    fmt = fmt_map[groupby]

    q = db.query(
        func.to_char(Ticket.created_at, fmt).label("period"),
        func.count(Ticket.id).label("count"),
    )
    if date_from:
        q = q.filter(Ticket.created_at >= date_from)
    if date_to:
        q = q.filter(Ticket.created_at <= date_to)

    rows = q.group_by("period").order_by("period").all()
    return APIResponse(
        success=True,
        message="Ticket volume fetched",
        data=[TicketVolumePoint(period=r.period, count=r.count) for r in rows],
    )
