"""Pydantic schemas for sleep entries."""
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class SleepBase(BaseModel):
    """Base sleep schema."""
    start_time: datetime = Field(..., description="Sleep start time in UTC")
    end_time: datetime | None = Field(None, description="Sleep end time in UTC (optional)")
    duration_min: int | None = Field(None, ge=0, le=1440, description="Duration in minutes (auto-calculated if end_time provided)")
    quality: str | None = Field(None, max_length=50, description="Sleep quality: great, good, fair, poor, etc.")
    notes: str | None = Field(None, max_length=500, description="Optional notes")


class SleepCreate(SleepBase):
    """Schema for creating a sleep entry."""
    pass


class SleepUpdate(BaseModel):
    """Schema for updating a sleep entry."""
    start_time: datetime | None = None
    end_time: datetime | None = None
    duration_min: int | None = Field(None, ge=0, le=1440)
    quality: str | None = Field(None, max_length=50)
    notes: str | None = Field(None, max_length=500)


class Sleep(SleepBase):
    """Sleep schema for responses."""
    id: UUID
    baby_id: UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class SleepListResponse(BaseModel):
    """Paginated sleep list response."""
    items: list[Sleep]
    total: int
    limit: int
    offset: int
