from __future__ import annotations
"""Nutrition estimate attached to a feeding entry."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, JSON, String
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class FeedingNutritionEstimate(Base):
    """Stores structured nutrient estimates for a feeding."""

    __tablename__ = "feeding_nutrition_estimates"

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
        unique=True,
        index=True,
    )
    baby_id: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey("babies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source: str = Column(String(30), nullable=True)
    calories: float = Column(Float, nullable=True)
    protein_g: float = Column(Float, nullable=True)
    fat_g: float = Column(Float, nullable=True)
    carbs_g: float = Column(Float, nullable=True)
    fiber_g: float = Column(Float, nullable=True)
    sugar_g: float = Column(Float, nullable=True)
    added_sugar_g: float = Column(Float, nullable=True)
    sodium_mg: float = Column(Float, nullable=True)
    iron_mg: float = Column(Float, nullable=True)
    calcium_mg: float = Column(Float, nullable=True)
    raw_payload: dict = Column(JSON, nullable=True)
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
        Index("ix_feeding_nutrition_estimates_baby_id", "baby_id"),
    )

