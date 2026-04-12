"""Pydantic schemas for growth entries."""
from datetime import date, datetime
from uuid import UUID
from pydantic import BaseModel, Field, model_validator


class GrowthBase(BaseModel):
    """Base growth schema."""
    measurement_date: date = Field(..., description="Date of measurement")
    weight_kg: float | None = Field(None, gt=0, le=30, description="Weight in kilograms")
    height_cm: float | None = Field(None, gt=0, le=150, description="Height in centimeters")
    head_circumference_cm: float | None = Field(None, gt=0, le=80, description="Head circumference in centimeters")
    notes: str | None = Field(None, max_length=500, description="Optional notes")

    @model_validator(mode="after")
    def at_least_one_measurement(self) -> "GrowthBase":
        if self.weight_kg is None and self.height_cm is None and self.head_circumference_cm is None:
            raise ValueError("At least one of weight_kg, height_cm, or head_circumference_cm must be provided")
        return self


class GrowthCreate(GrowthBase):
    """Schema for creating a growth entry."""
    pass


class GrowthUpdate(BaseModel):
    """Schema for updating a growth entry."""
    measurement_date: date | None = None
    weight_kg: float | None = Field(None, gt=0, le=30)
    height_cm: float | None = Field(None, gt=0, le=150)
    head_circumference_cm: float | None = Field(None, gt=0, le=80)
    notes: str | None = Field(None, max_length=500)


class Growth(GrowthBase):
    """Growth schema for responses."""
    id: UUID
    baby_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class GrowthListResponse(BaseModel):
    """Paginated growth list response."""
    items: list[Growth]
    total: int
    limit: int
    offset: int
