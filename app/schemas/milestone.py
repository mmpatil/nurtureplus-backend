"""Pydantic schemas for milestone entries."""
from datetime import date, datetime
from enum import Enum
from uuid import UUID
from pydantic import BaseModel, Field, AnyHttpUrl


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
    notes: str | None = Field(None, max_length=500, description="Optional notes")
    photo_url: AnyHttpUrl | None = Field(None, description="Firebase Storage download URL for milestone photo")


class MilestoneCreate(MilestoneBase):
    """Schema for creating a milestone entry."""
    pass


class MilestoneUpdate(BaseModel):
    """Schema for updating a milestone entry."""
    title: str | None = Field(None, min_length=1, max_length=255)
    category: MilestoneCategory | None = None
    achieved_date: date | None = None
    notes: str | None = Field(None, max_length=500)
    photo_url: AnyHttpUrl | None = None


class Milestone(MilestoneBase):
    """Milestone schema for responses."""
    id: UUID
    baby_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MilestoneListResponse(BaseModel):
    """Paginated milestone list response."""
    items: list[Milestone]
    total: int
    limit: int
    offset: int
