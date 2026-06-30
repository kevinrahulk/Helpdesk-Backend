"""
AI Helpdesk Ticket Assistant — SQLAlchemy ORM Models (PostgreSQL)
=================================================================
Stack  : Python 3.11+ · SQLAlchemy 2.0 (declarative ORM) · PostgreSQL
Naming : snake_case tables / columns; UUID primary keys throughout.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# ---------------------------------------------------------------------------
# Base + shared audit mixin
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class RoleNameEnum(str, enum.Enum):
    employee = "employee"
    agent    = "agent"
    admin    = "admin"


class TicketPriorityEnum(str, enum.Enum):
    low      = "low"
    medium   = "medium"
    high     = "high"
    critical = "critical"


class TicketStatusEnum(str, enum.Enum):
    open             = "open"
    in_progress      = "in_progress"
    waiting_for_user = "waiting_for_user"
    resolved         = "resolved"
    closed           = "closed"


class SuggestionTypeEnum(str, enum.Enum):
    creation = "creation"
    summary  = "summary"


# ---------------------------------------------------------------------------
# 1. roles
# ---------------------------------------------------------------------------

class Role(TimestampMixin, Base):
    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[RoleNameEnum] = mapped_column(
        Enum(RoleNameEnum, name="role_name_enum"),
        nullable=False,
        unique=True,
    )
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    users: Mapped[List["User"]] = relationship("User", back_populates="role")

    def __repr__(self) -> str:
        return f"<Role id={self.id} name={self.name}>"


# ---------------------------------------------------------------------------
# 2. users
# ---------------------------------------------------------------------------

class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        Index("ix_users_role_id", "role_id"),
        Index("ix_users_is_active", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    role: Mapped["Role"] = relationship("Role", back_populates="users")

    created_tickets: Mapped[List["Ticket"]] = relationship(
        "Ticket",
        foreign_keys="[Ticket.created_by]",
        back_populates="creator",
    )
    assigned_tickets: Mapped[List["Ticket"]] = relationship(
        "Ticket",
        foreign_keys="[Ticket.assigned_to]",
        back_populates="assignee",
    )
    comments: Mapped[List["TicketComment"]] = relationship(
        "TicketComment", back_populates="author"
    )
    status_changes: Mapped[List["TicketStatusLog"]] = relationship(
        "TicketStatusLog", back_populates="changed_by_user"
    )
    uploads: Mapped[List["TicketAttachment"]] = relationship(
        "TicketAttachment", back_populates="uploader"
    )
    notifications: Mapped[List["Notification"]] = relationship(
        "Notification", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email}>"


# ---------------------------------------------------------------------------
# 3. ticket_categories
# ---------------------------------------------------------------------------

class TicketCategory(TimestampMixin, Base):
    __tablename__ = "ticket_categories"
    __table_args__ = (
        UniqueConstraint("name", name="uq_ticket_categories_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    tickets: Mapped[List["Ticket"]] = relationship(
        "Ticket", back_populates="category"
    )

    def __repr__(self) -> str:
        return f"<TicketCategory id={self.id} name={self.name}>"


# ---------------------------------------------------------------------------
# 4. tickets
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# 5. ticket_ai_suggestions
# ---------------------------------------------------------------------------

class TicketAISuggestion(TimestampMixin, Base):
    __tablename__ = "ticket_ai_suggestions"
    __table_args__ = (
        Index("ix_ai_suggestions_ticket_id", "ticket_id"),
        Index("ix_ai_suggestions_type", "suggestion_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
    )
    suggestion_type: Mapped[SuggestionTypeEnum] = mapped_column(
        Enum(SuggestionTypeEnum, name="suggestion_type_enum"),
        nullable=False,
    )

    suggested_category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    suggested_priority: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    first_fix: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    similar_tickets: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    confidence_score: Mapped[Optional[float]] = mapped_column(
        Numeric(4, 2), nullable=True
    )
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    root_cause: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    suggested_reply: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    ticket: Mapped["Ticket"] = relationship(
        "Ticket", back_populates="ai_suggestions"
    )

    def __repr__(self) -> str:
        return (
            f"<TicketAISuggestion id={self.id} "
            f"ticket_id={self.ticket_id} type={self.suggestion_type}>"
        )


# ---------------------------------------------------------------------------
# 6. ticket_comments
# ---------------------------------------------------------------------------

class TicketComment(TimestampMixin, Base):
    __tablename__ = "ticket_comments"
    __table_args__ = (
        Index("ix_ticket_comments_ticket_id", "ticket_id"),
        Index("ix_ticket_comments_author_id", "author_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_internal: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    ticket: Mapped["Ticket"] = relationship("Ticket", back_populates="comments")
    author: Mapped["User"] = relationship("User", back_populates="comments")

    def __repr__(self) -> str:
        return (
            f"<TicketComment id={self.id} ticket_id={self.ticket_id} "
            f"internal={self.is_internal}>"
        )


# ---------------------------------------------------------------------------
# 7. ticket_status_logs
# ---------------------------------------------------------------------------

class TicketStatusLog(Base):
    __tablename__ = "ticket_status_logs"
    __table_args__ = (
        Index("ix_status_logs_ticket_id", "ticket_id"),
        Index("ix_status_logs_changed_by", "changed_by"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
    )
    changed_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    from_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    to_status: Mapped[str] = mapped_column(String(50), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    ticket: Mapped["Ticket"] = relationship("Ticket", back_populates="status_logs")
    changed_by_user: Mapped["User"] = relationship(
        "User", back_populates="status_changes"
    )

    def __repr__(self) -> str:
        return (
            f"<TicketStatusLog id={self.id} ticket_id={self.ticket_id} "
            f"{self.from_status!r} → {self.to_status!r}>"
        )


# ---------------------------------------------------------------------------
# 8. ticket_attachments
# ---------------------------------------------------------------------------

class TicketAttachment(TimestampMixin, Base):
    __tablename__ = "ticket_attachments"
    __table_args__ = (
        Index("ix_ticket_attachments_ticket_id", "ticket_id"),
        Index("ix_ticket_attachments_uploaded_by", "uploaded_by"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    ticket: Mapped["Ticket"] = relationship("Ticket", back_populates="attachments")
    uploader: Mapped["User"] = relationship("User", back_populates="uploads")

    def __repr__(self) -> str:
        return (
            f"<TicketAttachment id={self.id} "
            f"ticket_id={self.ticket_id} file={self.file_name}>"
        )


# ---------------------------------------------------------------------------
# 9. notifications
# ---------------------------------------------------------------------------

class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_id", "user_id"),
        Index("ix_notifications_is_read", "is_read"),
        Index("ix_notifications_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    ticket_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=True,
    )
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="notifications")
    ticket: Mapped[Optional["Ticket"]] = relationship("Ticket")

    def __repr__(self) -> str:
        return f"<Notification id={self.id} user_id={self.user_id} read={self.is_read}>"


# ---------------------------------------------------------------------------
# 10. system_settings
# ---------------------------------------------------------------------------

class SystemSetting(Base):
    __tablename__ = "system_settings"
    __table_args__ = (
        UniqueConstraint("key", name="uq_system_settings_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str] = mapped_column(String(500), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<SystemSetting key={self.key} value={self.value}>"
