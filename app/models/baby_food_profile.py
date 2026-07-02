from __future__ import annotations
"""Saved food suitability preferences for a baby."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Index, JSON, String
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class BabyFoodProfile(Base):
    """Structured allergies and restriction preferences for a baby."""

    __tablename__ = "baby_food_profiles"

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
        unique=True,
        index=True,
    )
    allergens: list[str] = Column(JSON, nullable=False, default=list)
    avoid_ingredients: list[str] = Column(JSON, nullable=False, default=list)
    dietary_flags: list[str] = Column(JSON, nullable=False, default=list)
    stage_override: str = Column(String(30), nullable=True)
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
        Index("ix_baby_food_profiles_baby_id", "baby_id"),
    )

