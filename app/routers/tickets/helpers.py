import uuid
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.models import (
    RoleNameEnum,
    Ticket,
    TicketAttachment,
    TicketComment,
    TicketStatusLog,
    User,
)
from app.schemas import TicketResponse


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


def resolve_similar_tickets(db: Session, raw_similar: list | str | None) -> list:
    if not raw_similar:
        return []

    if isinstance(raw_similar, str):
        try:
            import json
            items = json.loads(raw_similar)
        except Exception:
            return []
    else:
        items = raw_similar

    if not isinstance(items, list):
        return []

    resolved = []
    missing_nos = []
    for item in items:
        if isinstance(item, dict):
            if not item.get("ticket_id") and item.get("ticket_no"):
                missing_nos.append(item["ticket_no"])

    id_map = {}
    if missing_nos:
        rows = db.query(Ticket.ticket_no, Ticket.id).filter(Ticket.ticket_no.in_(missing_nos)).all()
        id_map = {row.ticket_no: str(row.id) for row in rows}

    for item in items:
        if isinstance(item, dict):
            new_item = dict(item)
            if not new_item.get("ticket_id") and new_item.get("ticket_no"):
                new_item["ticket_id"] = id_map.get(new_item["ticket_no"])
            resolved.append(new_item)
        else:
            resolved.append(item)

    return resolved


def _to_ticket_response(ticket: Ticket, db: Session, current_user: User) -> TicketResponse:
    resolved_similar = None
    if ticket.ai_similar_tickets:
        resolved_similar = resolve_similar_tickets(db, ticket.ai_similar_tickets)

    ticket_data = TicketResponse.model_validate(ticket)
    if current_user.role.name == RoleNameEnum.employee:
        ticket_data.comments = [c for c in ticket_data.comments if not c.is_internal]

    if resolved_similar is not None:
        from app.schemas.ai_suggestion import SimilarTicketRef
        ticket_data.ai_similar_tickets = [SimilarTicketRef.model_validate(item) for item in resolved_similar]

    return ticket_data
