from __future__ import annotations
"""Stored product analysis inputs and parsed facts."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class ProductAnalysis(Base):
    """Stores one analyzed product/package."""

    __tablename__ = "product_analyses"

    id: uuid.UUID = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    user_id: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_name: str = Column(String(255), nullable=True)
    brand_name: str = Column(String(255), nullable=True)
    package_front_url: str = Column(Text, nullable=True)
    package_back_url: str = Column(Text, nullable=True)
    ingredients_text: str = Column(Text, nullable=True)
    nutrition_facts_text: str = Column(Text, nullable=True)
    parsed_facts: dict = Column(JSON, nullable=True)
    status: str = Column(String(30), nullable=True)
    confidence: float = Column(Float, nullable=True)
    model_name: str = Column(String(100), nullable=True)
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
        Index("ix_product_analyses_user_id_created_at", "user_id", "created_at"),
    )

