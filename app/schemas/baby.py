from __future__ import annotations
"""Pydantic schemas for babies."""
from datetime import datetime, date
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, Field

from app.schemas.user import UserSummary


class BabyBase(BaseModel):
    """Base baby schema."""
    name: str = Field(..., min_length=1, max_length=100, description="Baby name")
    birth_date: date = Field(..., description="Baby birth date")
    photo_url: Optional[str] = Field(None, max_length=500, description="Optional photo URL")


class BabyCreate(BabyBase):
    """Schema for creating a baby."""
    pass


class BabyUpdate(BaseModel):
    """Schema for updating a baby."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    birth_date: Optional[date] = None
    photo_url: Optional[str] = Field(None, max_length=500)


class Baby(BabyBase):
    """Baby schema for responses — includes membership context when available."""
    id: UUID
    user_id: UUID                          # original owner FK (always present)
    created_at: datetime
    updated_at: datetime

    # Populated by the list / get endpoints that join baby_access
    current_user_role: Optional[str] = None   # "owner" | "caregiver"
    ownership_type: Optional[str] = None      # "owned" | "shared"
    caregiver_count: Optional[int] = None     # number of accepted caregivers (excl. owner)
    owner: Optional[UserSummary] = None       # populated for shared babies

    class Config:
        from_attributes = True


class BabyListResponse(BaseModel):
    """Paginated baby list response."""
    items: list[Baby]
    total: int
    limit: int
    offset: int

    class Config:
        from_attributes = True
