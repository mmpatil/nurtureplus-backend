"""Sleep entry database model."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base


class SleepEntry(Base):
    """Sleep entry model for tracking baby sleep."""
    
    __tablename__ = "sleep_entries"
    
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
    start_time: datetime = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    end_time: datetime = Column(
        DateTime(timezone=True),
        nullable=True,
    )
    duration_min: int = Column(Integer, nullable=True)  # Duration in minutes
    quality: str = Column(String(50), nullable=True)  # Quality rating: great, good, fair, poor, etc.
    notes: str = Column(Text, nullable=True)
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
    
    # Indexes for query optimization
    __table_args__ = (
        Index("ix_sleep_entries_baby_id", "baby_id"),
        Index("ix_sleep_entries_baby_id_start_time", "baby_id", "start_time"),
    )
    
    def __repr__(self) -> str:
        return f"<SleepEntry(id={self.id}, baby_id={self.baby_id}, start={self.start_time})>"
