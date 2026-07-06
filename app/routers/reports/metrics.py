from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import require_admin
from app.database import get_db
from app.models import (
    RoleNameEnum,
    Ticket,
    TicketCategory,
    TicketComment,
    TicketPriorityEnum,
    TicketStatusEnum,
    User,
    Role,
)
from app.routers.reports.helpers import _apply_filters, _base_query
from app.schemas import (
    APIResponse,
    AgentPerformanceRow,
    CategoryDistribution,
    EmployeeActivityReport,
    EmployeeActivityRow,
    PriorityDistribution,
    ReportSummary,
    SLAComplianceReport,
    TicketVolumePoint,
)

router = APIRouter()


@router.get("/summary", response_model=APIResponse[ReportSummary])
def report_summary(
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    priority: Optional[str] = Query(None),
    category_id: Optional[UUID] = Query(None),
    status: Optional[str] = Query(None, alias="status_filter"),
    agent_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """High-level metrics: totals, resolution time, SLA compliance. Admin only."""
    now = datetime.now(timezone.utc)
    q = _base_query(db, date_from, date_to)
    q = _apply_filters(q, status, priority, category_id, agent_id)

    total = q.count()
    open_count = q.filter(Ticket.status == TicketStatusEnum.open).count()
    in_progress = q.filter(Ticket.status == TicketStatusEnum.in_progress).count()
    resolved = q.filter(Ticket.status == TicketStatusEnum.resolved).count()
    closed = q.filter(Ticket.status == TicketStatusEnum.closed).count()
    overdue = q.filter(
        Ticket.sla_due_at < now,
        Ticket.status.notin_([TicketStatusEnum.resolved, TicketStatusEnum.closed]),
    ).count()

    # Average resolution hours (resolved_at - created_at for resolved/closed)
    resolved_tickets = q.filter(Ticket.resolved_at.isnot(None)).all()
    avg_hours: Optional[str] = None
    if resolved_tickets:
        total_secs = sum(
            (t.resolved_at - t.created_at).total_seconds()
            for t in resolved_tickets
            if t.resolved_at and t.created_at
        )
        avg_seconds = total_secs / len(resolved_tickets)
        hours = int(avg_seconds // 3600)
        minutes = int((avg_seconds % 3600) // 60)
        avg_hours = f"{hours}.{minutes}"

    # Average response time (first comment - created_at)
    avg_response: Optional[str] = None
    tickets_with_comments = q.filter(Ticket.resolved_at.isnot(None)).all()
    response_times = []
    for t in tickets_with_comments:
        first_comment = (
            db.query(TicketComment)
            .filter(TicketComment.ticket_id == t.id)
            .order_by(TicketComment.created_at.asc())
            .first()
        )
        if first_comment and t.created_at:
            diff = (first_comment.created_at - t.created_at).total_seconds()
            if diff > 0:
                response_times.append(diff)
    if response_times:
        avg_res_seconds = sum(response_times) / len(response_times)
        res_hours = int(avg_res_seconds // 3600)
        res_minutes = int((avg_res_seconds % 3600) // 60)
        avg_response = f"{res_hours}.{res_minutes}"

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
    vol_q = _base_query(db, date_from, date_to)
    vol_q = _apply_filters(vol_q, status, priority, category_id, agent_id)
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
            open_tickets=open_count,
            in_progress_tickets=in_progress,
            resolved_tickets=resolved,
            closed_tickets=closed,
            overdue_tickets=overdue,
            avg_resolution_hours=avg_hours,
            avg_response_hours=avg_response,
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
    """Per-agent: ticket counts + average resolution hours + SLA compliance. Admin only."""
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

        assigned_count = q.count()
        resolved_count = q.filter(
            Ticket.status.in_([TicketStatusEnum.resolved, TicketStatusEnum.closed])
        ).count()
        open_count = q.filter(
            Ticket.status.notin_([TicketStatusEnum.resolved, TicketStatusEnum.closed])
        ).count()
        resolved_tickets = q.filter(Ticket.resolved_at.isnot(None)).all()
        avg_h: Optional[str] = None
        if resolved_tickets:
            total_secs = sum(
                (t.resolved_at - t.created_at).total_seconds()
                for t in resolved_tickets
                if t.resolved_at and t.created_at
            )
            avg_seconds_agent = total_secs / len(resolved_tickets)
            hours_agent = int(avg_seconds_agent // 3600)
            minutes_agent = int((avg_seconds_agent % 3600) // 60)
            avg_h = f"{hours_agent}.{minutes_agent}"

        # SLA compliance
        sla_tickets = q.filter(
            Ticket.resolved_at.isnot(None),
            Ticket.sla_due_at.isnot(None),
        ).all()
        sla_pct: Optional[float] = None
        if sla_tickets:
            within = sum(1 for t in sla_tickets if t.resolved_at <= t.sla_due_at)
            sla_pct = round(within / len(sla_tickets) * 100, 1)

        rows.append(
            AgentPerformanceRow(
                agent_id=agent.id,
                agent_name=agent.full_name,
                agent_email=agent.email,
                assigned_tickets=assigned_count,
                resolved_tickets=resolved_count,
                open_tickets=open_count,
                tickets_handled=resolved_count,
                avg_resolution_hours=avg_h,
                sla_compliance_pct=sla_pct,
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
    status: Optional[str] = Query(None, alias="status_filter"),
    priority: Optional[str] = Query(None),
    category_id: Optional[UUID] = Query(None),
    agent_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Ticket volume grouped by day, week, or month. Admin only."""
    fmt_map = {
        "day": "YYYY-MM-DD",
        "week": "IYYY-IW",
        "month": "YYYY-MM",
    }
    if groupby not in fmt_map:
        raise HTTPException(status_code=400, detail="Invalid groupby period")
    fmt = fmt_map[groupby]

    q = db.query(
        func.to_char(Ticket.created_at, fmt).label("period"),
        func.count(Ticket.id).label("count"),
    )
    if date_from:
        q = q.filter(Ticket.created_at >= date_from)
    if date_to:
        q = q.filter(Ticket.created_at <= date_to)
    if status:
        q = q.filter(Ticket.status == status)
    if priority:
        q = q.filter(Ticket.priority == priority)
    if category_id:
        q = q.filter(Ticket.category_id == category_id)
    if agent_id:
        q = q.filter(Ticket.assigned_to == agent_id)

    rows = q.group_by("period").order_by("period").all()
    return APIResponse(
        success=True,
        message="Ticket volume fetched",
        data=[TicketVolumePoint(period=r.period, count=r.count) for r in rows],
    )


@router.get("/category-distribution", response_model=APIResponse[list[CategoryDistribution]])
def category_distribution(
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    status: Optional[str] = Query(None, alias="status_filter"),
    priority: Optional[str] = Query(None),
    agent_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Ticket count by category. Admin only."""
    q = db.query(
        func.coalesce(TicketCategory.name, "Uncategorized").label("category_name"),
        func.count(Ticket.id).label("count"),
    ).outerjoin(TicketCategory, Ticket.category_id == TicketCategory.id)

    if date_from:
        q = q.filter(Ticket.created_at >= date_from)
    if date_to:
        q = q.filter(Ticket.created_at <= date_to)
    if status:
        q = q.filter(Ticket.status == status)
    if priority:
        q = q.filter(Ticket.priority == priority)
    if agent_id:
        q = q.filter(Ticket.assigned_to == agent_id)

    rows = q.group_by("category_name").order_by(func.count(Ticket.id).desc()).all()
    return APIResponse(
        success=True,
        message="Category distribution fetched",
        data=[CategoryDistribution(category_name=r.category_name, count=r.count) for r in rows],
    )


@router.get("/priority-distribution", response_model=APIResponse[list[PriorityDistribution]])
def priority_distribution(
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    status: Optional[str] = Query(None, alias="status_filter"),
    category_id: Optional[UUID] = Query(None),
    agent_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Ticket count by priority. Admin only."""
    q = db.query(
        Ticket.priority.label("priority"),
        func.count(Ticket.id).label("count"),
    )
    if date_from:
        q = q.filter(Ticket.created_at >= date_from)
    if date_to:
        q = q.filter(Ticket.created_at <= date_to)
    if status:
        q = q.filter(Ticket.status == status)
    if category_id:
        q = q.filter(Ticket.category_id == category_id)
    if agent_id:
        q = q.filter(Ticket.assigned_to == agent_id)

    rows = q.group_by(Ticket.priority).all()
    return APIResponse(
        success=True,
        message="Priority distribution fetched",
        data=[PriorityDistribution(priority=r.priority.value if hasattr(r.priority, 'value') else str(r.priority), count=r.count) for r in rows],
    )


@router.get("/employee-activity", response_model=APIResponse[EmployeeActivityReport])
def employee_activity(
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Employee activity stats: tickets created, most active. Admin only."""
    employee_role = db.query(Role).filter(Role.name == RoleNameEnum.employee).first()
    if not employee_role:
        return APIResponse(success=True, message="No employees found",
                           data=EmployeeActivityReport())

    q = db.query(Ticket)
    if date_from:
        q = q.filter(Ticket.created_at >= date_from)
    if date_to:
        q = q.filter(Ticket.created_at <= date_to)

    total_created = q.count()

    # Count active employees (those who created at least one ticket)
    active_q = db.query(func.count(func.distinct(Ticket.created_by)))
    if date_from:
        active_q = active_q.filter(Ticket.created_at >= date_from)
    if date_to:
        active_q = active_q.filter(Ticket.created_at <= date_to)
    active_count = active_q.scalar() or 0

    # Most active requesters
    top_q = db.query(
        User.id,
        User.full_name,
        User.email,
        func.count(Ticket.id).label("tickets_created"),
    ).join(Ticket, Ticket.created_by == User.id)
    if date_from:
        top_q = top_q.filter(Ticket.created_at >= date_from)
    if date_to:
        top_q = top_q.filter(Ticket.created_at <= date_to)

    top_rows = (
        top_q.group_by(User.id, User.full_name, User.email)
        .order_by(func.count(Ticket.id).desc())
        .limit(10)
        .all()
    )

    most_active = [
        EmployeeActivityRow(
            employee_id=r.id,
            employee_name=r.full_name,
            employee_email=r.email,
            tickets_created=r.tickets_created,
        )
        for r in top_rows
    ]

    return APIResponse(
        success=True,
        message="Employee activity fetched",
        data=EmployeeActivityReport(
            total_tickets_created=total_created,
            active_employees=active_count,
            most_active=most_active,
        ),
    )
