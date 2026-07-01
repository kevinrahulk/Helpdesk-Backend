"""
Ticket service — business logic layer separating DB operations from route handlers.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
# pyrefly: ignore [missing-import]
from fastapi import HTTPException, status
# pyrefly: ignore [missing-import]
from sqlalchemy import func
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    RoleNameEnum,
    Ticket,
    TicketAISuggestion,
    TicketCategory,
    TicketPriorityEnum,
    TicketStatusEnum,
    TicketStatusLog,
    User,
)
import re
from app.schemas import TicketCreate, TicketStatusUpdate

settings = get_settings()

# ---------------------------------------------------------------------------
# Status transition matrix
# ---------------------------------------------------------------------------

VALID_TRANSITIONS: dict[TicketStatusEnum, list[TicketStatusEnum]] = {
    TicketStatusEnum.open: [TicketStatusEnum.in_progress],
    TicketStatusEnum.in_progress: [
        TicketStatusEnum.waiting_for_user,
        TicketStatusEnum.resolved,
    ],
    TicketStatusEnum.waiting_for_user: [TicketStatusEnum.in_progress, TicketStatusEnum.resolved],
    TicketStatusEnum.resolved: [
        TicketStatusEnum.closed,
        TicketStatusEnum.in_progress,  # reopen
    ],
    TicketStatusEnum.closed: [],  # terminal — no reopening
}

# ---------------------------------------------------------------------------
# SLA computation
# ---------------------------------------------------------------------------

SLA_HOURS: dict[TicketPriorityEnum, int] = {
    TicketPriorityEnum.critical: settings.SLA_HOURS_CRITICAL,
    TicketPriorityEnum.high:     settings.SLA_HOURS_HIGH,
    TicketPriorityEnum.medium:   settings.SLA_HOURS_MEDIUM,
    TicketPriorityEnum.low:      settings.SLA_HOURS_LOW,
}


def compute_sla_due(priority: TicketPriorityEnum) -> datetime:
    hours = SLA_HOURS[priority]
    return datetime.now(timezone.utc) + timedelta(hours=hours)


# ---------------------------------------------------------------------------
# Ticket number generation
# ---------------------------------------------------------------------------

def generate_ticket_no(db: Session) -> str:
    last = (
        db.query(Ticket.ticket_no)
        .order_by(Ticket.created_at.desc())
        .limit(100)
        .all()
    )
    max_num = 100  # start at 101
    for (tno,) in last:
        m = re.search(r'(\d+)$', tno or '')
        if m:
            max_num = max(max_num, int(m.group(1)))
    return f"TX-{max_num + 1}"


# ---------------------------------------------------------------------------
# Create ticket
# ---------------------------------------------------------------------------
def create_ticket(db: Session, payload: TicketCreate, creator: User) -> Ticket:
    # Validate category if provided
    if payload.category_id:
        cat = db.get(TicketCategory, payload.category_id)
        if not cat or not cat.is_active:
            raise HTTPException(status_code=400, detail="Invalid or inactive category.")

    ticket_no = generate_ticket_no(db)
    sla_due = compute_sla_due(payload.priority)

    ticket = Ticket(
        ticket_no=ticket_no,
        title=payload.title,
        description=payload.description,
        category_id=payload.category_id,
        priority=payload.priority,
        status=TicketStatusEnum.open,
        created_by=creator.id,
        sla_due_at=sla_due,
    )
    db.add(ticket)
    db.flush()  # get ticket.id before log

    # Initial status log (from_status=None → open)
    log = TicketStatusLog(
        ticket_id=ticket.id,
        changed_by=creator.id,
        from_status=None,
        to_status=TicketStatusEnum.open.value,
        reason="Ticket created",
    )
    db.add(log)
    db.commit()
    db.refresh(ticket)
    return ticket


# ---------------------------------------------------------------------------
# Status transition
# ---------------------------------------------------------------------------

def transition_status(
    db: Session,
    ticket: Ticket,
    payload: TicketStatusUpdate,
    actor: User,
) -> Ticket:
    current = ticket.status
    target = payload.status

    # BR-STAT-002: Closed is terminal
    if current == TicketStatusEnum.closed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Closed tickets cannot be reopened.",
        )

    # BR-STAT-001: Only valid transitions allowed
    allowed = VALID_TRANSITIONS.get(current, [])
    if target not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Transition from '{current.value}' to '{target.value}' is not allowed.",
        )

    # BR-STAT-004: Employee cannot change status (enforced at route level too)
    if actor.role.name == RoleNameEnum.employee:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Employees cannot change ticket status.")

    old_status = ticket.status
    ticket.status = target

    # Timestamp helpers
    now = datetime.now(timezone.utc)
    if target == TicketStatusEnum.resolved:
        ticket.resolved_at = now
    if target == TicketStatusEnum.closed:
        ticket.closed_at = now

    log = TicketStatusLog(
        ticket_id=ticket.id,
        changed_by=actor.id,
        from_status=old_status.value,
        to_status=target.value,
        reason=payload.reason,
    )
    db.add(log)
    db.commit()
    db.refresh(ticket)
    return ticket


# ---------------------------------------------------------------------------
# Assign ticket
# ---------------------------------------------------------------------------

def assign_ticket(db: Session, ticket: Ticket, agent_id: uuid.UUID, admin: User) -> Ticket:
    # Validate agent
    agent = db.get(User, agent_id)
    if not agent or not agent.is_active:
        raise HTTPException(status_code=404, detail="Agent not found or inactive.")
    if agent.role.name != RoleNameEnum.agent:
        raise HTTPException(status_code=400, detail="Target user is not an agent.")

    # BR-ASGN-002: Cannot reassign after closed
    if ticket.status == TicketStatusEnum.closed:
        raise HTTPException(status_code=422, detail="Cannot assign a closed ticket.")

    ticket.assigned_to = agent_id
    db.commit()
    db.refresh(ticket)
    return ticket
