from __future__ import annotations

import uuid
from typing import Optional

# pyrefly: ignore [missing-import]
from sqlalchemy import Enum, ForeignKey, Index, Numeric, String, Text
# pyrefly: ignore [missing-import]
from sqlalchemy.dialects.postgresql import JSON, UUID
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import SuggestionTypeEnum


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
    # Feature 2 (agent detail view) structured fields that don't have a
    # dedicated column: important_customer_info, actions_already_attempted,
    # pending_items, risk_level, errors. Kept as JSON rather than adding four
    # more columns since these are always read/written together.
    detail_context: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    ticket: Mapped["Ticket"] = relationship(
        "Ticket", back_populates="ai_suggestions"
    )

    def __repr__(self) -> str:
        return (
            f"<TicketAISuggestion id={self.id} "
            f"ticket_id={self.ticket_id} type={self.suggestion_type}>"
        )
