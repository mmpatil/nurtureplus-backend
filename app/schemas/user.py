from __future__ import annotations
"""Pydantic schemas for users."""
from datetime import datetime
from uuid import UUID
from typing import Optional
from pydantic import BaseModel


class UserBase(BaseModel):
    """Base user schema."""
    firebase_uid: str


class UserCreate(UserBase):
    """Schema for creating a user."""
    pass


class User(UserBase):
    """User schema for responses."""
    id: str
    created_at: datetime

    class Config:
        from_attributes = True


class UserSummary(BaseModel):
    """Minimal user profile included in caregiver and audit responses."""
    id: UUID
    display_name: Optional[str] = None
    email: Optional[str] = None
    relationship_label: Optional[str] = None

    class Config:
        from_attributes = True
