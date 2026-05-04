from __future__ import annotations
"""Pydantic schemas for caregiver collaboration and invites."""
from datetime import datetime
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, Field

from app.schemas.user import UserSummary


# ---------------------------------------------------------------------------
# Invite creation
# ---------------------------------------------------------------------------

class InviteCreate(BaseModel):
    """Request body for POST /babies/{baby_id}/caregivers/invite."""
    invite_email: Optional[str] = Field(
        None,
        description="Email address of the person to invite (optional for link-based invite)",
    )
    role: str = Field(
        "caregiver",
        description="Role to grant: 'caregiver' (owner cannot be invited)",
    )


# ---------------------------------------------------------------------------
# Individual membership record in list/detail responses
# ---------------------------------------------------------------------------

class CaregiverEntry(BaseModel):
    """One membership/invite row as returned to the owner."""
    id: UUID
    baby_id: UUID
    user_id: Optional[UUID] = None          # None until invite is accepted
    role: str
    status: str                           # pending | accepted | revoked
    invite_email: Optional[str] = None
    invite_expires_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    # Populated from the linked user record when status == accepted
    user: Optional[UserSummary] = None

    class Config:
        from_attributes = True


class CaregiverListResponse(BaseModel):
    """Response for GET /babies/{baby_id}/caregivers."""
    owner: CaregiverEntry
    caregivers: list[CaregiverEntry]      # accepted
    pending_invites: list[CaregiverEntry]


# ---------------------------------------------------------------------------
# Invite-specific responses
# ---------------------------------------------------------------------------

class InviteResponse(BaseModel):
    """Response returned after creating an invite."""
    id: UUID
    baby_id: UUID
    role: str
    status: str
    invite_email: Optional[str] = None
    invite_token: str
    share_code: str
    invite_expires_at: datetime

    class Config:
        from_attributes = True


class InvitePreview(BaseModel):
    """
    Response for GET /babies/invites/{token} — public preview before accepting.
    Does not require auth. Does not expose internal IDs as secrets.
    """
    baby_id: UUID
    baby_name: str
    inviter: Optional[UserSummary] = None
    role: str
    status: str
    invite_email: Optional[str] = None
    expires_at: Optional[datetime] = None
    is_valid: bool                        # False if expired or revoked
    is_expired: bool


class InviteAcceptRequest(BaseModel):
    """Request body for POST /babies/invites/accept."""
    token: str = Field(..., min_length=1)
