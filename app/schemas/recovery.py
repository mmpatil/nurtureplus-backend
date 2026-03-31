"""Pydantic schemas for recovery entries."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# Enum constraints
MOOD_OPTIONS = {"great", "good", "okay", "struggling", "overwhelmed"}
ENERGY_LEVEL_OPTIONS = {"veryLow", "low", "moderate", "high", "veryHigh"}
SYMPTOM_OPTIONS = {
    "soreness",
    "bleeding",
    "cramping",
    "breastPain",
    "headache",
    "nausea",
    "anxiety",
    "sadness",
    "insomnia",
    "hotFlashes",
}


class RecoveryEntryBase(BaseModel):
    """Base schema for recovery entry fields."""

    timestamp: datetime = Field(..., description="When the check-in occurred (UTC)")
    mood: str = Field(..., description="great, good, okay, struggling, overwhelmed")
    energy_level: str = Field(..., description="veryLow, low, moderate, high, veryHigh")
    water_intake_oz: int = Field(..., ge=0, le=128, description="Water intake in ounces (0-128)")
    symptoms: List[str] = Field(default_factory=list, description="Array of symptom strings")
    notes: Optional[str] = Field(None, description="Optional user notes")

    @field_validator("mood")
    @classmethod
    def validate_mood(cls, v: str) -> str:
        if v not in MOOD_OPTIONS:
            raise ValueError(f"mood must be one of {MOOD_OPTIONS}, got {v}")
        return v

    @field_validator("energy_level")
    @classmethod
    def validate_energy_level(cls, v: str) -> str:
        if v not in ENERGY_LEVEL_OPTIONS:
            raise ValueError(f"energy_level must be one of {ENERGY_LEVEL_OPTIONS}, got {v}")
        return v

    @field_validator("symptoms")
    @classmethod
    def validate_symptoms(cls, v: List[str]) -> List[str]:
        invalid_symptoms = set(v) - SYMPTOM_OPTIONS
        if invalid_symptoms:
            raise ValueError(f"Invalid symptoms: {invalid_symptoms}. Allowed: {SYMPTOM_OPTIONS}")
        return v


class RecoveryEntryCreate(RecoveryEntryBase):
    """Schema for creating a recovery entry."""

    pass


class RecoveryEntryUpdate(BaseModel):
    """Schema for updating a recovery entry (all fields optional)."""

    timestamp: Optional[datetime] = None
    mood: Optional[str] = None
    energy_level: Optional[str] = None
    water_intake_oz: Optional[int] = Field(None, ge=0, le=128)
    symptoms: Optional[List[str]] = None
    notes: Optional[str] = None

    @field_validator("mood")
    @classmethod
    def validate_mood(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in MOOD_OPTIONS:
            raise ValueError(f"mood must be one of {MOOD_OPTIONS}, got {v}")
        return v

    @field_validator("energy_level")
    @classmethod
    def validate_energy_level(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ENERGY_LEVEL_OPTIONS:
            raise ValueError(f"energy_level must be one of {ENERGY_LEVEL_OPTIONS}, got {v}")
        return v

    @field_validator("symptoms")
    @classmethod
    def validate_symptoms(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is not None:
            invalid_symptoms = set(v) - SYMPTOM_OPTIONS
            if invalid_symptoms:
                raise ValueError(f"Invalid symptoms: {invalid_symptoms}. Allowed: {SYMPTOM_OPTIONS}")
        return v


class RecoveryEntryResponse(RecoveryEntryBase):
    """Schema for recovery entry response."""

    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RecoveryEntryListResponse(BaseModel):
    """Schema for paginated recovery entry list response."""

    items: List[RecoveryEntryResponse]
    total: int
    limit: int
    offset: int

    model_config = {"from_attributes": True}


class RecoverySummaryResponse(BaseModel):
    """Schema for recovery summary over a time window."""

    days: int
    average_water_intake_oz: float
    check_in_count: int
    latest_entry: Optional[RecoveryEntryResponse] = None

    model_config = {"from_attributes": True}
