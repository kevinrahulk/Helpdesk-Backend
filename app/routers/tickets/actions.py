from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.ai.services.ai_orchestration_service import (
    trigger_ai_assignment_update,
    trigger_ai_resolution_update,
)
from app.auth import get_current_user, require_admin, require_agent_or_admin
from app.database import get_db
from app.models import RoleNameEnum, Ticket, TicketStatusEnum, TicketStatusLog, User
from app.routers.tickets.helpers import _to_ticket_response
from app.schemas import (
    APIResponse,
    TicketAssignRequest,
    TicketResponse,
    TicketStatusLogResponse,
    TicketStatusUpdate,
)
from app.services.notification_service import notify_assignment
from app.services.ticket_service import assign_ticket, transition_status
from app.websocket import manager

router = APIRouter(prefix="/tickets")


@router.patch("/{ticket_id}/status", response_model=APIResponse[TicketResponse])
def update_ticket_status(
    ticket_id: UUID,
    payload: TicketStatusUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_agent_or_admin),
):
    ticket = db.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")

    if current_user.role.name == RoleNameEnum.agent and ticket.assigned_to != current_user.id:
        raise HTTPException(status_code=403, detail="You can only update status of your assigned tickets.")

    ticket = transition_status(db, ticket, payload, current_user)
    db.refresh(ticket)
    if payload.status == TicketStatusEnum.resolved:
        background_tasks.add_task(trigger_ai_resolution_update, ticket.id)

    background_tasks.add_task(
        manager.broadcast,
        {
            "type": "TICKET_UPDATED",
            "ticket_id": str(ticket.id),
            "reason": "status_change",
        }
    )
    return APIResponse(
        success=True,
        message=f"Status updated to '{payload.status.value}'",
        data=_to_ticket_response(ticket, db, current_user),
    )


@router.patch("/{ticket_id}/assign", response_model=APIResponse[TicketResponse])
def assign_ticket_to_agent(
    ticket_id: UUID,
    payload: TicketAssignRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    ticket = db.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")

    old_agent_id = ticket.assigned_to
    ticket = assign_ticket(db, ticket, payload.agent_id, current_user)

    # Send notification to the assigned agent
    agent = db.get(User, payload.agent_id)
    if agent:
        notify_assignment(db, ticket, agent)
        db.commit()

    db.refresh(ticket)
    if old_agent_id != payload.agent_id:
        background_tasks.add_task(trigger_ai_assignment_update, ticket.id)

    background_tasks.add_task(
        manager.broadcast,
        {
            "type": "TICKET_UPDATED",
            "ticket_id": str(ticket.id),
            "reason": "assignment_change",
        }
    )
    return APIResponse(
        success=True,
        message="Ticket assigned successfully",
        data=_to_ticket_response(ticket, db, current_user),
    )


@router.get("/{ticket_id}/logs", response_model=APIResponse[list[TicketStatusLogResponse]])
def get_status_logs(
    ticket_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = db.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")

    role = current_user.role.name
    if role == RoleNameEnum.employee and ticket.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied.")
    if role == RoleNameEnum.agent and ticket.assigned_to != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied.")

    logs = (
        db.query(TicketStatusLog)
        .filter(TicketStatusLog.ticket_id == ticket_id)
        .options(joinedload(TicketStatusLog.changed_by_user).joinedload(User.role))
        .order_by(TicketStatusLog.changed_at.asc())
        .all()
    )

    return APIResponse(
        success=True,
        message="Status logs fetched",
        data=[TicketStatusLogResponse.model_validate(log) for log in logs],
    )
