"""Pydantic schemas for authentication."""
from pydantic import BaseModel


class SessionResponse(BaseModel):
    """Response from POST /auth/session endpoint."""
    user_id: str
    firebase_uid: str
    
    class Config:
        from_attributes = True
