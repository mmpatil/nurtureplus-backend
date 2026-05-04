from __future__ import annotations
"""Pydantic schemas for sleep entries."""
from datetime import datetime
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, Field
from app.schemas.user import UserSummary


class SleepBase(BaseModel):
    """Base sleep schema."""
    start_time: datetime = Field(..., description="Sleep start time in UTC")
    end_time: Optional[datetime] = Field(None, description="Sleep end time in UTC (optional)")
    duration_min: Optional[int] = Field(None, ge=0, le=1440, description="Duration in minutes (auto-calculated if end_time provided)")
    quality: Optional[str] = Field(None, max_length=50, description="Sleep quality: great, good, fair, poor, etc.")
    notes: Optional[str] = Field(None, max_length=500, description="Optional notes")


class SleepCreate(SleepBase):
    """Schema for creating a sleep entry."""
    pass


class SleepUpdate(BaseModel):
    """Schema for updating a sleep entry."""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_min: Optional[int] = Field(None, ge=0, le=1440)
    quality: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = Field(None, max_length=500)


class Sleep(SleepBase):
    """Sleep schema for responses."""
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


class SleepListResponse(BaseModel):
    """Paginated sleep list response."""
    items: list[Sleep]
    total: int
    limit: int
    offset: int
