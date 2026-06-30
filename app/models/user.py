# from __future__ import annotations

import uuid
from typing import List
# pyrefly: ignore [missing-import]
from sqlalchemy import Boolean, ForeignKey, Index, String, UniqueConstraint
# pyrefly: ignore [missing-import]
from sqlalchemy.dialects.postgresql import UUID
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin

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
