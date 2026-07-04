from __future__ import annotations
"""Message model for community groups."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Index, Text, String
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class GroupMessage(Base):
    """Stores one flat chat message inside a group."""

    __tablename__ = "group_messages"

    id: uuid.UUID = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    group_id: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_user_id: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    body: str = Column(Text, nullable=True)
    status: str = Column(String(20), nullable=False, default="active")
    removed_at: datetime = Column(DateTime(timezone=True), nullable=True)
    removed_by_user_id: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    removal_reason: str = Column(Text, nullable=True)
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
        Index("ix_group_messages_group_id_created_at", "group_id", "created_at"),
        Index("ix_group_messages_group_id_status", "group_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<GroupMessage(id={self.id}, group_id={self.group_id}, status={self.status})>"
