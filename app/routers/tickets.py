"""
Ticket lifecycle endpoints

POST   /tickets                    create ticket (employee)
GET    /tickets                    list tickets (role-filtered)
GET    /tickets/{id}               ticket detail
PATCH  /tickets/{id}               update fields (agent/admin)
PATCH  /tickets/{id}/status        status transition (agent/admin)
PATCH  /tickets/{id}/assign        assign to agent (admin)
GET    /tickets/{id}/logs          status history
POST   /tickets/{id}/comments      add comment (agent/admin)
GET    /tickets/{id}/comments      list comments (all, internal hidden from employee)
PATCH  /tickets/{id}/comments/{cid} edit comment (author or admin)
POST   /tickets/{id}/attachments   upload attachment metadata
GET    /tickets/{id}/attachments   list attachments
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, HTTPException, Query, status
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user, require_admin, require_agent_or_admin
from app.database import get_db
from app.models import (
    RoleNameEnum,
    SystemSetting,
    Ticket,
    TicketAttachment,
    TicketComment,
    TicketPriorityEnum,
    TicketStatusEnum,
    TicketStatusLog,
    User,
)
from app.schemas import (
    APIResponse,
    TicketAssignRequest,
    TicketAttachmentCreate,
    TicketAttachmentResponse,
    TicketCommentCreate,
    TicketCommentResponse,
    TicketCommentUpdate,
    TicketCreate,
    TicketListResponse,
    TicketResponse,
    TicketStatusLogResponse,
    TicketStatusUpdate,
    TicketSummary,
    TicketUpdate,
    UserSummary,
)
from app.services.ticket_service import (
    assign_ticket,
    create_ticket,
    transition_status,
)
from app.services.notification_service import (
    notify_assignment,
    notify_employee_comment,
    notify_agent_reply,
)

router = APIRouter(prefix="/tickets", tags=["Tickets"])


# ---------------------------------------------------------------------------
# Helper: load ticket or 404
# ---------------------------------------------------------------------------

def _get_ticket_or_404(ticket_id: UUID, db: Session) -> Ticket:
    ticket = (
        db.query(Ticket)
        .options(
            joinedload(Ticket.creator).joinedload(User.role),
            joinedload(Ticket.assignee).joinedload(User.role),
            joinedload(Ticket.category),
            joinedload(Ticket.ai_suggestions),
            joinedload(Ticket.comments).joinedload(TicketComment.author).joinedload(User.role),
            joinedload(Ticket.status_logs).joinedload(TicketStatusLog.changed_by_user).joinedload(User.role),
            joinedload(Ticket.attachments).joinedload(TicketAttachment.uploader).joinedload(User.role),
        )
        .filter(Ticket.id == ticket_id)
        .first()
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    return ticket


def _user_summary(user: Optional[User]) -> Optional[UserSummary]:
    if not user:
        return None
    return UserSummary(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=user.role.name.value if user.role else "employee",
    )


# ---------------------------------------------------------------------------
# Create Ticket
# ---------------------------------------------------------------------------
"""
    Employee creates a new support ticket.
    - AI suggestion ID is stored if provided (linked after ticket creation)
    - SLA due date is auto-computed from priority
    - Status auto-set to 'open'
"""
@router.post("", response_model=APIResponse[TicketResponse], status_code=status.HTTP_201_CREATED)
def create_new_ticket(
    payload: TicketCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Only employee (and optionally admin) can create tickets
    if current_user.role.name == RoleNameEnum.agent:
        raise HTTPException(status_code=403, detail="Agents cannot create tickets.")

    ticket = create_ticket(db, payload, current_user)
    db.refresh(ticket)
    ticket = _get_ticket_or_404(ticket.id, db)
    return APIResponse(
        success=True,
        message="Ticket created successfully",
        data=TicketResponse.model_validate(ticket),
    )


# ---------------------------------------------------------------------------
# List Tickets (role-filtered)
# ---------------------------------------------------------------------------

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
        q = q.filter(Ticket.title.ilike(f"%{search}%"))

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


# ---------------------------------------------------------------------------
# Get Ticket Detail
# ---------------------------------------------------------------------------
"""
    Full ticket detail with nested comments, logs, attachments.
    - Employee: only their own ticket
    - Agent: only assigned ticket
    - Admin: any ticket
    Internal comments are hidden from employees.
"""
@router.get("/{ticket_id}", response_model=APIResponse[TicketResponse])
def get_ticket(
    ticket_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),):
    ticket = _get_ticket_or_404(ticket_id, db)

    role = current_user.role.name
    if role == RoleNameEnum.employee and ticket.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied.")
    if role == RoleNameEnum.agent and ticket.assigned_to != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied.")

    # Filter internal comments for employees
    ticket_data = TicketResponse.model_validate(ticket)
    if role == RoleNameEnum.employee:
        ticket_data.comments = [c for c in ticket_data.comments if not c.is_internal]

    return APIResponse(success=True, message="Ticket fetched", data=ticket_data)


# ---------------------------------------------------------------------------
# Update Ticket Fields
# ---------------------------------------------------------------------------
@router.patch("/{ticket_id}", response_model=APIResponse[TicketResponse])
def update_ticket(
    ticket_id: UUID,
    payload: TicketUpdate,
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
    return APIResponse(success=True, message="Ticket updated", data=TicketResponse.model_validate(ticket))


# ---------------------------------------------------------------------------
# Status Transition
# ---------------------------------------------------------------------------
@router.patch("/{ticket_id}/status", response_model=APIResponse[TicketResponse])
def update_ticket_status(
    ticket_id: UUID,
    payload: TicketStatusUpdate,
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
    return APIResponse(
        success=True,
        message=f"Status updated to '{payload.status.value}'",
        data=TicketResponse.model_validate(ticket),
    )


# ---------------------------------------------------------------------------
# Assign Ticket
# ---------------------------------------------------------------------------
@router.patch("/{ticket_id}/assign", response_model=APIResponse[TicketResponse])
def assign_ticket_to_agent(
    ticket_id: UUID,
    payload: TicketAssignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    ticket = db.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")

    ticket = assign_ticket(db, ticket, payload.agent_id, current_user)

    # Send notification to the assigned agent
    agent = db.get(User, payload.agent_id)
    if agent:
        notify_assignment(db, ticket, agent)
        db.commit()

    db.refresh(ticket)
    return APIResponse(
        success=True,
        message="Ticket assigned successfully",
        data=TicketResponse.model_validate(ticket),
    )


# ---------------------------------------------------------------------------
# Status Logs
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------
@router.post("/{ticket_id}/comments", response_model=APIResponse[TicketCommentResponse], status_code=201)
def add_comment(
    ticket_id: UUID,
    payload: TicketCommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = db.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")

    role = current_user.role.name
    if role == RoleNameEnum.employee:
        if ticket.created_by != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied.")
        setting = db.query(SystemSetting).filter(
            SystemSetting.key == "employee_comments_enabled"
        ).first()
        if setting and setting.value.lower() != "true":
            raise HTTPException(
                status_code=403,
                detail="Comments have been disabled by the administrator.",
            )
        # Employees cannot post internal notes
        payload.is_internal = False

    if role == RoleNameEnum.agent and ticket.assigned_to != current_user.id:
        raise HTTPException(status_code=403, detail="You can only comment on your assigned tickets.")

    comment = TicketComment(
        ticket_id=ticket_id,
        author_id=current_user.id,
        body=payload.body,
        is_internal=payload.is_internal,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)

    # Send notifications
    if role == RoleNameEnum.employee:
        notify_employee_comment(db, ticket)
    else:
        notify_agent_reply(db, ticket)
    db.commit()

    # Load author relationship
    db.refresh(comment, ["author"])
    return APIResponse(
        success=True,
        message="Comment added",
        data=TicketCommentResponse.model_validate(comment),
    )

# Get all the comments
@router.get("/{ticket_id}/comments", response_model=APIResponse[list[TicketCommentResponse]])
def list_comments(
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

    q = (
        db.query(TicketComment)
        .options(joinedload(TicketComment.author).joinedload(User.role))
        .filter(TicketComment.ticket_id == ticket_id)
    )
    if role == RoleNameEnum.employee:
        q = q.filter(TicketComment.is_internal == False)

    comments = q.order_by(TicketComment.created_at.asc()).all()
    return APIResponse(
        success=True,
        message="Comments fetched",
        data=[TicketCommentResponse.model_validate(c) for c in comments],
    )

# Update the comments
@router.patch("/{ticket_id}/comments/{comment_id}", response_model=APIResponse[TicketCommentResponse])
def update_comment(
    ticket_id: UUID,
    comment_id: UUID,
    payload: TicketCommentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_agent_or_admin),
):
    """Edit a comment. Author or Admin only."""
    comment = db.get(TicketComment, comment_id)
    if not comment or comment.ticket_id != ticket_id:
        raise HTTPException(status_code=404, detail="Comment not found.")

    if current_user.role.name != RoleNameEnum.admin and comment.author_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only edit your own comments.")

    if payload.body is not None:
        comment.body = payload.body
    if payload.is_internal is not None:
        comment.is_internal = payload.is_internal

    db.commit()
    db.refresh(comment)
    return APIResponse(success=True, message="Comment updated", data=TicketCommentResponse.model_validate(comment))


# ---------------------------------------------------------------------------
# Attachments
# ---------------------------------------------------------------------------
@router.post("/{ticket_id}/attachments", response_model=APIResponse[TicketAttachmentResponse], status_code=201)
def add_attachment_metadata(
    ticket_id: UUID,
    payload: TicketAttachmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Register attachment metadata after file is uploaded to S3.
    The actual file bytes are handled outside this API (S3 pre-signed URL flow).
    Allowed content types: jpeg, png, pdf, docx, xlsx.
    Max size: 10 MB.
    """
    ALLOWED_TYPES = {
        "image/jpeg",
        "image/png",
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
    if payload.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Content type '{payload.content_type}' is not allowed.",
        )

    ticket = db.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")

    attachment = TicketAttachment(
        ticket_id=ticket_id,
        uploaded_by=current_user.id,
        file_name=payload.file_name,
        file_url=payload.file_url,
        content_type=payload.content_type,
        file_size_bytes=payload.file_size_bytes,
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return APIResponse(
        success=True,
        message="Attachment registered",
        data=TicketAttachmentResponse.model_validate(attachment),
    )


@router.get("/{ticket_id}/attachments", response_model=APIResponse[list[TicketAttachmentResponse]])
def list_attachments(
    ticket_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all attachments for a ticket."""
    ticket = db.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")

    role = current_user.role.name
    if role == RoleNameEnum.employee and ticket.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied.")
    if role == RoleNameEnum.agent and ticket.assigned_to != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied.")

    attachments = (
        db.query(TicketAttachment)
        .filter(TicketAttachment.ticket_id == ticket_id)
        .options(joinedload(TicketAttachment.uploader))
        .all()
    )
    return APIResponse(
        success=True,
        message="Attachments fetched",
        data=[TicketAttachmentResponse.model_validate(a) for a in attachments],
    )
