# from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

# pyrefly: ignore [missing-import]
from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
# pyrefly: ignore [missing-import]
from sqlalchemy.dialects.postgresql import UUID
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


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
