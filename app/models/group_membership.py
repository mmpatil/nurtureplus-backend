from __future__ import annotations
"""Membership model for community groups."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class GroupMembership(Base):
    """Tracks whether a user is active, left, or banned in a group."""

    __tablename__ = "group_memberships"

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
    user_id: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: str = Column(String(20), nullable=False)
    joined_at: datetime = Column(DateTime(timezone=True), nullable=True)
    left_at: datetime = Column(DateTime(timezone=True), nullable=True)
    banned_at: datetime = Column(DateTime(timezone=True), nullable=True)
    ban_reason: str = Column(Text, nullable=True)
    banned_by_user_id: uuid.UUID = Column(
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
        Index("uq_group_memberships_group_id_user_id", "group_id", "user_id", unique=True),
        Index("ix_group_memberships_group_id_status", "group_id", "status"),
        Index("ix_group_memberships_user_id_status", "user_id", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<GroupMembership(group_id={self.group_id}, user_id={self.user_id}, "
            f"status={self.status})>"
        )
