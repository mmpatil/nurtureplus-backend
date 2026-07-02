from __future__ import annotations
"""Schemas for package/product suitability analysis."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.feeding import ManualNutritionInput


class ProductAnalysisRequest(BaseModel):
    """Input payload for product/package analysis."""

    product_name: Optional[str] = Field(None, max_length=255)
    brand_name: Optional[str] = Field(None, max_length=255)
    package_front_url: Optional[str] = Field(None, max_length=2000)
    package_back_url: Optional[str] = Field(None, max_length=2000)
    ingredients_text: Optional[str] = Field(None, max_length=4000)
    nutrition_facts_text: Optional[str] = Field(None, max_length=4000)
    manual_nutrition: Optional[ManualNutritionInput] = None
    baby_ids: Optional[list[UUID]] = None


class ProductSuitabilityRow(BaseModel):
    """Verdict for one baby or child profile."""

    baby_id: UUID
    baby_name: str
    life_stage: str
    verdict: str
    confidence: float = Field(..., ge=0, le=1)
    reasons: list[str] = Field(default_factory=list)
    warning_flags: list[str] = Field(default_factory=list)
    allergen_hits: list[str] = Field(default_factory=list)


class ProductAnalysisResponse(BaseModel):
    """Saved product analysis result."""

    id: UUID
    product_name: Optional[str] = None
    brand_name: Optional[str] = None
    status: Optional[str] = None
    confidence: float = Field(..., ge=0, le=1)
    parsed_facts: dict[str, Any] = Field(default_factory=dict)
    package_front_url: Optional[str] = None
    package_back_url: Optional[str] = None
    ingredients_text: Optional[str] = None
    nutrition_facts_text: Optional[str] = None
    suitability: list[ProductSuitabilityRow] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
