"""Pydantic schemas for mood entries."""
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class MoodBase(BaseModel):
    """Base mood schema."""
    mood: str = Field(..., min_length=1, max_length=50, description="Mood: happy, sad, anxious, ok, etc.")
    energy: str = Field(..., min_length=1, max_length=50, description="Energy level: high, medium, low")
    timestamp: datetime = Field(..., description="Timestamp of mood check-in in UTC")
    notes: str | None = Field(None, max_length=500, description="Optional notes")


class MoodCreate(MoodBase):
    """Schema for creating a mood entry."""
    pass


class MoodUpdate(BaseModel):
    """Schema for updating a mood entry."""
    mood: str | None = Field(None, min_length=1, max_length=50)
    energy: str | None = Field(None, min_length=1, max_length=50)
    timestamp: datetime | None = None
    notes: str | None = Field(None, max_length=500)


class Mood(MoodBase):
    """Mood schema for responses."""
    id: UUID
    baby_id: UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class MoodListResponse(BaseModel):
    """Paginated mood list response."""
    items: list[Mood]
    total: int
    limit: int
    offset: int
