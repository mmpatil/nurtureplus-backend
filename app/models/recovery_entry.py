"""SQLAlchemy model for postpartum recovery entries."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    UUID,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY

from app.db.base import Base


class RecoveryEntry(Base):
    """Recovery entry for authenticated user (mother/postpartum tracking)."""

    __tablename__ = "recovery_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Recovery entry fields
    timestamp = Column(DateTime(timezone=True), nullable=False)  # When the check-in occurred
    mood = Column(String(20), nullable=False)  # great, good, okay, struggling, overwhelmed
    energy_level = Column(String(20), nullable=False)  # veryLow, low, moderate, high, veryHigh
    water_intake_oz = Column(Integer, nullable=False)  # 0-128
    symptoms = Column(ARRAY(String), nullable=False, default=[])  # Array of symptom strings
    notes = Column(Text, nullable=True)  # Optional user notes

    # Metadata
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Indexes for efficient queries
    __table_args__ = (
        Index("ix_recovery_entries_user_id", "user_id"),
        Index("ix_recovery_entries_user_timestamp", "user_id", "timestamp"),
        Index("ix_recovery_entries_timestamp", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<RecoveryEntry(id={self.id}, user_id={self.user_id}, mood={self.mood})>"
