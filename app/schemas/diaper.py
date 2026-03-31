"""Pydantic schemas for diaper entries."""
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class DiaperBase(BaseModel):
    """Base diaper schema."""
    diaper_type: str = Field(..., min_length=1, max_length=50, description="Diaper type: wet, dirty, both, dry")
    timestamp: datetime = Field(..., description="Timestamp of diaper change in UTC")
    notes: str | None = Field(None, max_length=500, description="Optional notes")


class DiaperCreate(DiaperBase):
    """Schema for creating a diaper entry."""
    pass


class DiaperUpdate(BaseModel):
    """Schema for updating a diaper entry."""
    diaper_type: str | None = Field(None, min_length=1, max_length=50)
    timestamp: datetime | None = None
    notes: str | None = Field(None, max_length=500)


class Diaper(DiaperBase):
    """Diaper schema for responses."""
    id: UUID
    baby_id: UUID
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
