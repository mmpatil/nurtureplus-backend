from __future__ import annotations
"""CRUD operations for feeding entries — membership-aware."""

import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud._baby_access_check import verify_baby_access
from app.models.babies import Baby
from app.models.baby_access import BabyAccess
from app.models.feeding_entry import FeedingEntry
from app.models.feeding_media import FeedingMedia
from app.models.feeding_nutrition_estimate import FeedingNutritionEstimate
from app.schemas.feeding import (
    FeedingCreate,
    FeedingMediaCreate,
    FeedingNutritionEstimateCreate,
    FeedingUpdate,
)

logger = logging.getLogger(__name__)


LEGACY_TYPE_TO_STRUCTURE: dict[str, tuple[str, str]] = {
    "bottle": ("milk_feed", "bottle_formula"),
    "breast_left": ("milk_feed", "breast_left"),
    "breast_right": ("milk_feed", "breast_right"),
    "both": ("milk_feed", "breast_both"),
}

STRUCTURE_TO_LEGACY_TYPE: dict[tuple[str | None, str | None], str] = {
    ("milk_feed", "bottle_formula"): "bottle",
    ("milk_feed", "bottle_breastmilk"): "bottle",
    ("milk_feed", "breast_left"): "breast_left",
    ("milk_feed", "breast_right"): "breast_right",
    ("milk_feed", "breast_both"): "both",
}

AGE_BAND_OPTIONS: list[tuple[str, int | None, str, list[tuple[str, str, str]]]] = [
    (
        "0-5 months",
        5,
        "infant_milk_only",
        [
            ("milk_feed", "breast_left", "Breastfeeding (left)"),
            ("milk_feed", "breast_right", "Breastfeeding (right)"),
            ("milk_feed", "breast_both", "Breastfeeding (both sides)"),
            ("milk_feed", "bottle_breastmilk", "Bottle of breastmilk"),
            ("milk_feed", "bottle_formula", "Bottle of formula"),
        ],
    ),
    (
        "6-11 months",
        11,
        "infant_solids_intro",
        [
            ("milk_feed", "breast_left", "Breastfeeding (left)"),
            ("milk_feed", "breast_right", "Breastfeeding (right)"),
            ("milk_feed", "breast_both", "Breastfeeding (both sides)"),
            ("milk_feed", "bottle_breastmilk", "Bottle of breastmilk"),
            ("milk_feed", "bottle_formula", "Bottle of formula"),
            ("solid_feed", "puree", "Puree"),
            ("solid_feed", "mash", "Mash"),
            ("solid_feed", "finger_food", "Finger food"),
            ("hydration", "water", "Water"),
        ],
    ),
    (
        "12-35 months",
        35,
        "toddler",
        [
            ("milk_feed", "bottle_breastmilk", "Breastmilk"),
            ("milk_feed", "bottle_formula", "Formula"),
            ("solid_feed", "meal", "Meal"),
            ("solid_feed", "snack", "Snack"),
            ("solid_feed", "finger_food", "Finger food"),
            ("hydration", "water", "Water"),
        ],
    ),
    (
        "36+ months",
        None,
        "child",
        [
            ("solid_feed", "meal", "Meal"),
            ("solid_feed", "snack", "Snack"),
            ("hydration", "water", "Water"),
            ("supplement", "vitamin", "Vitamin"),
            ("supplement", "medicine", "Medicine"),
        ],
    ),
]


@dataclass
class FeedingAgeOptions:
    """Derived age-specific feeding options."""

    age_months: int
    age_band: str
    options: list[dict[str, str]]


def _calculate_age_months(birth_date: date, at_time: datetime | None = None) -> int:
    reference_date = (at_time or datetime.now(timezone.utc)).date()
    months = (reference_date.year - birth_date.year) * 12 + (reference_date.month - birth_date.month)
    if reference_date.day < birth_date.day:
        months -= 1
    return max(months, 0)


def _derive_structure_from_legacy(feeding_type: str | None) -> tuple[str | None, str | None]:
    if not feeding_type:
        return None, None
    return LEGACY_TYPE_TO_STRUCTURE.get(feeding_type, (None, None))


def _derive_legacy_type(
    feeding_type: str | None,
    feeding_category: str | None,
    feeding_subtype: str | None,
) -> str:
    if feeding_type:
        return feeding_type
    return STRUCTURE_TO_LEGACY_TYPE.get((feeding_category, feeding_subtype), feeding_subtype or feeding_category or "bottle")


def _uses_structured_food_fields(payload: FeedingCreate | FeedingUpdate) -> bool:
    structured_fields = (
        payload.feeding_category,
        payload.feeding_subtype,
        payload.food_name,
        payload.brand_name,
        payload.amount_value,
        payload.amount_unit,
        payload.serving_count_offered,
        payload.serving_count_consumed,
        payload.consumed_fraction,
        payload.analysis_status,
        payload.analysis_confidence,
        payload.nutrition_source,
    )
    return any(value is not None for value in structured_fields)


async def _get_baby(db: AsyncSession, baby_id: UUID) -> Baby | None:
    result = await db.execute(select(Baby).where(Baby.id == baby_id))
    return result.scalar_one_or_none()


def _get_age_options_for_months(age_months: int) -> FeedingAgeOptions:
    for age_band, max_months, _stage_key, raw_options in AGE_BAND_OPTIONS:
        if max_months is None or age_months <= max_months:
            return FeedingAgeOptions(
                age_months=age_months,
                age_band=age_band,
                options=[
                    {"category": category, "subtype": subtype, "label": label}
                    for category, subtype, label in raw_options
                ],
            )
    return FeedingAgeOptions(age_months=age_months, age_band="36+ months", options=[])


def _validate_structured_option_for_age(
    feeding_category: str | None,
    feeding_subtype: str | None,
    age_options: FeedingAgeOptions,
) -> None:
    if not feeding_category and not feeding_subtype:
        return
    allowed_pairs = {(item["category"], item["subtype"]) for item in age_options.options}
    if (feeding_category, feeding_subtype) not in allowed_pairs:
        raise ValueError(
            f"Feeding option '{feeding_category}:{feeding_subtype}' is not available for age band {age_options.age_band}"
        )


def _normalize_structured_fields(
    payload: FeedingCreate | FeedingUpdate,
    *,
    fallback_category: str | None = None,
    fallback_subtype: str | None = None,
) -> dict[str, object | None]:
    category = payload.feeding_category or fallback_category
    subtype = payload.feeding_subtype or fallback_subtype
    legacy_type = _derive_legacy_type(payload.feeding_type, category, subtype)
    return {
        "feeding_type": legacy_type,
        "feeding_category": category,
        "feeding_subtype": subtype,
        "food_name": payload.food_name,
        "brand_name": payload.brand_name,
        "amount_ml": payload.amount_ml,
        "amount_value": payload.amount_value,
        "amount_unit": payload.amount_unit,
        "duration_min": payload.duration_min,
        "serving_count_offered": payload.serving_count_offered,
        "serving_count_consumed": payload.serving_count_consumed,
        "consumed_fraction": payload.consumed_fraction,
        "analysis_status": payload.analysis_status,
        "analysis_confidence": payload.analysis_confidence,
        "nutrition_source": payload.nutrition_source,
        "timestamp": payload.timestamp,
        "notes": payload.notes,
    }


async def get_feeding_options_for_baby(
    db: AsyncSession,
    baby_id: UUID,
    user_id: UUID,
) -> FeedingAgeOptions | None:
    """Return age-aware feeding options for a baby with access control."""
    if not await verify_baby_access(db, baby_id, user_id):
        return None
    baby = await _get_baby(db, baby_id)
    if baby is None:
        return None
    age_months = _calculate_age_months(baby.birth_date)
    return _get_age_options_for_months(age_months)


async def get_feeding_entries_for_baby(
    db: AsyncSession,
    baby_id: UUID,
    user_id: UUID,
    limit: int = 20,
    offset: int = 0,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
) -> tuple[list[FeedingEntry], int]:
    """Return paginated feeding entries; requires accepted membership."""
    if not await verify_baby_access(db, baby_id, user_id):
        return [], 0

    base_filter = [FeedingEntry.baby_id == baby_id]
    if from_time:
        base_filter.append(FeedingEntry.timestamp >= from_time)
    if to_time:
        base_filter.append(FeedingEntry.timestamp <= to_time)

    count_result = await db.execute(select(func.count(FeedingEntry.id)).where(*base_filter))
    total = count_result.scalar() or 0

    result = await db.execute(
        select(FeedingEntry)
        .where(*base_filter)
        .order_by(FeedingEntry.timestamp.desc())
        .limit(min(limit, 100))
        .offset(max(offset, 0))
    )
    return result.scalars().all(), total


async def get_feeding_entry_by_id(
    db: AsyncSession,
    feeding_id: UUID,
    user_id: UUID,
) -> FeedingEntry | None:
    """Get a feeding entry if the user has accepted access to its baby."""
    result = await db.execute(
        select(FeedingEntry)
        .join(BabyAccess, BabyAccess.baby_id == FeedingEntry.baby_id)
        .where(
            FeedingEntry.id == feeding_id,
            BabyAccess.user_id == user_id,
            BabyAccess.status == "accepted",
        )
    )
    return result.scalar_one_or_none()


async def create_feeding_entry(
    db: AsyncSession,
    baby_id: UUID,
    user_id: UUID,
    feeding_create: FeedingCreate,
    autocommit: bool = True,
) -> FeedingEntry | None:
    """Create a feeding entry; requires accepted membership."""
    if not await verify_baby_access(db, baby_id, user_id):
        return None

    fallback_category, fallback_subtype = _derive_structure_from_legacy(feeding_create.feeding_type)
    normalized = _normalize_structured_fields(
        feeding_create,
        fallback_category=fallback_category,
        fallback_subtype=fallback_subtype,
    )
    if _uses_structured_food_fields(feeding_create):
        baby = await _get_baby(db, baby_id)
        if baby is None:
            return None
        age_options = _get_age_options_for_months(_calculate_age_months(baby.birth_date, feeding_create.timestamp))
        _validate_structured_option_for_age(
            normalized["feeding_category"],
            normalized["feeding_subtype"],
            age_options,
        )

    feeding = FeedingEntry(
        baby_id=baby_id,
        created_by_user_id=user_id,
        updated_by_user_id=user_id,
        **normalized,
    )
    db.add(feeding)
    if autocommit:
        await db.commit()
        await db.refresh(feeding)
    else:
        await db.flush()
    return feeding


async def update_feeding_entry(
    db: AsyncSession,
    feeding_id: UUID,
    user_id: UUID,
    feeding_update: FeedingUpdate,
    is_owner: bool = False,
) -> FeedingEntry | None:
    """
    Update a feeding entry.

    - Owner (is_owner=True): can update any entry for the baby.
    - Caregiver: can only update entries they created.
    Returns None (→ 404/403 at route layer) if not permitted.
    """
    entry = await get_feeding_entry_by_id(db, feeding_id, user_id)
    if not entry:
        return None

    if not is_owner and entry.created_by_user_id != user_id:
        return None

    fallback_category = entry.feeding_category
    fallback_subtype = entry.feeding_subtype
    if feeding_update.feeding_type is not None:
        fallback_category, fallback_subtype = _derive_structure_from_legacy(feeding_update.feeding_type)
    elif not fallback_category and not fallback_subtype:
        fallback_category, fallback_subtype = _derive_structure_from_legacy(entry.feeding_type)

    normalized = _normalize_structured_fields(
        feeding_update,
        fallback_category=fallback_category,
        fallback_subtype=fallback_subtype,
    )
    if _uses_structured_food_fields(feeding_update):
        baby = await _get_baby(db, entry.baby_id)
        if baby is not None:
            age_options = _get_age_options_for_months(_calculate_age_months(baby.birth_date, feeding_update.timestamp or entry.timestamp))
            _validate_structured_option_for_age(
                normalized["feeding_category"],
                normalized["feeding_subtype"],
                age_options,
            )

    for key, value in feeding_update.model_dump(exclude_unset=True).items():
        if key in {"media", "nutrition_estimate"}:
            continue
        setattr(entry, key, value)

    for key, value in normalized.items():
        if key in feeding_update.model_dump(exclude_unset=True) or key in {"feeding_category", "feeding_subtype"}:
            setattr(entry, key, value)

    entry.updated_at = datetime.now(timezone.utc)
    entry.updated_by_user_id = user_id
    await db.commit()
    await db.refresh(entry)
    return entry


async def delete_feeding_entry(
    db: AsyncSession,
    feeding_id: UUID,
    user_id: UUID,
    is_owner: bool = False,
) -> bool:
    """Delete a feeding entry; owner can delete any, caregiver only their own."""
    entry = await get_feeding_entry_by_id(db, feeding_id, user_id)
    if not entry:
        return False

    if not is_owner and entry.created_by_user_id != user_id:
        return False

    await db.execute(delete(FeedingEntry).where(FeedingEntry.id == feeding_id))
    await db.commit()
    return True


async def list_feeding_media(
    db: AsyncSession,
    feeding_id: UUID,
) -> list[FeedingMedia]:
    """Return media rows attached to a feeding."""
    result = await db.execute(
        select(FeedingMedia)
        .where(FeedingMedia.feeding_id == feeding_id)
        .order_by(FeedingMedia.created_at.asc())
    )
    return result.scalars().all()


async def get_feeding_nutrition_estimate(
    db: AsyncSession,
    feeding_id: UUID,
) -> FeedingNutritionEstimate | None:
    """Return the nutrient estimate for a feeding."""
    result = await db.execute(
        select(FeedingNutritionEstimate).where(FeedingNutritionEstimate.feeding_id == feeding_id)
    )
    return result.scalar_one_or_none()


async def create_feeding_media(
    db: AsyncSession,
    feeding_id: UUID,
    baby_id: UUID,
    media_items: list[FeedingMediaCreate],
    *,
    autocommit: bool = True,
) -> list[FeedingMedia]:
    """Replace feeding media with the provided items."""
    await db.execute(delete(FeedingMedia).where(FeedingMedia.feeding_id == feeding_id))
    created: list[FeedingMedia] = []
    for item in media_items:
        media = FeedingMedia(
            feeding_id=feeding_id,
            baby_id=baby_id,
            media_role=item.media_role,
            media_url=item.media_url,
        )
        db.add(media)
        created.append(media)
    if autocommit:
        await db.commit()
        for media in created:
            await db.refresh(media)
    else:
        await db.flush()
    return created


async def upsert_feeding_nutrition_estimate(
    db: AsyncSession,
    feeding_id: UUID,
    baby_id: UUID,
    estimate: FeedingNutritionEstimateCreate,
    *,
    autocommit: bool = True,
) -> FeedingNutritionEstimate:
    """Create or update the feeding nutrition estimate."""
    existing = await get_feeding_nutrition_estimate(db, feeding_id)
    if existing is None:
        existing = FeedingNutritionEstimate(feeding_id=feeding_id, baby_id=baby_id)
        db.add(existing)

    for key, value in estimate.model_dump(exclude_unset=True).items():
        setattr(existing, key, value)

    if autocommit:
        await db.commit()
        await db.refresh(existing)
    else:
        await db.flush()
    return existing
