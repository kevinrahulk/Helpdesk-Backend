import csv
import io
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

from app.auth import require_admin
from app.database import get_db
from app.models import Ticket, User
from app.routers.reports.helpers import _apply_filters, _base_query

router = APIRouter()


@router.get("/export")
def export_report(
    format: str = Query("csv", pattern="^(csv|excel)$"),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    status: Optional[str] = Query(None, alias="status_filter"),
    priority: Optional[str] = Query(None),
    category_id: Optional[UUID] = Query(None),
    agent_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Export ticket data as CSV or Excel. Admin only."""
    q = _base_query(db, date_from, date_to)
    q = _apply_filters(q, status, priority, category_id, agent_id)
    q = q.options(
        joinedload(Ticket.creator),
        joinedload(Ticket.assignee),
        joinedload(Ticket.category),
    )
    tickets = q.order_by(Ticket.created_at.desc()).all()

    headers = [
        "Ticket No", "Title", "Status", "Priority", "Category",
        "Requester", "Assignee", "Created At", "SLA Due", "Resolved At",
    ]

    rows = []
    for t in tickets:
        rows.append([
            t.ticket_no,
            t.title,
            t.status.value if hasattr(t.status, 'value') else str(t.status),
            t.priority.value if hasattr(t.priority, 'value') else str(t.priority),
            t.category.name if t.category else "—",
            t.creator.full_name if t.creator else "—",
            t.assignee.full_name if t.assignee else "Unassigned",
            t.created_at.isoformat() if t.created_at else "—",
            t.sla_due_at.isoformat() if t.sla_due_at else "—",
            t.resolved_at.isoformat() if t.resolved_at else "—",
        ])

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(rows)

    content_type = "text/csv"
    filename = "tickets_report.csv"
    if format == "excel":
        content_type = "application/vnd.ms-excel"
        filename = "tickets_report.xls"

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type=content_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
