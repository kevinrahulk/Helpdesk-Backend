from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.ai.services.ai_orchestration_service import (
    trigger_initial_ai_generation_if_missing,
    trigger_similar_tickets_generation_if_missing,
)
from app.auth import get_current_user, require_agent_or_admin
from app.database import get_db
from app.models import RoleNameEnum, Ticket, TicketPriorityEnum, TicketStatusEnum, User
from app.routers.tickets.helpers import _get_ticket_or_404, _to_ticket_response
from app.schemas import (
    APIResponse,
    TicketCreate,
    TicketListResponse,
    TicketResponse,
    TicketSummary,
    TicketUpdate,
)
from app.services.ticket_service import create_ticket
from app.websocket import manager

router = APIRouter(prefix="/tickets")


@router.post("", response_model=APIResponse[TicketResponse], status_code=status.HTTP_201_CREATED)
def create_new_ticket(
    payload: TicketCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Only employee (and optionally admin) can create tickets
    if current_user.role.name == RoleNameEnum.agent:
        raise HTTPException(status_code=403, detail="Agents cannot create tickets.")

    ticket = create_ticket(db, payload, current_user)
    db.refresh(ticket)
    ticket = _get_ticket_or_404(ticket.id, db)
    if not ticket.ai_summary or not ticket.ai_first_fix:
        # Full pipeline missing (e.g. ticket submitted without using the
        # "Analyze Issue" preview) — this run also generates and stores
        # similar tickets, exactly once, as part of the same graph.
        background_tasks.add_task(trigger_initial_ai_generation_if_missing, ticket.id)
    elif not ticket.ai_similar_tickets:
        background_tasks.add_task(trigger_similar_tickets_generation_if_missing, ticket.id)

    background_tasks.add_task(
        manager.broadcast,
        {
            "type": "TICKET_CREATED",
            "ticket_id": str(ticket.id),
        }
    )
    return APIResponse(
        success=True,
        message="Ticket created successfully",
        data=_to_ticket_response(ticket, db, current_user),
    )


@router.get("", response_model=APIResponse[TicketListResponse])
def list_tickets(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    priority: Optional[str] = Query(None),
    category_id: Optional[UUID] = Query(None),
    search: Optional[str] = Query(None, description="Search in title"),
    assigned: Optional[str] = Query(None, description="Filter by assignment: 'unassigned' for tickets with no assignee"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return tickets scoped to the caller's role:
    - Employee: only own tickets
    - Agent: only assigned tickets
    - Admin: all tickets
    """
    q = db.query(Ticket)

    role = current_user.role.name
    if role == RoleNameEnum.employee:
        q = q.filter(Ticket.created_by == current_user.id)
    elif role == RoleNameEnum.agent:
        q = q.filter(Ticket.assigned_to == current_user.id)
    # admin: no filter

    if status_filter:
        try:
            s = TicketStatusEnum(status_filter)
            q = q.filter(Ticket.status == s)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status_filter}")

    if priority:
        try:
            p = TicketPriorityEnum(priority)
            q = q.filter(Ticket.priority == p)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid priority: {priority}")

    if category_id:
        q = q.filter(Ticket.category_id == category_id)

    if search:
        q = q.filter(Ticket.title.ilike(f"%{search}%") | Ticket.ticket_no.ilike(f"%{search}%"))

    if assigned and assigned.lower() == "unassigned":
        q = q.filter(Ticket.assigned_to.is_(None))

    total = q.count()
    tickets = (
        q.options(
            joinedload(Ticket.creator).joinedload(User.role),
            joinedload(Ticket.assignee).joinedload(User.role),
        )
        .order_by(Ticket.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return APIResponse(
        success=True,
        message="Tickets fetched",
        data=TicketListResponse(
            items=[TicketSummary.model_validate(t) for t in tickets],
            total=total,
            page=page,
            page_size=page_size,
        ),
    )


@router.get("/{ticket_id}", response_model=APIResponse[TicketResponse])
def get_ticket(
    ticket_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = _get_ticket_or_404(ticket_id, db)

    role = current_user.role.name
    if role == RoleNameEnum.employee and ticket.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied.")
    if role == RoleNameEnum.agent and ticket.assigned_to != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied.")

    ticket_data = _to_ticket_response(ticket, db, current_user)
    return APIResponse(success=True, message="Ticket fetched", data=ticket_data)


@router.patch("/{ticket_id}", response_model=APIResponse[TicketResponse])
def update_ticket(
    ticket_id: UUID,
    payload: TicketUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_agent_or_admin),
):
    ticket = db.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")

    if current_user.role.name == RoleNameEnum.agent and ticket.assigned_to != current_user.id:
        raise HTTPException(status_code=403, detail="You can only update your assigned tickets.")

    updates = payload.model_dump(exclude_none=True)
    for key, val in updates.items():
        setattr(ticket, key, val)

    db.commit()
    db.refresh(ticket)
    return APIResponse(success=True, message="Ticket updated", data=_to_ticket_response(ticket, db, current_user))
