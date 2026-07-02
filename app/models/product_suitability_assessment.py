from __future__ import annotations
"""Per-baby suitability verdict for one analyzed product."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, JSON, String
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class ProductSuitabilityAssessment(Base):
    """Stores one product suitability verdict for one baby."""

    __tablename__ = "product_suitability_assessments"

    id: uuid.UUID = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    product_analysis_id: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey("product_analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    baby_id: uuid.UUID = Column(
        UUID(as_uuid=True),
        ForeignKey("babies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    life_stage: str = Column(String(30), nullable=False)
    verdict: str = Column(String(10), nullable=False)
    confidence: float = Column(Float, nullable=True)
    reasons: list[str] = Column(JSON, nullable=False, default=list)
    warning_flags: list[str] = Column(JSON, nullable=False, default=list)
    allergen_hits: list[str] = Column(JSON, nullable=False, default=list)
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
        Index(
            "ix_product_suitability_assessments_product_analysis_baby",
            "product_analysis_id",
            "baby_id",
        ),
    )
