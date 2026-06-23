from __future__ import annotations
"""Schemas for voice-driven log creation."""

from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, field_validator


class VoiceLogType(str, Enum):
    feeding = "feeding"
    diaper = "diaper"
    sleep = "sleep"
    mood = "mood"
    recovery = "recovery"
    growth = "growth"
    milestone = "milestone"


class VoiceLogRequest(BaseModel):
    transcript: str = Field(..., min_length=1, max_length=4000)
    baby_id: Optional[UUID] = None
    timezone: str = Field(..., min_length=1, max_length=100)
    client_now: datetime

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("timezone must be a valid IANA timezone") from exc
        return value

    @field_validator("client_now")
    @classmethod
    def validate_client_now(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("client_now must include timezone information")
        return value


class VoiceLogDraftAction(BaseModel):
    log_type: VoiceLogType
    confidence: float = Field(..., ge=0, le=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class VoiceLogCreatedAction(BaseModel):
    log_type: VoiceLogType
    confidence: float = Field(..., ge=0, le=1)
    resource: dict[str, Any]


class VoiceLogResponse(BaseModel):
    status: Literal["created", "needs_confirmation", "rejected"]
    created_actions: list[VoiceLogCreatedAction] = Field(default_factory=list)
    draft_actions: list[VoiceLogDraftAction] = Field(default_factory=list)
    message: str
