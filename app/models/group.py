from __future__ import annotations
"""Community group model."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class Group(Base):
    """Community group users can discover and join."""

    __tablename__ = "groups"

    id: uuid.UUID = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    name: str = Column(String(120), nullable=False)
    description: str = Column(Text, nullable=True)
    status: str = Column(String(20), nullable=False, default="active")
    primary_category: str = Column(String(40), nullable=False)
    custom_category_label: str = Column(String(100), nullable=True)
    locality_label: str = Column(String(150), nullable=True)
    city: str = Column(String(100), nullable=True)
    state: str = Column(String(100), nullable=True)
    country: str = Column(String(100), nullable=True)
    created_by_user_id: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_by_user_id: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: datetime = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: datetime = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_groups_status", "status"),
        Index("ix_groups_primary_category", "primary_category"),
        Index("ix_groups_city_state_country", "city", "state", "country"),
    )

    def __repr__(self) -> str:
        return f"<Group(id={self.id}, name={self.name}, status={self.status})>"
