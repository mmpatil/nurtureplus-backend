from __future__ import annotations
"""Pydantic schemas for milestone entries."""
from datetime import date, datetime
from enum import Enum
from uuid import UUID
from typing import Optional
from pydantic import AnyHttpUrl, BaseModel, Field, field_validator
from app.schemas.user import UserSummary


class MilestoneCategory(str, Enum):
    motor = "motor"
    social = "social"
    language = "language"
    feeding = "feeding"
    sleep = "sleep"
    other = "other"


class MilestoneBase(BaseModel):
    """Base milestone schema."""
    title: str = Field(..., min_length=1, max_length=255, description="Milestone title")
    category: MilestoneCategory = Field(..., description="Milestone category")
    achieved_date: date = Field(..., description="Date milestone was achieved")
    notes: Optional[str] = Field(None, max_length=500, description="Optional notes")
    photo_url: Optional[AnyHttpUrl] = Field(None, description="Firebase Storage download URL for milestone photo")

    @field_validator("achieved_date", mode="before")
    @classmethod
    def coerce_achieved_date(cls, value: date | datetime) -> date:
        if isinstance(value, datetime):
            return value.date()
        return value


class MilestoneCreate(MilestoneBase):
    """Schema for creating a milestone entry."""
    pass


class MilestoneUpdate(BaseModel):
    """Schema for updating a milestone entry."""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    category: Optional[MilestoneCategory] = None
    achieved_date: Optional[date] = None
    notes: Optional[str] = Field(None, max_length=500)
    photo_url: Optional[AnyHttpUrl] = None


class Milestone(MilestoneBase):
    """Milestone schema for responses."""
    id: UUID
    baby_id: UUID
    created_by_user_id: Optional[UUID] = None
    updated_by_user_id: Optional[UUID] = None
    created_by: Optional[UserSummary] = None
    updated_by: Optional[UserSummary] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MilestoneListResponse(BaseModel):
    """Paginated milestone list response."""
    items: list[Milestone]
    total: int
    limit: int
    offset: int
