from datetime import datetime
from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session
from app.models import Ticket

def _base_query(db: Session, date_from: Optional[datetime], date_to: Optional[datetime]):
    q = db.query(Ticket)
    if date_from:
        q = q.filter(Ticket.created_at >= date_from)
    if date_to:
        q = q.filter(Ticket.created_at <= date_to)
    return q


def _apply_filters(q, status: Optional[str], priority: Optional[str],
                   category_id: Optional[UUID], agent_id: Optional[UUID]):
    if status:
        q = q.filter(Ticket.status == status)
    if priority:
        q = q.filter(Ticket.priority == priority)
    if category_id:
        q = q.filter(Ticket.category_id == category_id)
    if agent_id:
        q = q.filter(Ticket.assigned_to == agent_id)
    return q
