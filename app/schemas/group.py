from __future__ import annotations
"""Pydantic schemas for community groups."""

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


GroupPrimaryCategory = Literal[
    "locality",
    "residential_community",
    "workplace",
    "breastfeeding",
    "new_mothers",
    "baby_age",
    "toddler_mothers",
    "pregnancy",
    "postpartum_support",
    "general_parenting",
    "other",
]
GroupStatus = Literal["active", "archived"]
GroupMembershipStatus = Literal["active", "left", "banned"]
GroupMessageStatus = Literal["active", "removed"]
GroupRequestStatus = Literal["pending", "approved", "rejected", "merged"]
AttachmentKind = Literal["image", "video", "audio", "file", "link"]

LOCATION_REQUIRED_CATEGORIES = {
    "locality",
    "residential_community",
    "workplace",
}


def _normalize_tag_list(tags: list[str] | None) -> list[str]:
    if not tags:
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for raw in tags:
        cleaned = " ".join(str(raw).strip().lower().split())
        if not cleaned:
            continue
        if cleaned in seen:
            continue
        seen.add(cleaned)
        normalized.append(cleaned)
    return normalized


class GroupUserSummary(BaseModel):
    """Group-safe user summary without email exposure."""

    id: UUID
    display_name: Optional[str] = None

    class Config:
        from_attributes = True


class GroupPayloadBase(BaseModel):
    """Shared validation rules for groups and group requests."""

    name: str = Field(..., min_length=1, max_length=120)
    description: Optional[str] = Field(None, max_length=2000)
    primary_category: GroupPrimaryCategory
    custom_category_label: Optional[str] = Field(None, min_length=1, max_length=100)
    locality_label: Optional[str] = Field(None, min_length=1, max_length=150)
    city: Optional[str] = Field(None, min_length=1, max_length=100)
    state: Optional[str] = Field(None, min_length=1, max_length=100)
    country: Optional[str] = Field(None, min_length=1, max_length=100)
    tags: list[str] = Field(default_factory=list)

    @field_validator("tags", mode="before")
    @classmethod
    def normalize_tags(cls, value):
        return _normalize_tag_list(value)

    @model_validator(mode="after")
    def validate_category_requirements(self):
        if self.primary_category == "other" and not self.custom_category_label:
            raise ValueError("custom_category_label is required when primary_category is 'other'")
        if self.primary_category in LOCATION_REQUIRED_CATEGORIES and not self.locality_label:
            raise ValueError("locality_label is required for locality-based groups")
        return self


class GroupCreate(GroupPayloadBase):
    """Admin-only payload for direct group creation."""

    status: GroupStatus = "active"


class GroupUpdate(BaseModel):
    """Admin-only payload for updating an existing group."""

    name: Optional[str] = Field(None, min_length=1, max_length=120)
    description: Optional[str] = Field(None, max_length=2000)
    status: Optional[GroupStatus] = None
    primary_category: Optional[GroupPrimaryCategory] = None
    custom_category_label: Optional[str] = Field(None, min_length=1, max_length=100)
    locality_label: Optional[str] = Field(None, min_length=1, max_length=150)
    city: Optional[str] = Field(None, min_length=1, max_length=100)
    state: Optional[str] = Field(None, min_length=1, max_length=100)
    country: Optional[str] = Field(None, min_length=1, max_length=100)
    tags: Optional[list[str]] = None

    @field_validator("tags", mode="before")
    @classmethod
    def normalize_tags(cls, value):
        if value is None:
            return None
        return _normalize_tag_list(value)


class Group(GroupPayloadBase):
    """Response model for a community group."""

    id: UUID
    status: GroupStatus
    member_count: int = 0
    membership_status: Optional[str] = None
    can_join: bool = False
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class GroupListResponse(BaseModel):
    """Paginated community-group list response."""

    items: list[Group]
    total: int
    limit: int
    offset: int


class GroupMembershipResponse(BaseModel):
    """Response model for a user's membership in a group."""

    id: UUID
    group_id: UUID
    user_id: UUID
    status: GroupMembershipStatus
    joined_at: Optional[datetime] = None
    left_at: Optional[datetime] = None
    banned_at: Optional[datetime] = None
    ban_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class GroupMember(BaseModel):
    """Active group member list entry."""

    id: UUID
    group_id: UUID
    user_id: UUID
    status: GroupMembershipStatus
    joined_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    user: Optional[GroupUserSummary] = None

    class Config:
        from_attributes = True


class GroupMemberListResponse(BaseModel):
    """Response for listing active members in a group."""

    items: list[GroupMember]
    total: int


class GroupMessageAttachmentBase(BaseModel):
    """Shared attachment metadata fields."""

    attachment_kind: AttachmentKind
    url: str = Field(..., min_length=1, max_length=2000)
    mime_type: Optional[str] = Field(None, max_length=200)
    file_name: Optional[str] = Field(None, max_length=255)
    size_bytes: Optional[int] = Field(None, ge=0)


class GroupMessageAttachmentCreate(GroupMessageAttachmentBase):
    """Input payload for a message attachment."""


class GroupMessageAttachment(GroupMessageAttachmentBase):
    """Response model for a persisted message attachment."""

    id: UUID
    message_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


class GroupMessageCreate(BaseModel):
    """Payload for sending a message in a group."""

    body: Optional[str] = Field(None, max_length=4000)
    attachments: list[GroupMessageAttachmentCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_content(self):
        if not (self.body and self.body.strip()) and not self.attachments:
            raise ValueError("Message body or at least one attachment is required")
        return self


class GroupMessage(BaseModel):
    """Response model for a group message."""

    id: UUID
    group_id: UUID
    sender_user_id: UUID
    body: Optional[str] = None
    status: GroupMessageStatus
    removed_at: Optional[datetime] = None
    removal_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    sender: Optional[GroupUserSummary] = None
    attachments: list[GroupMessageAttachment] = Field(default_factory=list)

    class Config:
        from_attributes = True


class GroupMessageListResponse(BaseModel):
    """Paginated list of messages for a group."""

    items: list[GroupMessage]
    total: int
    limit: int
    offset: int


class GroupState(BaseModel):
    """Per-user state for a group chat."""

    group_id: UUID
    unread_count: int = Field(0, ge=0)
    notifications_enabled: bool = True
    last_read_message_id: Optional[UUID] = None
    last_activity_at: Optional[datetime] = None


class GroupStateUpdate(BaseModel):
    """Partial update payload for a user's group chat state."""

    last_read_message_id: Optional[UUID] = None
    mark_all_read: Optional[bool] = None
    notifications_enabled: Optional[bool] = None


class GroupRequestCreate(GroupPayloadBase):
    """Payload for a user-submitted request to create a group."""

    request_note: Optional[str] = Field(None, max_length=2000)


class GroupRequest(BaseModel):
    """Response model for a group request."""

    id: UUID
    requester_user_id: UUID
    name: str
    description: Optional[str] = None
    primary_category: GroupPrimaryCategory
    custom_category_label: Optional[str] = None
    locality_label: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    request_note: Optional[str] = None
    status: GroupRequestStatus
    resolution_note: Optional[str] = None
    resolved_group_id: Optional[UUID] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    requester: Optional[GroupUserSummary] = None
    resolved_by: Optional[GroupUserSummary] = None

    class Config:
        from_attributes = True


class GroupRequestListResponse(BaseModel):
    """Paginated list of group requests."""

    items: list[GroupRequest]
    total: int
    limit: int
    offset: int


class GroupRequestApprove(BaseModel):
    """Admin payload for approving a pending group request."""

    name: Optional[str] = Field(None, min_length=1, max_length=120)
    description: Optional[str] = Field(None, max_length=2000)
    primary_category: Optional[GroupPrimaryCategory] = None
    custom_category_label: Optional[str] = Field(None, min_length=1, max_length=100)
    locality_label: Optional[str] = Field(None, min_length=1, max_length=150)
    city: Optional[str] = Field(None, min_length=1, max_length=100)
    state: Optional[str] = Field(None, min_length=1, max_length=100)
    country: Optional[str] = Field(None, min_length=1, max_length=100)
    tags: Optional[list[str]] = None
    resolution_note: Optional[str] = Field(None, max_length=2000)

    @field_validator("tags", mode="before")
    @classmethod
    def normalize_tags(cls, value):
        if value is None:
            return None
        return _normalize_tag_list(value)


class GroupRequestReject(BaseModel):
    """Admin payload for rejecting a group request."""

    resolution_note: Optional[str] = Field(None, max_length=2000)


class GroupRequestMerge(BaseModel):
    """Admin payload for merging a duplicate request into an active group."""

    target_group_id: UUID
    resolution_note: Optional[str] = Field(None, max_length=2000)


class GroupRequestResolutionResponse(BaseModel):
    """Response payload for approve/reject/merge admin actions."""

    request: GroupRequest
    group: Optional[Group] = None
    requester_joined: bool = False


class GroupBanRequest(BaseModel):
    """Admin payload for banning a user from a group."""

    ban_reason: Optional[str] = Field(None, max_length=1000)


class GroupBanListResponse(BaseModel):
    """Response for listing currently banned users in a group."""

    items: list[GroupMember]
    total: int
