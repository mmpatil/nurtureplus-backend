from __future__ import annotations
"""Schemas for package/product suitability analysis."""

from datetime import datetime
from typing import Any, Literal, Optional
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


class ProductConcern(BaseModel):
    """One structured concern found during product analysis."""

    code: str
    label: str
    severity: Literal["high", "medium", "low"]
    message: str


class ProductAnalysisSource(BaseModel):
    """One source used to build the analysis."""

    url: str
    domain: str
    source_kind: Literal["brand", "retailer", "manual", "package_text", "llm"]
    used_fields: list[str] = Field(default_factory=list)


class ProductSuitabilityRow(BaseModel):
    """Verdict for one baby or child profile."""

    baby_id: UUID
    baby_name: str
    life_stage: str
    verdict: Literal["very_bad", "bad", "average", "good", "excellent"]
    headline: str = ""
    confidence: float = Field(..., ge=0, le=1)
    ingredient_concerns: list[ProductConcern] = Field(default_factory=list)
    category_concerns: list[ProductConcern] = Field(default_factory=list)
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
    lookup_status: Literal["not_attempted", "fetched", "partial", "not_found", "failed"] = "not_attempted"
    category_guess: Optional[str] = None
    analysis_sources: list[ProductAnalysisSource] = Field(default_factory=list)
    package_front_url: Optional[str] = None
    package_back_url: Optional[str] = None
    ingredients_text: Optional[str] = None
    nutrition_facts_text: Optional[str] = None
    suitability: list[ProductSuitabilityRow] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
