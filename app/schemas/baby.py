"""Pydantic schemas for babies."""
from datetime import datetime, date
from uuid import UUID
from pydantic import BaseModel, Field


class BabyBase(BaseModel):
    """Base baby schema."""
    name: str = Field(..., min_length=1, max_length=100, description="Baby name")
    birth_date: date = Field(..., description="Baby birth date")
    photo_url: str | None = Field(None, max_length=500, description="Optional photo URL")


class BabyCreate(BabyBase):
    """Schema for creating a baby."""
    pass


class BabyUpdate(BaseModel):
    """Schema for updating a baby."""
    name: str | None = Field(None, min_length=1, max_length=100)
    birth_date: date | None = None
    photo_url: str | None = Field(None, max_length=500)


class Baby(BabyBase):
    """Baby schema for responses."""
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime
    
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
