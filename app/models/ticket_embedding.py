"""
Embedding storage for semantic similar-ticket search (Feature 3).

Uses `pgvector` (Postgres extension + `pgvector-python`'s SQLAlchemy
type) when available. If the `pgvector` package or the Postgres
extension is not installed, `app.ai.tools.vector_search` transparently
falls back to an in-process cosine-similarity scan (see that module's
docstring) — the rest of the system does not need to know which path
is active.

Enable the extension once per database:
    CREATE EXTENSION IF NOT EXISTS vector;
"""

from __future__ import annotations

import uuid
from typing import Optional

# pyrefly: ignore [missing-import]
from sqlalchemy import ForeignKey, Index, Text
# pyrefly: ignore [missing-import]
from sqlalchemy.dialects.postgresql import UUID
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.ai.config import get_ai_settings
from app.models.base import Base, TimestampMixin

try:
    # pyrefly: ignore [missing-import]
    from pgvector.sqlalchemy import Vector

    _HAS_PGVECTOR = True
except ImportError:  # pragma: no cover - exercised only when pgvector isn't installed
    _HAS_PGVECTOR = False

    def Vector(dim: int):  # type: ignore[no-redef]
        # Fallback column type: store the embedding as JSON floats.
        # app.ai.tools.vector_search detects this and switches to a
        # Python-side cosine-similarity fallback automatically.
        # pyrefly: ignore [missing-import]
        from sqlalchemy.dialects.postgresql import JSON

        return JSON


_settings = get_ai_settings()


class TicketEmbedding(TimestampMixin, Base):
    """One embedding vector per ticket, derived from title + description
    (+ resolution summary, once resolved), used for semantic similarity
    search in Feature 1 (creation assistant) and Feature 3 (reusable
    similar-ticket node)."""

    __tablename__ = "ticket_embeddings"
    __table_args__ = (
        Index("ix_ticket_embeddings_ticket_id", "ticket_id", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tickets.id", ondelete="CASCADE"),
        nullable=False,
    )
    embedding = mapped_column(Vector(_settings.EMBEDDING_DIMENSIONS), nullable=False)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)

    ticket: Mapped["Ticket"] = relationship("Ticket")

    def __repr__(self) -> str:
        return f"<TicketEmbedding id={self.id} ticket_id={self.ticket_id}>"


HAS_PGVECTOR = _HAS_PGVECTOR
