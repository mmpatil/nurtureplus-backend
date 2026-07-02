from __future__ import annotations
"""Media attached to a feeding analysis or entry."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class FeedingMedia(Base):
    """Stores before/after meal and package photos for a feeding."""

    __tablename__ = "feeding_media"

    id: uuid.UUID = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    feeding_id: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey("feeding_entries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    baby_id: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey("babies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    media_role: str = Column(String(30), nullable=False)
    media_url: str = Column(Text, nullable=False)
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
        Index("ix_feeding_media_feeding_id_role", "feeding_id", "media_role"),
        Index("ix_feeding_media_baby_id", "baby_id"),
    )

