"""Pydantic schemas for users."""
from datetime import datetime
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
