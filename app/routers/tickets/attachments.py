from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user
from app.database import get_db
from app.models import RoleNameEnum, Ticket, TicketAttachment, User
from app.schemas import APIResponse, TicketAttachmentCreate, TicketAttachmentResponse

router = APIRouter(prefix="/tickets")


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
