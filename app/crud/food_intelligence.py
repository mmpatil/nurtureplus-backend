from __future__ import annotations
"""Food analysis, baby food profiles, and product suitability helpers."""

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.crud import feeding_entries
from app.models.babies import Baby
from app.models.baby_access import BabyAccess
from app.models.baby_food_profile import BabyFoodProfile
from app.models.feeding_entry import FeedingEntry
from app.models.product_analysis import ProductAnalysis
from app.models.product_suitability_assessment import ProductSuitabilityAssessment
from app.schemas.feeding import (
    Feeding,
    FeedingAnalysisDraft,
    FeedingAnalysisRequest,
    FeedingAnalysisResponse,
    FeedingConfirmRequest,
    FeedingCreate,
    FeedingMediaCreate,
    FeedingNutritionEstimateCreate,
    SuggestedFeedingPayload,
)
from app.schemas.food_profile import BabyFoodProfileResponse, BabyFoodProfileUpdate
from app.schemas.product_analysis import (
    ProductAnalysisSource,
    ProductConcern,
    ProductAnalysisRequest,
    ProductAnalysisResponse,
    ProductSuitabilityRow,
)

logger = logging.getLogger(__name__)


DEFAULT_FOOD_NUTRITION: dict[str, dict[str, float]] = {
    "apple": {"calories": 52, "carbs_g": 14, "fiber_g": 2.4, "sugar_g": 10},
    "banana": {"calories": 89, "carbs_g": 23, "fiber_g": 2.6, "sugar_g": 12},
    "avocado": {"calories": 160, "fat_g": 15, "fiber_g": 7, "carbs_g": 9},
    "oatmeal": {"calories": 68, "carbs_g": 12, "fiber_g": 1.7, "protein_g": 2.4},
    "yogurt": {"calories": 61, "protein_g": 3.5, "fat_g": 3.3, "carbs_g": 4.7, "calcium_mg": 121},
    "puree": {"calories": 70, "carbs_g": 12, "fiber_g": 2, "protein_g": 1.5},
}

WARNING_INGREDIENTS = {
    "honey": ("Honey", "high", "Honey is not recommended before 12 months."),
    "alcohol": ("Alcohol", "high", "Alcohol is not appropriate for children."),
    "caffeine": ("Caffeine", "high", "Caffeine is not appropriate for babies and children."),
    "coffee": ("Coffee", "high", "Coffee is not appropriate for babies and children."),
    "energy drink": ("Energy Drink", "high", "Energy drinks are not appropriate for children."),
    "popcorn": ("Popcorn", "high", "Popcorn can be a choking hazard for young children."),
    "whole nuts": ("Whole Nuts", "high", "Whole nuts can be a choking hazard for young children."),
    "hard candy": ("Hard Candy", "high", "Hard candy can be a choking hazard for young children."),
    "whole grape": ("Whole Grapes", "high", "Whole grapes can be a choking hazard for young children."),
}

RETAILER_DOMAINS = {
    "amazon.com",
    "walmart.com",
    "target.com",
    "instacart.com",
    "wholefoodsmarket.com",
    "kroger.com",
    "costco.com",
}

PRODUCT_CATEGORY_KEYWORDS = {
    "dessert": ["dessert", "cookie", "cake", "candy", "ice cream", "pudding"],
    "drink": ["juice", "drink", "beverage", "smoothie", "tea"],
    "snack": ["snack", "puffs", "bites", "bar", "bars", "cracker", "crackers"],
    "puree": ["puree", "mash", "blend"],
    "meal": ["meal", "oatmeal", "dinner", "lunch", "breakfast"],
    "yogurt": ["yogurt", "yoghurt"],
}

WEBSITE_LOOKUP_USER_AGENT = "NurturePlusBot/1.0"


@dataclass
class FeedingAnalysisOutcome:
    """Internal result for a feeding analysis."""

    feeding: FeedingCreate
    nutrition_estimate: FeedingNutritionEstimateCreate | None
    confidence: float
    warnings: list[str]


@dataclass
class ProductWebsiteLookupResult:
    """Best-effort structured data extracted from web product pages."""

    parsed_facts: dict[str, Any]
    lookup_status: str
    category_guess: str | None
    analysis_sources: list[ProductAnalysisSource]


def _lower_text(*values: str | None) -> str:
    return " ".join(value.lower() for value in values if value)


def _extract_float(text: str, pattern: str) -> float | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None
    try:
        return float(match.group(1))
    except (TypeError, ValueError):
        return None


def _parse_nutrition_text(text: str | None) -> dict[str, float]:
    if not text:
        return {}
    return {
        key: value
        for key, value in {
            "calories": _extract_float(text, r"calories?\s*[:\-]?\s*(\d+(?:\.\d+)?)"),
            "protein_g": _extract_float(text, r"protein\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*g"),
            "fat_g": _extract_float(text, r"(?:total\s+)?fat\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*g"),
            "carbs_g": _extract_float(text, r"(?:total\s+)?carb(?:ohydrates?)?\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*g"),
            "fiber_g": _extract_float(text, r"fiber\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*g"),
            "sugar_g": _extract_float(text, r"(?:total\s+)?sugar\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*g"),
            "added_sugar_g": _extract_float(text, r"added\s+sugars?\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*g"),
            "sodium_mg": _extract_float(text, r"sodium\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*mg"),
            "iron_mg": _extract_float(text, r"iron\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*mg"),
            "calcium_mg": _extract_float(text, r"calcium\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*mg"),
        }.items()
        if value is not None
    }


def _scale_nutrition(values: dict[str, float], multiplier: float) -> dict[str, float]:
    return {key: round(value * multiplier, 2) for key, value in values.items()}


def _nutrition_from_food_name(food_name: str | None) -> dict[str, float]:
    lowered_name = (food_name or "").lower()
    for keyword, values in DEFAULT_FOOD_NUTRITION.items():
        if keyword in lowered_name:
            return values.copy()
    return {"calories": 80.0}


def _estimate_consumed_fraction(feeding: FeedingCreate, media: list[FeedingMediaCreate]) -> float | None:
    if feeding.consumed_fraction is not None:
        return feeding.consumed_fraction
    if feeding.serving_count_offered and feeding.serving_count_consumed is not None and feeding.serving_count_offered > 0:
        return min(max(feeding.serving_count_consumed / feeding.serving_count_offered, 0.0), 1.0)
    roles = {item.normalized_media_role for item in media}
    if "meal_before" in roles and "meal_after" in roles:
        return 0.5
    if "meal_before" in roles:
        return 0.75
    return None


def _normalize_media_roles(feeding: FeedingCreate) -> FeedingCreate:
    normalized = feeding.model_copy(deep=True)
    if normalized.media:
        normalized.media = [
            FeedingMediaCreate(
                media_role=item.normalized_media_role,
                media_url=item.media_url,
            )
            for item in normalized.media
        ]
    return normalized


def _title_case_words(value: str) -> str:
    return " ".join(word.capitalize() for word in value.split())


def validate_feeding_media_urls(
    media_items: list[FeedingMediaCreate] | None,
    firebase_uid: str,
) -> None:
    """Validate supported feeding media URLs for the authenticated user."""
    if not media_items:
        return

    expected_prefix = f"users/{firebase_uid}/feedings/"
    for item in media_items:
        media_url = item.media_url.strip()
        parsed = urlparse(media_url)

        if parsed.scheme in {"http", "https"}:
            continue
        if parsed.scheme != "gs":
            raise ValueError("Meal photo URL must use https:// or gs://.")

        bucket = parsed.netloc.strip()
        object_path = parsed.path.lstrip("/")
        if not bucket or not object_path:
            raise ValueError("Meal photo gs:// URL is malformed.")
        if not object_path.startswith(expected_prefix):
            raise ValueError(
                f"Meal photo must be uploaded under users/{firebase_uid}/feedings/..."
            )


def _parse_voice_transcript_fields(transcript: str | None) -> dict[str, Any]:
    if not transcript:
        return {}
    normalized = transcript.strip().lower()
    if not normalized:
        return {}

    inferred: dict[str, Any] = {}

    amount_match = re.search(r"(\d+(?:\.\d+)?)\s*(oz|ounce|ounces|ml|milliliters?)\b", normalized)
    if amount_match:
        amount_value = float(amount_match.group(1))
        amount_unit = amount_match.group(2)
        if amount_unit.startswith("ounce") or amount_unit == "oz":
            amount_unit = "oz"
        elif amount_unit.startswith("milliliter") or amount_unit == "ml":
            amount_unit = "ml"
        inferred["amount_value"] = amount_value
        inferred["amount_unit"] = amount_unit

    if "ate most" in normalized or "mostly ate" in normalized:
        inferred["consumed_fraction"] = 0.75
        inferred["serving_count_consumed"] = 0.75
    elif "ate half" in normalized or "half of it" in normalized:
        inferred["consumed_fraction"] = 0.5
        inferred["serving_count_consumed"] = 0.5
    elif "ate all" in normalized or "finished it" in normalized:
        inferred["consumed_fraction"] = 1.0
        inferred["serving_count_consumed"] = 1.0

    food_phrases = [
        "banana puree",
        "apple puree",
        "oatmeal",
        "yogurt",
        "avocado",
        "banana mash",
    ]
    for phrase in food_phrases:
        if phrase in normalized:
            inferred["food_name"] = _title_case_words(phrase)
            break

    inferred["notes"] = transcript.strip()
    return inferred


def _apply_inference_precedence(
    feeding: FeedingCreate,
    transcript_values: dict[str, Any],
) -> None:
    field_names = (
        "food_name",
        "amount_value",
        "amount_unit",
        "consumed_fraction",
        "serving_count_consumed",
        "notes",
    )
    for field_name in field_names:
        current_value = getattr(feeding, field_name)
        if current_value is None and field_name in transcript_values:
            setattr(feeding, field_name, transcript_values[field_name])


def _finalize_suggested_feeding(
    feeding: FeedingCreate,
    nutrition_estimate: FeedingNutritionEstimateCreate | None,
) -> SuggestedFeedingPayload:
    return SuggestedFeedingPayload(
        **feeding.model_dump(exclude={"nutrition_estimate"}),
        nutrition_estimate=nutrition_estimate,
    )


def _build_feeding_outcome(body: FeedingAnalysisRequest) -> FeedingAnalysisOutcome:
    feeding = _normalize_media_roles(body.feeding)
    media = feeding.media or []
    warnings: list[str] = []
    nutrition_source = "photo_estimate"
    confidence = 0.7
    transcript_values = _parse_voice_transcript_fields(body.voice_transcript)

    _apply_inference_precedence(feeding, transcript_values)
    if body.voice_transcript and not transcript_values:
        warnings.append("Voice transcript was too vague to confidently infer structured meal details.")

    consumed_fraction = _estimate_consumed_fraction(feeding, media)
    serving_count_offered = feeding.serving_count_offered
    serving_count_consumed = feeding.serving_count_consumed

    if body.manual_nutrition is not None:
        nutrition_values = {
            key: value
            for key, value in body.manual_nutrition.model_dump(
                exclude={
                    "serving_size_description",
                    "servings_offered",
                    "servings_consumed",
                    "raw_payload",
                    "source",
                },
                exclude_none=True,
            ).items()
        }
        servings_offered = body.manual_nutrition.servings_offered or serving_count_offered or 1.0
        servings_consumed = body.manual_nutrition.servings_consumed
        if servings_consumed is None:
            servings_consumed = servings_offered * consumed_fraction
        multiplier = servings_consumed
        nutrition_values = _scale_nutrition(nutrition_values, multiplier)
        nutrition_source = "manual"
        confidence = 0.96
        serving_count_offered = servings_offered
        serving_count_consumed = servings_consumed
    else:
        parsed = _parse_nutrition_text(body.nutrition_label_text)
        if parsed:
            multiplier = serving_count_consumed
            if multiplier is None:
                multiplier = consumed_fraction or 1.0
            nutrition_values = _scale_nutrition(parsed, float(multiplier))
            nutrition_source = "label_text"
            confidence = 0.9
        else:
            inferred_nutrition = _nutrition_from_food_name(feeding.food_name) if feeding.food_name else {}
            nutrition_values = (
                _scale_nutrition(inferred_nutrition, consumed_fraction or 1.0)
                if inferred_nutrition
                else {}
            )
            if media:
                warnings.append("Nutrition was estimated from meal context and may need review.")
            if body.voice_transcript and feeding.food_name:
                confidence = max(confidence, 0.82)

    if feeding.amount_value is None and feeding.amount_ml is not None:
        feeding.amount_value = float(feeding.amount_ml)
        feeding.amount_unit = feeding.amount_unit or "ml"

    feeding.serving_count_offered = serving_count_offered
    feeding.serving_count_consumed = serving_count_consumed
    feeding.consumed_fraction = consumed_fraction
    feeding.analysis_status = "needs_confirmation" if not _should_autosave(confidence, body.autosave) else "estimated"
    feeding.analysis_confidence = confidence
    if nutrition_source in {"manual", "label_text"}:
        feeding.nutrition_source = nutrition_source
    elif body.voice_transcript or media:
        feeding.nutrition_source = "estimated"
    else:
        feeding.nutrition_source = nutrition_source
    if feeding.feeding_category is None and feeding.food_name:
        feeding.feeding_category = "solid_feed"
        feeding.feeding_subtype = feeding.feeding_subtype or "meal"
    if feeding.feeding_type == "bottle" and feeding.feeding_subtype == "bottle_breastmilk":
        feeding.feeding_type = "bottle"
    if feeding.brand_name is None and body.voice_transcript and "homemade" in body.voice_transcript.lower():
        feeding.brand_name = "Homemade"
    if feeding.serving_count_consumed is not None and feeding.serving_count_offered is None:
        feeding.serving_count_offered = 1.0
    if feeding.serving_count_offered is None and feeding.consumed_fraction is not None:
        feeding.serving_count_offered = 1.0
        feeding.serving_count_consumed = feeding.consumed_fraction

    if body.voice_transcript and feeding.amount_value is None and feeding.food_name:
        warnings.append("Please double-check the amount.")

    estimate = None
    if nutrition_values:
        estimate = FeedingNutritionEstimateCreate(
            source=nutrition_source,
            raw_payload={
                "nutrition_label_text": body.nutrition_label_text,
                "ingredients_text": body.ingredients_text,
                "voice_transcript": body.voice_transcript,
                "warnings": warnings,
            },
            **nutrition_values,
        )
    return FeedingAnalysisOutcome(
        feeding=feeding,
        nutrition_estimate=estimate,
        confidence=confidence,
        warnings=warnings,
    )


def _should_autosave(confidence: float, explicit_preference: bool | None) -> bool:
    if explicit_preference is not None:
        return explicit_preference
    return confidence >= settings.food_ai_autosave_threshold


async def _serialize_saved_feeding(
    db: AsyncSession,
    feeding_entry: FeedingEntry,
) -> Feeding:
    from app.api.routes import _serialize_entry_with_audit

    return await _serialize_entry_with_audit(db, feeding_entry, Feeding)


async def analyze_feeding(
    db: AsyncSession,
    baby_id: UUID,
    user_id: UUID,
    body: FeedingAnalysisRequest,
) -> FeedingAnalysisResponse:
    """Analyze a food feeding and optionally auto-save it."""
    outcome = _build_feeding_outcome(body)
    has_usable_suggestion = bool(
        outcome.feeding.food_name
        or outcome.feeding.amount_value is not None
        or outcome.feeding.serving_count_consumed is not None
        or outcome.nutrition_estimate is not None
    )

    if not _should_autosave(outcome.confidence, body.autosave):
        if not has_usable_suggestion:
            return FeedingAnalysisResponse(
                status="rejected",
                message="I couldn't infer a usable feeding suggestion from the provided inputs.",
                confidence=outcome.confidence,
                warnings=outcome.warnings,
                draft=FeedingAnalysisDraft(
                    feeding=outcome.feeding,
                    nutrition_estimate=outcome.nutrition_estimate,
                    confidence=outcome.confidence,
                    warnings=outcome.warnings,
                ),
            )
        return FeedingAnalysisResponse(
            status="needs_confirmation",
            message="Prefilled what I could from the provided meal details.",
            confidence=outcome.confidence,
            warnings=outcome.warnings,
            draft=FeedingAnalysisDraft(
                feeding=outcome.feeding,
                nutrition_estimate=outcome.nutrition_estimate,
                confidence=outcome.confidence,
                warnings=outcome.warnings,
            ),
            suggested_feeding=_finalize_suggested_feeding(
                outcome.feeding,
                outcome.nutrition_estimate,
            ),
        )

    try:
        feeding_entry = await feeding_entries.create_feeding_entry(
            db,
            baby_id,
            user_id,
            outcome.feeding,
            autocommit=False,
        )
        if feeding_entry is None:
            raise ValueError("Baby not found")
        if outcome.feeding.media:
            await feeding_entries.create_feeding_media(
                db,
                feeding_entry.id,
                baby_id,
                outcome.feeding.media,
                autocommit=False,
            )
        if outcome.nutrition_estimate is not None:
            await feeding_entries.upsert_feeding_nutrition_estimate(
                db,
                feeding_entry.id,
                baby_id,
                outcome.nutrition_estimate,
                autocommit=False,
            )
        await db.commit()
        await db.refresh(feeding_entry)
    except Exception:
        await db.rollback()
        raise

    return FeedingAnalysisResponse(
        status="created",
        message="Feeding analysis saved.",
        confidence=outcome.confidence,
        warnings=outcome.warnings,
        feeding=await _serialize_saved_feeding(db, feeding_entry),
        draft=FeedingAnalysisDraft(
            feeding=outcome.feeding,
            nutrition_estimate=outcome.nutrition_estimate,
            confidence=outcome.confidence,
            warnings=outcome.warnings,
        ) if has_usable_suggestion else None,
        suggested_feeding=_finalize_suggested_feeding(
            outcome.feeding,
            outcome.nutrition_estimate,
        ) if has_usable_suggestion else None,
    )


async def confirm_feeding_analysis(
    db: AsyncSession,
    baby_id: UUID,
    user_id: UUID,
    body: FeedingConfirmRequest,
) -> Feeding:
    """Persist a reviewed feeding analysis draft."""
    try:
        feeding_entry = await feeding_entries.create_feeding_entry(
            db,
            baby_id,
            user_id,
            body.feeding,
            autocommit=False,
        )
        if feeding_entry is None:
            raise ValueError("Baby not found")
        if body.feeding.media:
            await feeding_entries.create_feeding_media(
                db,
                feeding_entry.id,
                baby_id,
                body.feeding.media,
                autocommit=False,
            )
        if body.nutrition_estimate is not None:
            await feeding_entries.upsert_feeding_nutrition_estimate(
                db,
                feeding_entry.id,
                baby_id,
                body.nutrition_estimate,
                autocommit=False,
            )
        await db.commit()
        await db.refresh(feeding_entry)
    except Exception:
        await db.rollback()
        raise

    return await _serialize_saved_feeding(db, feeding_entry)


async def get_baby_food_profile(
    db: AsyncSession,
    baby_id: UUID,
) -> BabyFoodProfileResponse:
    """Return the saved food profile for a baby, or sensible defaults."""
    result = await db.execute(select(BabyFoodProfile).where(BabyFoodProfile.baby_id == baby_id))
    profile = result.scalar_one_or_none()
    if profile is None:
        return BabyFoodProfileResponse(
            baby_id=baby_id,
            allergens=[],
            avoid_ingredients=[],
            dietary_flags=[],
            stage_override=None,
        )
    return BabyFoodProfileResponse.model_validate(profile)


async def update_baby_food_profile(
    db: AsyncSession,
    baby_id: UUID,
    body: BabyFoodProfileUpdate,
) -> BabyFoodProfileResponse:
    """Create or update a baby's food profile."""
    result = await db.execute(select(BabyFoodProfile).where(BabyFoodProfile.baby_id == baby_id))
    profile = result.scalar_one_or_none()
    if profile is None:
        profile = BabyFoodProfile(baby_id=baby_id)
        db.add(profile)

    for key, value in body.model_dump().items():
        setattr(profile, key, value)

    await db.commit()
    await db.refresh(profile)
    return BabyFoodProfileResponse.model_validate(profile)


async def _get_accessible_babies(
    db: AsyncSession,
    user_id: UUID,
    requested_baby_ids: list[UUID] | None,
) -> list[Baby]:
    query = (
        select(Baby)
        .join(BabyAccess, BabyAccess.baby_id == Baby.id)
        .where(
            BabyAccess.user_id == user_id,
            BabyAccess.status == "accepted",
        )
        .order_by(Baby.created_at.desc())
    )
    if requested_baby_ids:
        query = query.where(Baby.id.in_(requested_baby_ids))  # noqa: SIM118
    result = await db.execute(query)
    return result.scalars().all()


async def _get_profile_map(
    db: AsyncSession,
    baby_ids: list[UUID],
) -> dict[UUID, BabyFoodProfile]:
    if not baby_ids:
        return {}
    result = await db.execute(
        select(BabyFoodProfile).where(BabyFoodProfile.baby_id.in_(baby_ids))  # noqa: SIM118
    )
    profiles = result.scalars().all()
    return {profile.baby_id: profile for profile in profiles}


def _determine_life_stage(baby: Baby, stage_override: str | None = None) -> str:
    if stage_override:
        return stage_override
    age_options = feeding_entries._get_age_options_for_months(
        feeding_entries._calculate_age_months(baby.birth_date)
    )
    return age_options.age_band


def _parse_product_facts(body: ProductAnalysisRequest) -> tuple[dict[str, Any], float]:
    parsed_facts: dict[str, Any] = {}
    confidence = 0.68

    if body.manual_nutrition is not None:
        parsed_facts.update(body.manual_nutrition.model_dump(exclude_none=True))
        confidence = 0.96
    parsed_from_text = _parse_nutrition_text(body.nutrition_facts_text)
    if parsed_from_text:
        parsed_facts.update(parsed_from_text)
        confidence = max(confidence, 0.9)
    if body.ingredients_text:
        parsed_facts["ingredients"] = [
            segment.strip().lower()
            for segment in re.split(r",|;", body.ingredients_text)
            if segment.strip()
        ]
        confidence = max(confidence, 0.85)
    return parsed_facts, confidence


def _llm_input_available(body: ProductAnalysisRequest, parsed_facts: dict[str, Any]) -> bool:
    return bool(
        parsed_facts
        or body.package_front_url
        or body.package_back_url
        or body.ingredients_text
        or body.nutrition_facts_text
    )


class OpenAIFoodExtractor:
    """Optional structured extractor for package information."""

    def __init__(self, *, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    async def extract_product_facts(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            from openai import OpenAI
        except ImportError:
            return {}

        client = OpenAI(api_key=self.api_key)
        prompt = (
            "Extract structured nutrition facts and ingredients for baby food suitability analysis. "
            "Return JSON with keys: product_name, brand_name, ingredients, calories, protein_g, fat_g, "
            "carbs_g, fiber_g, sugar_g, added_sugar_g, sodium_mg, iron_mg, calcium_mg, category_guess."
        )
        user_content = json.dumps(payload)
        try:
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model=self.model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_content},
                ],
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("OpenAI food extraction failed: %s", exc)
            return {}

        content = response.choices[0].message.content if response.choices else None
        if not content:
            return {}
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {}


def _merge_parsed_facts(
    existing: dict[str, Any],
    incoming: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    merged = existing.copy()
    used_fields: list[str] = []
    for key, value in incoming.items():
        if value in (None, "", [], {}):
            continue
        if key not in merged or merged[key] in (None, "", [], {}):
            merged[key] = value
            used_fields.append(key)
    return merged, used_fields


def _make_source(
    *,
    url: str,
    domain: str,
    source_kind: str,
    used_fields: list[str],
) -> ProductAnalysisSource | None:
    if not used_fields:
        return None
    return ProductAnalysisSource(
        url=url,
        domain=domain,
        source_kind=source_kind,
        used_fields=sorted(set(used_fields)),
    )


def _build_local_sources(
    body: ProductAnalysisRequest,
    parsed_facts: dict[str, Any],
) -> list[ProductAnalysisSource]:
    sources: list[ProductAnalysisSource] = []
    if body.manual_nutrition is not None:
        source = _make_source(
            url="manual://input",
            domain="manual",
            source_kind="manual",
            used_fields=list(body.manual_nutrition.model_dump(exclude_none=True).keys()),
        )
        if source:
            sources.append(source)

    package_fields: list[str] = []
    if body.ingredients_text:
        package_fields.append("ingredients")
    for field_name in (
        "calories",
        "protein_g",
        "fat_g",
        "carbs_g",
        "fiber_g",
        "sugar_g",
        "added_sugar_g",
        "sodium_mg",
        "iron_mg",
        "calcium_mg",
    ):
        if field_name in parsed_facts:
            package_fields.append(field_name)
    if body.package_front_url:
        package_fields.append("package_front_url")
    if body.package_back_url:
        package_fields.append("package_back_url")
    source = _make_source(
        url="package_text://input",
        domain="package_text",
        source_kind="package_text",
        used_fields=package_fields,
    )
    if source:
        sources.append(source)
    return sources


def _parsed_facts_complete_enough(parsed_facts: dict[str, Any]) -> bool:
    has_ingredients = bool(parsed_facts.get("ingredients"))
    nutrition_keys = {"calories", "protein_g", "fat_g", "carbs_g", "fiber_g", "sugar_g", "added_sugar_g", "sodium_mg"}
    has_nutrition = any(parsed_facts.get(key) not in (None, "", [], {}) for key in nutrition_keys)
    return has_ingredients and has_nutrition


def _guess_product_category(text: str) -> str | None:
    lowered = text.lower()
    for category, keywords in PRODUCT_CATEGORY_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return category
    return None


def _search_brand_tokens(body: ProductAnalysisRequest) -> list[str]:
    source = body.brand_name or body.product_name or ""
    return [token for token in re.findall(r"[a-z0-9]+", source.lower()) if len(token) >= 4]


def _build_product_search_query(body: ProductAnalysisRequest) -> str:
    parts = [body.brand_name, body.product_name]
    if body.ingredients_text:
        parts.append("ingredients")
    if body.nutrition_facts_text:
        parts.append("nutrition")
    return " ".join(part.strip() for part in parts if part and part.strip())


def _classify_source_kind(url: str, body: ProductAnalysisRequest) -> str:
    domain = urlparse(url).netloc.lower().removeprefix("www.")
    if domain in RETAILER_DOMAINS:
        return "retailer"
    brand_tokens = _search_brand_tokens(body)
    if not brand_tokens:
        return "brand"
    return "brand" if any(token in domain for token in brand_tokens) else "retailer"


def _rank_product_candidates(raw_results: list[dict[str, Any]], body: ProductAnalysisRequest) -> list[dict[str, str]]:
    ranked: list[tuple[int, dict[str, str]]] = []
    brand_tokens = _search_brand_tokens(body)
    product_name = (body.product_name or "").lower()
    for item in raw_results:
        url = item.get("link")
        if not isinstance(url, str) or not url.startswith("http"):
            continue
        domain = urlparse(url).netloc.lower().removeprefix("www.")
        title = str(item.get("title") or "")
        source_kind = _classify_source_kind(url, body)
        priority = 1 if source_kind == "retailer" else 0
        priority += 0 if any(token in domain for token in brand_tokens) else 1
        priority += 0 if not product_name or product_name in title.lower() else 1
        ranked.append(
            (
                priority,
                {
                    "url": url,
                    "domain": domain,
                    "source_kind": source_kind,
                },
            )
        )
    ranked.sort(key=lambda item: item[0])
    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for _, candidate in ranked:
        if candidate["url"] in seen:
            continue
        seen.add(candidate["url"])
        deduped.append(candidate)
    return deduped[:3]


async def _search_product_candidates(body: ProductAnalysisRequest) -> list[dict[str, str]]:
    try:
        import httpx
    except ImportError:
        logger.warning("httpx is not installed; skipping website lookup")
        return []

    query = _build_product_search_query(body)
    if not query or not settings.serpapi_api_key:
        return []

    async with httpx.AsyncClient(
        timeout=2.0,
        follow_redirects=True,
        headers={"User-Agent": WEBSITE_LOOKUP_USER_AGENT},
    ) as client:
        response = await client.get(
            "https://serpapi.com/search.json",
            params={
                "engine": "google",
                "q": query,
                "api_key": settings.serpapi_api_key,
                "num": 10,
            },
        )
        response.raise_for_status()
        payload = response.json()
    organic_results = payload.get("organic_results")
    if not isinstance(organic_results, list):
        return []
    return _rank_product_candidates(organic_results, body)


def _flatten_json_ld(node: Any) -> list[dict[str, Any]]:
    if isinstance(node, list):
        flattened: list[dict[str, Any]] = []
        for item in node:
            flattened.extend(_flatten_json_ld(item))
        return flattened
    if isinstance(node, dict):
        flattened = [node]
        graph = node.get("@graph")
        if isinstance(graph, list):
            flattened.extend(_flatten_json_ld(graph))
        return flattened
    return []


def _coerce_ingredients(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip().lower() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [
            segment.strip().lower()
            for segment in re.split(r",|;", value)
            if segment.strip()
        ]
    return []


def _extract_numeric_value(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    match = re.search(r"(\d+(?:\.\d+)?)", value)
    if not match:
        return None
    return float(match.group(1))


def _parse_schema_nutrition(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    extracted = {
        "calories": _extract_numeric_value(value.get("calories")),
        "protein_g": _extract_numeric_value(value.get("proteinContent")),
        "fat_g": _extract_numeric_value(value.get("fatContent")),
        "carbs_g": _extract_numeric_value(value.get("carbohydrateContent")),
        "fiber_g": _extract_numeric_value(value.get("fiberContent")),
        "sugar_g": _extract_numeric_value(value.get("sugarContent")),
        "sodium_mg": _extract_numeric_value(value.get("sodiumContent")),
    }
    return {key: amount for key, amount in extracted.items() if amount is not None}


def _extract_visible_section(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return re.sub(r"\s+", " ", match.group(1)).strip()


def _extract_product_page_data(html: str, url: str) -> tuple[dict[str, Any], str | None]:
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.warning("beautifulsoup4 is not installed; skipping website parsing")
        return {}, None

    soup = BeautifulSoup(html, "html.parser")
    extracted: dict[str, Any] = {}
    category_guess: str | None = None

    for script in soup.find_all("script", attrs={"type": re.compile("ld\\+json", re.IGNORECASE)}):
        script_text = script.string or script.get_text()
        if not script_text:
            continue
        try:
            payload = json.loads(script_text)
        except json.JSONDecodeError:
            continue
        for node in _flatten_json_ld(payload):
            node_type = node.get("@type")
            normalized_type = " ".join(node_type) if isinstance(node_type, list) else str(node_type or "")
            if "Product" not in normalized_type:
                continue
            if isinstance(node.get("name"), str):
                extracted.setdefault("product_name", node["name"].strip())
            brand_value = node.get("brand")
            if isinstance(brand_value, dict) and isinstance(brand_value.get("name"), str):
                extracted.setdefault("brand_name", brand_value["name"].strip())
            elif isinstance(brand_value, str):
                extracted.setdefault("brand_name", brand_value.strip())
            ingredients = _coerce_ingredients(node.get("ingredients"))
            if ingredients:
                extracted.setdefault("ingredients", ingredients)
            nutrition = _parse_schema_nutrition(node.get("nutrition") or node.get("nutritionInformation"))
            if nutrition:
                extracted, _ = _merge_parsed_facts(extracted, nutrition)
            if isinstance(node.get("category"), str):
                category_guess = category_guess or _guess_product_category(node["category"])

    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    meta_description_tag = soup.find("meta", attrs={"name": "description"}) or soup.find(
        "meta", attrs={"property": "og:description"}
    )
    meta_description = meta_description_tag.get("content", "").strip() if meta_description_tag else ""
    text = soup.get_text(" ", strip=True)
    combined_text = " ".join(part for part in (title, meta_description, text[:6000]) if part)

    ingredients_section = _extract_visible_section(
        combined_text,
        r"ingredients?\s*[:\-]\s*(.+?)(?:nutrition facts|nutrition|allergen|distributed by|$)",
    )
    if ingredients_section and "ingredients" not in extracted:
        extracted["ingredients"] = _coerce_ingredients(ingredients_section)

    nutrition_section = _extract_visible_section(
        combined_text,
        r"(nutrition facts?.+?)(?:ingredients?|distributed by|$)",
    )
    nutrition_text = nutrition_section or combined_text
    nutrition = _parse_nutrition_text(nutrition_text)
    if nutrition:
        extracted, _ = _merge_parsed_facts(extracted, nutrition)

    category_guess = category_guess or _guess_product_category(combined_text) or _guess_product_category(url)
    return extracted, category_guess


async def _fetch_product_page(url: str) -> str | None:
    try:
        import httpx
    except ImportError:
        logger.warning("httpx is not installed; skipping product page fetch")
        return None

    async with httpx.AsyncClient(
        timeout=2.0,
        follow_redirects=True,
        headers={"User-Agent": WEBSITE_LOOKUP_USER_AGENT},
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text


async def _lookup_product_website_data_impl(
    body: ProductAnalysisRequest,
    parsed_facts: dict[str, Any],
) -> ProductWebsiteLookupResult:
    candidates = await _search_product_candidates(body)
    if not candidates:
        return ProductWebsiteLookupResult(
            parsed_facts={},
            lookup_status="not_found",
            category_guess=None,
            analysis_sources=[],
        )

    merged_facts: dict[str, Any] = {}
    category_guess: str | None = None
    analysis_sources: list[ProductAnalysisSource] = []
    had_candidate_data = False
    for candidate in candidates:
        try:
            html = await _fetch_product_page(candidate["url"])
        except Exception as exc:  # noqa: BLE001
            logger.warning("Product page fetch failed for %s: %s", candidate["url"], exc)
            continue
        if not html:
            continue
        extracted, fetched_category = _extract_product_page_data(html, candidate["url"])
        if not extracted and not fetched_category:
            continue
        had_candidate_data = True
        merged_facts, used_fields = _merge_parsed_facts(merged_facts, extracted)
        if fetched_category and not category_guess:
            category_guess = fetched_category
            used_fields.append("category_guess")
        source = _make_source(
            url=candidate["url"],
            domain=candidate["domain"],
            source_kind=candidate["source_kind"],
            used_fields=used_fields,
        )
        if source:
            analysis_sources.append(source)
        combined = parsed_facts.copy()
        combined, _ = _merge_parsed_facts(combined, merged_facts)
        if _parsed_facts_complete_enough(combined):
            break

    if not had_candidate_data:
        return ProductWebsiteLookupResult(
            parsed_facts={},
            lookup_status="not_found",
            category_guess=None,
            analysis_sources=[],
        )

    combined = parsed_facts.copy()
    combined, used_fields = _merge_parsed_facts(combined, merged_facts)
    lookup_status = "fetched" if _parsed_facts_complete_enough(combined) else "partial"
    return ProductWebsiteLookupResult(
        parsed_facts={field: combined[field] for field in used_fields if field in combined},
        lookup_status=lookup_status,
        category_guess=category_guess,
        analysis_sources=analysis_sources,
    )


async def _lookup_product_website_data(
    body: ProductAnalysisRequest,
    parsed_facts: dict[str, Any],
) -> ProductWebsiteLookupResult:
    if (
        not settings.website_lookup_enabled
        or not settings.serpapi_api_key
        or not body.product_name
        or _parsed_facts_complete_enough(parsed_facts)
    ):
        return ProductWebsiteLookupResult(
            parsed_facts={},
            lookup_status="not_attempted",
            category_guess=None,
            analysis_sources=[],
        )
    try:
        return await asyncio.wait_for(
            _lookup_product_website_data_impl(body, parsed_facts),
            timeout=settings.website_lookup_timeout_seconds,
        )
    except asyncio.TimeoutError:
        logger.warning("Product website lookup timed out for %s", body.product_name)
        return ProductWebsiteLookupResult(
            parsed_facts={},
            lookup_status="failed",
            category_guess=None,
            analysis_sources=[],
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Product website lookup failed: %s", exc)
        return ProductWebsiteLookupResult(
            parsed_facts={},
            lookup_status="failed",
            category_guess=None,
            analysis_sources=[],
        )


async def _maybe_enrich_product_facts(
    body: ProductAnalysisRequest,
    parsed_facts: dict[str, Any],
    category_guess: str | None,
) -> tuple[dict[str, Any], str | None, list[str]]:
    if not settings.openai_api_key or not _llm_input_available(body, parsed_facts):
        return parsed_facts, category_guess, []
    extractor = OpenAIFoodExtractor(api_key=settings.openai_api_key, model=settings.resolved_food_ai_model)
    extracted = await extractor.extract_product_facts(
        {
            "request": body.model_dump(mode="json", exclude_none=True),
            "current_facts": parsed_facts,
            "category_guess": category_guess,
        }
    )
    if not extracted:
        return parsed_facts, category_guess, []

    llm_category = extracted.pop("category_guess", None)
    enriched, used_fields = _merge_parsed_facts(parsed_facts, extracted)
    if llm_category and not category_guess:
        category_guess = _guess_product_category(str(llm_category)) or str(llm_category)
        used_fields.append("category_guess")
    return enriched, category_guess, sorted(set(used_fields))


def _contains_any(text: str, terms: list[str]) -> list[str]:
    return [term for term in terms if term and term.lower() in text]


def _make_concern(code: str, label: str, severity: str, message: str) -> ProductConcern:
    return ProductConcern(code=code, label=label, severity=severity, message=message)


def _category_is_sweet(text: str, category_guess: str | None) -> bool:
    return (category_guess in {"dessert", "drink"} or "sweet" in text or "dessert" in text or "cookie" in text or "candy" in text)


def _category_is_snack(text: str, category_guess: str | None) -> bool:
    return category_guess == "snack" or "snack" in text or "puffs" in text or "cracker" in text


def _collect_positive_signals(parsed_facts: dict[str, Any]) -> list[str]:
    signals: list[str] = []
    if float(parsed_facts.get("protein_g") or 0) >= 3:
        signals.append("contains meaningful protein")
    if float(parsed_facts.get("fiber_g") or 0) >= 2:
        signals.append("contains some fiber")
    if float(parsed_facts.get("iron_mg") or 0) >= 1:
        signals.append("contains iron")
    if float(parsed_facts.get("added_sugar_g") or 0) == 0:
        signals.append("has no added sugar detected")
    return signals


def _build_headline(
    verdict: str,
    concerns: list[ProductConcern],
    positive_signals: list[str],
) -> str:
    verdict_label = verdict.replace("_", " ")
    if concerns:
        primary = concerns[0].message.rstrip(".")
        return f"{verdict_label.capitalize()} fit because {primary[:1].lower() + primary[1:]}."
    if verdict == "excellent":
        return "Excellent fit for this age group with strong nutrition signals and no major concerns found."
    if verdict == "good":
        return "Good fit for this age group with no major ingredient concerns found."
    if verdict == "average":
        return "Average fit. No major red flags were found, but the product does not stand out as a strong match."
    return f"{verdict_label.capitalize()} fit for this age group."


def _assess_product_for_baby(
    baby: Baby,
    profile: BabyFoodProfile | None,
    parsed_facts: dict[str, Any],
    body: ProductAnalysisRequest,
    *,
    confidence: float,
    category_guess: str | None,
) -> ProductSuitabilityRow:
    stage = _determine_life_stage(baby, profile.stage_override if profile else None)
    text = _lower_text(
        body.product_name,
        body.brand_name,
        body.ingredients_text,
        body.nutrition_facts_text,
        " ".join(parsed_facts.get("ingredients", [])) if isinstance(parsed_facts.get("ingredients"), list) else None,
        category_guess,
    )
    ingredient_concerns: list[ProductConcern] = []
    category_concerns: list[ProductConcern] = []
    reasons: list[str] = []
    warning_flags: list[str] = []

    age_months = feeding_entries._calculate_age_months(baby.birth_date)

    for ingredient, (label, severity, reason) in WARNING_INGREDIENTS.items():
        if ingredient in text:
            ingredient_concerns.append(_make_concern(ingredient, label, severity, reason))
            warning_flags.append(ingredient)

    added_sugar = float(parsed_facts.get("added_sugar_g") or 0)
    sodium = float(parsed_facts.get("sodium_mg") or 0)
    if age_months < 12 and added_sugar > 0:
        ingredient_concerns.append(
            _make_concern(
                "added_sugar",
                "Added Sugar",
                "high",
                "Added sugar is not ideal for babies under 12 months.",
            )
        )
        warning_flags.append("added_sugar")
    elif added_sugar >= 8:
        ingredient_concerns.append(
            _make_concern(
                "added_sugar",
                "Added Sugar",
                "medium",
                "This product contains a meaningful amount of added sugar.",
            )
        )
        warning_flags.append("added_sugar")
    if age_months < 12 and sodium >= 140:
        ingredient_concerns.append(
            _make_concern(
                "high_sodium",
                "High Sodium",
                "high",
                "Sodium is high for a baby under 12 months.",
            )
        )
        warning_flags.append("high_sodium")
    elif sodium >= 200:
        ingredient_concerns.append(
            _make_concern(
                "high_sodium",
                "High Sodium",
                "medium",
                "This product appears fairly high in sodium for a young child.",
            )
        )
        warning_flags.append("high_sodium")
    if age_months < 6 and ("meal" in text or "snack" in text or "puree" in text or body.product_name):
        category_concerns.append(
            _make_concern(
                "solid_before_6_months",
                "Solid Foods Before 6 Months",
                "high",
                "Solid foods generally need extra caution before 6 months.",
            )
        )
        warning_flags.append("solid_before_6_months")

    allergen_hits: list[str] = []
    if profile is not None:
        allergen_hits.extend(_contains_any(text, profile.allergens or []))
        allergen_hits.extend(_contains_any(text, profile.avoid_ingredients or []))
    if allergen_hits:
        ingredient_concerns.append(
            _make_concern(
                "profile_conflict",
                "Saved Food Restriction Conflict",
                "high",
                "This product appears to conflict with the child's saved food restrictions.",
            )
        )
        warning_flags.append("profile_conflict")

    if (
        (_category_is_sweet(text, category_guess) or (category_guess == "snack" and added_sugar > 0))
        and (added_sugar > 0 or "sweet" in text or "dessert" in text or category_guess == "snack")
    ):
        category_concerns.append(
            _make_concern(
                "sweet_treat",
                "Sweet Treat",
                "high" if age_months < 12 and added_sugar > 0 else "medium",
                "This looks like a sweet snack or dessert-style product for this age group.",
            )
        )
        warning_flags.append("sweet_treat")
    if category_guess == "drink" and (added_sugar > 0 or float(parsed_facts.get("sugar_g") or 0) > 8):
        category_concerns.append(
            _make_concern(
                "sweetened_drink",
                "Sweetened Drink",
                "high" if age_months < 12 else "medium",
                "Sweetened drinks are usually not a strong fit for babies and toddlers.",
            )
        )
        warning_flags.append("sweetened_drink")
    if _category_is_snack(text, category_guess) and sodium >= 140:
        category_concerns.append(
            _make_concern(
                "salty_snack",
                "Salty Snack",
                "high" if age_months < 12 else "medium",
                "This appears to be a salty snack for a young child.",
            )
        )
        warning_flags.append("salty_snack")

    all_concerns = ingredient_concerns + category_concerns
    positive_signals = _collect_positive_signals(parsed_facts)
    high_count = sum(1 for concern in all_concerns if concern.severity == "high")
    medium_count = sum(1 for concern in all_concerns if concern.severity == "medium")
    has_complete_data = _parsed_facts_complete_enough(parsed_facts)

    if high_count:
        verdict = "very_bad"
    elif medium_count >= 2:
        verdict = "bad"
    elif medium_count == 1 or confidence < 0.8:
        verdict = "average"
    elif positive_signals and has_complete_data:
        verdict = "excellent"
    elif has_complete_data or confidence >= 0.82:
        verdict = "good"
    else:
        verdict = "average"

    if all_concerns:
        reasons = [concern.message for concern in all_concerns]
    else:
        reasons = ["No major ingredient or age-stage concerns were detected."]
        if positive_signals:
            reasons.append(f"Positive signals: {', '.join(positive_signals)}.")

    headline = _build_headline(verdict, all_concerns, positive_signals)
    return ProductSuitabilityRow(
        baby_id=baby.id,
        baby_name=baby.name,
        life_stage=stage,
        verdict=verdict,
        headline=headline,
        confidence=confidence,
        ingredient_concerns=ingredient_concerns,
        category_concerns=category_concerns,
        reasons=reasons,
        warning_flags=sorted(set(warning_flags)),
        allergen_hits=sorted(set(allergen_hits)),
    )


async def analyze_product(
    db: AsyncSession,
    user_id: UUID,
    body: ProductAnalysisRequest,
) -> ProductAnalysisResponse:
    """Analyze a product for one or more accessible babies."""
    babies = await _get_accessible_babies(db, user_id, body.baby_ids)
    if body.baby_ids and len(babies) != len(body.baby_ids):
        raise ValueError("One or more babies are not accessible for product analysis")

    parsed_facts, confidence = _parse_product_facts(body)
    analysis_sources = _build_local_sources(body, parsed_facts)
    category_guess = _guess_product_category(
        _lower_text(
            body.product_name,
            body.brand_name,
            body.ingredients_text,
            body.nutrition_facts_text,
        )
    )

    website_lookup = await _lookup_product_website_data(body, parsed_facts)
    parsed_facts, website_used_fields = _merge_parsed_facts(parsed_facts, website_lookup.parsed_facts)
    if website_lookup.category_guess and not category_guess:
        category_guess = website_lookup.category_guess
        website_used_fields.append("category_guess")
    analysis_sources.extend(website_lookup.analysis_sources)
    if website_lookup.lookup_status in {"fetched", "partial"}:
        confidence = max(confidence, 0.82 if website_lookup.lookup_status == "partial" else 0.86)

    parsed_facts, category_guess, llm_used_fields = await _maybe_enrich_product_facts(body, parsed_facts, category_guess)
    llm_source = _make_source(
        url="llm://openai",
        domain="openai",
        source_kind="llm",
        used_fields=llm_used_fields,
    )
    if llm_source:
        analysis_sources.append(llm_source)
        confidence = max(confidence, 0.88)

    analysis = ProductAnalysis(
        user_id=user_id,
        product_name=body.product_name or parsed_facts.get("product_name"),
        brand_name=body.brand_name or parsed_facts.get("brand_name"),
        package_front_url=body.package_front_url,
        package_back_url=body.package_back_url,
        ingredients_text=body.ingredients_text,
        nutrition_facts_text=body.nutrition_facts_text,
        parsed_facts=parsed_facts,
        status="completed",
        confidence=confidence,
        lookup_status=website_lookup.lookup_status,
        category_guess=category_guess,
        analysis_sources=[source.model_dump(mode="json") for source in analysis_sources],
        model_name=settings.resolved_food_ai_model if settings.openai_api_key else "heuristic",
        raw_payload=body.model_dump(mode="json", exclude_none=True),
    )
    db.add(analysis)
    await db.flush()

    profile_map = await _get_profile_map(db, [baby.id for baby in babies])
    rows: list[ProductSuitabilityRow] = []
    await db.execute(
        delete(ProductSuitabilityAssessment).where(
            ProductSuitabilityAssessment.product_analysis_id == analysis.id
        )
    )
    for baby in babies:
        row = _assess_product_for_baby(
            baby,
            profile_map.get(baby.id),
            parsed_facts,
            body,
            confidence=confidence,
            category_guess=category_guess,
        )
        rows.append(row)
        db.add(
            ProductSuitabilityAssessment(
                product_analysis_id=analysis.id,
                baby_id=baby.id,
                life_stage=row.life_stage,
                verdict=row.verdict,
                headline=row.headline,
                confidence=row.confidence,
                ingredient_concerns=[concern.model_dump(mode="json") for concern in row.ingredient_concerns],
                category_concerns=[concern.model_dump(mode="json") for concern in row.category_concerns],
                reasons=row.reasons,
                warning_flags=row.warning_flags,
                allergen_hits=row.allergen_hits,
            )
        )

    await db.commit()
    await db.refresh(analysis)

    return ProductAnalysisResponse(
        id=analysis.id,
        product_name=analysis.product_name,
        brand_name=analysis.brand_name,
        status=analysis.status,
        confidence=analysis.confidence or confidence,
        parsed_facts=analysis.parsed_facts or {},
        lookup_status=analysis.lookup_status or website_lookup.lookup_status,
        category_guess=analysis.category_guess,
        analysis_sources=[
            ProductAnalysisSource.model_validate(source)
            for source in (analysis.analysis_sources or [])
        ],
        package_front_url=analysis.package_front_url,
        package_back_url=analysis.package_back_url,
        ingredients_text=analysis.ingredients_text,
        nutrition_facts_text=analysis.nutrition_facts_text,
        suitability=rows,
        created_at=analysis.created_at,
        updated_at=analysis.updated_at,
    )
