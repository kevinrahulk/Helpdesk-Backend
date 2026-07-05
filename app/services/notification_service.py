"""
Notification service — creates notifications for ticket events.
"""

from __future__ import annotations

from typing import Optional, List
from uuid import UUID

# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session

from app.models import (
    Notification,
    RoleNameEnum,
    Role,
    Ticket,
    User,
)


def create_notification(
    db: Session,
    user_id: UUID,
    title: str,
    message: str,
    ticket_id: Optional[UUID] = None,
) -> Notification:
    """Create a single notification record."""
    notif = Notification(
        user_id=user_id,
        title=title,
        message=message,
        ticket_id=ticket_id,
    )
    db.add(notif)

    # Broadcast notification in real-time via WebSocket
    import asyncio
    from app.websocket import manager
    if manager.loop and manager.loop.is_running():
        asyncio.run_coroutine_threadsafe(
            manager.send_personal_message(
                {"type": "NOTIFICATION_RECEIVED", "unread_count_increment": 1},
                str(user_id)
            ),
            manager.loop
        )
    return notif


def notify_assignment(db: Session, ticket: Ticket, agent: User) -> None:
    """Notify the assigned agent when they are assigned a ticket."""
    create_notification(
        db,
        user_id=agent.id,
        title="Ticket Assigned",
        message=f"You have been assigned Ticket {ticket.ticket_no}.",
        ticket_id=ticket.id,
    )


def notify_employee_comment(db: Session, ticket: Ticket) -> None:
    """
    When an employee comments, notify:
    - The assigned support agent (if any)
    - All admins
    """
    notified: set[UUID] = set()

    # Notify assigned agent
    if ticket.assigned_to:
        create_notification(
            db,
            user_id=ticket.assigned_to,
            title="Employee Comment",
            message=f"Employee commented on Ticket {ticket.ticket_no}.",
            ticket_id=ticket.id,
        )
        notified.add(ticket.assigned_to)

    # Notify all admins
    admin_role = db.query(Role).filter(Role.name == RoleNameEnum.admin).first()
    if admin_role:
        admins = (
            db.query(User)
            .filter(User.role_id == admin_role.id, User.is_active == True)
            .all()
        )
        for admin in admins:
            if admin.id not in notified:
                create_notification(
                    db,
                    user_id=admin.id,
                    title="Employee Comment",
                    message=f"Employee commented on Ticket {ticket.ticket_no}.",
                    ticket_id=ticket.id,
                )
                notified.add(admin.id)


def notify_agent_reply(db: Session, ticket: Ticket) -> None:
    """
    When agent/admin comments, notify the ticket requester (employee).
    """
    if ticket.created_by:
        create_notification(
            db,
            user_id=ticket.created_by,
            title="Support Reply",
            message=f"Support has replied to your ticket {ticket.ticket_no}.",
            ticket_id=ticket.id,
        )
