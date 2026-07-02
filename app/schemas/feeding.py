from __future__ import annotations
"""Pydantic schemas for feeding entries."""
from datetime import datetime
from uuid import UUID
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field
from app.schemas.user import UserSummary


NORMALIZED_FEEDING_MEDIA_ROLES = {
    "meal_before": "meal_before",
    "before_meal_photo": "meal_before",
    "meal_after": "meal_after",
    "after_meal_photo": "meal_after",
    "package_front": "package_front",
    "package_front_photo": "package_front",
    "package_back": "package_back",
    "package_back_photo": "package_back",
}


class FeedingMediaBase(BaseModel):
    """Shared feeding media fields."""

    media_role: Literal[
        "meal_before",
        "meal_after",
        "package_front",
        "package_back",
        "before_meal_photo",
        "after_meal_photo",
        "package_front_photo",
        "package_back_photo",
    ]
    media_url: str = Field(..., min_length=1, max_length=2000)


class FeedingMediaCreate(FeedingMediaBase):
    """Schema for creating feeding media."""

    @property
    def normalized_media_role(self) -> str:
        return NORMALIZED_FEEDING_MEDIA_ROLES[self.media_role]


class FeedingMedia(FeedingMediaBase):
    """Schema for returning feeding media."""

    id: UUID
    feeding_id: UUID
    baby_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FeedingNutritionEstimateBase(BaseModel):
    """Structured nutrient estimate for a feeding."""

    source: Optional[str] = Field(None, max_length=30)
    calories: Optional[float] = Field(None, ge=0)
    protein_g: Optional[float] = Field(None, ge=0)
    fat_g: Optional[float] = Field(None, ge=0)
    carbs_g: Optional[float] = Field(None, ge=0)
    fiber_g: Optional[float] = Field(None, ge=0)
    sugar_g: Optional[float] = Field(None, ge=0)
    added_sugar_g: Optional[float] = Field(None, ge=0)
    sodium_mg: Optional[float] = Field(None, ge=0)
    iron_mg: Optional[float] = Field(None, ge=0)
    calcium_mg: Optional[float] = Field(None, ge=0)
    raw_payload: Optional[dict[str, Any]] = None


class FeedingNutritionEstimateCreate(FeedingNutritionEstimateBase):
    """Schema for creating a feeding nutrition estimate."""


class FeedingNutritionEstimate(FeedingNutritionEstimateBase):
    """Schema for returning feeding nutrition estimates."""

    id: UUID
    feeding_id: UUID
    baby_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FeedingBase(BaseModel):
    """Base feeding schema."""
    feeding_type: str = Field(..., min_length=1, max_length=50, description="Feeding type: bottle, breast_left, breast_right, both")
    amount_ml: Optional[int] = Field(None, ge=0, le=500, description="Amount in milliliters")
    duration_min: Optional[int] = Field(None, ge=0, le=180, description="Duration in minutes")
    timestamp: datetime = Field(..., description="Timestamp of feeding in UTC")
    notes: Optional[str] = Field(None, max_length=500, description="Optional notes")
    feeding_category: Optional[str] = Field(None, min_length=1, max_length=50)
    feeding_subtype: Optional[str] = Field(None, min_length=1, max_length=50)
    food_name: Optional[str] = Field(None, min_length=1, max_length=255)
    brand_name: Optional[str] = Field(None, min_length=1, max_length=255)
    amount_value: Optional[float] = Field(None, ge=0)
    amount_unit: Optional[str] = Field(None, min_length=1, max_length=30)
    serving_count_offered: Optional[float] = Field(None, ge=0)
    serving_count_consumed: Optional[float] = Field(None, ge=0)
    consumed_fraction: Optional[float] = Field(None, ge=0, le=1)
    analysis_status: Optional[str] = Field(None, min_length=1, max_length=30)
    analysis_confidence: Optional[float] = Field(None, ge=0, le=1)
    nutrition_source: Optional[str] = Field(None, min_length=1, max_length=30)


class FeedingCreate(FeedingBase):
    """Schema for creating a feeding entry."""
    media: Optional[list[FeedingMediaCreate]] = None
    nutrition_estimate: Optional[FeedingNutritionEstimateCreate] = None


class FeedingUpdate(BaseModel):
    """Schema for updating a feeding entry."""
    feeding_type: Optional[str] = Field(None, min_length=1, max_length=50)
    amount_ml: Optional[int] = Field(None, ge=0, le=500)
    duration_min: Optional[int] = Field(None, ge=0, le=180)
    timestamp: Optional[datetime] = None
    notes: Optional[str] = Field(None, max_length=500)
    feeding_category: Optional[str] = Field(None, min_length=1, max_length=50)
    feeding_subtype: Optional[str] = Field(None, min_length=1, max_length=50)
    food_name: Optional[str] = Field(None, min_length=1, max_length=255)
    brand_name: Optional[str] = Field(None, min_length=1, max_length=255)
    amount_value: Optional[float] = Field(None, ge=0)
    amount_unit: Optional[str] = Field(None, min_length=1, max_length=30)
    serving_count_offered: Optional[float] = Field(None, ge=0)
    serving_count_consumed: Optional[float] = Field(None, ge=0)
    consumed_fraction: Optional[float] = Field(None, ge=0, le=1)
    analysis_status: Optional[str] = Field(None, min_length=1, max_length=30)
    analysis_confidence: Optional[float] = Field(None, ge=0, le=1)
    nutrition_source: Optional[str] = Field(None, min_length=1, max_length=30)


class Feeding(FeedingBase):
    """Feeding schema for responses."""
    id: UUID
    baby_id: UUID
    created_by_user_id: Optional[UUID] = None
    updated_by_user_id: Optional[UUID] = None
    created_by: Optional[UserSummary] = None
    updated_by: Optional[UserSummary] = None
    created_at: datetime
    updated_at: datetime
    media: list[FeedingMedia] = Field(default_factory=list)
    nutrition_estimate: Optional[FeedingNutritionEstimate] = None

    class Config:
        from_attributes = True


class FeedingListResponse(BaseModel):
    """Paginated feeding list response."""
    items: list[Feeding]
    total: int
    limit: int
    offset: int


class FeedingOption(BaseModel):
    """One age-appropriate feeding option."""

    category: str
    subtype: str
    label: str


class FeedingOptionsResponse(BaseModel):
    """Response for available feeding options for a baby's age."""

    baby_id: UUID
    age_months: int
    age_band: str
    options: list[FeedingOption]


class ManualNutritionInput(FeedingNutritionEstimateBase):
    """Manual nutrition facts provided by the user."""

    serving_size_description: Optional[str] = Field(None, max_length=100)
    servings_offered: Optional[float] = Field(None, ge=0)
    servings_consumed: Optional[float] = Field(None, ge=0)


class FeedingAnalysisRequest(BaseModel):
    """Input for AI-assisted meal analysis."""

    feeding: FeedingCreate
    nutrition_label_text: Optional[str] = Field(None, max_length=4000)
    ingredients_text: Optional[str] = Field(None, max_length=4000)
    manual_nutrition: Optional[ManualNutritionInput] = None
    voice_transcript: Optional[str] = Field(None, max_length=4000)
    autosave: Optional[bool] = None


class FeedingAnalysisDraft(BaseModel):
    """Draft feeding and estimate returned for review."""

    feeding: FeedingCreate
    nutrition_estimate: Optional[FeedingNutritionEstimateCreate] = None
    confidence: float = Field(..., ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)


class SuggestedFeedingPayload(FeedingCreate):
    """Response-safe suggested feeding payload with no DB metadata."""


class FeedingAnalysisResponse(BaseModel):
    """Response for a feeding analysis request."""

    status: Literal["created", "needs_confirmation", "rejected"]
    message: str
    confidence: float = Field(..., ge=0, le=1)
    feeding: Optional[Feeding] = None
    draft: Optional[FeedingAnalysisDraft] = None
    warnings: list[str] = Field(default_factory=list)
    suggested_feeding: Optional[SuggestedFeedingPayload] = None


class FeedingConfirmRequest(BaseModel):
    """Confirm and save a previously drafted feeding analysis."""

    feeding: FeedingCreate
    nutrition_estimate: Optional[FeedingNutritionEstimateCreate] = None
