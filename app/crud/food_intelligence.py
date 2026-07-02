from __future__ import annotations
"""Food analysis, baby food profiles, and product suitability helpers."""

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any
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
    "honey": ("bad", "Honey is not recommended before 12 months."),
    "alcohol": ("bad", "Alcohol is not appropriate for children."),
    "caffeine": ("bad", "Caffeine is not appropriate for babies and children."),
    "coffee": ("bad", "Coffee is not appropriate for babies and children."),
    "energy drink": ("bad", "Energy drinks are not appropriate for children."),
    "popcorn": ("bad", "Popcorn can be a choking hazard for young children."),
    "whole nuts": ("bad", "Whole nuts can be a choking hazard for young children."),
    "hard candy": ("bad", "Hard candy can be a choking hazard for young children."),
    "whole grape": ("bad", "Whole grapes can be a choking hazard for young children."),
}


@dataclass
class FeedingAnalysisOutcome:
    """Internal result for a feeding analysis."""

    feeding: FeedingCreate
    nutrition_estimate: FeedingNutritionEstimateCreate | None
    confidence: float
    warnings: list[str]


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


def _llm_input_available(body: ProductAnalysisRequest) -> bool:
    return bool(body.package_front_url or body.package_back_url or body.ingredients_text or body.nutrition_facts_text)


class OpenAIFoodExtractor:
    """Optional structured extractor for package information."""

    def __init__(self, *, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    async def extract_product_facts(self, body: ProductAnalysisRequest) -> dict[str, Any]:
        try:
            from openai import OpenAI
        except ImportError:
            return {}

        client = OpenAI(api_key=self.api_key)
        prompt = (
            "Extract structured nutrition facts and ingredients for baby food suitability analysis. "
            "Return JSON with keys: product_name, brand_name, ingredients, calories, protein_g, fat_g, "
            "carbs_g, fiber_g, sugar_g, added_sugar_g, sodium_mg, iron_mg, calcium_mg."
        )
        user_content = json.dumps(body.model_dump(mode="json", exclude_none=True))
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


async def _maybe_enrich_product_facts(body: ProductAnalysisRequest, parsed_facts: dict[str, Any]) -> dict[str, Any]:
    if not settings.openai_api_key or not _llm_input_available(body):
        return parsed_facts
    extractor = OpenAIFoodExtractor(api_key=settings.openai_api_key, model=settings.food_ai_model)
    extracted = await extractor.extract_product_facts(body)
    if not extracted:
        return parsed_facts
    enriched = parsed_facts.copy()
    for key, value in extracted.items():
        enriched.setdefault(key, value)
    return enriched


def _contains_any(text: str, terms: list[str]) -> list[str]:
    return [term for term in terms if term and term.lower() in text]


def _assess_product_for_baby(
    baby: Baby,
    profile: BabyFoodProfile | None,
    parsed_facts: dict[str, Any],
    body: ProductAnalysisRequest,
) -> ProductSuitabilityRow:
    stage = _determine_life_stage(baby, profile.stage_override if profile else None)
    text = _lower_text(
        body.product_name,
        body.brand_name,
        body.ingredients_text,
        body.nutrition_facts_text,
        " ".join(parsed_facts.get("ingredients", [])) if isinstance(parsed_facts.get("ingredients"), list) else None,
    )
    warning_flags: list[str] = []
    reasons: list[str] = []
    verdict_score = 2

    age_months = feeding_entries._calculate_age_months(baby.birth_date)

    for ingredient, (severity, reason) in WARNING_INGREDIENTS.items():
        if ingredient in text:
            warning_flags.append(ingredient)
            reasons.append(reason)
            if severity == "bad":
                verdict_score = min(verdict_score, 0)

    added_sugar = float(parsed_facts.get("added_sugar_g") or 0)
    sodium = float(parsed_facts.get("sodium_mg") or 0)
    if age_months < 12 and added_sugar > 0:
        warning_flags.append("added_sugar")
        reasons.append("Added sugar is not ideal for babies under 12 months.")
        verdict_score = min(verdict_score, 1)
    if age_months < 12 and sodium >= 140:
        warning_flags.append("high_sodium")
        reasons.append("Sodium is high for a baby under 12 months.")
        verdict_score = min(verdict_score, 0)
    if age_months < 6 and ("meal" in text or "snack" in text or "puree" in text or body.product_name):
        warning_flags.append("solid_before_6_months")
        reasons.append("Solid foods generally need extra caution before 6 months.")
        verdict_score = min(verdict_score, 0)

    allergen_hits: list[str] = []
    if profile is not None:
        allergen_hits.extend(_contains_any(text, profile.allergens or []))
        allergen_hits.extend(_contains_any(text, profile.avoid_ingredients or []))
    if allergen_hits:
        reasons.append("This product appears to conflict with the child's saved food restrictions.")
        verdict_score = min(verdict_score, 0)

    verdict = {2: "good", 1: "okay", 0: "bad"}[verdict_score]
    if not reasons:
        reasons.append("No obvious age-stage or saved-profile concerns were detected.")

    confidence = 0.96 if body.manual_nutrition else 0.9 if body.nutrition_facts_text or body.ingredients_text else 0.74
    return ProductSuitabilityRow(
        baby_id=baby.id,
        baby_name=baby.name,
        life_stage=stage,
        verdict=verdict,
        confidence=confidence,
        reasons=reasons,
        warning_flags=warning_flags,
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
    parsed_facts = await _maybe_enrich_product_facts(body, parsed_facts)

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
        model_name=settings.food_ai_model if settings.openai_api_key else "heuristic",
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
        row = _assess_product_for_baby(baby, profile_map.get(baby.id), parsed_facts, body)
        rows.append(row)
        db.add(
            ProductSuitabilityAssessment(
                product_analysis_id=analysis.id,
                baby_id=baby.id,
                life_stage=row.life_stage,
                verdict=row.verdict,
                confidence=row.confidence,
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
        package_front_url=analysis.package_front_url,
        package_back_url=analysis.package_back_url,
        ingredients_text=analysis.ingredients_text,
        nutrition_facts_text=analysis.nutrition_facts_text,
        suitability=rows,
        created_at=analysis.created_at,
        updated_at=analysis.updated_at,
    )
