from __future__ import annotations
"""Pydantic schemas for diaper entries."""
from datetime import datetime
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, Field
from app.schemas.user import UserSummary


class DiaperBase(BaseModel):
    """Base diaper schema."""
    diaper_type: str = Field(..., min_length=1, max_length=50, description="Diaper type: wet, dirty, both, dry")
    timestamp: datetime = Field(..., description="Timestamp of diaper change in UTC")
    notes: Optional[str] = Field(None, max_length=500, description="Optional notes")


class DiaperCreate(DiaperBase):
    """Schema for creating a diaper entry."""
    pass


class DiaperUpdate(BaseModel):
    """Schema for updating a diaper entry."""
    diaper_type: Optional[str] = Field(None, min_length=1, max_length=50)
    timestamp: Optional[datetime] = None
    notes: Optional[str] = Field(None, max_length=500)


class Diaper(DiaperBase):
    """Diaper schema for responses."""
    id: UUID
    baby_id: UUID
    created_by_user_id: Optional[UUID] = None
    updated_by_user_id: Optional[UUID] = None
    created_by: Optional[UserSummary] = None
    updated_by: Optional[UserSummary] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DiaperListResponse(BaseModel):
    """Paginated diaper list response."""
    items: list[Diaper]
    total: int
    limit: int
    offset: int
