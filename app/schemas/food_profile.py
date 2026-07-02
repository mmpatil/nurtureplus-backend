from __future__ import annotations
"""Schemas for baby food profiles."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class BabyFoodProfileBase(BaseModel):
    """Editable baby food profile fields."""

    allergens: list[str] = Field(default_factory=list)
    avoid_ingredients: list[str] = Field(default_factory=list)
    dietary_flags: list[str] = Field(default_factory=list)
    stage_override: Optional[str] = Field(None, max_length=30)


class BabyFoodProfileUpdate(BabyFoodProfileBase):
    """Upsert payload for a baby's food profile."""


class BabyFoodProfileResponse(BabyFoodProfileBase):
    """Returned baby food profile."""

    id: Optional[UUID] = None
    baby_id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
