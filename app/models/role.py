# from __future__ import annotations
import uuid
from typing import List, Optional
# pyrefly: ignore [missing-import]
from sqlalchemy import Enum, String
# pyrefly: ignore [missing-import]
from sqlalchemy.dialects.postgresql import UUID
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin
from app.models.enums import RoleNameEnum


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
