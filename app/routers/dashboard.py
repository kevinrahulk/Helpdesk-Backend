"""
Module 2 — Dashboard
GET /dashboard  — role-filtered summary statistics
"""

from datetime import datetime, timezone
from sqlalchemy.orm import joinedload
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import (
    Role,
    RoleNameEnum,
    Ticket,
    TicketPriorityEnum,
    TicketStatusEnum,
    User,
)
from app.schemas import (
    AdminDashboard,
    AgentDashboard,
    AgentWorkload,
    APIResponse,
    EmployeeDashboard,
    TicketSummary,
)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("", response_model=APIResponse)
def get_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns role-specific dashboard data:
    - Employee  → own ticket counts + recent
    - Agent     → assigned ticket counts + SLA breach count
    - Admin     → system-wide counts + agent workload
    """
    role = current_user.role.name
    now = datetime.now(timezone.utc)

    if role == RoleNameEnum.employee:
        base = db.query(Ticket).filter(Ticket.created_by == current_user.id)

        open_count = base.filter(
            Ticket.status.notin_([TicketStatusEnum.resolved, TicketStatusEnum.closed])
        ).count()

        closed_count = base.filter(
            Ticket.status == TicketStatusEnum.closed
        ).count()

        recent = (
            base.order_by(Ticket.created_at.desc()).limit(5).all()
        )

        return APIResponse(
            success=True,
            message="Employee dashboard",
            data=EmployeeDashboard(
                open_tickets=open_count,
                closed_tickets=closed_count,
                recent_tickets=[TicketSummary.model_validate(t) for t in recent],
            ),
        )

    elif role == RoleNameEnum.agent:
        base = db.query(Ticket).filter(Ticket.assigned_to == current_user.id)

        open_count = base.filter(Ticket.status == TicketStatusEnum.open).count()
        in_progress = base.filter(Ticket.status == TicketStatusEnum.in_progress).count()
        waiting = base.filter(Ticket.status == TicketStatusEnum.waiting_for_user).count()

        # SLA breached = sla_due_at passed and not resolved/closed
        sla_breached = base.filter(
            Ticket.sla_due_at < now,
            Ticket.status.notin_([TicketStatusEnum.resolved, TicketStatusEnum.closed]),
        ).count()

        recent = base.order_by(Ticket.created_at.desc()).limit(5).all()

        return APIResponse(
            success=True,
            message="Agent dashboard",
            data=AgentDashboard(
                assigned_open=open_count,
                assigned_in_progress=in_progress,
                assigned_waiting=waiting,
                sla_breached=sla_breached,
                recently_assigned=[TicketSummary.model_validate(t) for t in recent],
            ),
        )

    else:  # admin
        total = db.query(func.count(Ticket.id)).scalar() or 0

        open_count = (
            db.query(func.count(Ticket.id))
            .filter(Ticket.status == TicketStatusEnum.open)
            .scalar() or 0
        )
        in_progress_count = (
            db.query(func.count(Ticket.id))
            .filter(Ticket.status == TicketStatusEnum.in_progress)
            .scalar() or 0
        )
        resolved_count = (
            db.query(func.count(Ticket.id))
            .filter(Ticket.status == TicketStatusEnum.resolved)
            .scalar() or 0
        )
        closed_count = (
            db.query(func.count(Ticket.id))
            .filter(Ticket.status == TicketStatusEnum.closed)
            .scalar() or 0
        )
        overdue = (
            db.query(func.count(Ticket.id))
            .filter(
                Ticket.sla_due_at < now,
                Ticket.status.notin_([TicketStatusEnum.resolved, TicketStatusEnum.closed]),
            )
            .scalar() or 0
        )
        unassigned = (
            db.query(func.count(Ticket.id))
            .filter(
                Ticket.assigned_to == None,
                Ticket.status.notin_([TicketStatusEnum.resolved, TicketStatusEnum.closed]),
            )
            .scalar() or 0
        )
        high_priority = (
            db.query(func.count(Ticket.id))
            .filter(
                Ticket.priority.in_([TicketPriorityEnum.high, TicketPriorityEnum.critical]),
                Ticket.status.notin_([TicketStatusEnum.resolved, TicketStatusEnum.closed]),
            )
            .scalar() or 0
        )

        from datetime import date
        today_start = datetime.combine(date.today(), datetime.min.time()).replace(tzinfo=timezone.utc)
        todays = (
            db.query(func.count(Ticket.id))
            .filter(Ticket.created_at >= today_start)
            .scalar() or 0
        )

        # Agent workload
        agent_role = db.query(Role).filter(Role.name == RoleNameEnum.agent).first()
        workload = []
        if agent_role:
            agents = (
                db.query(User)
                .filter(User.role_id == agent_role.id, User.is_active == True)
                .all()
            )
            for agent in agents:
                oc = (
                    db.query(func.count(Ticket.id))
                    .filter(
                        Ticket.assigned_to == agent.id,
                        Ticket.status.notin_([TicketStatusEnum.resolved, TicketStatusEnum.closed]),
                    )
                    .scalar() or 0
                )
                workload.append(
                    AgentWorkload(
                        id=agent.id,
                        full_name=agent.full_name,
                        email=agent.email,
                        open_ticket_count=oc,
                    )
                )

        recent = (
            db.query(Ticket)
            .options(
                joinedload(Ticket.creator).joinedload(User.role),
                joinedload(Ticket.assignee).joinedload(User.role),
            )
            .order_by(Ticket.created_at.desc())
            .limit(10)
            .all()
        )

        return APIResponse(
            success=True,
            message="Admin dashboard",
            data=AdminDashboard(
                total_tickets=total,
                open_tickets=open_count,
                in_progress_tickets=in_progress_count,
                resolved_tickets=resolved_count,
                closed_tickets=closed_count,
                overdue_tickets=overdue,
                unassigned_tickets=unassigned,
                high_priority_tickets=high_priority,
                pending_assignments=unassigned,
                todays_tickets=todays,
                agent_workload=workload,
                recent_tickets=[TicketSummary.model_validate(t) for t in recent],
            ),
        )
