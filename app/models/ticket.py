# from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional
# pyrefly: ignore [missing-import]
from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text, UniqueConstraint
# pyrefly: ignore [missing-import]
from sqlalchemy.dialects.postgresql import UUID, JSON
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import TicketPriorityEnum, TicketStatusEnum


class Ticket(TimestampMixin, Base):
    __tablename__ = "tickets"
    __table_args__ = (
        UniqueConstraint("ticket_no", name="uq_tickets_ticket_no"),
        Index("ix_tickets_created_by", "created_by"),
        Index("ix_tickets_assigned_to", "assigned_to"),
        Index("ix_tickets_status", "status"),
        Index("ix_tickets_priority", "priority"),
        Index("ix_tickets_category_id", "category_id"),
        Index("ix_tickets_sla_due_at", "sla_due_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ticket_no: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    category_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ticket_categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    priority: Mapped[TicketPriorityEnum] = mapped_column(
        Enum(TicketPriorityEnum, name="ticket_priority_enum"),
        nullable=False,
        default=TicketPriorityEnum.medium,
    )
    status: Mapped[TicketStatusEnum] = mapped_column(
        Enum(TicketStatusEnum, name="ticket_status_enum"),
        nullable=False,
        default=TicketStatusEnum.open,
    )

    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    assigned_to: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    sla_due_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    ai_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_first_fix: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ai_similar_tickets: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    last_ai_updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    category: Mapped[Optional["TicketCategory"]] = relationship(
        "TicketCategory", back_populates="tickets"
    )
    creator: Mapped["User"] = relationship(
        "User", foreign_keys=[created_by], back_populates="created_tickets"
    )
    assignee: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[assigned_to], back_populates="assigned_tickets"
    )
    ai_suggestions: Mapped[List["TicketAISuggestion"]] = relationship(
        "TicketAISuggestion", back_populates="ticket", cascade="all, delete-orphan"
    )
    comments: Mapped[List["TicketComment"]] = relationship(
        "TicketComment", back_populates="ticket", cascade="all, delete-orphan"
    )
    status_logs: Mapped[List["TicketStatusLog"]] = relationship(
        "TicketStatusLog", back_populates="ticket", cascade="all, delete-orphan"
    )
    attachments: Mapped[List["TicketAttachment"]] = relationship(
        "TicketAttachment", back_populates="ticket", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Ticket id={self.id} ticket_no={self.ticket_no} status={self.status}>"
