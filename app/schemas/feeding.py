"""Pydantic schemas for feeding entries."""
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class FeedingBase(BaseModel):
    """Base feeding schema."""
    feeding_type: str = Field(..., min_length=1, max_length=50, description="Feeding type: bottle, breast_left, breast_right, both")
    amount_ml: int | None = Field(None, ge=0, le=500, description="Amount in milliliters")
    duration_min: int | None = Field(None, ge=0, le=180, description="Duration in minutes")
    timestamp: datetime = Field(..., description="Timestamp of feeding in UTC")
    notes: str | None = Field(None, max_length=500, description="Optional notes")


class FeedingCreate(FeedingBase):
    """Schema for creating a feeding entry."""
    pass


class FeedingUpdate(BaseModel):
    """Schema for updating a feeding entry."""
    feeding_type: str | None = Field(None, min_length=1, max_length=50)
    amount_ml: int | None = Field(None, ge=0, le=500)
    duration_min: int | None = Field(None, ge=0, le=180)
    timestamp: datetime | None = None
    notes: str | None = Field(None, max_length=500)


class Feeding(FeedingBase):
    """Feeding schema for responses."""
    id: UUID
    baby_id: UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class FeedingListResponse(BaseModel):
    """Paginated feeding list response."""
    items: list[Feeding]
    total: int
    limit: int
    offset: int
