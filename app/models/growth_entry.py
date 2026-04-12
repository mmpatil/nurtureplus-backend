"""Growth entry database model."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base


class GrowthEntry(Base):
    """Growth entry model for tracking baby measurements."""

    __tablename__ = "growth_entries"

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
    measurement_date: datetime = Column(DateTime(timezone=True), nullable=False, index=True)
    weight_kg: float = Column(Float, nullable=True)
    height_cm: float = Column(Float, nullable=True)
    head_circumference_cm: float = Column(Float, nullable=True)
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

    __table_args__ = (
        Index("ix_growth_entries_baby_id_date", "baby_id", "measurement_date"),
    )

    def __repr__(self) -> str:
        return f"<GrowthEntry(id={self.id}, baby_id={self.baby_id}, date={self.measurement_date})>"
