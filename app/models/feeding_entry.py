from __future__ import annotations
"""Feeding entry database model."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Index, Text, Float
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base


class FeedingEntry(Base):
    """Feeding entry model for tracking baby feedings."""
    
    __tablename__ = "feeding_entries"
    
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
    feeding_type: str = Column(String(50), nullable=False)  # bottle, breast_left, breast_right, both
    feeding_category: str = Column(String(50), nullable=True)
    feeding_subtype: str = Column(String(50), nullable=True)
    food_name: str = Column(String(255), nullable=True)
    brand_name: str = Column(String(255), nullable=True)
    amount_ml: int = Column(Integer, nullable=True)  # Amount in milliliters
    amount_value: float = Column(Float, nullable=True)
    amount_unit: str = Column(String(30), nullable=True)
    duration_min: int = Column(Integer, nullable=True)  # Duration in minutes
    serving_count_offered: float = Column(Float, nullable=True)
    serving_count_consumed: float = Column(Float, nullable=True)
    consumed_fraction: float = Column(Float, nullable=True)
    analysis_status: str = Column(String(30), nullable=True)
    analysis_confidence: float = Column(Float, nullable=True)
    nutrition_source: str = Column(String(30), nullable=True)
    timestamp: datetime = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    notes: str = Column(Text, nullable=True)
    # Audit: which caregiver/owner logged or last edited this entry
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
    
    # Indexes for query optimization
    __table_args__ = (
        Index("ix_feeding_entries_baby_id", "baby_id"),
        Index("ix_feeding_entries_baby_id_timestamp", "baby_id", "timestamp"),
    )
    
    def __repr__(self) -> str:
        return f"<FeedingEntry(id={self.id}, baby_id={self.baby_id}, type={self.feeding_type})>"
