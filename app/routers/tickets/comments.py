from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user, require_agent_or_admin
from app.database import get_db
from app.models import (
    RoleNameEnum,
    SystemSetting,
    Ticket,
    TicketComment,
    TicketStatusEnum,
    TicketStatusLog,
    User,
)
from app.schemas import (
    APIResponse,
    TicketCommentCreate,
    TicketCommentResponse,
    TicketCommentUpdate,
)
from app.services.notification_service import notify_agent_reply, notify_employee_comment
from app.websocket import manager

router = APIRouter(prefix="/tickets")


@router.post("/{ticket_id}/comments", response_model=APIResponse[TicketCommentResponse], status_code=201)
def add_comment(
    ticket_id: UUID,
    payload: TicketCommentCreate,
    background_tasks: BackgroundTasks,
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

    # Automated status transition on comment
    old_status = ticket.status
    new_status = None

    if role == RoleNameEnum.employee:
        # Employee commented
        if ticket.status in (TicketStatusEnum.open, TicketStatusEnum.waiting_for_user, TicketStatusEnum.resolved):
            new_status = TicketStatusEnum.in_progress
    else:
        # Agent or Admin commented
        if not payload.is_internal:
            # It's a public reply to the employee (message to employee)
            if ticket.status in (TicketStatusEnum.open, TicketStatusEnum.in_progress):
                new_status = TicketStatusEnum.waiting_for_user

    if new_status and new_status != old_status:
        ticket.status = new_status
        now = datetime.now(timezone.utc)
        if new_status == TicketStatusEnum.resolved:
            ticket.resolved_at = now
        elif new_status == TicketStatusEnum.closed:
            ticket.closed_at = now

        log = TicketStatusLog(
            ticket_id=ticket.id,
            changed_by=current_user.id,
            from_status=old_status.value,
            to_status=new_status.value,
            reason="Automated transition on comment",
        )
        db.add(log)
        db.commit()
        db.refresh(ticket)

    # Send notifications
    if role == RoleNameEnum.employee:
        notify_employee_comment(db, ticket)
    else:
        notify_agent_reply(db, ticket)
    db.commit()

    # Load author relationship
    db.refresh(comment, ["author"])

    background_tasks.add_task(
        manager.broadcast,
        {
            "type": "TICKET_UPDATED",
            "ticket_id": str(ticket_id),
            "reason": "new_comment",
        }
    )
    return APIResponse(
        success=True,
        message="Comment added",
        data=TicketCommentResponse.model_validate(comment),
    )


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
