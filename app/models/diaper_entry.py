"""Diaper entry database model."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base


class DiaperEntry(Base):
    """Diaper entry model for tracking baby diaper changes."""
    
    __tablename__ = "diaper_entries"
    
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
    diaper_type: str = Column(String(50), nullable=False)  # wet, dirty, both, dry
    timestamp: datetime = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
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
        Index("ix_diaper_entries_baby_id", "baby_id"),
        Index("ix_diaper_entries_baby_id_timestamp", "baby_id", "timestamp"),
    )
    
    def __repr__(self) -> str:
        return f"<DiaperEntry(id={self.id}, baby_id={self.baby_id}, type={self.diaper_type})>"
