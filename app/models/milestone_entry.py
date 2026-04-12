"""Milestone entry database model."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base


class MilestoneEntry(Base):
    """Milestone entry model for tracking baby developmental milestones."""

    __tablename__ = "milestone_entries"

    id: uuid.UUID = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    baby_id: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey("babies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: str = Column(String(255), nullable=False)
    category: str = Column(String(50), nullable=False)  # motor, social, language, feeding, sleep, other
    achieved_date: datetime = Column(DateTime(timezone=True), nullable=False, index=True)
    notes: str = Column(Text, nullable=True)
    photo_url: str = Column(Text, nullable=True)  # Firebase Storage download URL
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
        Index("ix_milestone_entries_baby_id_date", "baby_id", "achieved_date"),
    )

    def __repr__(self) -> str:
        return f"<MilestoneEntry(id={self.id}, baby_id={self.baby_id}, title={self.title})>"
