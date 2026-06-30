# from __future__ import annotations

import uuid
from typing import List, Optional
# pyrefly: ignore [missing-import]
from sqlalchemy import Boolean, String, Text, UniqueConstraint
# pyrefly: ignore [missing-import]
from sqlalchemy.dialects.postgresql import UUID
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


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
